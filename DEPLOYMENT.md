# Deployment Plan — Joyce Content Creator (Sora)

## Overview

This project has **2 components** to deploy:

| Component | Type | Runtime | Purpose |
|---|---|---|---|
| **Telegram Bot** | Worker process (always-on) | Python long-polling | Joyce's primary content creation interface |
| **Streamlit Web App** | Web service (on-demand) | Streamlit server | Secondary browser-based interface |

Both can be deployed independently or together on a single platform.

---

## Recommended Deployment Strategy

### Option A: Railway.app (Recommended — Simplest)

**Why Railway:** One-click GitHub deploy, excellent Python support, both worker + web on one platform, generous free tier, environment variable UI, auto-deploys on push.

| Component | Service Type | Railway Plan | Monthly Cost |
|---|---|---|---|
| Telegram Bot | Worker service | Trial / Hobby | $0-5 |
| Streamlit App | Web service | Trial / Hobby | $0-5 |
| **Total** | | | **$0-10/mo** |

### Option B: Split Deployment (Most Cost-Effective)

| Component | Platform | Cost |
|---|---|---|
| Telegram Bot | Railway.app (worker) | $0-5/mo |
| Streamlit App | Streamlit Community Cloud (free) | $0 |
| **Total** | | **$0-5/mo** |

### Option C: DigitalOcean Droplet (Most Control)

| Component | Platform | Cost |
|---|---|---|
| Both on single VPS | DigitalOcean $6/mo droplet | $6/mo |

---

## Step-by-Step: Option A (Railway.app)

### Prerequisites
- GitHub repo: https://github.com/madsbag/Joyce-content
- Railway account: https://railway.app (sign up with GitHub)
- API keys ready: Anthropic, OpenAI, Telegram Bot Token

### Step 1: Create Telegram Bot on Telegram

1. Open Telegram, search for **@BotFather**
2. Send `/newbot`
3. Name it: `Happy Journey with Joyce Content Bot`
4. Username: `joyce_content_bot` (or similar available name)
5. **Save the bot token** — you'll need it for deployment

6. Get Joyce's Telegram User ID:
   - Search for **@userinfobot** on Telegram
   - Send it any message — it replies with your user ID
   - **Save this number** — it restricts the bot to Joyce only

### Step 2: Deploy Telegram Bot to Railway

1. Go to https://railway.app and sign in with GitHub
2. Click **"New Project"** → **"Deploy from GitHub Repo"**
3. Select **madsbag/Joyce-content**
4. Railway auto-detects Python — click **"Deploy"**

5. **Configure as Worker (not web):**
   - Go to the service **Settings** tab
   - Under **Deploy** section, set the **Start Command** to:
     ```
     python scripts/run_telegram.py
     ```
   - Under **Networking**, **remove the port** (this is a worker, not a web server)

6. **Add Environment Variables:**
   - Go to the **Variables** tab
   - Add these variables:
     ```
     ANTHROPIC_API_KEY=sk-ant-your-key-here
     OPENAI_API_KEY=sk-your-key-here
     TELEGRAM_BOT_TOKEN=your-bot-token-from-botfather
     JOYCE_TELEGRAM_USER_ID=your-telegram-user-id
     CLAUDE_MODEL=claude-sonnet-4-5-20250929
     ```

7. Click **"Deploy"** — Railway builds and starts the bot
8. Check **Logs** tab to verify it says "Starting Happy Journey with Joyce — Telegram Bot (Sora)"
9. Test: Open Telegram, message your bot, send `/start`

### Step 3: Deploy Streamlit Web App to Railway

1. In the same Railway project, click **"New Service"** → **"Deploy from GitHub Repo"**
2. Select the same repo **madsbag/Joyce-content** again
3. This creates a second service from the same repo

4. **Configure as Web Service:**
   - Settings → Start Command:
     ```
     streamlit run scripts/run_web.py --server.port $PORT --server.address 0.0.0.0
     ```
   - Under **Networking**, Railway auto-assigns a port and public URL

5. **Add the same Environment Variables** (copy from the Telegram service)

6. Deploy — Railway gives you a public URL like `joyce-content.up.railway.app`

### Step 4: Verify Everything Works

- [ ] Telegram: Send `/start` to the bot — see welcome message
- [ ] Telegram: Send `/post` → pick Instagram → type a topic → get 2 options
- [ ] Telegram: Pick Option A → get clean copy-paste text
- [ ] Telegram: Send a free-form message → get 2 options
- [ ] Web: Open the Railway URL → see Streamlit chat
- [ ] Web: Type a topic → get 2 options
- [ ] Telegram: Send `/update_voice` → upload .docx → confirm update

---

## Step-by-Step: Option B (Railway + Streamlit Cloud)

### Telegram Bot on Railway
Follow Steps 1-2 from Option A above.

### Streamlit App on Streamlit Community Cloud (Free)

1. Go to https://share.streamlit.io
2. Sign in with GitHub
3. Click **"New app"**
4. Select repo: `madsbag/Joyce-content`
5. Branch: `main`
6. Main file path: `scripts/run_web.py`
7. Click **"Advanced settings"** and add your secrets:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-your-key-here"
   OPENAI_API_KEY = "sk-your-key-here"
   ```
8. Click **"Deploy"**

**Note:** Streamlit Community Cloud apps sleep after inactivity and wake on visit. This is fine for a secondary interface.

---

## Step-by-Step: Option C (DigitalOcean Droplet)

### For users who want full control on a single server.

1. Create a $6/mo Ubuntu 24.04 droplet on DigitalOcean
2. SSH in and set up:

```bash
# Install Python and deps
sudo apt update && sudo apt install -y python3.12 python3-pip git

