"""DALL-E image prompt builder for brand-consistent visuals."""

BRAND_IMAGE_STYLE = """
Style: warm editorial photography, soft natural lighting, golden hour warmth.
Color palette: warm golds, soft creams, earth tones, sage greens, muted naturals.
Mood: serene, contemplative, grounding, inviting.
No text, no words, no letters in the image.
No people's faces unless specifically requested.
Clean, minimal composition with breathing room.
"""

SUBJECT_SUGGESTIONS = {
    "reflection": "An open journal with a warm cup of tea on a wooden table, soft morning light through a window, plants nearby",
    "nature": "A gentle winding path through golden-lit trees, soft autumn tones, peaceful and inviting",
    "transition": "A doorway or threshold with warm light spilling through, suggesting new possibility",
    "growth": "A small plant growing in soft earth, warm natural light, close-up with bokeh background",
    "clarity": "A still lake reflecting soft golden sky, minimal composition, sense of calm",
    "connection": "Two comfortable chairs near a window with soft light, a cozy reading nook feel",
    "rest": "Soft blanket draped over a chair, warm tea, candle, evening golden light",
    "courage": "A wide open landscape at dawn, warm colors beginning to emerge, sense of expansiveness",
    "default": "A warm, inviting still life with natural elements — journal, tea, plants — in soft golden light",
}


def get_image_subject_hint(topic: str) -> str:
    """Get a subject suggestion based on the topic keywords."""
    topic_lower = topic.lower()
    for keyword, suggestion in SUBJECT_SUGGESTIONS.items():
        if keyword in topic_lower:
            return suggestion
    return SUBJECT_SUGGESTIONS["default"]
