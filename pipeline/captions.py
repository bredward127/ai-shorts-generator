"""Stage 4b: word-level captions via faster-whisper -> brand ASS subtitles.

Karaoke style: a few words on screen at a time, each word turning amber as it's
spoken. Burned into the video by ffmpeg in assemble.py (free, high quality).
"""
from __future__ import annotations

from pathlib import Path

from . import config
from .util import log, step


def _cc(t: float) -> str:
    """seconds -> ASS time h:mm:ss.cc"""
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    cs = int(round((t - int(t)) * 100))
    if cs == 100:
        cs = 0
        s += 1
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _hex_to_ass(color: str) -> str:
    """#RRGGBB -> ASS &HBBGGRR&"""
    c = color.lstrip("#")
    return f"&H00{c[4:6]}{c[2:4]}{c[0:2]}&".upper()


def _header() -> str:
    b = config.BRAND
    primary = _hex_to_ass(b["accent"])     # color after a word is "sung"
    secondary = _hex_to_ass(b["text"])     # color before (white)
    m = config.CAPTION_MARGIN_H
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {config.WIDTH}
PlayResY: {config.HEIGHT}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,{config.CAPTION_FONT},{config.CAPTION_FONTSIZE},{primary},{secondary},&H00000000&,&H66000000&,1,0,0,0,100,100,0,0,1,7,5,2,{m},{m},{config.CAPTION_MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _group(words: list[dict]) -> list[list[dict]]:
    """Short, punchy caption chunks that never overflow: cap by words AND chars,
    and break on noticeable pauses (scene cuts) or sentence ends."""
    max_words = config.CAPTION_MAX_WORDS
    max_chars = config.CAPTION_MAX_CHARS
    lines, cur, cur_chars = [], [], 0
    for i, w in enumerate(words):
        word = w["word"].strip()
        gap = i > 0 and (w["start"] - words[i - 1]["end"]) > 0.55
        too_long = cur and (cur_chars + len(word) + 1 > max_chars or len(cur) >= max_words)
        if cur and (gap or too_long):
            lines.append(cur)
            cur, cur_chars = [], 0
        cur.append(w)
        cur_chars += len(word) + 1
        if word.endswith((".", "?", "!")):
            lines.append(cur)
            cur, cur_chars = [], 0
    if cur:
        lines.append(cur)
    return lines


def _dialogue(line: list[dict]) -> str:
    start = _cc(line[0]["start"])
    end = _cc(line[-1]["end"])
    parts = []
    for w in line:
        dur_cs = max(1, int(round((w["end"] - w["start"]) * 100)))
        parts.append(f"{{\\k{dur_cs}}}{w['word'].strip().upper()} ")
    return f"Dialogue: 0,{start},{end},Karaoke,,0,0,0,,{''.join(parts).strip()}"


def _run_whisper(audio_path: Path, device: str, compute: str) -> list[dict]:
    """Load + transcribe. ctranslate2 errors surface while iterating segments,
    so we materialize the generator here to catch a missing-CUDA failure."""
    from faster_whisper import WhisperModel

    model = WhisperModel(config.WHISPER_MODEL, device=device, compute_type=compute)
    segments, _ = model.transcribe(str(audio_path), word_timestamps=True, vad_filter=True)
    words: list[dict] = []
    for seg in segments:                       # iteration triggers actual compute
        for w in seg.words or []:
            words.append({"word": w.word, "start": w.start, "end": w.end})
    return words


def _norm(w: str) -> str:
    import re
    return re.sub(r"[^a-z0-9']", "", w.lower())


def _align_to_script(wwords: list[dict], true_text: str) -> list[dict]:
    """Keep Whisper's timing but use the SCRIPT's spelling (Whisper mishears words
    like 'trades' -> 'traid'). Align the two word sequences and emit the true words."""
    import difflib

    true_tokens = true_text.split()
    if not true_tokens or not wwords:
        return wwords
    a = [_norm(w["word"]) for w in wwords]
    b = [_norm(t) for t in true_tokens]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    out: list[dict] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                w = wwords[i1 + k]
                out.append({"word": true_tokens[j1 + k], "start": w["start"], "end": w["end"]})
        elif tag in ("replace", "insert"):
            n = j2 - j1
            if n == 0:
                continue
            if i2 > i1:                       # borrow timing from the whisper block
                t0, t1 = wwords[i1]["start"], wwords[i2 - 1]["end"]
            else:                              # pure insertion: slot between neighbors
                t0 = out[-1]["end"] if out else (wwords[i1]["start"] if i1 < len(wwords) else 0.0)
                t1 = wwords[i1]["start"] if i1 < len(wwords) else t0 + 0.3 * n
            span = max(0.06, t1 - t0)
            for k in range(n):
                out.append({"word": true_tokens[j1 + k],
                            "start": t0 + span * k / n, "end": t0 + span * (k + 1) / n})
        # tag == "delete": whisper had extra words; drop them
    return out


def transcribe_words(audio_path: Path) -> list[dict]:
    if config.WHISPER_DEVICE == "cuda":
        try:
            return _run_whisper(audio_path, "cuda", "float16")
        except Exception as e:  # noqa: BLE001 - CUDA libs (cublas/cudnn) not present
            log(f"whisper cuda unavailable ({type(e).__name__}); falling back to cpu")
    return _run_whisper(audio_path, "cpu", "int8")


def generate(audio_path: Path, ass_path: Path,
             true_text: str | None = None,
             keep_ranges: list[tuple[float, float]] | None = None) -> Path:
    """Transcribe and write ASS. Whisper provides timing; `true_text` (the script)
    provides correct spelling. keep_ranges optionally restricts which words show."""
    step("Captions")
    words = transcribe_words(audio_path)
    if true_text:
        words = _align_to_script(words, true_text)
    if keep_ranges is not None:
        words = [w for w in words if any(a <= w["start"] < b for a, b in keep_ranges)]
    lines = _group(words)
    body = "\n".join(_dialogue(ln) for ln in lines)
    ass_path.write_text(_header() + body + "\n", encoding="utf-8")
    log(f"{len(words)} words -> {len(lines)} caption lines")
    return ass_path
