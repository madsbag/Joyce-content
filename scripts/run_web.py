"""Entry point to start the Streamlit web app.

Usage:
    streamlit run scripts/run_web.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from interfaces.web_app import main

if __name__ == "__main__":
    main()
