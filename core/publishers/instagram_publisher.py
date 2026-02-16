"""Instagram publishing via the Graph API.

Flow:
1. Upload image to imgbb (temp public URL, auto-deletes)
2. Create media container on Instagram Graph API
3. Poll container status until FINISHED
4. Publish the container → post goes live

Requires:
- Instagram Business Account linked to a Facebook Page
- Meta Developer App with instagram_basic + instagram_content_publish permissions
- Long-lived access token (60-day, auto-refreshable)
- imgbb API key for temporary image hosting
"""

import base64
import json
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from config.settings import (
    INSTAGRAM_APP_ID,
    INSTAGRAM_APP_SECRET,
    INSTAGRAM_TOKEN_FILE,
    IMGBB_API_KEY,
    GRAPH_API_VERSION,
)

logger = logging.getLogger(__name__)

GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


# ── Custom exceptions ────────────────────────────────────────

class PublishError(Exception):
    """Base exception for publishing failures."""


class TokenExpiredError(PublishError):
    """Access token has expired — user must re-run setup."""


class RateLimitError(PublishError):
    """Graph API rate limit exceeded."""

    def __init__(self, message: str, retry_after: int = 0):
        super().__init__(message)
        self.retry_after = retry_after  # minutes


class ImageUploadError(PublishError):
    """Failed to upload image to temporary hosting."""


class ContainerError(PublishError):
    """Media container creation or polling failed."""


# ── Publisher ─────────────────────────────────────────────────

