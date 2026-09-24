"""Central configuration: paths, brand constants, model + API settings.

Everything here is overridable via environment variables (a `.env` file is loaded
automatically). The pipeline is image-first: every scene is a generated cinematic
image with motion; the only on-screen text is the karaoke captions, and the voice
carries the message.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# --- Paths ------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

ASSETS = ROOT / "assets"
LOGO_DIR = ASSETS / "logo"
FONT_DIR = ASSETS / "fonts"
MUSIC_DIR = ASSETS / "music"
BRAND_DIR = ASSETS / "brand"
OUTRO_DIR = ASSETS / "outro"
TEMPLATES = ROOT / "templates"
PROMPTS = ROOT / "prompts"
OUTPUT = ROOT / "output"
DATA = ROOT / "data"

# --- Clip library -----------------------------------------------------------
LIBRARY = ROOT / "library"
LIB_IMAGES = LIBRARY / "images"
LIB_CLIPS = LIBRARY / "clips"
LIB_DB = LIBRARY / "index.db"
INVENTORY_CSV = LIBRARY / "inventory.csv"

for _d in (ASSETS, LOGO_DIR, FONT_DIR, MUSIC_DIR, BRAND_DIR, OUTRO_DIR, OUTPUT, DATA,
           LIBRARY, LIB_IMAGES, LIB_CLIPS):
    _d.mkdir(parents=True, exist_ok=True)


def _flag(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# Runtime matching: reuse a library clip when similarity >= threshold, else
# generate a new clip and add it to the library (match-then-generate).
EMBED_MODEL = "text-embedding-3-small"
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.40"))
RECENCY_WINDOW = int(os.getenv("RECENCY_WINDOW", "8"))   # don't reuse a clip used in the last N videos
USE_LIBRARY = _flag("USE_LIBRARY", True)

# Brand overlays (all optional). Drop your own square PNG at assets/logo/logo.png.
LOGO_PNG = LOGO_DIR / "logo.png"
WATERMARK_PNG = BRAND_DIR / "watermark.png"      # logo + disclaimer, composed once
OUTRO_CARD_PNG = BRAND_DIR / "outro_card.png"    # true-portrait end card
BRAND_PLATE = OUTRO_DIR / "brand_plate.png"      # optional landscape reference (unused)
PREBUILT_OUTRO = OUTRO_DIR / "outro.mp4"         # built once, stitched to every video
OUTRO_VO = OUTRO_DIR / "outro_vo.mp3"            # outro call-to-action voiceover

# Watermark is on by default (replace assets/logo/logo.png with yours, or set
# WATERMARK=false). The branded outro is opt-in (set OUTRO=true + your brand).
ENABLE_WATERMARK = _flag("WATERMARK", True)
ENABLE_OUTRO = _flag("OUTRO", False)
OUTRO_SECONDS = float(os.getenv("OUTRO_SECONDS", "3.6"))

# --- Video format -----------------------------------------------------------
WIDTH = 1080
HEIGHT = 1920
FPS = 30
TARGET_SECONDS = int(os.getenv("TARGET_SECONDS", "20"))   # tighter, snappier shorts
MIN_SCENE_SECONDS = 1.8
MAX_SCENE_SECONDS = 6.0
SCENE_PAD = 0.22                # silence after each line before the cut (snappy)

# --- Brand (override via env; used by watermark, outro, and the dashboard) ---
BRAND = {
    "name": os.getenv("BRAND_NAME", "Your Brand"),
    "url": os.getenv("BRAND_URL", ""),
    "tagline": os.getenv("BRAND_TAGLINE", ""),
    "disclaimer": os.getenv("BRAND_DISCLAIMER", ""),
    "bg": os.getenv("BRAND_BG", "#0B0F17"),
    "surface": os.getenv("BRAND_SURFACE", "#131A24"),
    "accent": os.getenv("BRAND_ACCENT", "#6366F1"),
    "accent_2": os.getenv("BRAND_ACCENT_2", "#8B5CF6"),
    "text": "#F8FAFC",
    "muted": "#94A3B8",
    "display_font": "Sora",
    "body_font": "Inter",
}
# Spoken call-to-action mixed under the outro (only used when OUTRO=true).
OUTRO_VO_TEXT = os.getenv("OUTRO_VO_TEXT", f"Follow {BRAND['name']}.")

# --- Content -----------------------------------------------------------------
# Optional niche/focus injected into the scriptwriter (e.g. "personal finance",
# "fitness motivation", "tech explainers"). Empty = purely topic-driven.
CONTENT_NICHE = os.getenv("CONTENT_NICHE", "").strip()
# Fallback topic when no topic is given and the backlog is empty.
DEFAULT_TOPIC = os.getenv("DEFAULT_TOPIC", "one small habit that quietly changes everything")
# Optional scriptwriter preset: a file in prompts/presets/ (name, with or without
# .md). Empty = the default prompts/scriptgen_system.md. See prompts/presets/README.md.
SCRIPT_PROMPT = os.getenv("SCRIPT_PROMPT", "").strip()

# --- Models / APIs ----------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
FAL_KEY = os.getenv("FAL_KEY", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")   # free at pexels.com/api
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "") # free at pixabay.com/api

# Script writer: "openai" (default) or "claude". Claude only covers scriptgen —
# voiceover and clip-matching embeddings have no Claude equivalent and stay on
# their own providers below.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()
CLAUDE_SCRIPT_MODEL = os.getenv("CLAUDE_SCRIPT_MODEL", "claude-sonnet-5")

# Voiceover: "openai" (stock TTS voices), "fal" (zero-shot voice cloning via
# fal.ai — reuses FAL_KEY, no separate account needed), or "elevenlabs"
# (also voice cloning, needs its own account/key).
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "openai").strip().lower()
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")

# fal.ai voice cloning: drop a reference sample from the dashboard's Settings
# page and it's uploaded to fal once; FAL_VOICE_REF_URL is that hosted URL,
# reused (with the text) on every narration line — no per-voice "training" step.
FAL_TTS_MODEL = os.getenv("FAL_TTS_MODEL", "fal-ai/chatterbox/text-to-speech")
FAL_VOICE_REF_URL = os.getenv("FAL_VOICE_REF_URL", "")

# Length each library clip is trimmed to (stitch-time stretches to the scene).
LIB_CLIP_SECONDS = 5.0
# How many variants to fetch per stock query (you curate/delete the weak ones).
STOCK_VARIANTS = int(os.getenv("STOCK_VARIANTS", "5"))

SCRIPT_MODEL = os.getenv("SCRIPT_MODEL", "gpt-5-mini")   # sharpest scripts. Use "gpt-4o" for speed.
METADATA_MODEL = "gpt-4o-mini"

TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICE = os.getenv("TTS_VOICE", "onyx")
TTS_INSTRUCTIONS = os.getenv("TTS_INSTRUCTIONS", (
    "Fast, punchy, assertive viral short-form narrator. Speak QUICKLY with urgency "
    "and confidence — you are grabbing a scrolling viewer by the collar, loud and "
    "commanding but never shouting. Hit key words hard, minimal pauses, high energy "
    "from the very first word. Bold and intense, like a hype storyteller, not a lecture."
))
# Extra speed-up applied to the rendered voice (atempo). 1.0 = none.
SPEECH_TEMPO = float(os.getenv("SPEECH_TEMPO", "1.15"))

# --- Image generation -------------------------------------------------------
IMAGE_BACKEND = os.getenv("IMAGE_BACKEND", "fal")     # "fal" (Flux) | "local" (SDXL)
FAL_FLUX_MODEL = os.getenv("FAL_FLUX_MODEL", "fal-ai/flux/dev")
IMAGE_SIZE = {"width": 768, "height": 1344}           # 9:16, cover-cropped to 1080x1920
IMAGE_STEPS = 28
# Consistent visual identity across every scene. Tune to taste (photoreal vs stylized).
IMAGE_STYLE = os.getenv("IMAGE_STYLE", (
    "cinematic still, dramatic moody lighting, shallow depth of field, volumetric haze, "
    "rich color grade with warm amber and deep teal accents, film grain, highly detailed, "
    "vertical 9:16 composition. No text, no letters, no numbers, no words, no captions, "
    "no signs, no labels, no logos, no watermark, no readable UI or screens."
))

# --- Motion (image -> video) ------------------------------------------------
# Every scene's still can be animated into a living clip via an i2v model.
#   ANIMATE = "all"  -> animate every scene (max quality, costs fal credit per clip)
#           = "none" -> Ken Burns zoom/pan only (free) — the cost-safe default
#           = "N"    -> animate the N most important scenes, Ken Burns the rest
ANIMATE = os.getenv("ANIMATE", "none")
# Sweet spot: Wan 2.2 5B at ~$0.15/clip. Swap to "fal-ai/wan-i2v" for 14B ($0.40).
I2V_MODEL = os.getenv("I2V_MODEL", "fal-ai/wan/v2.2-5b/image-to-video")
# Ken Burns presets cycle for varied motion on any non-animated scenes / fallback.
KEN_BURNS_CYCLE = ["in", "pan_right", "out", "pan_left", "in", "pan_up"]

# --- Captions ---------------------------------------------------------------
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cuda")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
CAPTION_FONT = BRAND["display_font"]
CAPTION_FONTSIZE = 84
CAPTION_MARGIN_H = 140          # left+right margin so text wraps and never overflows
CAPTION_MARGIN_V = 700          # distance from bottom (sits in the lower-middle)
CAPTION_MAX_WORDS = 3
CAPTION_MAX_CHARS = 15

# --- Watermark --------------------------------------------------------------
WATERMARK_LOGO_PX = int(os.getenv("WATERMARK_LOGO_PX", "96"))   # bottom-right logo size
WATERMARK_OPACITY = float(os.getenv("WATERMARK_OPACITY", "0.9"))

# Local SDXL (free fallback). Few-step model fits a 6 GB GPU.
SDXL_MODEL = os.getenv("SDXL_MODEL", "stabilityai/sdxl-turbo")

# Narration pacing fallback when no API key is set (offline smoke tests).
WORDS_PER_MINUTE = 165
