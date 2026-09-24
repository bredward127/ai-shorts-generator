"""Bring your own footage into the clip library — e.g. a first-person clip you
filmed yourself — so it's picked up by match-then-generate or hand-picked as
B-roll for any scene in the Create workflow, exactly like stock/AI clips.

A long recording is chopped into LIB_CLIP_SECONDS-ish segments (one library
entry each) so match-then-generate has several usable moments to pick from,
rather than one long clip stretched or squeezed to fit a short scene.
"""
from __future__ import annotations

from pathlib import Path

from . import config, library
from .util import ffprobe_duration, log, run, slugify, step

MAX_SEGMENTS = 8   # cap so one long recording can't flood the library in one go


def _normalize_segment(src: Path, dst: Path, start: float) -> None:
    vf = (f"scale={config.WIDTH}:{config.HEIGHT}:force_original_aspect_ratio=increase,"
          f"crop={config.WIDTH}:{config.HEIGHT},fps={config.FPS},setsar=1,format=yuv420p")
    run(["ffmpeg", "-y", "-ss", f"{start}", "-i", str(src), "-an",
         "-t", f"{config.LIB_CLIP_SECONDS}", "-vf", vf,
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", str(dst)])


def add_still(src: Path, description: str, group: str = "mine", cid: str | None = None) -> str:
    """Turn a photo into a short, gently zooming library clip so it can sit in a
    scene like any video B-roll. Returns the clip id."""
    cid = cid or f"mine_{slugify(src.stem)[:24]}"
    clip = config.LIB_CLIPS / f"{cid}.mp4"
    frames = int(config.LIB_CLIP_SECONDS * config.FPS)
    W, H = config.WIDTH, config.HEIGHT
    vf = (f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
          f"zoompan=z='min(zoom+0.0006,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          f":d={frames}:s={W}x{H}:fps={config.FPS},setsar=1,format=yuv420p")
    run(["ffmpeg", "-y", "-loop", "1", "-i", str(src), "-vf", vf, "-frames:v", str(frames),
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", str(clip)])
    libimg = config.LIB_IMAGES / f"{cid}.jpg"
    run(["ffmpeg", "-y", "-i", str(src), "-frames:v", "1", str(libimg)])
    row = {"id": cid, "group": group, "lighting": "", "style": "personal",
           "description": description, "image_prompt": description, "motion_prompt": ""}
    library.add_clip(row, libimg, clip, ffprobe_duration(clip),
                     library.embed(f"{description} ({group})"))
    log(f"  {cid} added (photo -> {config.LIB_CLIP_SECONDS:.0f}s zoom clip)")
    return cid


def add_upload(src: Path, description: str, group: str = "mine",
               base: str | None = None) -> list[str]:
    """Split `src` into one or more clips and add each to the library. Returns
    the new clip ids."""
    step(f"Adding your footage: {src.name}")
    total = ffprobe_duration(src)
    seg_len = config.LIB_CLIP_SECONDS
    n_segments = min(MAX_SEGMENTS, max(1, int(total // seg_len))) if total > seg_len + 1 else 1
    base = base or f"mine_{slugify(src.stem)[:24]}"
    embedding = library.embed(f"{description} ({group})")

    ids: list[str] = []
    for i in range(n_segments):
        start = i * seg_len
        cid = base if n_segments == 1 else f"{base}_{i + 1:02d}"
        clip = config.LIB_CLIPS / f"{cid}.mp4"
        _normalize_segment(src, clip, start)
        libimg = config.LIB_IMAGES / f"{cid}.jpg"
        run(["ffmpeg", "-y", "-ss", "0.3", "-i", str(clip), "-frames:v", "1", str(libimg)])
        row = {"id": cid, "group": group, "lighting": "", "style": "personal",
               "description": description, "image_prompt": description, "motion_prompt": ""}
        library.add_clip(row, libimg, clip, ffprobe_duration(clip), embedding)
        ids.append(cid)
        log(f"  {cid} added ({start:.1f}s–{start + seg_len:.1f}s of the source)")
    return ids
