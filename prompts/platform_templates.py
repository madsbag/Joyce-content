"""Platform-specific content templates for Instagram and Rednote."""

INSTAGRAM_TEMPLATE = """
PLATFORM: Instagram
LANGUAGE: English only

CONTENT TYPE AUTO-DETECTION:
Based on the topic, automatically choose the best format:
- Feed Post: reflective, narrative, emotionally-driven content (single image + caption)
- Carousel: multi-step insights, lists, frameworks, how-to content (3-7 slides)
- Reel Caption: short, punchy hook meant to accompany video content
- Story: casual, in-the-moment engagement prompt

State your chosen type and a brief reason at the start.

CAPTION STRUCTURE (Feed Post):
1. HOOK (first line, visible before "...more"): A reflective statement or gentle
   provocation that stops the scroll. Under 15 words. This is the most important line.
2. BODY (2-3 short paragraphs): Expand the hook with warmth, grounded insight, and
   a reflective turn. Use blank lines between paragraphs for readability.
3. INVITATION (closing): A soft call to engagement — a question, an invitation to DM,
   or a "save this" prompt. Never salesy or pushy.

CAPTION STRUCTURE (Carousel):
1. COVER SLIDE: Title that captures the theme (under 10 words)
2. SLIDES 2-6: One insight per slide, concise, each can stand alone
3. FINAL SLIDE: Summary or call to save/share
4. CAPTION: Brief context for the carousel + hashtags

CAPTION STRUCTURE (Reel Caption):
1. HOOK: Under 10 words, punchy, curiosity-driving
2. CONTEXT: 1-2 sentences expanding the hook
3. CTA: Simple engagement prompt

FORMATTING RULES:
- Caption length: 150-300 words for feed posts
- Use blank lines between paragraphs (Instagram renders these)
- Emojis: 0-2 max, only if they add warmth (not decoration)
- Hashtags: 8-12 hashtags in a separate block after the caption
- Always use contractions (you're, don't, it's)
- Oxford comma always
- Direct address: always "you", never "people" or "many"

HASHTAG TIERS:
- Brand (always include): #HappyJourneyWithJoyce
- Niche (3-4): from pool of #MidlifeTransition #LifeAfter40 #MidlifeWomen #FindingClarity
  #LifeTransitions #NewChapter #MidlifeJourney #WellnessCoaching #BodyTalk #TalentNumerology
- Topic-specific (3-4): generated based on post content
- Broad reach (2-3): from #PersonalGrowth #SelfDiscovery #InnerWork #Mindfulness
"""

REDNOTE_TEMPLATE = """
PLATFORM: Rednote (Xiaohongshu / Little Red Book)
LANGUAGES: Generate BOTH English AND Chinese versions

REDNOTE-SPECIFIC RULES:
- Rednote posts ALWAYS have a visible title (required by platform)
- Content is more personal, story-driven, and vulnerable than Instagram
- Rednote culture favors real talk, personal sharing, and authentic experience
- Shorter sentences, more paragraph breaks than Instagram
- Emojis: 2-4 integrated naturally (Rednote is more emoji-friendly)
- Tags use # format, 5-8 tags

TITLE:
- 10-20 characters, curiosity-driven or emotionally resonant
- May include 1-2 emojis
- Not clickbait — grounded and honest

BODY STRUCTURE:
1. PERSONAL OPENING: Start with a relatable moment, feeling, or micro-story
2. INSIGHT: The core message, delivered conversationally
3. PRACTICAL TAKEAWAY: One actionable thought or reflection prompt
4. CLOSING: Warm sign-off or question for engagement

CHINESE VERSION RULES:
- This is NOT a literal translation. It is a culturally adapted version.
- Maintain Joyce's warm, grounded, affirming tone in Chinese
- Use 你 (informal "you"), not 您 (formal)
- Use conversational Mandarin, not formal or literary Chinese
- Adapt idioms and references for Chinese-speaking audience
- Rednote's audience may skew younger but Joyce's niche exists on the platform

OUTPUT FORMAT:
Provide both versions clearly separated:

**English Version:**
Title: [title]
[body content]
Tags: #tag1 #tag2 ...

**Chinese Version (中文版):**
标题: [Chinese title]
[Chinese body content]
标签: #tag1 #tag2 ...

HASHTAG TIERS (include both English and Chinese):
- Brand: #HappyJourneyWithJoyce #快乐旅程
- Niche: #MidlifeTransition #中年转变 #人生下半场 #自我成长
- Topic-specific: generated per post
- Broad: #PersonalGrowth #身心灵 #成长日记
"""

DUAL_OPTION_TEMPLATE = """
DUAL CONTENT OPTIONS:
You MUST generate exactly 2 distinct content options for every post.

OPTION A — "Reflective":
- Leads with a question or introspective statement
- More contemplative and narrative in style
- Emphasizes the "reflective" and "warm" voice attributes
- Slightly longer, more story-driven

OPTION B — "Direct":
- Leads with a bold, clear statement or insight
- More action-oriented and grounded
- Emphasizes the "clear" and "grounded" voice attributes
- Slightly shorter, punchier

CRITICAL: Both options MUST:
- Stay fully on-brand (same terminology rules, same words-to-avoid)
- Include complete hashtags and visual suggestions
- Be ready to post as-is
- Be genuinely different in structure and feel, not just word swaps

FORMAT:
===== OPTION A (Reflective) =====
Content Type: [auto-detected type]
[Full content here]

===== OPTION B (Direct) =====
Content Type: [auto-detected type — may differ from Option A]
[Full content here]
"""

AUTO_CONTENT_TYPE_RULES = """
CONTENT TYPE AUTO-DETECTION:
You determine the best content type — Joyce does NOT choose manually.

Decision criteria:
1. Topic complexity: multi-point topics → carousel; single-emotion → feed post
2. Content nature: lists/tips/steps → carousel; narrative/reflection → feed post
3. Brand voice fit: reflective themes → feed post; actionable advice → carousel
4. Platform: Rednote always uses its native post format; Instagram varies
5. Consider what would serve the audience best for this specific message

State your chosen content type and a one-line reason at the top of each option.
"""
