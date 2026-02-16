import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)
ASSETS_DIR = BASE_DIR / "assets"
DATA_DIR = BASE_DIR / "data"
BRAND_VOICE_FILE = ASSETS_DIR / "brand_voice_guide.txt"
BRAND_VOICE_BACKUP = ASSETS_DIR / "brand_voice_guide.bak.txt"
PREFERENCES_FILE = DATA_DIR / "preferences.json"
FONTS_DIR = ASSETS_DIR / "fonts"
LOGO_DIR = ASSETS_DIR / "logo"

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
JOYCE_TELEGRAM_USER_ID = int(os.getenv("JOYCE_TELEGRAM_USER_ID", "0"))

# Model settings
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
MAX_TOKENS_POST = int(os.getenv("MAX_TOKENS_POST", "3000"))
MAX_TOKENS_CALENDAR = int(os.getenv("MAX_TOKENS_CALENDAR", "8000"))

# Image generation
DALLE_MODEL = "dall-e-3"
INSTAGRAM_IMAGE_SIZE = "1024x1024"
REDNOTE_IMAGE_SIZE = "1024x1792"  # 9:16 vertical for Rednote

# Preference memory
MAX_PREFERENCES = 10

# Strategist agent
MAX_TOKENS_STRATEGIST = int(os.getenv("MAX_TOKENS_STRATEGIST", "2048"))
SESSION_STORAGE_DIR = DATA_DIR / "sessions"
MAX_RECENT_SESSIONS = 3

# Brand colors (for image overlays)
BRAND_COLORS = {
    "warm_gold": "#C4A35A",
    "cream": "#F5F0E8",
    "sage_green": "#8B9D83",
    "earth_brown": "#6B5B4F",
    "soft_white": "#FAFAF7",
}

# Platform limits
INSTAGRAM_MAX_CAPTION = 2200
INSTAGRAM_MAX_HASHTAGS = 30
REDNOTE_MAX_TITLE = 20
REDNOTE_MAX_BODY_CHARS = 1000

# ── Publishing ────────────────────────────────────────────────
# Master switch — set to "true" to enable publish buttons after approval
PUBLISH_ENABLED = os.getenv("PUBLISH_ENABLED", "false").lower() == "true"

# Instagram Graph API
INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID", "")
INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET", "")
INSTAGRAM_TOKEN_FILE = BASE_DIR / "config" / "instagram_token.json"
GRAPH_API_VERSION = "v21.0"

# Image hosting for Instagram (Graph API needs a public URL)
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "")
