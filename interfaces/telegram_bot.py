"""Telegram bot setup and entry point."""

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
    post_start,
    post_platform,
    post_topic,
    post_image_choice,
    post_photo_upload,
    post_approve,
    post_revise_input,
    calendar_start,
    calendar_themes,
    calendar_platform,
    calendar_frequency,
    calendar_navigate,
    update_voice_start,
    update_voice_upload,
    free_form_message,
    cancel,
    # Conversation states
    POST_PLATFORM,
    POST_TOPIC,
    POST_IMAGE_CHOICE,
    POST_PHOTO_UPLOAD,
    POST_APPROVE,
    POST_REVISE,
    CAL_THEMES,
    CAL_PLATFORM,
    CAL_FREQUENCY,
    CAL_NAVIGATE,
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
    # If no user ID configured, allow all (for development)
    return filters.ALL


def create_bot() -> Application:
    """Create and configure the Telegram bot application."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    user_filter = auth_filter()

    # Post creation conversation
    post_conv = ConversationHandler(
        entry_points=[
            CommandHandler("post", post_start, filters=user_filter),
            CallbackQueryHandler(post_start, pattern="^create_post$"),
        ],
        states={
            POST_PLATFORM: [CallbackQueryHandler(post_platform, pattern="^platform_")],
            POST_TOPIC: [MessageHandler(user_filter & filters.TEXT & ~filters.COMMAND, post_topic)],
            POST_IMAGE_CHOICE: [CallbackQueryHandler(post_image_choice, pattern="^image_")],
            POST_PHOTO_UPLOAD: [
                MessageHandler(user_filter & filters.PHOTO, post_photo_upload),
                MessageHandler(user_filter & filters.Document.IMAGE, post_photo_upload),
            ],
            POST_APPROVE: [CallbackQueryHandler(post_approve, pattern="^approve_")],
            POST_REVISE: [MessageHandler(user_filter & filters.TEXT & ~filters.COMMAND, post_revise_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # Calendar conversation
    calendar_conv = ConversationHandler(
        entry_points=[
            CommandHandler("calendar", calendar_start, filters=user_filter),
            CallbackQueryHandler(calendar_start, pattern="^weekly_calendar$"),
        ],
        states={
            CAL_THEMES: [MessageHandler(user_filter & filters.TEXT & ~filters.COMMAND, calendar_themes)],
            CAL_PLATFORM: [CallbackQueryHandler(calendar_platform, pattern="^calplatform_")],
            CAL_FREQUENCY: [CallbackQueryHandler(calendar_frequency, pattern="^calfreq_")],
            CAL_NAVIGATE: [CallbackQueryHandler(calendar_navigate, pattern="^calnav_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # Brand voice update conversation
    voice_conv = ConversationHandler(
        entry_points=[CommandHandler("update_voice", update_voice_start, filters=user_filter)],
        states={
            VOICE_UPLOAD: [
                MessageHandler(user_filter & filters.Document.ALL, update_voice_upload),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # Register handlers (order matters — conversations first)
    app.add_handler(post_conv)
    app.add_handler(calendar_conv)
    app.add_handler(voice_conv)
    app.add_handler(CommandHandler("start", start, filters=user_filter))
    app.add_handler(CommandHandler("help", help_command, filters=user_filter))

    # Free-form message handler (catches everything else)
    app.add_handler(
        MessageHandler(
            user_filter & filters.TEXT & ~filters.COMMAND,
            free_form_message,
        )
    )

    return app
