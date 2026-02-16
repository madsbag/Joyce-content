"""Preference memory system — learns from Joyce's approved posts."""

import json
from datetime import datetime
from pathlib import Path
from config.settings import PREFERENCES_FILE, MAX_PREFERENCES


def _ensure_file():
    """Create preferences file if it doesn't exist."""
    PREFERENCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not PREFERENCES_FILE.exists():
        PREFERENCES_FILE.write_text("[]", encoding="utf-8")


def load_preferences() -> list[dict]:
    """Load all stored preferences."""
    _ensure_file()
    return json.loads(PREFERENCES_FILE.read_text(encoding="utf-8"))


def save_approval(
    platform: str,
    topic: str,
    chosen_option: str,
    style_used: str,
    content_type: str,
    caption: str,
    hashtag_count: int,
    revision_notes: list[str] | None = None,
):
    """Save an approved post to preference memory.

    Args:
        platform: "instagram" or "rednote"
        topic: The topic/theme of the post
        chosen_option: "A" or "B"
        style_used: "reflective" or "direct"
        content_type: "feed_post", "carousel", "reel_caption", "story"
        caption: The final approved caption text
        hashtag_count: Number of hashtags in the approved post
        revision_notes: List of revision feedback strings (if any)
    """
    preferences = load_preferences()

    # Analyze the caption for pattern tracking
    has_question_hook = caption.strip().split("\n")[0].strip().endswith("?")
    has_personal_story = any(
        phrase in caption.lower()
        for phrase in ["i remember", "i noticed", "i've been", "the other day", "this week"]
    )
    word_count = len(caption.split())

    entry = {
        "approved_at": datetime.now().isoformat(),
        "platform": platform,
        "topic": topic,
        "chosen_option": chosen_option,
        "style_used": style_used,
        "content_type": content_type,
        "caption_length_words": word_count,
        "has_question_hook": has_question_hook,
        "has_personal_story": has_personal_story,
        "revision_notes": revision_notes or [],
        "hashtag_count": hashtag_count,
    }

    preferences.append(entry)

    # FIFO: keep only the most recent MAX_PREFERENCES entries
    if len(preferences) > MAX_PREFERENCES:
        preferences = preferences[-MAX_PREFERENCES:]

    PREFERENCES_FILE.write_text(
        json.dumps(preferences, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def build_preference_summary() -> str:
    """Analyze preferences and build a summary string for the system prompt."""
    preferences = load_preferences()
    if not preferences:
        return ""

    total = len(preferences)

    # Option preference
    option_a_count = sum(1 for p in preferences if p["chosen_option"] == "A")
    option_b_count = total - option_a_count

    # Style preference
    reflective_count = sum(1 for p in preferences if p["style_used"] == "reflective")
    direct_count = total - reflective_count

    # Caption length
    word_counts = [p["caption_length_words"] for p in preferences]
    avg_words = sum(word_counts) // total if total > 0 else 200
    min_words = min(word_counts) if word_counts else 150
    max_words = max(word_counts) if word_counts else 300

    # Hook preferences
    question_hooks = sum(1 for p in preferences if p.get("has_question_hook"))
    personal_stories = sum(1 for p in preferences if p.get("has_personal_story"))

    # Content type distribution
    type_counts = {}
    for p in preferences:
        ct = p.get("content_type", "feed_post")
        type_counts[ct] = type_counts.get(ct, 0) + 1
    favorite_type = max(type_counts, key=type_counts.get) if type_counts else "feed_post"

    # Hashtag count
    hashtag_counts = [p.get("hashtag_count", 10) for p in preferences]
    avg_hashtags = sum(hashtag_counts) // total if total > 0 else 10

    # Common revision notes
    all_revisions = []
    for p in preferences:
        all_revisions.extend(p.get("revision_notes", []))
    revision_summary = ""
    if all_revisions:
        # Simple frequency analysis
        revision_lower = [r.lower() for r in all_revisions]
        common_patterns = []
        if any("short" in r for r in revision_lower):
            common_patterns.append('"make it shorter"')
        if any("long" in r for r in revision_lower):
            common_patterns.append('"make it longer"')
        if any("question" in r for r in revision_lower):
            common_patterns.append('"add a question"')
        if any("personal" in r for r in revision_lower):
            common_patterns.append('"make it more personal"')
        if common_patterns:
            revision_summary = f"- Common revision requests: {', '.join(common_patterns)}"

    # Build summary
    lines = [
        f"Based on {total} recently approved posts:",
        f"- Prefers Option {'A (reflective)' if option_a_count >= option_b_count else 'B (direct)'} — chosen {max(option_a_count, option_b_count)}/{total} times",
        f"- Preferred caption length: {min_words}-{max_words} words (average {avg_words})",
        f"- Question hooks: {'often' if question_hooks > total // 2 else 'sometimes'} used ({question_hooks}/{total})",
        f"- Personal stories: {'often' if personal_stories > total // 2 else 'sometimes'} included ({personal_stories}/{total})",
        f"- Favorite content type: {favorite_type.replace('_', ' ')}",
        f"- Preferred hashtag count: ~{avg_hashtags}",
    ]
    if revision_summary:
        lines.append(revision_summary)

    return "\n".join(lines)
