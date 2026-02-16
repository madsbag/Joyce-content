"""Telegram bot handlers — thin I/O layer for the Strategist agent."""

import asyncio
import io
import logging
import shutil
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import ContextTypes, ConversationHandler
from docx import Document as DocxDocument

from config.settings import BRAND_VOICE_FILE, BRAND_VOICE_BACKUP
from core.strategist import Strategist, AgentAction
from core.session import SessionManager

logger = logging.getLogger(__name__)

TELEGRAM_MAX_LENGTH = 4096

# Brand voice update state
VOICE_UPLOAD = 20

# Shared instances
_strategist: Strategist | None = None
_session_manager: SessionManager | None = None


def _get_strategist() -> Strategist:
    global _strategist
    if _strategist is None:
        _strategist = Strategist()
    return _strategist


def _get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


# ============================================================
# Message splitting for Telegram's 4096 char limit
# ============================================================

async def _safe_reply(message, text: str, **kwargs):
    """Send a message, splitting into chunks if it exceeds Telegram's limit."""
    if len(text) <= TELEGRAM_MAX_LENGTH:
        try:
            await message.reply_text(text, **kwargs)
        except Exception:
            kwargs.pop("parse_mode", None)
            await message.reply_text(text, **kwargs)
        return

    chunks = []
    current = ""
    for paragraph in text.split("\n\n"):
        if len(current) + len(paragraph) + 2 > TELEGRAM_MAX_LENGTH:
            if current:
                chunks.append(current.strip())
            while len(paragraph) > TELEGRAM_MAX_LENGTH:
                chunks.append(paragraph[:TELEGRAM_MAX_LENGTH])
                paragraph = paragraph[TELEGRAM_MAX_LENGTH:]
            current = paragraph
        else:
            current = current + "\n\n" + paragraph if current else paragraph
    if current.strip():
        chunks.append(current.strip())

    for chunk in chunks:
        try:
            await message.reply_text(chunk, **kwargs)
        except Exception:
            kwargs_clean = {k: v for k, v in kwargs.items() if k != "parse_mode"}
            await message.reply_text(chunk, **kwargs_clean)


# ============================================================
# Action dispatcher — sends AgentActions to Telegram
# ============================================================

