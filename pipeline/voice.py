"""Per-scene narration via gpt-4o-mini-tts.

One consistent brand voice, tone-steered via `instructions`, then sped up slightly
(atempo) for a punchy delivery. Scene durations follow the real audio so cuts sync
to the voice. Without an API key it writes silent clips sized by a WPM estimate.
"""
from __future__ import annotations

from pathlib import Path

from . import config
from .models import Script
from .util import ffprobe_duration, log, run, step


def _apply_tempo(src: Path, dst: Path) -> None:
    if abs(config.SPEECH_TEMPO - 1.0) < 0.01:
        if src != dst:
            src.replace(dst)
        return
    run(["ffmpeg", "-y", "-i", str(src), "-filter:a",
         f"atempo={config.SPEECH_TEMPO:.3f}", str(dst)])
    if src != dst and src.exists():
        src.unlink()


def _silent_clip(text: str, out: Path) -> float:
    words = max(1, len(text.split()))
    dur = max(config.MIN_SCENE_SECONDS,
              min(config.MAX_SCENE_SECONDS,
                  words / config.WORDS_PER_MINUTE * 60 / config.SPEECH_TEMPO + 0.4))
    run(["ffmpeg", "-y", "-f", "lavfi", "-i",
         "anullsrc=r=44100:cl=stereo", "-t", f"{dur:.3f}", "-q:a", "9", str(out)])
    return dur


def _tts_clip_openai(client, text: str, out: Path) -> float:
    raw = out.with_name(out.stem + "_raw.mp3")
    with client.audio.speech.with_streaming_response.create(
        model=config.TTS_MODEL, voice=config.TTS_VOICE, input=text,
        instructions=config.TTS_INSTRUCTIONS, response_format="mp3",
    ) as response:
        response.stream_to_file(str(raw))
    _apply_tempo(raw, out)
    return ffprobe_duration(out)


def _tts_clip_elevenlabs(text: str, out: Path) -> float:
    """Narrate with a cloned (or any) ElevenLabs voice — set ELEVENLABS_VOICE_ID
    via the dashboard's Settings page (clone-a-voice) or in .env."""
    import requests

    raw = out.with_name(out.stem + "_raw.mp3")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}"
    r = requests.post(
        url,
        headers={"xi-api-key": config.ELEVENLABS_API_KEY, "Accept": "audio/mpeg"},
        json={"text": text, "model_id": config.ELEVENLABS_MODEL,
              "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}},
        timeout=120,
    )
    r.raise_for_status()
    raw.write_bytes(r.content)
    _apply_tempo(raw, out)
    return ffprobe_duration(out)


def _tts_clip_fal(text: str, out: Path) -> float:
    """Narrate with a cloned voice via fal.ai (zero-shot: the reference sample is
    passed on every call, no separate training step). Set FAL_VOICE_REF_URL from
    the dashboard's Settings page (clone-a-voice) or in .env."""
    import fal_client
    import requests

    raw = out.with_name(out.stem + "_raw.mp3")
    result = fal_client.subscribe(
        config.FAL_TTS_MODEL,
        arguments={"text": text, "audio_url": config.FAL_VOICE_REF_URL},
    )
    url = result.get("audio", {}).get("url") or result.get("audio_url") or result["audio"]["url"]
    raw.write_bytes(requests.get(url, timeout=120).content)
    _apply_tempo(raw, out)
    return ffprobe_duration(out)


def clone_voice_fal(sample_path: Path) -> str:
    """Upload a reference sample to fal's CDN and return its URL, to reuse as
    FAL_VOICE_REF_URL on every narration line. Used by the dashboard's "clone my
    voice" upload when the fal.ai option is picked — reuses the existing FAL_KEY,
    no separate account needed."""
    import fal_client

    if not config.FAL_KEY:
        raise RuntimeError("FAL_KEY not set")
    return fal_client.upload_file(str(sample_path))


def clone_voice(name: str, sample_paths: list[Path]) -> str:
    """Upload one or more audio samples to ElevenLabs and return the new voice_id.
    Used by the dashboard's "clone my voice" upload."""
    import requests

    if not config.ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not set")
    files = [("files", (p.name, p.open("rb"), "audio/mpeg")) for p in sample_paths]
    try:
        r = requests.post(
            "https://api.elevenlabs.io/v1/voices/add",
            headers={"xi-api-key": config.ELEVENLABS_API_KEY},
            data={"name": name},
            files=files,
            timeout=120,
        )
    finally:
        for _, (_, fh, _) in files:
            fh.close()
    r.raise_for_status()
    return r.json()["voice_id"]


def _ready() -> str:
    """Which narration path is usable right now: 'openai' | 'fal' | 'elevenlabs' | ''."""
    if config.TTS_PROVIDER == "fal" and config.FAL_KEY and config.FAL_VOICE_REF_URL:
        return "fal"
    if config.TTS_PROVIDER == "elevenlabs" and config.ELEVENLABS_API_KEY and config.ELEVENLABS_VOICE_ID:
        return "elevenlabs"
    if config.OPENAI_API_KEY:
        return "openai"
    return ""


def synthesize(audio_dir: Path, script: Script) -> list[dict]:
    step("Voiceover")
    provider = _ready()
    client = None
    if provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
    elif not provider:
        log("no voice API key configured — writing silent timed clips")

    out_info: list[dict] = []
    for scene in script.scenes:
        out = audio_dir / f"scene_{scene.index:02d}.mp3"
        text = scene.narration.strip()
        if not out.exists():
            if provider == "fal":
                dur = _tts_clip_fal(text, out)
            elif provider == "elevenlabs":
                dur = _tts_clip_elevenlabs(text, out)
            elif provider == "openai":
                dur = _tts_clip_openai(client, text, out)
            else:
                dur = _silent_clip(text, out)
        else:
            dur = ffprobe_duration(out)
        dur = max(config.MIN_SCENE_SECONDS, dur + config.SCENE_PAD)
        log(f"scene {scene.index}: {dur:.2f}s")
        out_info.append({"index": scene.index, "path": str(out), "duration": round(dur, 3)})
    return out_info
