"""End-to-end production of one video: visuals (library match -> generate on miss),
voice, captions, music, outro, assembly. Shared by the CLI and the dashboard.
"""
from __future__ import annotations

from pathlib import Path

from . import animate, cards, config, images as imggen, library, match, scriptgen, state, voice
from .assemble import assemble
from .models import Script
from .util import ffprobe_duration, log, run as run_cmd, step, write_json


def _normalize_clip(src: Path, dst: Path) -> None:
    vf = (f"scale={config.WIDTH}:{config.HEIGHT}:force_original_aspect_ratio=increase,"
          f"crop={config.WIDTH}:{config.HEIGHT},fps={config.FPS},setsar=1,format=yuv420p")
    run_cmd(["ffmpeg", "-y", "-i", str(src), "-an", "-vf", vf,
             "-c:v", "libx264", "-preset", "medium", "-crf", "18", str(dst)])


def _generate_and_store(scene, video, images: dict, motion: dict) -> None:
    """Miss path: generate an image (+animation) and add it to the library."""
    img = video.scenes_dir / f"scene_{scene.index:02d}.png"
    can_fal = config.IMAGE_BACKEND == "fal" and config.FAL_KEY
    try:
        if not can_fal:
            raise RuntimeError("no fal image backend")
        url = imggen.generate_image(scene.image_prompt, img)
        images[scene.index] = img
        if config.ANIMATE != "none" and config.FAL_KEY:
            raw = video.scenes_dir / f"scene_{scene.index:02d}_raw.mp4"
            animate.i2v(img, url, scene.motion_prompt, raw)
            cid = f"gen_{video.slug}_{scene.index:02d}"
            clip = config.LIB_CLIPS / f"{cid}.mp4"
            _normalize_clip(raw, clip)
            raw.unlink(missing_ok=True)
            row = {"id": cid, "group": "generated", "lighting": "", "style": "",
                   "description": scene.image_prompt, "image_prompt": scene.image_prompt,
                   "motion_prompt": scene.motion_prompt}
            library.add_clip(row, img, clip, ffprobe_duration(clip),
                             library.embed(scene.image_prompt))
            motion[scene.index] = clip
            log(f"scene {scene.index}: generated + added to library ({cid})")
        else:
            log(f"scene {scene.index}: generated still (Ken Burns)")
    except Exception as e:  # noqa: BLE001
        log(f"scene {scene.index}: generation failed ({e}); fallback background")
        cards.render_fallback_bg(img)
        images[scene.index] = img


def build_visuals(video, script: Script, on_stage=None, overrides: dict | None = None):
    step("Visuals (library match -> generate on miss)")
    overrides = overrides or {}
    images: dict[int, Path] = {}
    motion: dict[int, Path] = {}
    used_ids: set[str] = set()
    scene_clips: dict[str, str] = {}
    for scene in script.scenes:
        if on_stage:
            on_stage(f"scene {scene.index}/{len(script.scenes)} visuals")
        # explicit user choice (preview/swap) wins
        chosen = overrides.get(scene.index) or overrides.get(str(scene.index))
        if chosen:
            clip = library.get_clip(chosen)
            if clip and Path(clip["video_path"]).exists():
                motion[scene.index] = Path(clip["video_path"])
                library.mark_used(clip["id"], video.slug)
                used_ids.add(clip["id"])
                scene_clips[str(scene.index)] = clip["id"]
                log(f"scene {scene.index}: chosen {clip['id']}")
                continue
        clip, score = match.match_scene(scene, used_ids)
        if clip and Path(clip["video_path"]).exists():
            motion[scene.index] = Path(clip["video_path"])
            library.mark_used(clip["id"], video.slug)
            used_ids.add(clip["id"])
            scene_clips[str(scene.index)] = clip["id"]
            log(f"scene {scene.index}: reuse {clip['id']} (match {score:.2f})")
        else:
            log(f"scene {scene.index}: no match (best {score:.2f}) -> generate")
            _generate_and_store(scene, video, images, motion)
    video.manifest["scene_clips"] = scene_clips
    video.save()
    return images, motion


def make(topic: str | None, script: Script | None = None, on_stage=None,
         clip_overrides: dict | None = None) -> Path:
    topic = topic or state.next_topic() or config.DEFAULT_TOPIC
    if on_stage:
        on_stage("writing script")
    script = script or scriptgen.generate(topic)
    video = state.Video(script.slug)
    write_json(video.script_path, script.model_dump())
    state.record_video(video, topic, "generating")

    images, motion = build_visuals(video, script, on_stage=on_stage, overrides=clip_overrides)
    if on_stage:
        on_stage("voiceover")
    audio_info = voice.synthesize(video.audio_dir, script)
    if on_stage:
        on_stage("assembling")
    have_narration = bool(voice._ready())
    final = assemble(video, script, images, audio_info,
                     motion_clips=motion, want_captions=have_narration)

    video.mark("complete", final=str(final))
    state.record_video(video, topic, "complete")
    if on_stage:
        on_stage("done")
    return final