async def _dispatch_actions(message, actions: list[AgentAction]):
    """Send a list of AgentActions to Telegram."""
    for action in actions:
        try:
            if action.type == "text" and action.text:
                await _safe_reply(message, action.text, parse_mode=action.parse_mode)
            elif action.type == "photo" and action.image_bytes:
                await message.reply_photo(
                    photo=action.image_bytes,
                    caption=action.text[:1024] if action.text else None,
                )
            elif action.type == "buttons" and action.buttons:
                keyboard = [
                    [
                        InlineKeyboardButton(btn["text"], callback_data=btn["data"])
                        for btn in row
                    ]
                    for row in action.buttons
                ]
                await message.reply_text(
                    action.text or "Choose an option:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
        except Exception as e:
            logger.error("Failed to dispatch action %s: %s", action.type, e)


# ============================================================
# Progress helper — status message + typing heartbeat
# ============================================================

async def _run_with_progress(
    message,
    strategist: Strategist,
    session,
    user_content: list[dict],
    memory_context: str,
) -> list[AgentAction]:
    """Run a strategist turn with live progress feedback in Telegram."""
    chat = message.chat

    # Send initial status message
    status_msg = await message.reply_text("⏳ Thinking...")

    # Typing heartbeat — re-sends TYPING every 4s so the indicator stays alive
    typing_active = True

    async def _typing_heartbeat():
        while typing_active:
            try:
                await chat.send_action(ChatAction.TYPING)
            except Exception:
                pass
            await asyncio.sleep(4)

    heartbeat_task = asyncio.create_task(_typing_heartbeat())

    # Progress callback — edits the status message in-place
    async def _progress_callback(status_text: str):
        try:
            await status_msg.edit_text(status_text)
        except Exception:
            pass  # message unchanged or already deleted

    try:
        actions = await strategist.run_turn(
            session, user_content, memory_context,
            progress_callback=_progress_callback,
        )
    finally:
        # Cleanup: stop heartbeat, delete status message
        typing_active = False
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        try:
            await status_msg.delete()
        except Exception:
            pass

    return actions


# ============================================================
# /start and /help
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message — start a new strategist session."""
    sm = _get_session_manager()
    user_id = update.effective_user.id

    # End any existing session (async — summarizes with Claude)
    await sm.end_session(user_id)

    # Create fresh session
    sm.get_or_create(user_id)

    await update.message.reply_text(
        "Hi Joyce! I'm Sora, your content strategist.\n\n"
        "What are we creating today? You can:\n"
        "- Describe a post idea (vague or detailed)\n"
        "- Send me text you've already written\n"
        "- Send a photo you want to use\n"
        "- Say \"plan my week\" for a content calendar\n\n"
        "Just tell me what's on your mind."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information."""
    text = (
        "*Available Commands:*\n\n"
        "/start — Start a new content session\n"
        "/post — Same as /start\n"
        "/update\\_voice — Upload a new brand voice document\n"
        "/help — Show this help message\n"
        "/cancel — End current session\n\n"
        "*How to use:*\n"
        "Just message me naturally. I'll help shape your idea, "
        "then produce content options for you to pick from.\n\n"
        "You can send:\n"
        "- A rough idea: \"something about letting go\"\n"
        "- A detailed brief: \"short punchy post about...\" \n"
        "- Your own written text for me to refine\n"
        "- A photo to pair with a post\n"
        "- \"plan my week\" for a content calendar"
    )
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if msg:
        await msg.reply_text(text, parse_mode="Markdown")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel / end the current session."""
    sm = _get_session_manager()
    user_id = update.effective_user.id
    await sm.end_session(user_id)
    await update.message.reply_text("Session ended. Send /start to begin a new one.")


# ============================================================
# Universal message handler — feeds into the strategist
# ============================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any text message — route to the strategist agent."""
    sm = _get_session_manager()
    strategist = _get_strategist()
    user_id = update.effective_user.id
    logger.info("Message from user %s: %s", user_id, update.message.text[:100])

    # Auto-create session if none exists
    session = sm.get_or_create(user_id)

    # Build user content
    user_content = [{"type": "text", "text": update.message.text}]

    try:
        # Serialize turns per user
        async with sm.get_lock(user_id):
            memory_context = sm.load_memory_context(user_id)
            actions = await _run_with_progress(
                update.message, strategist, session, user_content, memory_context,
            )

        logger.info("Strategist returned %d actions for user %s", len(actions), user_id)

        # Dispatch to Telegram
        await _dispatch_actions(update.message, actions)
    except Exception as e:
        logger.error("Error handling message from user %s: %s", user_id, e, exc_info=True)
        await update.message.reply_text(
            "Sorry, something went wrong processing your message. Please try again or /cancel."
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo uploads — store on session and inform the strategist."""
    sm = _get_session_manager()
    strategist = _get_strategist()
    user_id = update.effective_user.id
    logger.info("Photo from user %s", user_id)

    session = sm.get_or_create(user_id)

    # Download the photo
    if update.message.photo:
        photo = update.message.photo[-1]  # highest resolution
    elif update.message.document:
        photo = update.message.document
    else:
        await update.message.reply_text("Please send a photo. Try again or /cancel.")
        return

    file = await photo.get_file()
    image_bytes = await file.download_as_bytearray()
    session.uploaded_photo = bytes(image_bytes)

    # Build user content (inform strategist about the upload)
    caption = update.message.caption or ""
    text = "[Joyce uploaded a photo]"
    if caption:
        text += f" with caption: {caption}"

    user_content = [{"type": "text", "text": text}]

    try:
        async with sm.get_lock(user_id):
            memory_context = sm.load_memory_context(user_id)
            actions = await _run_with_progress(
                update.message, strategist, session, user_content, memory_context,
            )

        await _dispatch_actions(update.message, actions)
    except Exception as e:
        logger.error("Error handling photo from user %s: %s", user_id, e, exc_info=True)
        await update.message.reply_text(
            "Sorry, something went wrong processing your photo. Please try again or /cancel."
        )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses — translate to strategist message."""
    query = update.callback_query
    await query.answer()

    sm = _get_session_manager()
    strategist = _get_strategist()
    user_id = update.effective_user.id
    logger.info("Button press from user %s: %s", user_id, query.data)

    session = sm.get_or_create(user_id)

    # Echo the button press as visible text so there's a record in chat
    button_label = query.data.replace("_", " ").title()  # "pick_a" → "Pick A"
    await query.message.reply_text(f"Joyce selected: {button_label}")

    # Translate button press into a text message for the strategist
    button_data = query.data
    user_content = [{"type": "text", "text": f"[BUTTON: {button_data}]"}]

    try:
        async with sm.get_lock(user_id):
            memory_context = sm.load_memory_context(user_id)
            actions = await _run_with_progress(
                query.message, strategist, session, user_content, memory_context,
            )

        await _dispatch_actions(query.message, actions)
    except Exception as e:
        logger.error("Error handling callback from user %s: %s", user_id, e, exc_info=True)
        await query.message.reply_text(
            "Sorry, something went wrong. Please try again or /cancel."
        )


# ============================================================
# Brand voice update (kept as standalone ConversationHandler)
# ============================================================

async def update_voice_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the brand voice update flow."""
    await update.message.reply_text(
        "Upload your new brand voice document (.docx format).\n\n"
        "I'll back up the current one and start using the new guide immediately."
    )
    return VOICE_UPLOAD


async def update_voice_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle brand voice document upload."""
    doc = update.message.document
    if not doc.file_name.endswith(".docx"):
        await update.message.reply_text(
            "Please upload a .docx file. Other formats aren't supported yet."
        )
        return VOICE_UPLOAD

    try:
        file = await doc.get_file()
        file_bytes = await file.download_as_bytearray()

        docx_doc = DocxDocument(io.BytesIO(bytes(file_bytes)))
        lines = []
        for paragraph in docx_doc.paragraphs:
            text = paragraph.text.strip()
            lines.append(text if text else "")
        for table in docx_doc.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                lines.append(" | ".join(cells))
            lines.append("")

        new_content = "\n".join(lines)

        if BRAND_VOICE_FILE.exists():
            shutil.copy2(BRAND_VOICE_FILE, BRAND_VOICE_BACKUP)

        BRAND_VOICE_FILE.write_text(new_content, encoding="utf-8")

        await update.message.reply_text(
            "Brand voice updated!\n\n"
            f"New guide: {len(new_content)} characters, {len(new_content.split())} words.\n"
            "Your next content will use the new guide automatically."
        )

    except Exception as e:
        logger.error("Brand voice update failed: %s", e)
        await update.message.reply_text(
            f"Something went wrong processing the document. Error: {e}\n"
            "Please try again or contact support."
        )

    return ConversationHandler.END
