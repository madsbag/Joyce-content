"""Central content generation engine — wraps Claude API for all content creation."""

import json
import anthropic
from config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL, MAX_TOKENS_POST, MAX_TOKENS_CALENDAR
from prompts.system_prompt import (
    build_system_prompt,
    build_calendar_system_prompt,
    build_image_prompt_system,
    build_production_prompt,
    build_production_calendar_prompt,
)
from core.memory import build_preference_summary
from utils.formatting import parse_dual_options


class ContentEngine:
    """Main content generation engine for Happy Journey with Joyce."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = CLAUDE_MODEL

    def generate_post(
        self,
        platform: str,
        topic: str,
        context: str = "",
        revision_notes: str = "",
        conversation_history: list | None = None,
    ) -> dict:
        """Generate a social media post with 2 options.

        Args:
            platform: "instagram", "rednote", or "both"
            topic: The topic/theme for the post
            context: Optional additional context or angle
            revision_notes: Feedback for revision (appended to history)
            conversation_history: Prior messages for context continuity

        Returns:
            Parsed result with option_a, option_b, and raw response
        """
        preference_summary = build_preference_summary()
        system_prompt = build_system_prompt(platform, preference_summary)

        # Build user message
        user_message = f"Topic: {topic}"
        if context:
            user_message += f"\n\nAdditional context: {context}"

        # Build messages list
        messages = []
        if conversation_history:
            messages.extend(conversation_history)

        if revision_notes:
            user_message = (
                f"Please revise the previous content with this feedback:\n"
                f"{revision_notes}\n\n"
                f"Original topic: {topic}"
            )
            if context:
                user_message += f"\nOriginal context: {context}"

        messages.append({"role": "user", "content": user_message})

        response = self._call_claude(system_prompt, messages, MAX_TOKENS_POST)
        return parse_dual_options(response)

    def generate_calendar(
        self,
        platforms: list[str],
        themes: list[str],
        num_posts: int,
        week_label: str = "",
    ) -> str:
        """Generate a full weekly content calendar.

        Args:
            platforms: List of platforms (["instagram"], ["rednote"], or both)
            themes: List of weekly themes
            num_posts: Number of posts for the week
            week_label: Label like "Feb 17-23, 2026"

        Returns:
            Raw calendar text (parsed per-post by the interface layer)
        """
        preference_summary = build_preference_summary()
        platform_str = " and ".join(platforms) if len(platforms) > 1 else platforms[0]
        system_prompt = build_calendar_system_prompt(
            platform_str, num_posts, preference_summary
        )

        user_message = (
            f"Generate a weekly content calendar for {platform_str}.\n\n"
            f"Week: {week_label or 'This week'}\n"
            f"Number of posts: {num_posts}\n"
            f"Themes: {', '.join(themes)}\n\n"
            f"Create {num_posts} posts, each with 2 options (A and B)."
        )

        messages = [{"role": "user", "content": user_message}]
        return self._call_claude(system_prompt, messages, MAX_TOKENS_CALENDAR)

    def generate_image_prompt(self, caption: str, platform: str) -> str:
        """Generate a DALL-E prompt for a brand-consistent image.

        Args:
            caption: The post caption to create an image for
            platform: "instagram" or "rednote" (affects aspect ratio guidance)

        Returns:
            A DALL-E 3 prompt string
        """
        system_prompt = build_image_prompt_system()
        aspect_note = ""
        if platform == "rednote":
            aspect_note = " The image should work in a vertical 3:4 aspect ratio."
        elif platform == "instagram":
            aspect_note = " The image should work in a 1:1 square aspect ratio."

        user_message = (
            f"Create an image prompt for this social media caption:\n\n"
            f"{caption}{aspect_note}"
        )

        messages = [{"role": "user", "content": user_message}]
        return self._call_claude(system_prompt, messages, max_tokens=300)

    # ── New strategist-driven methods ──────────────────────────

    def generate_from_brief(self, brief: dict) -> dict:
        """Execute a structured text brief from the strategist.

        The brief contains all creative decisions already made. The production
        copywriter just writes to spec.

        Args:
            brief: Structured brief dict with keys like topic, content_type,
                   form, style, hook_direction, words_to_use, etc.

        Returns:
            Parsed result with option_a, option_b, and raw response.
        """
        system_prompt = build_production_prompt()

        # Format the brief as a clear user message
        brief_text = f"CREATIVE BRIEF:\n\n"
        brief_text += f"Platform: {brief.get('platform', 'instagram')}\n"
        brief_text += f"Topic: {brief.get('topic', '')}\n"
        brief_text += f"Content Type: {brief.get('content_type', 'feed_post')}\n"
        brief_text += f"Form: {brief.get('form', 'prose')}\n"
        brief_text += f"Style: {brief.get('style', 'conversational')}\n"
        brief_text += f"Word Count Target: {brief.get('word_count_target', 200)}\n"
        brief_text += f"Emotional Register: {brief.get('emotional_register', 'warm, grounded')}\n\n"

        brief_text += f"Hook Direction: {brief.get('hook_direction', 'Choose an engaging opening')}\n"
        brief_text += f"Content Direction: {brief.get('content_direction', '')}\n"
        brief_text += f"CTA Direction: {brief.get('cta_direction', 'Soft engagement invitation')}\n\n"

        words_use = brief.get("words_to_use", [])
        words_avoid = brief.get("words_to_avoid", [])
        if words_use:
            brief_text += f"Words to USE: {', '.join(words_use)}\n"
        if words_avoid:
            brief_text += f"Words to AVOID: {', '.join(words_avoid)}\n"

        brief_text += f"\nHashtag Guidance: {brief.get('hashtag_guidance', '8-12 hashtags')}\n"

        user_script = brief.get("user_script", "")
        if user_script:
            brief_text += (
                f"\nUSER'S OWN SCRIPT (refine this — do NOT abandon it):\n"
                f"{user_script}\n"
            )

        messages = [{"role": "user", "content": brief_text}]
        response = self._call_claude(system_prompt, messages, MAX_TOKENS_POST)
        return parse_dual_options(response)

    def generate_calendar_from_brief(
        self,
        brief: str,
        platforms: list[str],
        num_posts: int,
    ) -> str:
        """Execute a calendar brief from the strategist.

        Args:
            brief: Strategist's calendar brief text (themes, angles, variation notes)
            platforms: Target platforms
            num_posts: Number of posts

        Returns:
            Raw calendar text.
        """
        system_prompt = build_production_calendar_prompt()
        platform_str = " and ".join(platforms) if len(platforms) > 1 else platforms[0]

        user_message = (
            f"CALENDAR BRIEF:\n\n"
            f"Platform: {platform_str}\n"
            f"Number of posts: {num_posts}\n\n"
            f"{brief}"
        )

        messages = [{"role": "user", "content": user_message}]
        return self._call_claude(system_prompt, messages, MAX_TOKENS_CALENDAR)

    # ── Legacy methods (kept for backward compatibility) ─────

    def _call_claude(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int = 2000,
    ) -> str:
        """Make the actual API call to Claude.

        Args:
            system_prompt: The assembled system prompt
            messages: List of message dicts with role and content
            max_tokens: Maximum tokens for the response

        Returns:
            The text response from Claude
        """
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
