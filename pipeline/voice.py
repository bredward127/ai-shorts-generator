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


def _tts_clip(client, text: str, out: Path) -> float:
    raw = out.with_name(out.stem + "_raw.mp3")
    with client.audio.speech.with_streaming_response.create(
        model=config.TTS_MODEL, voice=config.TTS_VOICE, input=text,
        instructions=config.TTS_INSTRUCTIONS, response_format="mp3",
    ) as response:
        response.stream_to_file(str(raw))
    _apply_tempo(raw, out)
    return ffprobe_duration(out)


def synthesize(audio_dir: Path, script: Script) -> list[dict]:
    step("Voiceover")
    client = None
    if config.OPENAI_API_KEY:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
    else:
        log("no OPENAI_API_KEY — writing silent timed clips")

    out_info: list[dict] = []
    for scene in script.scenes:
        out = audio_dir / f"scene_{scene.index:02d}.mp3"
        text = scene.narration.strip()
        if not out.exists():
            dur = _tts_clip(client, text, out) if client else _silent_clip(text, out)
        else:
            dur = ffprobe_duration(out)
        dur = max(config.MIN_SCENE_SECONDS, dur + config.SCENE_PAD)
        log(f"scene {scene.index}: {dur:.2f}s")
        out_info.append({"index": scene.index, "path": str(out), "duration": round(dur, 3)})
    return out_info
