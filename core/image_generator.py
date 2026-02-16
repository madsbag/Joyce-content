"""DALL-E 3 image generation for brand-consistent visuals."""

import io
import httpx
from openai import OpenAI
from config.settings import OPENAI_API_KEY, DALLE_MODEL, INSTAGRAM_IMAGE_SIZE, REDNOTE_IMAGE_SIZE


class ImageGenerator:
    """Generate brand-consistent images using DALL-E 3."""

    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def generate(self, prompt: str, platform: str = "instagram") -> bytes:
        """Generate an image from a DALL-E prompt.

        Args:
            prompt: The DALL-E image prompt
            platform: "instagram" (1:1) or "rednote" (9:16 vertical)

        Returns:
            Image bytes (PNG)
        """
        size = INSTAGRAM_IMAGE_SIZE if platform == "instagram" else REDNOTE_IMAGE_SIZE

        response = self.client.images.generate(
            model=DALLE_MODEL,
            prompt=prompt,
            size=size,
            quality="standard",
            n=1,
        )

        image_url = response.data[0].url

        # Download the image
        image_response = httpx.get(image_url)
        image_response.raise_for_status()
        return image_response.content

    def generate_from_caption(
        self,
        caption: str,
        platform: str,
        content_engine,
    ) -> tuple[bytes, str]:
        """Generate an image by first creating a DALL-E prompt from the caption.

        Args:
            caption: The post caption
            platform: "instagram" or "rednote"
            content_engine: ContentEngine instance (to generate the DALL-E prompt)

        Returns:
            Tuple of (image_bytes, dalle_prompt_used)
        """
        dalle_prompt = content_engine.generate_image_prompt(caption, platform)
        image_bytes = self.generate(dalle_prompt, platform)
        return image_bytes, dalle_prompt
