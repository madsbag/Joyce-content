"""Session state management for the strategist agent."""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import anthropic

from config.settings import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    SESSION_STORAGE_DIR,
    MAX_RECENT_SESSIONS,
)

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """Holds state for one strategist conversation."""

    session_id: str = field(default_factory=lambda: f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}")
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    messages: list[dict] = field(default_factory=list)  # Claude API message history

    # Attachments & generated artifacts (not persisted in transcript)
    uploaded_photo: bytes | None = None
    generated_options: dict | None = None  # parsed result from generate_text_content
    generated_images: dict[str, bytes] = field(default_factory=dict)  # "option_a" / "option_b"
    approved_option: str | None = None
    platform: str | None = None
    topic: str | None = None


SUMMARIZE_PROMPT = """\
You are summarizing a content creation session between Joyce (user) and Sora (her content strategist bot).

Analyze the conversation transcript and produce a JSON object with these fields:

{
  "summary": "2-3 sentence narrative summary of what happened in this session",
  "topics_discussed": ["list of content topics that came up"],
  "parked_ideas": ["ideas mentioned but not yet produced into posts"],
  "style_preferences": "any new style preferences Joyce expressed (tone, length, form, etc.) — empty string if none",
  "decisions": ["key decisions Joyce made, e.g. 'prefers Option A reflective style', 'wants more nature imagery'"]
}

Rules:
- Only include what actually happened — don't infer or speculate
- parked_ideas = ideas Joyce mentioned but no post was generated for them
- If a parked idea from a previous session was produced this time, don't include it
- Keep each field concise
- Return ONLY the JSON object, no markdown fences"""


