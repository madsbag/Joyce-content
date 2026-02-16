"""Telegram bot setup — simplified for the Strategist agent architecture."""

import logging
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from config.settings import TELEGRAM_BOT_TOKEN, JOYCE_TELEGRAM_USER_ID
from interfaces.telegram_handlers import (
    start,
    help_command,
    cancel,
    handle_message,
    handle_photo,
    handle_callback,
    update_voice_start,
    update_voice_upload,
    VOICE_UPLOAD,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def auth_filter():
    """Create a filter that only allows Joyce's user ID."""
    if JOYCE_TELEGRAM_USER_ID:
        return filters.User(user_id=JOYCE_TELEGRAM_USER_ID)
    return filters.ALL


def create_bot() -> Application:
    """Create and configure the Telegram bot application."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    user_filter = auth_filter()

    # ── Brand voice update (standalone ConversationHandler) ──
    voice_conv = ConversationHandler(
        entry_points=[
            CommandHandler("update_voice", update_voice_start, filters=user_filter),
        ],
        states={
            VOICE_UPLOAD: [
                MessageHandler(user_filter & filters.Document.ALL, update_voice_upload),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    app.add_handler(voice_conv)

    # ── Commands ─────────────────────────────────────────────
    app.add_handler(CommandHandler("start", start, filters=user_filter))
    app.add_handler(CommandHandler("post", start, filters=user_filter))
    app.add_handler(CommandHandler("calendar", start, filters=user_filter))
    app.add_handler(CommandHandler("help", help_command, filters=user_filter))
    app.add_handler(CommandHandler("cancel", cancel, filters=user_filter))

    # ── Callback queries (button presses → strategist) ───────
    app.add_handler(CallbackQueryHandler(handle_callback))

    # ── Photo uploads → strategist ───────────────────────────
    app.add_handler(MessageHandler(
        user_filter & filters.PHOTO, handle_photo,
    ))
    app.add_handler(MessageHandler(
        user_filter & filters.Document.IMAGE, handle_photo,
    ))

    # ── Universal text handler (all text → strategist) ───────
    app.add_handler(MessageHandler(
        user_filter & filters.TEXT & ~filters.COMMAND,
        handle_message,
    ))

    return app
