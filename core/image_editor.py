"""Pillow-based image editor for text overlays and branding."""

import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageFilter
from config.settings import BRAND_COLORS, FONTS_DIR, LOGO_DIR


def _get_font(size: int = 36) -> ImageFont.FreeTypeFont:
    """Load brand font, falling back to default if not available."""
    # Look for custom brand fonts
    font_files = list(FONTS_DIR.glob("*.ttf")) + list(FONTS_DIR.glob("*.otf"))
    if font_files:
        return ImageFont.truetype(str(font_files[0]), size)
    # Fallback to system font
    try:
        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
    except OSError:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except OSError:
            return ImageFont.load_default()


def _get_average_brightness(image: Image.Image, region: tuple) -> float:
    """Calculate average brightness of a region to determine text color."""
    cropped = image.crop(region)
    grayscale = cropped.convert("L")
    pixels = list(grayscale.getdata())
    return sum(pixels) / len(pixels) if pixels else 128


def add_text_overlay(
    image_bytes: bytes,
    text: str,
    position: str = "bottom",
) -> bytes:
    """Add a text overlay with semi-transparent background strip.

    Args:
        image_bytes: Input image as bytes
        text: Quote or hook text to overlay
        position: "top", "center", or "bottom"

    Returns:
        Modified image as PNG bytes
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    width, height = img.size

    # Create overlay layer
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Calculate font size based on image width (responsive)
    font_size = max(24, width // 20)
    font = _get_font(font_size)

    # Word wrap text
    wrapped_lines = _word_wrap(text, font, width - 80)  # 40px padding each side

    # Calculate text block height
    line_height = font_size + 8
    text_block_height = len(wrapped_lines) * line_height + 40  # 20px padding top/bottom

    # Determine position
    if position == "top":
        y_start = 20
    elif position == "center":
        y_start = (height - text_block_height) // 2
    else:  # bottom
        y_start = height - text_block_height - 40

    # Draw semi-transparent background strip
    strip_color = (0, 0, 0, 140)  # Black with ~55% opacity
    draw.rectangle(
        [0, y_start, width, y_start + text_block_height],
        fill=strip_color,
    )

    # Determine text color based on background brightness
    region = (0, y_start, width, y_start + text_block_height)
    brightness = _get_average_brightness(img, region)
    # With dark overlay, always use light text
    text_color = BRAND_COLORS["cream"]

    # Draw text
    y = y_start + 20
    for line in wrapped_lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2  # Center horizontally
        draw.text((x, y), line, fill=text_color, font=font)
        y += line_height

    # Composite overlay onto image
    result = Image.alpha_composite(img, overlay)
    result = result.convert("RGB")

    output = io.BytesIO()
    result.save(output, format="PNG", quality=95)
    return output.getvalue()


def add_logo(image_bytes: bytes, opacity: float = 0.6) -> bytes:
    """Add Joyce's logo as a small watermark in the bottom-right corner.

    Args:
        image_bytes: Input image as bytes
        opacity: Logo opacity (0.0 to 1.0)

    Returns:
        Modified image as PNG bytes
    """
    logo_files = list(LOGO_DIR.glob("*.png")) + list(LOGO_DIR.glob("*.jpg"))
    if not logo_files:
        return image_bytes  # No logo available, return unchanged

    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    logo = Image.open(logo_files[0]).convert("RGBA")

    # Resize logo to ~10% of image width
    logo_width = img.width // 10
    ratio = logo_width / logo.width
    logo_height = int(logo.height * ratio)
    logo = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)

    # Apply opacity
    if opacity < 1.0:
        alpha = logo.getchannel("A")
        alpha = alpha.point(lambda p: int(p * opacity))
        logo.putalpha(alpha)

    # Position: bottom-right with padding
    padding = 20
    position = (img.width - logo_width - padding, img.height - logo_height - padding)

    img.paste(logo, position, logo)
    result = img.convert("RGB")

    output = io.BytesIO()
    result.save(output, format="PNG", quality=95)
    return output.getvalue()


def apply_brand_filter(
    image_bytes: bytes,
    add_brand_logo: bool = True,
) -> bytes:
    """Apply brand-consistent color filter and optionally logo to uploaded image.

    Transforms the image to match Joyce's brand aesthetic:
    warm tones, soft contrast, gentle golden-hour feel.

    Args:
        image_bytes: Joyce's uploaded photo as bytes
        add_brand_logo: Whether to add the logo watermark

    Returns:
        Processed image as PNG bytes
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # 1. Warm tone shift — push slightly toward golden/warm hues
    # Slightly boost color warmth
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(1.05)  # Subtle saturation bump

    # Boost brightness slightly for that airy feel
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(1.03)

    # Soften contrast slightly for a gentler look
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(0.95)

    # 2. Warm color overlay — blend a very faint gold tint
    warm_overlay = Image.new("RGB", img.size, (255, 243, 224))  # Warm cream/gold
    img = Image.blend(img, warm_overlay, alpha=0.06)  # Very subtle

    # 3. Slight soft glow (optional gentle blur blend for dreamy feel)
    soft = img.filter(ImageFilter.GaussianBlur(radius=2))
    img = Image.blend(img, soft, alpha=0.08)  # 8% blend for subtle softness

    # Save intermediate result
    output = io.BytesIO()
    img.save(output, format="PNG", quality=95)
    result = output.getvalue()

    # 4. Add logo watermark if available
    if add_brand_logo:
        result = add_logo(result)

    return result


def process_uploaded_image(
    image_bytes: bytes,
    overlay_text: str = "",
    add_brand_logo: bool = True,
) -> bytes:
    """Full pipeline: apply brand filter and optionally add text overlay.

    Args:
        image_bytes: Joyce's uploaded photo as bytes
        overlay_text: Hook line or quote to overlay (optional, empty = no overlay)
        add_brand_logo: Whether to add the logo watermark

    Returns:
        Processed image as PNG bytes
    """
    # Apply brand color filter first
    result = apply_brand_filter(image_bytes, add_brand_logo=False)

    # Add text overlay only if explicitly requested
    if overlay_text:
        result = add_text_overlay(result, overlay_text)

    if add_brand_logo:
        result = add_logo(result)

    return result


def _word_wrap(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current_line = ""

    # Create a temporary draw for text measurement
    tmp_img = Image.new("RGB", (1, 1))
    tmp_draw = ImageDraw.Draw(tmp_img)

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = tmp_draw.textbbox((0, 0), test_line, font=font)
        line_width = bbox[2] - bbox[0]

        if line_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines
