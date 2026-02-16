"""Strategist agent — conversational creative director for Joyce's content."""

import asyncio
import json
import logging
from dataclasses import dataclass, field

import anthropic

from config.settings import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    MAX_TOKENS_STRATEGIST,
    PUBLISH_ENABLED,
)
from core.content_engine import ContentEngine
from core.image_generator import ImageGenerator
from core.image_editor import apply_brand_filter
from core.memory import save_approval
from core.session import Session
from core.publishers.instagram_publisher import InstagramPublisher, PublishError
from core.publishers.rednote_publisher import RednotePublisher
from prompts.strategist_prompt import build_strategist_system_prompt
from utils.formatting import parse_dual_options, format_clean_copy, count_hashtags

logger = logging.getLogger(__name__)


# ── AgentAction: what to send back to Telegram ───────────────


@dataclass
class AgentAction:
    """A single action to dispatch to the Telegram interface."""

    type: str  # "text", "photo", "buttons"
    text: str = ""
    image_bytes: bytes | None = None
    buttons: list[list[dict]] | None = None  # [[{"text": ..., "data": ...}]]
    parse_mode: str | None = None


# ── Tool definitions ─────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "generate_text_content",
        "description": (
            "Execute a structured creative brief to produce social media post content "
            "with two options (A and B). Call this ONLY after you have shaped the idea "
            "with Joyce and crafted a detailed brief. The production copywriter will "
            "execute your brief faithfully."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "enum": ["instagram", "rednote", "both"],
                    "description": "Target platform",
                },
                "topic": {
                    "type": "string",
                    "description": "Core subject of the post",
                },
                "content_type": {
                    "type": "string",
                    "enum": ["feed_post", "carousel", "reel_caption", "story"],
                    "description": "Type of content to produce",
                },
                "form": {
                    "type": "string",
                    "description": "Form of writing: prose, poetry, list, micro-story, question-led",
                },
                "style": {
                    "type": "string",
                    "description": "Writing style: 'short and punchy', 'conversational', 'verbose and narrative', 'poetic and sparse'",
                },
                "word_count_target": {
                    "type": "integer",
                    "description": "Target word count for the caption",
                },
                "hook_direction": {
                    "type": "string",
                    "description": "Specific direction for the opening hook line",
                },
                "content_direction": {
                    "type": "string",
                    "description": "Detailed direction for the body content — what to explore, what angle, what insight to build toward",
                },
                "cta_direction": {
                    "type": "string",
                    "description": "Direction for the closing call-to-action or engagement invitation",
                },
                "words_to_use": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific words/phrases that MUST appear in the content",
                },
                "words_to_avoid": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Words/phrases that must NOT appear",
                },
                "emotional_register": {
                    "type": "string",
                    "description": "The emotional tone: e.g. 'warm, grounded, gently encouraging'",
                },
                "hashtag_guidance": {
                    "type": "string",
                    "description": "Hashtag count and focus areas",
                },
                "user_script": {
                    "type": "string",
                    "description": "If Joyce provided her own written text, include it here. The copywriter will refine it rather than replace it.",
                    "default": "",
                },
            },
            "required": ["platform", "topic", "content_type", "hook_direction", "content_direction", "words_to_use", "words_to_avoid"],
        },
    },
    {
        "name": "generate_image",
        "description": (
            "Generate a brand-consistent AI image using DALL-E 3. "
            "Costs ~$0.04 per image. ONLY call this after Joyce confirms she wants "
            "an AI image. Your image_brief should be a specific, ready-to-use DALL-E "
            "prompt describing subject, composition, colors, lighting, and mood."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "image_brief": {
                    "type": "string",
                    "description": "Detailed DALL-E prompt: subject, composition, color palette, lighting, mood. Under 100 words.",
                },
                "platform": {
                    "type": "string",
                    "enum": ["instagram", "rednote"],
                    "description": "Platform (instagram=square 1:1, rednote=vertical 3:4)",
                },
                "option_label": {
                    "type": "string",
                    "description": "Which option this image is for: 'option_a', 'option_b', or 'standalone'",
                    "default": "standalone",
                },
            },
            "required": ["image_brief", "platform"],
        },
    },
    {
        "name": "apply_brand_filter",
        "description": (
            "Apply brand-consistent color filtering to a photo Joyce uploaded. "
            "Warms tones, softens contrast, adds subtle gold tint. "
            "Only call when Joyce has uploaded a photo in this session."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "add_logo": {
                    "type": "boolean",
                    "description": "Whether to add brand logo watermark",
                    "default": True,
                },
            },
            "required": [],
        },
    },
    {
        "name": "present_options",
        "description": (
            "Present the generated content options to Joyce with approval buttons. "
            "Call this after generate_text_content to show Pick A / Pick B / Revise "
            "buttons. You should also include a brief summary of each option."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "option_a_summary": {
                    "type": "string",
                    "description": "Brief description of Option A for the button context",
                },
                "option_b_summary": {
                    "type": "string",
                    "description": "Brief description of Option B for the button context",
                },
            },
            "required": ["option_a_summary", "option_b_summary"],
        },
    },
    {
        "name": "generate_calendar",
        "description": (
            "Generate a weekly content calendar with multiple posts. "
            "Call this when Joyce wants to plan her content week."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "calendar_brief": {
                    "type": "string",
                    "description": "Detailed brief: themes per day, angles, variation notes, any specific direction",
                },
                "platforms": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["instagram", "rednote"]},
                    "description": "Target platforms",
                },
                "num_posts": {
                    "type": "integer",
                    "description": "Number of posts for the week (3-7)",
                },
            },
            "required": ["calendar_brief", "platforms", "num_posts"],
        },
    },
    {
        "name": "save_approval",
        "description": (
            "Save Joyce's approved post to preference memory. Call this immediately "
            "after she picks an option (pick_a or pick_b)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "option": {
                    "type": "string",
                    "enum": ["a", "b"],
                    "description": "Which option Joyce approved",
                },
                "platform": {"type": "string"},
                "topic": {"type": "string"},
            },
            "required": ["option", "platform", "topic"],
        },
    },
    {
        "name": "publish_content",
        "description": (
            "Publish approved content to a platform. Instagram publishes directly "
            "via Graph API. Rednote formats into copyable blocks (no API). "
            "Only call after Joyce explicitly approves and requests publishing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "enum": ["instagram", "rednote"],
                },
                "option": {
                    "type": "string",
                    "enum": ["a", "b"],
                    "description": "Which approved option to publish",
                },
            },
            "required": ["platform", "option"],
        },
    },
]


