#!/usr/bin/env python3
"""One-time Instagram OAuth setup for the Joyce Content bot.

This script:
1. Opens the Meta OAuth dialog in your browser
2. Runs a local HTTP server to capture the callback
3. Exchanges the auth code for a short-lived token
4. Exchanges that for a long-lived token (60-day, auto-refreshable)
5. Retrieves the IG Business Account ID
6. Saves everything to config/instagram_token.json

Prerequisites:
- An Instagram Business or Creator account
- A Facebook Page linked to that Instagram account
- A Meta Developer App with:
    - instagram_basic permission
    - instagram_content_publish permission
    - pages_show_list permission
    - pages_read_engagement permission
- INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET in your .env file

Usage:
    python scripts/setup_instagram.py
"""

import json
import sys
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Add project root to path
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import (
    INSTAGRAM_APP_ID,
    INSTAGRAM_APP_SECRET,
    INSTAGRAM_TOKEN_FILE,
    GRAPH_API_VERSION,
)

import httpx

REDIRECT_HOST = "localhost"
REDIRECT_PORT = 8888
REDIRECT_URI = f"http://{REDIRECT_HOST}:{REDIRECT_PORT}/callback"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

PERMISSIONS = [
    "instagram_basic",
    "instagram_content_publish",
    "pages_show_list",
    "pages_read_engagement",
]


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handles the OAuth redirect callback."""

    auth_code: str | None = None

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/callback":
            params = parse_qs(parsed.query)
            if "code" in params:
                OAuthCallbackHandler.auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Authorization successful!</h1>"
                    b"<p>You can close this window and return to the terminal.</p>"
                    b"</body></html>"
                )
            else:
                error = params.get("error_description", ["Unknown error"])[0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    f"<html><body><h1>Authorization failed</h1>"
                    f"<p>{error}</p></body></html>".encode()
                )
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress HTTP log noise


def get_auth_code() -> str:
    """Open browser for OAuth and wait for the callback."""
    auth_url = (
        f"https://www.facebook.com/{GRAPH_API_VERSION}/dialog/oauth?"
        f"client_id={INSTAGRAM_APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={','.join(PERMISSIONS)}"
        f"&response_type=code"
    )

    print("\n📱 Opening browser for Instagram authorization...")
    print(f"   If it doesn't open, visit:\n   {auth_url}\n")
    webbrowser.open(auth_url)

    print("⏳ Waiting for authorization callback...")
    server = HTTPServer((REDIRECT_HOST, REDIRECT_PORT), OAuthCallbackHandler)
    while OAuthCallbackHandler.auth_code is None:
        server.handle_request()

    code = OAuthCallbackHandler.auth_code
    print(f"✅ Authorization code received")
    return code


def exchange_for_short_token(code: str) -> str:
    """Exchange auth code for a short-lived access token."""
    print("🔄 Exchanging code for short-lived token...")
    resp = httpx.get(
        f"{GRAPH_BASE}/oauth/access_token",
        params={
            "client_id": INSTAGRAM_APP_ID,
            "client_secret": INSTAGRAM_APP_SECRET,
            "redirect_uri": REDIRECT_URI,
            "code": code,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"No access_token in response: {data}")
    print("✅ Short-lived token obtained")
    return token


def exchange_for_long_token(short_token: str) -> tuple[str, int]:
    """Exchange short-lived token for a long-lived token (60 days)."""
    print("🔄 Exchanging for long-lived token (60-day)...")
    resp = httpx.get(
        f"{GRAPH_BASE}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": INSTAGRAM_APP_ID,
            "client_secret": INSTAGRAM_APP_SECRET,
            "fb_exchange_token": short_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access_token")
    expires_in = data.get("expires_in", 5184000)  # default 60 days
    if not token:
        raise RuntimeError(f"No access_token in response: {data}")
    print(f"✅ Long-lived token obtained (expires in {expires_in // 86400} days)")
    return token, expires_in


def get_ig_business_account(token: str) -> tuple[str, str]:
    """Find the Instagram Business Account ID linked to the user's Facebook Page."""
    print("🔍 Looking for Instagram Business Account...")

    # Get user's pages
    resp = httpx.get(
        f"{GRAPH_BASE}/me/accounts",
        params={"access_token": token, "fields": "id,name,instagram_business_account"},
        timeout=30,
    )
    resp.raise_for_status()
    pages = resp.json().get("data", [])

    if not pages:
        raise RuntimeError(
            "No Facebook Pages found. Make sure your account has a Facebook Page "
            "linked to an Instagram Business Account."
        )

    # Find a page with an Instagram business account
    for page in pages:
        ig_account = page.get("instagram_business_account")
        if ig_account:
            ig_id = ig_account["id"]
            page_id = page["id"]
            page_name = page.get("name", "Unknown")
            print(f"✅ Found Instagram account {ig_id} via Page '{page_name}'")
            return ig_id, page_id

    # List available pages for debugging
    page_names = [p.get("name", p["id"]) for p in pages]
    raise RuntimeError(
        f"No Instagram Business Account found on your Pages: {page_names}. "
        "Make sure your Instagram account is linked to a Facebook Page "
        "and is a Business or Creator account."
    )


def save_token_data(
    access_token: str,
    expires_in: int,
    ig_user_id: str,
    page_id: str,
):
    """Save all credentials to config/instagram_token.json."""
    now = datetime.now(timezone.utc)
    data = {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_at": (now + timedelta(seconds=expires_in)).isoformat(),
        "ig_user_id": ig_user_id,
        "page_id": page_id,
        "created_at": now.isoformat(),
    }

    INSTAGRAM_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    INSTAGRAM_TOKEN_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"\n💾 Token saved to {INSTAGRAM_TOKEN_FILE}")


def main():
    print("=" * 50)
    print("  Instagram Publishing Setup")
    print("=" * 50)

    # Validate config
    if not INSTAGRAM_APP_ID:
        print("❌ INSTAGRAM_APP_ID not set in .env")
        sys.exit(1)
    if not INSTAGRAM_APP_SECRET:
        print("❌ INSTAGRAM_APP_SECRET not set in .env")
        sys.exit(1)

    try:
        # Step 1: OAuth
        code = get_auth_code()

        # Step 2: Short-lived token
        short_token = exchange_for_short_token(code)

        # Step 3: Long-lived token
        long_token, expires_in = exchange_for_long_token(short_token)

        # Step 4: Find IG Business Account
        ig_user_id, page_id = get_ig_business_account(long_token)

        # Step 5: Save
        save_token_data(long_token, expires_in, ig_user_id, page_id)

        print("\n" + "=" * 50)
        print("  ✅ Setup complete!")
        print("=" * 50)
        print(f"  Instagram User ID: {ig_user_id}")
        print(f"  Token expires: {expires_in // 86400} days from now")
        print(f"  Token auto-refreshes when < 7 days remaining")
        print()
        print("  Next steps:")
        print("  1. Set PUBLISH_ENABLED=true in .env")
        print("  2. Make sure IMGBB_API_KEY is set in .env")
        print("  3. Restart the bot")
        print("  4. Use /post and pick an option — you'll see a Publish button!")

    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