class SessionManager:
    """Manages active sessions and persistent memory per user."""

    def __init__(self):
        SESSION_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self._active: dict[int, Session] = {}  # user_id -> Session
        self._locks: dict[int, asyncio.Lock] = {}  # per-user turn serialization
        self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def get_lock(self, user_id: int) -> asyncio.Lock:
        """Get or create a per-user lock to serialize agent turns."""
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]

    def get_or_create(self, user_id: int) -> Session:
        """Return the active session, or create a new one."""
        if user_id not in self._active:
            self._active[user_id] = Session()
        return self._active[user_id]

    def has_active_session(self, user_id: int) -> bool:
        return user_id in self._active

    async def end_session(self, user_id: int) -> Session | None:
        """End the active session, summarize with Claude, and archive.

        Returns the ended session.
        """
        session = self._active.pop(user_id, None)
        if session and session.messages:
            await self._archive_session(user_id, session)
        return session

    def load_memory_context(self, user_id: int) -> str:
        """Build memory context string for the strategist's system prompt."""
        memory_file = SESSION_STORAGE_DIR / f"memory_{user_id}.json"
        if not memory_file.exists():
            return ""

        data = json.loads(memory_file.read_text(encoding="utf-8"))
        parts = []

        # Structured summary
        summary = data.get("structured_summary", {})
        if summary:
            parts.append("=== JOYCE'S CONTENT HISTORY ===")
            if summary.get("topics_discussed"):
                parts.append(f"Topics explored: {', '.join(summary['topics_discussed'][-10:])}")
            if summary.get("parked_ideas"):
                parts.append(f"Parked ideas (not yet produced): {', '.join(summary['parked_ideas'])}")
            if summary.get("style_preferences"):
                parts.append(f"Style tendencies: {summary['style_preferences']}")
            if summary.get("decisions"):
                parts.append(f"Key decisions: {'; '.join(summary['decisions'][-5:])}")
            parts.append("")

        # Recent session summaries
        recent = data.get("recent_sessions", [])
        if recent:
            parts.append("=== RECENT SESSIONS ===")
            for sess in recent[-MAX_RECENT_SESSIONS:]:
                date = sess.get("started_at", "")[:10]
                summary_text = sess.get("summary", "No summary")
                parts.append(f"Session {date}: {summary_text}")
            parts.append("")

        return "\n".join(parts)

    # ── Archival ──────────────────────────────────────────────

    async def _archive_session(self, user_id: int, session: Session):
        """Archive a completed session with Claude-powered summarization."""
        memory_file = SESSION_STORAGE_DIR / f"memory_{user_id}.json"

        if memory_file.exists():
            data = json.loads(memory_file.read_text(encoding="utf-8"))
        else:
            data = {
                "structured_summary": {
                    "topics_discussed": [],
                    "parked_ideas": [],
                    "style_preferences": "",
                    "decisions": [],
                },
                "recent_sessions": [],
            }

        # Extract transcript first (needed for both summary approaches)
        transcript = self._extract_transcript(session.messages)

        # Summarize with Claude (falls back to basic if it fails)
        summary_data = await self._summarize_with_claude(transcript, session)

        narrative_summary = summary_data.get("summary", "")
        if not narrative_summary:
            narrative_summary = self._build_basic_summary(session)

        # Add to recent sessions
        data["recent_sessions"].append({
            "session_id": session.session_id,
            "started_at": session.started_at,
            "ended_at": datetime.now().isoformat(),
            "summary": narrative_summary,
            "transcript": transcript,
        })

        # Trim: keep full transcripts for last N sessions only
        for i, sess in enumerate(data["recent_sessions"]):
            if i < len(data["recent_sessions"]) - MAX_RECENT_SESSIONS:
                sess.pop("transcript", None)  # keep summary, drop transcript

        # Merge structured summary
        self._merge_structured_summary(data["structured_summary"], summary_data, session)

        memory_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Session %s archived for user %s", session.session_id, user_id)

    async def _summarize_with_claude(
        self, transcript: list[dict], session: Session
    ) -> dict:
        """Call Claude to produce a structured session summary.

        Returns a dict with: summary, topics_discussed, parked_ideas,
        style_preferences, decisions. Returns partial/empty dict on failure.
        """
        # Build a readable transcript for Claude
        lines = []
        for entry in transcript:
            role = "Joyce" if entry["role"] == "user" else "Sora"
            lines.append(f"{role}: {entry['text']}")
        transcript_text = "\n".join(lines)

        if not transcript_text.strip():
            return {}

        # Add session metadata
        meta = f"Platform: {session.platform or 'not set'}. "
        meta += f"Topic: {session.topic or 'not set'}. "
        if session.approved_option:
            meta += f"Joyce approved Option {session.approved_option.upper()}."

        user_message = (
            f"Session metadata: {meta}\n\n"
            f"Transcript:\n{transcript_text}"
        )

        try:
            response = await asyncio.to_thread(
                self._client.messages.create,
                model=CLAUDE_MODEL,
                max_tokens=500,
                system=SUMMARIZE_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            raw = response.content[0].text.strip()

            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()

            result = json.loads(raw)
            logger.info("Claude summarization successful")
            return result

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse Claude summary JSON: %s", e)
            return {}
        except Exception as e:
            logger.warning("Claude summarization failed, using basic: %s", e)
            return {}

    def _merge_structured_summary(
        self, summary: dict, new_data: dict, session: Session
    ):
        """Merge new session insights into the running structured summary."""
        # Topics
        new_topics = new_data.get("topics_discussed", [])
        if session.topic and session.topic not in new_topics:
            new_topics.append(session.topic)
        for topic in new_topics:
            if topic and topic not in summary["topics_discussed"]:
                summary["topics_discussed"].append(topic)
        summary["topics_discussed"] = summary["topics_discussed"][-20:]

        # Parked ideas — add new, remove any that were produced this session
        produced_topics = set(t.lower() for t in new_topics)
        existing_parked = summary.get("parked_ideas", [])
        # Remove parked ideas that match produced topics
        existing_parked = [
            idea for idea in existing_parked
            if idea.lower() not in produced_topics
        ]
        # Add newly parked ideas
        new_parked = new_data.get("parked_ideas", [])
        for idea in new_parked:
            if idea and idea not in existing_parked:
                existing_parked.append(idea)
        summary["parked_ideas"] = existing_parked[-10:]

        # Style preferences — append new insights, keep concise
        new_style = new_data.get("style_preferences", "")
        if new_style:
            existing_style = summary.get("style_preferences", "")
            if existing_style:
                # Combine, keeping it under 300 chars
                combined = f"{existing_style}; {new_style}"
                summary["style_preferences"] = combined[-300:]
            else:
                summary["style_preferences"] = new_style[:300]

        # Decisions — append new, keep last 10
        new_decisions = new_data.get("decisions", [])
        for decision in new_decisions:
            if decision and decision not in summary["decisions"]:
                summary["decisions"].append(decision)
        summary["decisions"] = summary["decisions"][-10:]

    # ── Fallback summary (no Claude call) ─────────────────────

    def _build_basic_summary(self, session: Session) -> str:
        """Build a brief text summary from session messages (fallback)."""
        user_msgs = []
        for msg in session.messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    user_msgs.append(content[:100])
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            user_msgs.append(block["text"][:100])

        topic = session.topic or "unspecified topic"
        option = f"Option {session.approved_option.upper()}" if session.approved_option else "no approval"
        platform = session.platform or "unspecified"

        summary = f"Topic: {topic}. Platform: {platform}. Outcome: {option}."
        if user_msgs:
            summary += f" Joyce said: '{user_msgs[0]}'"
        return summary[:300]

    # ── Transcript extraction ─────────────────────────────────

    def _extract_transcript(self, messages: list[dict]) -> list[dict]:
        """Extract a lightweight transcript from Claude API messages."""
        transcript = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if isinstance(content, str):
                transcript.append({"role": role, "text": content[:500]})
            elif isinstance(content, list):
                texts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            texts.append(block["text"][:500])
                        elif block.get("type") == "tool_use":
                            texts.append(f"[tool: {block.get('name', '?')}]")
                        elif block.get("type") == "tool_result":
                            texts.append("[tool result]")
                if texts:
                    transcript.append({"role": role, "text": " | ".join(texts)})

        return transcript[-30:]  # last 30 messages max
