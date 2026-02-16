"""Entry point to start the Telegram bot."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interfaces.telegram_bot import create_bot


def main():
    print("Starting Happy Journey with Joyce — Telegram Bot (Sora)")
    print("Press Ctrl+C to stop.")
    app = create_bot()
    app.run_polling()


if __name__ == "__main__":
    main()
