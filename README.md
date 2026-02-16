# Happy Journey with Joyce — Content Studio

AI-powered social media content creator for **Happy Journey with Joyce**, a wellness coaching business. Generates on-brand Instagram and Rednote posts using Claude AI, with optional AI image generation via DALL-E 3.

## Features

- **2 content options** per request (Reflective + Direct styles) — pick your favorite
- **Auto-detects content type** (feed post, carousel, reel caption) based on your topic
- **Instagram** (English) and **Rednote/Xiaohongshu** (English + Chinese)
- **Weekly content calendar** generation (3-7 posts planned at once)
- **AI image generation** (DALL-E 3) or **text overlay on your own photos** (Pillow)
- **Preference memory** — learns from your last 10 approved posts
- **Hot-swappable brand voice** — update via Telegram command or file upload, no redeployment needed
- **Two interfaces**: Telegram Bot (primary) + Streamlit Web App

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd Joyce-Content
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your API keys:
- `ANTHROPIC_API_KEY` — from [console.anthropic.com](https://console.anthropic.com)
- `OPENAI_API_KEY` — from [platform.openai.com](https://platform.openai.com) (for DALL-E images)
- `TELEGRAM_BOT_TOKEN` — from [@BotFather](https://t.me/BotFather) on Telegram
- `JOYCE_TELEGRAM_USER_ID` — your Telegram user ID (for security)

### 3. Export brand voice (first time only)

```bash
python scripts/export_brand_voice.py
```

This converts the `.docx` brand voice guide to plain text.

### 4. Add brand assets (optional)

- Place your logo PNG in `assets/logo/`
- Place custom fonts (TTF/OTF) in `assets/fonts/`

## Usage

### Telegram Bot

```bash
python scripts/run_telegram.py
```

**Commands:**
- `/start` — Main menu
- `/post` — Create a single post (guided flow)
- `/calendar` — Generate a weekly content calendar
- `/update_voice` — Upload a new brand voice document
- `/help` — Show help

**Free-form mode:** Just type naturally!
- "Write a post about letting go of perfectionism"
- "Rednote post about BodyTalk"
- "5 post ideas about career transitions"

### Web App (Streamlit)

```bash
streamlit run scripts/run_web.py
```

Use the sidebar to select platform, upload photos, or update the brand voice.

## How It Works

1. **You provide a topic** — via Telegram message or web chat
2. **Sora generates 2 options** — Option A (reflective) and Option B (direct), both fully on-brand
3. **You pick, revise, or regenerate** — iterative until you're happy
4. **Get clean copy** — ready to paste into Instagram or Rednote
5. **Preferences are saved** — Sora learns what you like over time

## Updating Brand Voice

No code changes or redeployment needed:

- **Telegram:** Send `/update_voice` and upload a new `.docx` file
- **Web:** Use the "Upload Brand Voice" button in the sidebar
- **Manual:** Replace `assets/brand_voice_guide.txt` on the server

## Project Structure

```
Joyce-Content/
├── config/settings.py          # Configuration and env vars
├── prompts/
│   ├── system_prompt.py        # Layered system prompt builder
│   ├── platform_templates.py   # Instagram + Rednote rules
│   └── image_prompt.py         # DALL-E prompt guidelines
├── core/
│   ├── content_engine.py       # Claude API wrapper
│   ├── image_generator.py      # DALL-E 3 integration
│   ├── image_editor.py         # Pillow text overlays
│   ├── memory.py               # Preference learning
│   └── hashtag_engine.py       # Hashtag pools
├── interfaces/
│   ├── telegram_bot.py         # Bot setup
│   ├── telegram_handlers.py    # Conversation flows
│   └── web_app.py              # Streamlit UI
├── utils/                      # Formatting + validators
├── assets/                     # Brand voice, fonts, logo
├── data/                       # Preferences JSON
└── scripts/                    # Entry points
```

## Cost Estimate

| Component | Monthly Cost |
|---|---|
| Claude API (text) | ~$5-15 |
| DALL-E 3 (images) | ~$2-5 (optional) |
| Railway.app (hosting) | ~$5 |
| **Total** | **~$12-25/mo** |
