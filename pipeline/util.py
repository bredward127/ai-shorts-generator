"""Small shared helpers: ffmpeg/ffprobe wrappers, slugify, logging."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def log(msg: str) -> None:
    print(f"   - {msg}", flush=True)


def step(msg: str) -> None:
    print(f"\n>> {msg}", flush=True)


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60].strip("-") or "short"


def run(cmd: list[str], quiet: bool = True) -> None:
    """Run a subprocess, raising with captured output on failure."""
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if proc.returncode != 0:
        sys.stdout.write(proc.stdout)
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd[:3])} ...")
    if not quiet:
        sys.stdout.write(proc.stdout)


def ffprobe_duration(path: Path) -> float:
    """Return media duration in seconds."""
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
