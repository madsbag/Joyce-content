"""Rednote (Xiaohongshu) content formatter for manual posting.

Rednote has NO public API and prohibits automated posting.
This module formats approved content into individually copyable blocks
(English + Chinese) that Joyce can paste directly into the Rednote app.
"""

import re
import logging

logger = logging.getLogger(__name__)


class RednotePublisher:
    """Format approved content for easy manual Rednote posting."""

    def format_for_clipboard(self, option: dict, clean_text: str = "") -> dict:
        """Parse an approved option into separate copyable blocks.

        The content engine generates Rednote content in a bilingual format
        with distinct English and Chinese sections. This method separates
        them into individually copyable pieces.

        Args:
            option: The approved option dict with caption, hashtags, etc.
            clean_text: The format_clean_copy output (caption + hashtags)

        Returns:
            {
                "title": str,
                "body": str,
                "tags": str,
                "chinese_title": str,
                "chinese_body": str,
                "chinese_tags": str,
                "full_text": str,  # everything combined
            }
        """
        raw = option.get("caption") or option.get("raw") or clean_text or ""
        hashtags = option.get("hashtags", "")

        result = {
            "title": "",
            "body": "",
            "tags": "",
            "chinese_title": "",
            "chinese_body": "",
            "chinese_tags": "",
            "full_text": clean_text or raw,
        }

        # Try to split English and Chinese sections
        # Common patterns from the content engine:
        #   "--- ENGLISH ---" / "--- CHINESE ---"
        #   "**English Version**" / "**Chinese Version**"
        #   "🇬🇧 English" / "🇨🇳 Chinese"
        #   Or the Chinese text starts after a blank line with Chinese chars

        en_text, cn_text = self._split_languages(raw)

        # Parse English section
        if en_text:
            result["title"] = self._extract_title(en_text)
            result["body"] = self._extract_body(en_text)
            result["tags"] = self._extract_tags(en_text, hashtags, is_chinese=False)
        else:
            # Fallback: use the whole text as English
            result["title"] = self._extract_title(raw)
            result["body"] = self._extract_body(raw)
            result["tags"] = self._extract_tags(raw, hashtags, is_chinese=False)

        # Parse Chinese section
        if cn_text:
            result["chinese_title"] = self._extract_title(cn_text)
            result["chinese_body"] = self._extract_body(cn_text)
            result["chinese_tags"] = self._extract_tags(cn_text, "", is_chinese=True)

        return result

    def format_posting_instructions(self) -> str:
        """Return step-by-step instructions for posting to Rednote."""
        return (
            "📱 How to post on Rednote (小红书):\n\n"
            "1. Open the Xiaohongshu app\n"
            "2. Tap the + button to create a post\n"
            "3. Add your image (save it from above first)\n"
            "4. Paste the title into the title field\n"
            "5. Paste the body into the content field\n"
            "6. Add the tags\n"
            "7. Review and publish!\n\n"
            "Tip: Long-press each message above to copy it."
        )

    # ── Internal helpers ──────────────────────────────────────

    def _split_languages(self, text: str) -> tuple[str, str]:
        """Split bilingual content into English and Chinese sections."""
        # Pattern 1: Explicit section markers
        for pattern in [
            r"[-=]{3,}\s*(?:ENGLISH|English)\s*[-=]{3,}(.*?)[-=]{3,}\s*(?:CHINESE|Chinese|中文)\s*[-=]{3,}(.*)",
            r"\*\*\s*English\s*(?:Version)?\s*\*\*(.*?)\*\*\s*(?:Chinese|中文)\s*(?:Version|版本)?\s*\*\*(.*)",
            r"🇬🇧\s*English(.*?)🇨🇳\s*(?:Chinese|中文)(.*)",
        ]:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip(), match.group(2).strip()

        # Pattern 2: Look for a block of Chinese characters
        # If more than 20 consecutive Chinese chars appear, split there
        cn_block = re.search(
            r"([\u4e00-\u9fff][\u4e00-\u9fff\s，。！？、：；""''（）【】…—·]{19,})",
            text,
        )
        if cn_block:
            split_pos = cn_block.start()
            en_part = text[:split_pos].strip()
            cn_part = text[split_pos:].strip()
            if en_part and cn_part:
                return en_part, cn_part

        # No clear split — return all as English
        return text, ""

    def _extract_title(self, text: str) -> str:
        """Extract the title (first line or explicit Title: field)."""
        # Check for explicit title field
        title_match = re.search(
            r"\*?\*?(?:Title|标题)\*?\*?:\s*(.+?)(?:\n|$)",
            text,
            re.IGNORECASE,
        )
        if title_match:
            return title_match.group(1).strip()

        # Use first non-empty line as title
        for line in text.split("\n"):
            line = line.strip()
            if line and not line.startswith(("#", "*", "-", "=")):
                # Trim to Rednote title limit
                return line[:20] if len(line) > 20 else line

        return ""

    def _extract_body(self, text: str) -> str:
        """Extract the body (everything except title and tags)."""
        lines = text.split("\n")
        body_lines = []
        skip_first = True  # Skip the first line (title)

        for line in lines:
            stripped = line.strip()
            # Skip title-like fields
            if re.match(r"\*?\*?(?:Title|标题)\*?\*?:", stripped, re.IGNORECASE):
                continue
            # Skip tag/hashtag lines
            if re.match(r"\*?\*?(?:Tags?|Hashtags?|标签)\*?\*?:", stripped, re.IGNORECASE):
                continue
            if stripped.startswith("#") and not stripped.startswith("# "):
                # Hashtag line, skip
                continue
            if skip_first and stripped:
                skip_first = False
                continue
            body_lines.append(line)

        body = "\n".join(body_lines).strip()
        # Remove leading/trailing section markers
        body = re.sub(r"^[-=]{3,}.*?[-=]{3,}\s*\n?", "", body)
        return body

    def _extract_tags(self, text: str, hashtags: str, is_chinese: bool) -> str:
        """Extract hashtags/tags from the text."""
        # Check for explicit tags field
        tag_match = re.search(
            r"\*?\*?(?:Tags?|Hashtags?|标签)\*?\*?:\s*\n?(.*?)$",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if tag_match:
            return tag_match.group(1).strip()

        # Fallback: collect all #hashtag patterns
        tags = re.findall(r"#[\w\u4e00-\u9fff]+", text)
        if tags:
            return " ".join(tags)

        # Use the separate hashtags field
        if hashtags:
            return hashtags

        return ""
