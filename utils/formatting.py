"""Output parsing and formatting helpers."""

import re


def parse_dual_options(response_text: str) -> dict:
    """Parse Claude's response into structured Option A and Option B.

    Returns:
        {
            "option_a": {"content_type": str, "caption": str, "hashtags": str, "visual": str},
            "option_b": {"content_type": str, "caption": str, "hashtags": str, "visual": str},
            "raw": str  # full response
        }
    """
    result = {"raw": response_text}

    # Split on option delimiters
    option_a_match = re.search(
        r"={3,}\s*OPTION\s*A.*?={3,}\s*\n(.*?)(?=={3,}\s*OPTION\s*B|$)",
        response_text,
        re.DOTALL | re.IGNORECASE,
    )
    option_b_match = re.search(
        r"={3,}\s*OPTION\s*B.*?={3,}\s*\n(.*?)$",
        response_text,
        re.DOTALL | re.IGNORECASE,
    )

    result["option_a"] = _parse_single_option(
        option_a_match.group(1) if option_a_match else ""
    )
    result["option_b"] = _parse_single_option(
        option_b_match.group(1) if option_b_match else ""
    )

    return result


def _parse_single_option(text: str) -> dict:
    """Parse a single option's text into structured fields."""
    option = {
        "content_type": "",
        "caption": "",
        "hashtags": "",
        "visual": "",
        "raw": text.strip(),
    }

    # Extract content type
    ct_match = re.search(
        r"\*?\*?Content Type\*?\*?:\s*(.+?)(?:\n|$)", text, re.IGNORECASE
    )
    if ct_match:
        option["content_type"] = ct_match.group(1).strip()

    # Extract caption
    caption_match = re.search(
        r"\*?\*?Caption\*?\*?:\s*\n?(.*?)(?=\*?\*?Hashtags?\*?\*?:|\*?\*?Visual|$)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if caption_match:
        option["caption"] = caption_match.group(1).strip()

    # Extract hashtags
    hashtag_match = re.search(
        r"\*?\*?Hashtags?\*?\*?:\s*\n?(.*?)(?=\*?\*?Visual|$)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if hashtag_match:
        option["hashtags"] = hashtag_match.group(1).strip()

    # Extract visual suggestion
    visual_match = re.search(
        r"\*?\*?Visual Suggestion\*?\*?:\s*\n?(.*?)$",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if visual_match:
        option["visual"] = visual_match.group(1).strip()

    return option


def format_clean_copy(option: dict) -> str:
    """Format an approved option as clean, copy-paste-ready text."""
    parts = []
    if option.get("caption"):
        parts.append(option["caption"])
    if option.get("hashtags"):
        parts.append("")  # blank line
        parts.append(option["hashtags"])
    return "\n".join(parts) if parts else option.get("raw", "")


def format_telegram_preview(option: dict, label: str) -> str:
    """Format an option for Telegram preview display."""
    lines = [f"**{label}**"]
    if option.get("content_type"):
        lines.append(f"📋 Type: {option['content_type']}")
    lines.append("")
    if option.get("caption"):
        lines.append(option["caption"])
    if option.get("hashtags"):
        lines.append("")
        lines.append(option["hashtags"])
    if option.get("visual"):
        lines.append("")
        lines.append(f"🖼 Visual: {option['visual']}")
    return "\n".join(lines)


def count_hashtags(hashtag_text: str) -> int:
    """Count the number of hashtags in a string."""
    return len(re.findall(r"#\w+", hashtag_text))