# Clone repo
git clone https://github.com/madsbag/Joyce-content.git
cd Joyce-content

# Install dependencies
pip3 install -r requirements.txt

# Create .env file
cp .env.example .env
nano .env  # Fill in your API keys

# Run Telegram bot as a background service
sudo tee /etc/systemd/service/joyce-telegram.service << 'HEREDOC'
[Unit]
Description=Joyce Content Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/Joyce-content
ExecStart=/usr/bin/python3 scripts/run_telegram.py
Restart=always
RestartSec=10
EnvironmentFile=/root/Joyce-content/.env

[Install]
WantedBy=multi-user.target
HEREDOC

sudo systemctl enable joyce-telegram
sudo systemctl start joyce-telegram

# Run Streamlit as a background service
sudo tee /etc/systemd/service/joyce-web.service << 'HEREDOC'
[Unit]
Description=Joyce Content Web App
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/Joyce-content
ExecStart=/usr/bin/streamlit run scripts/run_web.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=10
EnvironmentFile=/root/Joyce-content/.env

[Install]
WantedBy=multi-user.target
HEREDOC

sudo systemctl enable joyce-web
sudo systemctl start joyce-web
```

3. Access Streamlit at `http://your-droplet-ip:8501`
4. (Optional) Add a domain + SSL with Nginx reverse proxy + Certbot

---

## Adding Procfile and railway.toml (for Railway)

These files help Railway understand how to build and run the services.

### Procfile (for the Telegram bot service)
Already handled by the start command in Railway settings. No Procfile needed.

### railway.toml (optional — for build configuration)
Can be added if Railway has trouble auto-detecting Python:

```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python scripts/run_telegram.py"
restartPolicyType = "always"
```

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API key from console.anthropic.com |
| `OPENAI_API_KEY` | Yes* | OpenAI key for DALL-E 3 image generation (*optional if skipping images) |
| `TELEGRAM_BOT_TOKEN` | Yes | From @BotFather on Telegram |
| `JOYCE_TELEGRAM_USER_ID` | Yes | Joyce's Telegram user ID (security) |
| `CLAUDE_MODEL` | No | Default: `claude-sonnet-4-5-20250929` |
| `MAX_TOKENS_POST` | No | Default: `3000` |
| `MAX_TOKENS_CALENDAR` | No | Default: `8000` |

---

## Auto-Deploy on Git Push

Both Railway and Streamlit Cloud auto-deploy when you push to `main`:

```bash
# Make changes locally, then:
git add <files>
git commit -m "Update content templates"
git push origin main
# → Railway and Streamlit Cloud automatically rebuild and redeploy
```

---

## Updating Brand Voice (No Redeployment Needed)

The brand voice can be updated **without any code changes or redeployment**:

1. **Via Telegram:** Joyce sends `/update_voice` and uploads a new `.docx`
2. **Via Streamlit:** Upload in sidebar under "Brand Voice"
3. **Via file:** Replace `assets/brand_voice_guide.txt` on the server

The system reads the brand voice file fresh on every API call — no restart needed.

**Important for Railway/Streamlit Cloud:** The file system is ephemeral on these platforms. Brand voice updates via Telegram/Streamlit will persist until the next deploy. For permanent updates:
- Update the `.txt` file in the GitHub repo and push
- Or use Option C (DigitalOcean) where file changes persist

---

## Monitoring and Maintenance

### Railway
- **Logs:** Railway dashboard → Service → Logs tab (real-time)
- **Metrics:** CPU, memory, network usage visible in dashboard
- **Alerts:** Set up in Railway project settings
- **Restart:** Click "Restart" in service settings if needed

### Cost Monitoring
- **Anthropic:** Check usage at console.anthropic.com → Usage
- **OpenAI:** Check usage at platform.openai.com → Usage
- **Railway:** Check usage in project settings → Usage tab

### Expected Monthly Costs

| Usage Level | Claude API | DALL-E 3 | Railway | Total |
|---|---|---|---|---|
| Light (20 posts/mo) | ~$3 | ~$1 | $0-5 | **$4-9** |
| Medium (50 posts/mo) | ~$8 | ~$3 | $5 | **$16** |
| Heavy (100+ posts/mo) | ~$15 | ~$5 | $5 | **$25** |

---

## Scaling Later

When Joyce's business grows:
- **Add LinkedIn/Twitter:** Add new platform templates in `prompts/platform_templates.py`
- **Multiple users:** Add user authentication, switch from JSON to SQLite/PostgreSQL
- **API access:** Wrap `ContentEngine` in a FastAPI endpoint for third-party integrations
- **Scheduled posting:** Add `python-telegram-bot` job queue for auto-posting at optimal times
- **Analytics:** Track which posts perform best and feed that back into preference memory

---

## Troubleshooting

| Issue | Solution |
|---|---|
| Bot not responding | Check Railway logs for errors. Verify `TELEGRAM_BOT_TOKEN` is correct. |
| "Brand voice not found" error | Run `python scripts/export_brand_voice.py` or upload via `/update_voice` |
| Image generation fails | Verify `OPENAI_API_KEY` is set. DALL-E 3 is optional — content works without it. |
| Content doesn't sound like Joyce | Check `assets/brand_voice_guide.txt` exists and is not empty. |
| Streamlit app shows blank | Check environment variables are set in Streamlit Cloud secrets. |
| Railway build fails | Ensure `requirements.txt` is in repo root. Check Python version compatibility. |
| Bot responds to strangers | Set `JOYCE_TELEGRAM_USER_ID` to restrict access. |