class InstagramPublisher:
    """Publish content to Instagram via the Graph API."""

    def __init__(self):
        self._token_data: dict | None = None

    # ── Public API ────────────────────────────────────────────

    def is_configured(self) -> bool:
        """Check whether Instagram credentials are present and token is valid."""
        if not INSTAGRAM_APP_ID or not INSTAGRAM_APP_SECRET:
            return False
        data = self._load_token()
        if not data or not data.get("access_token"):
            return False
        # Check expiry
        expires = data.get("expires_at", "")
        if expires:
            try:
                exp_dt = datetime.fromisoformat(expires)
                if exp_dt < datetime.now(timezone.utc):
                    return False
            except ValueError:
                pass
        return True

    def publish_photo_post(self, image_bytes: bytes, caption: str) -> dict:
        """Publish a single-image feed post.

        Args:
            image_bytes: PNG/JPEG image as raw bytes
            caption: Full caption text including hashtags

        Returns:
            {"id": media_id} on success

        Raises:
            TokenExpiredError, RateLimitError, ImageUploadError,
            ContainerError, PublishError
        """
        self._refresh_token_if_needed()
        token = self._get_token()
        ig_user_id = self._get_ig_user_id()

        # Step 1 — Upload image to imgbb for a public URL
        image_url = self._upload_to_imgbb(image_bytes)
        logger.info("Image uploaded to imgbb: %s", image_url)

        # Step 2 — Create media container
        creation_id = self._create_media_container(ig_user_id, image_url, caption, token)
        logger.info("Media container created: %s", creation_id)

        # Step 3 — Poll until ready
        self._wait_for_container(creation_id, token)

        # Step 4 — Publish
        media_id = self._publish_container(ig_user_id, creation_id, token)
        logger.info("Published to Instagram: %s", media_id)

        return {"id": media_id}

    # ── Token management ──────────────────────────────────────

    def _load_token(self) -> dict:
        """Load token data from the JSON file."""
        if self._token_data:
            return self._token_data
        if not INSTAGRAM_TOKEN_FILE.exists():
            return {}
        try:
            data = json.loads(INSTAGRAM_TOKEN_FILE.read_text(encoding="utf-8"))
            self._token_data = data
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load Instagram token: %s", e)
            return {}

    def _save_token(self, data: dict):
        """Save token data to disk."""
        INSTAGRAM_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        INSTAGRAM_TOKEN_FILE.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
        self._token_data = data

    def _get_token(self) -> str:
        data = self._load_token()
        token = data.get("access_token", "")
        if not token:
            raise TokenExpiredError("No access token found. Run setup_instagram.py.")
        return token

    def _get_ig_user_id(self) -> str:
        data = self._load_token()
        uid = data.get("ig_user_id", "")
        if not uid:
            raise PublishError("No Instagram user ID found. Run setup_instagram.py.")
        return uid

    def _refresh_token_if_needed(self):
        """Refresh the long-lived token if it expires within 7 days."""
        data = self._load_token()
        expires = data.get("expires_at", "")
        if not expires:
            return

        try:
            exp_dt = datetime.fromisoformat(expires)
        except ValueError:
            return

        now = datetime.now(timezone.utc)
        if exp_dt < now:
            raise TokenExpiredError(
                "Instagram token has expired. Re-run setup_instagram.py."
            )

        days_left = (exp_dt - now).days
        if days_left > 7:
            return  # Still fresh enough

        logger.info("Token expires in %d days — refreshing...", days_left)
        try:
            resp = httpx.get(
                f"{GRAPH_BASE}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": INSTAGRAM_APP_ID,
                    "client_secret": INSTAGRAM_APP_SECRET,
                    "fb_exchange_token": data["access_token"],
                },
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()

            data["access_token"] = result["access_token"]
            expires_in = result.get("expires_in", 5184000)  # default 60 days
            new_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            data["expires_at"] = new_expiry.isoformat()
            data["refreshed_at"] = datetime.now(timezone.utc).isoformat()
            self._save_token(data)
            logger.info("Token refreshed successfully, new expiry: %s", data["expires_at"])
        except Exception as e:
            logger.error("Token refresh failed: %s", e)
            # Don't raise — the current token is still valid for a few more days

    # ── Image hosting ─────────────────────────────────────────

    def _upload_to_imgbb(self, image_bytes: bytes) -> str:
        """Upload image to imgbb and return a public HTTPS URL.

        Auto-deletes after 10 minutes (600 seconds).
        """
        if not IMGBB_API_KEY:
            raise ImageUploadError(
                "IMGBB_API_KEY not configured. Add it to .env to enable publishing."
            )

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        try:
            resp = httpx.post(
                "https://api.imgbb.com/1/upload",
                data={
                    "key": IMGBB_API_KEY,
                    "image": b64,
                    "expiration": 600,  # 10 minutes
                },
                timeout=60,
            )
            resp.raise_for_status()
            result = resp.json()
            if not result.get("success"):
                raise ImageUploadError(f"imgbb error: {result}")
            return result["data"]["url"]
        except httpx.HTTPError as e:
            raise ImageUploadError(f"Image upload failed: {e}") from e

    # ── Graph API calls ───────────────────────────────────────

    def _create_media_container(
        self, ig_user_id: str, image_url: str, caption: str, token: str
    ) -> str:
        """Create an Instagram media container (step 1 of publish)."""
        try:
            resp = httpx.post(
                f"{GRAPH_BASE}/{ig_user_id}/media",
                data={
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": token,
                },
                timeout=30,
            )
            self._check_graph_error(resp)
            return resp.json()["id"]
        except (httpx.HTTPError, KeyError) as e:
            raise ContainerError(f"Container creation failed: {e}") from e

    def _wait_for_container(
        self, creation_id: str, token: str, timeout: int = 60, interval: int = 3
    ):
        """Poll container status until FINISHED or timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = httpx.get(
                    f"{GRAPH_BASE}/{creation_id}",
                    params={
                        "fields": "status_code",
                        "access_token": token,
                    },
                    timeout=15,
                )
                status = resp.json().get("status_code", "")
                if status == "FINISHED":
                    return
                if status == "ERROR":
                    error_msg = resp.json().get("status", "Unknown error")
                    raise ContainerError(f"Container processing failed: {error_msg}")
                time.sleep(interval)
            except httpx.HTTPError as e:
                logger.warning("Status poll error: %s", e)
                time.sleep(interval)
        raise ContainerError("Container processing timed out after 60 seconds.")

    def _publish_container(
        self, ig_user_id: str, creation_id: str, token: str
    ) -> str:
        """Publish a ready container (step 2 of publish)."""
        try:
            resp = httpx.post(
                f"{GRAPH_BASE}/{ig_user_id}/media_publish",
                data={
                    "creation_id": creation_id,
                    "access_token": token,
                },
                timeout=30,
            )
            self._check_graph_error(resp)
            return resp.json()["id"]
        except (httpx.HTTPError, KeyError) as e:
            raise PublishError(f"Publishing failed: {e}") from e

    def _check_graph_error(self, resp: httpx.Response):
        """Check a Graph API response for errors and raise appropriately."""
        if resp.status_code == 429:
            raise RateLimitError(
                "Instagram rate limit exceeded. Try again later.",
                retry_after=15,
            )
        if resp.status_code >= 400:
            try:
                error = resp.json().get("error", {})
                code = error.get("code", 0)
                msg = error.get("message", resp.text)
                # Code 190 = invalid/expired token
                if code == 190:
                    raise TokenExpiredError(msg)
                raise PublishError(f"Instagram API error ({code}): {msg}")
            except (json.JSONDecodeError, AttributeError):
                raise PublishError(f"Instagram API error: {resp.text}")
