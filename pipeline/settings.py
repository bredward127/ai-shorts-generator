"""Runtime settings: lets the dashboard's Settings page write API keys straight
into .env (no hand-editing files) and pushes the change into this already-running
process immediately, so a saved key works without restarting the app.
"""
from __future__ import annotations

import os

from dotenv import set_key

from . import config

ENV_PATH = config.ROOT / ".env"

# Every key the Settings page can read/write. Values are strings; config.py
# re-parses booleans/floats from os.environ on its own, so we mirror the
# string form here and keep config's typed attribute in sync by hand where
# a setting has a non-string type on the config module.
KEYS = [
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY",
    "FAL_KEY", "PEXELS_API_KEY", "PIXABAY_API_KEY",
    "LLM_PROVIDER", "CLAUDE_SCRIPT_MODEL",
    "TTS_PROVIDER", "TTS_VOICE", "ELEVENLABS_VOICE_ID",
]

SECRET_KEYS = {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY",
               "FAL_KEY", "PEXELS_API_KEY", "PIXABAY_API_KEY"}


def _mask(val: str) -> str:
    if not val:
        return ""
    return val if len(val) <= 8 else f"{val[:4]}…{val[-4:]}"


def current(masked: bool = True) -> dict[str, str]:
    out = {}
    for k in KEYS:
        v = getattr(config, k, "") or ""
        out[k] = _mask(v) if (masked and k in SECRET_KEYS) else v
    return out


def save(values: dict[str, str]) -> dict[str, str]:
    """Write the given keys to .env and update this process's live config."""
    if not ENV_PATH.exists():
        ENV_PATH.touch()
    updated = {}
    for key in KEYS:
        if key not in values:
            continue
        val = (values[key] or "").strip()
        if key in SECRET_KEYS and "…" in val:
            continue  # a masked placeholder was sent back unchanged — skip it
        set_key(str(ENV_PATH), key, val, quote_mode="never")
        os.environ[key] = val
        setattr(config, key, val)
        updated[key] = val
    return updated