# ── Tool result wrapper ──────────────────────────────────────


@dataclass
class ToolResult:
    """Result of executing a tool, including side effects for Telegram."""

    content: str  # text returned to Claude as tool_result
    side_effects: list[AgentAction] = field(default_factory=list)


# ── Strategist class ─────────────────────────────────────────


class Strategist:
    """Conversational agent that shapes content ideas and orchestrates production."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = CLAUDE_MODEL
        self.tools = TOOL_DEFINITIONS
        self.content_engine = ContentEngine()
        self.image_generator = ImageGenerator()

    async def run_turn(
        self,
        session: Session,
        new_user_content: list[dict],
        memory_context: str = "",
    ) -> list[AgentAction]:
        """Execute one full agent turn.

        1. Append new user content to session messages
        2. Call Claude with strategist prompt + tools
        3. If tool calls in response, execute them, feed results back, re-call
        4. Collect all text blocks and side effects as AgentActions

        Args:
            session: The active Session object
            new_user_content: List of content blocks (text, image refs)
            memory_context: Persistent memory string

        Returns:
            List of AgentActions to dispatch to Telegram
        """
        # Append user message
        session.messages.append({"role": "user", "content": new_user_content})

        system_prompt = build_strategist_system_prompt(
            memory_context=memory_context,
            publish_enabled=PUBLISH_ENABLED,
        )

        actions: list[AgentAction] = []
        max_iterations = 10  # safety cap on tool call loops

        for _ in range(max_iterations):
            # Call Claude (sync API, run in thread to avoid blocking event loop)
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=MAX_TOKENS_STRATEGIST,
                system=system_prompt,
                messages=session.messages,
                tools=self.tools,
            )

            logger.info("Claude response: stop_reason=%s, blocks=%d", response.stop_reason, len(response.content))

            # Append assistant response to session history
            # Convert content blocks to serializable dicts
            assistant_content = []
            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                    actions.append(AgentAction(type="text", text=block.text))
                elif block.type == "tool_use":
                    logger.info("Tool call: %s", block.name)
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            session.messages.append({"role": "assistant", "content": assistant_content})

            # If no tool calls, turn is done
            if response.stop_reason == "end_turn":
                break

            # Process tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        result = await self._execute_tool(
                            block.name, block.input, session
                        )
                    except Exception as e:
                        logger.error("Tool %s failed: %s", block.name, e)
                        result = ToolResult(
                            content=f"Tool error: {e}",
                            side_effects=[],
                        )

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result.content,
                    })
                    actions.extend(result.side_effects)

            # Append tool results as a user message
            session.messages.append({"role": "user", "content": tool_results})

        return actions

    # ── Tool execution dispatch ──────────────────────────────

    async def _execute_tool(
        self, name: str, input_data: dict, session: Session
    ) -> ToolResult:
        """Route a tool call to the appropriate handler."""
        handlers = {
            "generate_text_content": self._tool_generate_text,
            "generate_image": self._tool_generate_image,
            "apply_brand_filter": self._tool_apply_brand_filter,
            "present_options": self._tool_present_options,
            "generate_calendar": self._tool_generate_calendar,
            "save_approval": self._tool_save_approval,
            "publish_content": self._tool_publish_content,
        }

        handler = handlers.get(name)
        if not handler:
            return ToolResult(content=f"Unknown tool: {name}")

        return await handler(input_data, session)

    # ── Individual tool handlers ─────────────────────────────

    async def _tool_generate_text(
        self, input_data: dict, session: Session
    ) -> ToolResult:
        """Generate text content from a structured brief."""
        result = await asyncio.to_thread(
            self.content_engine.generate_from_brief, input_data
        )

        session.generated_options = result
        session.platform = input_data.get("platform", "instagram")
        session.topic = input_data.get("topic", "")

        # Build a summary for Claude to read
        opt_a = result.get("option_a", {})
        opt_b = result.get("option_b", {})
        caption_a = opt_a.get("caption") or opt_a.get("raw", "")
        caption_b = opt_b.get("caption") or opt_b.get("raw", "")

        # Side effects: send the full options to Telegram
        side_effects = []
        for label, key in [("Option A", "option_a"), ("Option B", "option_b")]:
            opt = result.get(key, {})
            preview = _format_option_preview(opt, label)
            side_effects.append(AgentAction(type="text", text=preview))

        summary = (
            f"Content generated successfully.\n\n"
            f"Option A ({len(caption_a.split())} words): {caption_a[:150]}...\n\n"
            f"Option B ({len(caption_b.split())} words): {caption_b[:150]}..."
        )

        return ToolResult(content=summary, side_effects=side_effects)

    async def _tool_generate_image(
        self, input_data: dict, session: Session
    ) -> ToolResult:
        """Generate an AI image from the strategist's DALL-E prompt."""
        image_brief = input_data["image_brief"]
        platform = input_data.get("platform", "instagram")
        option_label = input_data.get("option_label", "standalone")

        try:
            img_bytes = await asyncio.to_thread(
                self.image_generator.generate, image_brief, platform
            )
        except Exception as e:
            return ToolResult(content=f"Image generation failed: {e}")

        # Store on session
        session.generated_images[option_label] = img_bytes

        return ToolResult(
            content=f"Image generated for {option_label}. Prompt: {image_brief[:100]}",
            side_effects=[
                AgentAction(
                    type="photo",
                    image_bytes=img_bytes,
                    text=f"AI-generated image",
                ),
            ],
        )

    async def _tool_apply_brand_filter(
        self, input_data: dict, session: Session
    ) -> ToolResult:
        """Apply brand filter to Joyce's uploaded photo."""
        if not session.uploaded_photo:
            return ToolResult(content="No photo uploaded in this session.")

        add_logo = input_data.get("add_logo", True)

        try:
            filtered = await asyncio.to_thread(
                apply_brand_filter, session.uploaded_photo, add_logo
            )
        except Exception as e:
            return ToolResult(content=f"Brand filter failed: {e}")

        session.uploaded_photo = filtered  # replace with filtered version

        return ToolResult(
            content="Brand filter applied. Photo ready.",
            side_effects=[
                AgentAction(
                    type="photo",
                    image_bytes=filtered,
                    text="Your photo with brand-consistent filtering applied.",
                ),
            ],
        )

    async def _tool_present_options(
        self, input_data: dict, session: Session
    ) -> ToolResult:
        """Present Pick/Revise buttons to Joyce."""
        opt_a_summary = input_data.get("option_a_summary", "Reflective")
        opt_b_summary = input_data.get("option_b_summary", "Direct")

        buttons = [
            [
                {"text": f"Pick A", "data": "pick_a"},
                {"text": f"Pick B", "data": "pick_b"},
            ],
            [
                {"text": "Revise A", "data": "revise_a"},
                {"text": "Revise B", "data": "revise_b"},
            ],
        ]

        return ToolResult(
            content="Options presented to Joyce with Pick/Revise buttons. Waiting for her selection.",
            side_effects=[
                AgentAction(
                    type="buttons",
                    text=f"A: {opt_a_summary}\nB: {opt_b_summary}\n\nWhich do you prefer?",
                    buttons=buttons,
                ),
            ],
        )

    async def _tool_generate_calendar(
        self, input_data: dict, session: Session
    ) -> ToolResult:
        """Generate a weekly content calendar."""
        calendar_brief = input_data["calendar_brief"]
        platforms = input_data.get("platforms", ["instagram"])
        num_posts = input_data.get("num_posts", 5)

        try:
            calendar_text = await asyncio.to_thread(
                self.content_engine.generate_calendar_from_brief,
                calendar_brief,
                platforms,
                num_posts,
            )
        except Exception as e:
            return ToolResult(content=f"Calendar generation failed: {e}")

        return ToolResult(
            content=f"Calendar generated with {num_posts} posts.",
            side_effects=[
                AgentAction(type="text", text=calendar_text),
            ],
        )

    async def _tool_save_approval(
        self, input_data: dict, session: Session
    ) -> ToolResult:
        """Save approved post to preference memory."""
        option_key = input_data.get("option", "a")
        platform = input_data.get("platform", session.platform or "instagram")
        topic = input_data.get("topic", session.topic or "")

        result = session.generated_options
        if not result:
            return ToolResult(content="No generated options to save.")

        option = result.get(f"option_{option_key}", {})
        caption = option.get("caption") or option.get("raw", "")
        style = "reflective" if option_key == "a" else "direct"

        # Normalize content type
        raw_ct = option.get("content_type", "feed_post").lower()
        if "carousel" in raw_ct:
            content_type = "carousel"
        elif "reel" in raw_ct:
            content_type = "reel_caption"
        elif "story" in raw_ct:
            content_type = "story"
        else:
            content_type = "feed_post"

        save_approval(
            platform=platform,
            topic=topic,
            chosen_option=option_key.upper(),
            style_used=style,
            content_type=content_type,
            caption=caption,
            hashtag_count=count_hashtags(option.get("hashtags", "")),
        )

        session.approved_option = option_key

        # Send final clean copy
        clean = format_clean_copy(option)
        side_effects = [
            AgentAction(
                type="text",
                text=f"Approved! Here's your final post — ready to copy:\n\n{clean}",
            ),
        ]

        # Include the image if one was generated for this option
        img = session.generated_images.get(f"option_{option_key}")
        if img:
            side_effects.append(AgentAction(type="photo", image_bytes=img, text="Your post image"))
        elif session.uploaded_photo:
            side_effects.append(AgentAction(type="photo", image_bytes=session.uploaded_photo, text="Your post photo"))

        return ToolResult(
            content=f"Post saved to preference memory. Option {option_key.upper()} approved.",
            side_effects=side_effects,
        )

    async def _tool_publish_content(
        self, input_data: dict, session: Session
    ) -> ToolResult:
        """Publish content to a platform."""
        platform = input_data["platform"]
        option_key = input_data.get("option", session.approved_option or "a")

        result = session.generated_options
        if not result:
            return ToolResult(content="No content to publish.")

        option = result.get(f"option_{option_key}", {})
        clean = format_clean_copy(option)

        # Get the image
        img = session.generated_images.get(f"option_{option_key}")
        if not img:
            img = session.uploaded_photo

        if platform == "instagram":
            return await self._publish_instagram(clean, img)
        elif platform == "rednote":
            return self._publish_rednote(option, clean)
        else:
            return ToolResult(content=f"Unknown platform: {platform}")

    async def _publish_instagram(self, caption: str, image_bytes: bytes | None) -> ToolResult:
        """Publish to Instagram via Graph API."""
        publisher = InstagramPublisher()

        if not publisher.is_configured():
            return ToolResult(
                content="Instagram is not configured. Run: python scripts/setup_instagram.py"
            )

        if not image_bytes:
            return ToolResult(
                content="Instagram requires an image. No image available for this post."
            )

        try:
            result = await asyncio.to_thread(
                publisher.publish_photo_post, image_bytes, caption
            )
            media_id = result.get("id", "unknown")
            return ToolResult(content=f"Published to Instagram! Media ID: {media_id}")
        except PublishError as e:
            return ToolResult(content=f"Instagram publish failed: {e}")

    def _publish_rednote(self, option_data: dict, clean_text: str) -> ToolResult:
        """Format Rednote content into copyable blocks."""
        publisher = RednotePublisher()
        formatted = publisher.format_for_clipboard(option_data, clean_text)

        blocks = []
        if formatted.get("title"):
            blocks.append(f"Title:\n{formatted['title']}")
        if formatted.get("body"):
            blocks.append(f"Body:\n{formatted['body']}")
        if formatted.get("tags"):
            blocks.append(f"Tags:\n{formatted['tags']}")
        if formatted.get("chinese_title"):
            blocks.append(f"Chinese Title (中文标题):\n{formatted['chinese_title']}")
        if formatted.get("chinese_body"):
            blocks.append(f"Chinese Body (中文正文):\n{formatted['chinese_body']}")
        if formatted.get("chinese_tags"):
            blocks.append(f"Chinese Tags (中文标签):\n{formatted['chinese_tags']}")

        side_effects = [
            AgentAction(type="text", text=block) for block in blocks
        ]

        instructions = publisher.format_posting_instructions()
        side_effects.append(AgentAction(type="text", text=instructions))

        return ToolResult(
            content="Rednote content formatted into copyable blocks.",
            side_effects=side_effects,
        )


# ── Helpers ──────────────────────────────────────────────────


def _format_option_preview(option: dict, label: str) -> str:
    """Format an option for Telegram display."""
    lines = [f"*{label}*"]
    if option.get("content_type"):
        lines.append(f"Type: {option['content_type']}")
    lines.append("")

    content = option.get("caption") or option.get("raw", "")
    if content:
        lines.append(content)

    if option.get("hashtags"):
        lines.append("")
        lines.append(option["hashtags"])

    if option.get("visual"):
        lines.append("")
        lines.append(f"Visual: {option['visual']}")

    return "\n".join(lines)
