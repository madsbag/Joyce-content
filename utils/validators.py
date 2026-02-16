"""Platform-specific content validators."""

from config.settings import (
    INSTAGRAM_MAX_CAPTION,
    INSTAGRAM_MAX_HASHTAGS,
    REDNOTE_MAX_TITLE,
    REDNOTE_MAX_BODY_CHARS,
)
from utils.formatting import count_hashtags


def validate_instagram(caption: str, hashtags: str) -> list[str]:
    """Validate Instagram content. Returns list of warnings (empty = valid)."""
    warnings = []
    if len(caption) > INSTAGRAM_MAX_CAPTION:
        warnings.append(
            f"Caption is {len(caption)} chars (max {INSTAGRAM_MAX_CAPTION})"
        )
    tag_count = count_hashtags(hashtags)
    if tag_count > INSTAGRAM_MAX_HASHTAGS:
        warnings.append(
            f"Too many hashtags: {tag_count} (max {INSTAGRAM_MAX_HASHTAGS})"
        )
    return warnings


def validate_rednote(title: str, body: str) -> list[str]:
    """Validate Rednote content. Returns list of warnings (empty = valid)."""
    warnings = []
    if len(title) > REDNOTE_MAX_TITLE:
        warnings.append(
            f"Title is {len(title)} chars (max {REDNOTE_MAX_TITLE})"
        )
    if len(body) > REDNOTE_MAX_BODY_CHARS:
        warnings.append(
            f"Body is {len(body)} chars (max {REDNOTE_MAX_BODY_CHARS})"
        )
    return warnings
