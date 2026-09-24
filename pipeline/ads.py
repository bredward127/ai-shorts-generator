"""Ad planner: messaging brief + DIY shot list (via Claude), shot-setup diagrams
and the final ad layout (both rendered to PNG with the same Playwright/Jinja
recipe the video pipeline uses for its watermark/outro overlays).

Everything for one ad lives under ADS_DIR/<slug>/: plan.json, photos/ (raw
uploads + auto-split crops), diagrams/ (one PNG per shot), final.png.
"""
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config
from .ad_models import AdPlan, AdVideoScript
from .util import log, slugify, step

PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".webp")
VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv")

_env = Environment(
    loader=FileSystemLoader(str(config.TEMPLATES)),
    autoescape=select_autoescape(["html"]),
)

ACCENT = "#C4693B"


# --- project storage ----------------------------------------------------------
def _dir(slug: str) -> Path:
    d = config.ADS_DIR / slug
    (d / "photos").mkdir(parents=True, exist_ok=True)
    (d / "diagrams").mkdir(parents=True, exist_ok=True)
    return d


def save_plan(plan: AdPlan) -> Path:
    d = _dir(plan.slug)
    p = d / "plan.json"
    p.write_text(json.dumps(plan.model_dump(), indent=2), encoding="utf-8")
    return p


def load_plan(slug: str) -> AdPlan | None:
    p = config.ADS_DIR / slug / "plan.json"
    if not p.exists():
        return None
    return AdPlan(**json.loads(p.read_text(encoding="utf-8")))


def list_ads() -> list[dict]:
    if not config.ADS_DIR.exists():
        return []
    out = []
    for d in sorted(config.ADS_DIR.iterdir(), reverse=True):
        plan = load_plan(d.name) if (d / "plan.json").exists() else None
        if plan:
            out.append({"slug": plan.slug, "product_name": plan.product_name,
                       "hook": plan.brief.hook, "has_final": (d / "final.png").exists()})
    return out


def _claude_structured(system: str, user: str, model_cls, tool_name: str):
    """Ask Claude for output matching a pydantic model (forced tool call)."""
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("Add your Anthropic API key in Settings first — the ad planner "
                           "uses Claude to write the plan and the video script.")
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=config.CLAUDE_SCRIPT_MODEL,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
        tools=[{"name": tool_name, "description": "Submit the result.",
                "input_schema": model_cls.model_json_schema()}],
        tool_choice={"type": "tool", "name": tool_name},
    )
    tool_use = next(b for b in resp.content if b.type == "tool_use")
    return model_cls(**tool_use.input)


# --- stage 1: plan --------------------------------------------------------------
def plan(description: str, audience: str, platform: str = "Instagram/Facebook feed (4:5)") -> AdPlan:
    """Generate the messaging brief + shot list via Claude. Requires ANTHROPIC_API_KEY."""
    step("Planning ad")
    system = (
        "You are a direct-response ad strategist and photography director. Given a physical "
        "product, write a messaging brief and a DIY shot list for someone who is NOT a "
        "photographer to shoot themselves at home.\n\n"
        "Messaging rules: lead the hook with the problem/moment, not the product name. Name a "
        "specific, recognizable annoyance in the problem line. For every feature, translate it "
        "into a benefit — never list a bare spec. Value props are 3-6 words, benefit-first. "
        "Never invent a price, discount, review count, shipping claim, or urgency claim that "
        "wasn't given to you.\n\n"
        "Shot list rules: 2-4 shots, each one earning its place because it proves a specific "
        "line in the brief (a hero/context shot, a feature close-up, and — only if the product's "
        "value depends on its shape or multiple states — a profile/silhouette shot). Be concrete "
        "and literal in angle/framing/lighting/mistake fields — these are read by someone who has "
        "never done a product photo shoot, so 'nice lighting' is useless; 'soft daylight from a "
        "window to the side, no direct sun' is what they need. Every shot will be captured both "
        "as a photo AND as a 3-5 second phone video clip used as B-roll under a voiceover, so "
        "fill 'motion' with one simple, steady camera move a beginner can do."
    )
    user = f"Product: {description}\nAudience for this ad: {audience}\nPlatform: {platform}"
    result = _claude_structured(system, user, AdPlan, "write_ad_plan")
    result.slug = slugify(result.slug or result.product_name)
    save_plan(result)
    log(f"plan ready · {len(result.shots)} shots · slug={result.slug}")
    return result


# --- composite photo splitting ---------------------------------------------------
def split_composite(src: Path, slug: str) -> list[Path]:
    """Split a 2x2 composite/collage product photo into individual crops, by
    detecting the actual seam (the near-white gutter) rather than assuming a
    dead-center 50/50 split. Returns the 4 crop paths."""
    from PIL import Image
    import numpy as np

    im = Image.open(src).convert("RGB")
    gray = np.array(im.convert("L"))
    h, w = gray.shape
    row_means = gray.mean(axis=1)
    split_row = int(h * 0.40) + int(row_means[int(h * 0.40):int(h * 0.60)].argmax())
    col_means = gray.mean(axis=0)
    split_col = int(w * 0.40) + int(col_means[int(w * 0.40):int(w * 0.60)].argmax())

    # trim any black letterbox bars at the outer edges
    top = next((y for y in range(min(60, h)) if row_means[y] > 200), 0)
    bottom = h - next((y for y in range(min(60, h)) if row_means[h - 1 - y] > 200), 0)

    pad = 4
    boxes = {
        "tl": (0, top, split_col - pad, split_row - pad),
        "tr": (split_col + pad, top, w, split_row - pad),
        "bl": (0, split_row + pad, split_col - pad, bottom),
        "br": (split_col + pad, split_row + pad, w, bottom),
    }
    out_dir = _dir(slug) / "photos"
    paths = []
    for name, box in boxes.items():
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        p = out_dir / f"split_{name}.png"
        im.crop(box).save(p)
        paths.append(p)
    log(f"split composite into {len(paths)} crops")
    return paths


# --- stage 2: shot diagrams -----------------------------------------------------
def render_shot_diagram(plan_obj: AdPlan, index: int) -> Path:
    """Render shot #index (0-based) as a labeled setup diagram PNG."""
    from playwright.sync_api import sync_playwright

    shot = plan_obj.shots[index]
    w, h = 780, 660
    html = _env.get_template("ad_shot_diagram.html").render(
        w=w, h=h, accent=ACCENT, shot=shot, index=index + 1, total=len(plan_obj.shots),
        role="Hero" if index == 0 else ("Feature close-up" if shot.diagram_layout == "macro" else ""),
    )
    out = _dir(plan_obj.slug) / "diagrams" / f"shot_{index + 1}.png"
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--force-color-profile=srgb"])
        page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        page.set_content(html, wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(120)
        page.screenshot(path=str(out), type="png")
        browser.close()
    return out


def render_all_diagrams(plan_obj: AdPlan) -> list[Path]:
    return [render_shot_diagram(plan_obj, i) for i in range(len(plan_obj.shots))]


# --- stage 3: assemble the final ad ----------------------------------------------
def assemble(plan_obj: AdPlan, image_paths: list[Path], platform: str = "4:5",
             accent: str = ACCENT) -> Path:
    """Build the final ad PNG from 1-3 real photos + the saved plan's brief."""
    from playwright.sync_api import sync_playwright
    import base64

    step("Assembling ad")
    sizes = {"4:5": (1080, 1350), "1:1": (1080, 1080), "9:16": (1080, 1920)}
    w, h = sizes.get(platform, (1080, 1350))

    images = []
    for i, p in enumerate(image_paths[:3]):
        data = base64.b64encode(Path(p).read_bytes()).decode()
        ext = Path(p).suffix.lstrip(".").lower() or "png"
        badge, style = "", "dark"
        if i == 0 and plan_obj.shots:
            badge = ""  # hero image: no badge, keep it clean
        elif plan_obj.shots and len(plan_obj.shots) > i:
            badge = plan_obj.shots[i].proves
            style = "accent"
        images.append({"src": f"data:image/{ext};base64,{data}", "alt": plan_obj.shots[i].name
                       if i < len(plan_obj.shots) else plan_obj.product_name,
                       "badge": badge, "badge_style": style})

    headline_size = 60 if len(plan_obj.brief.hook) < 40 else 48
    html = _env.get_template("ad_final.html").render(
        w=w, h=h, accent=accent, headline_size=headline_size,
        img_h=int(h * 0.38), eyebrow="", hook=plan_obj.brief.hook,
        problem=plan_obj.brief.problem, images=images,
        value_props=plan_obj.brief.value_props, product_name=plan_obj.product_name,
        support_line="", cta=plan_obj.brief.cta,
    )
    out = _dir(plan_obj.slug) / "final.png"
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--force-color-profile=srgb"])
        page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        page.set_content(html, wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(150)
        page.screenshot(path=str(out), type="png")
        browser.close()
    log(f"final ad -> {out}")
    return out


# --- media → shot assignment -----------------------------------------------------
def _media_path(slug: str) -> Path:
    return _dir(slug) / "media.json"


def media_map(slug: str) -> dict[str, int]:
    """{uploaded filename: shot number (1-based, 0 = unassigned)}."""
    p = _media_path(slug)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def assign_media(slug: str, filename: str, shot: int) -> None:
    m = media_map(slug)
    m[filename] = int(shot)
    _media_path(slug).write_text(json.dumps(m, indent=2), encoding="utf-8")


def _ingest(slug: str, filename: str, description: str) -> list[str]:
    """Add one uploaded photo/video to the clip library (once) and return its
    clip id(s). Videos may yield several ~5s segments; photos yield one."""
    from . import library, upload

    src = _dir(slug) / "photos" / filename
    base = f"ad_{slug[:20]}_{slugify(Path(filename).stem)[:20]}"
    if src.suffix.lower() in VIDEO_EXTS:
        if library.has(base) or library.has(f"{base}_01"):
            return [c["id"] for c in library.all_clips()
                    if c["id"] == base or c["id"].startswith(base + "_")]
        return upload.add_upload(src, description, group=f"ad-{slug[:24]}", base=base)
    if library.has(base):
        return [base]
    return [upload.add_still(src, description, group=f"ad-{slug[:24]}", cid=base)]


# --- stage 4: the video ad (voice + B-roll + captions + music) ------------------
def video_script(plan_obj: AdPlan) -> AdVideoScript:
    """Turn the brief into a 4-6 line spoken voiceover, each line pinned to the
    shot whose footage plays under it."""
    step("Writing video ad script")
    shots = "\n".join(f"{i + 1}. {s.name} — {s.proves} (framing: {s.framing})"
                      for i, s in enumerate(plan_obj.shots))
    b = plan_obj.brief
    feats = "\n".join(f"- {f.feature}: {f.benefit}" for f in b.features)
    system = (
        "You write voiceover scripts for short vertical video ads (TikTok/Reels/Shorts), "
        f"about {config.TARGET_SECONDS} seconds spoken. Structure: hook line first, then the "
        "problem, then 1-3 benefit lines, then the call to action. One sentence per scene, "
        "conversational, punchy, written to be SAID out loud. Use the brief's own hook and CTA "
        "wording where it's already strong. Pin every scene to the shot whose footage best "
        "shows what's being said; the hook usually sits on the hero shot, feature lines on "
        "close-ups. Reusing a shot across scenes is fine. Never invent prices, discounts, "
        "reviews, or urgency."
    )
    user = (f"Product: {plan_obj.product_name}\nHook: {b.hook}\nProblem: {b.problem}\n"
            f"Features → benefits:\n{feats}\nValue props: {', '.join(b.value_props)}\n"
            f"CTA: {b.cta}\n\nShot list (footage the creator filmed):\n{shots}")
    script = _claude_structured(system, user, AdVideoScript, "write_video_ad")
    (_dir(plan_obj.slug) / "video_script.json").write_text(
        json.dumps(script.model_dump(), indent=2), encoding="utf-8")
    return script


def make_video(plan_obj: AdPlan, on_stage=None) -> str:
    """Full video ad: script → your footage as B-roll per scene → voiceover (your
    cloned voice if set in Settings) → karaoke captions → music bed → final.mp4.
    Scenes with no footage fall back to library match / AI generation. Returns
    the video id shown on the Videos tab."""
    import shutil

    from . import produce, state
    from .models import Scene, Script

    say = on_stage or (lambda s: None)
    say("writing voiceover script")
    vs = video_script(plan_obj)

    say("adding your footage to the library")
    by_shot: dict[int, list[str]] = {}
    for filename, shot_no in media_map(plan_obj.slug).items():
        if not shot_no or not (_dir(plan_obj.slug) / "photos" / filename).exists():
            continue
        shot = plan_obj.shots[shot_no - 1] if shot_no <= len(plan_obj.shots) else None
        desc = f"{plan_obj.product_name}: {shot.name}" if shot else plan_obj.product_name
        by_shot.setdefault(shot_no, []).extend(_ingest(plan_obj.slug, filename, desc))

    # Rotate through a shot's clips so two scenes on the same shot don't repeat
    # the exact same moment.
    overrides: dict[int, str] = {}
    used: dict[int, int] = {}
    for sc in vs.scenes:
        clips = by_shot.get(sc.shot_index) or []
        if clips:
            n = used.get(sc.shot_index, 0)
            overrides[sc.index] = clips[n % len(clips)]
            used[sc.shot_index] = n + 1

    script = Script(
        topic=plan_obj.product_name, slug=f"{plan_obj.slug[:40]}-ad",
        scenes=[Scene(index=s.index, image_prompt=s.visual_description,
                      narration=s.narration, motion_prompt="", hero=False)
                for s in vs.scenes],
        youtube_title=vs.youtube_title, youtube_description=vs.youtube_description,
        tiktok_caption=vs.tiktok_caption, x_caption=vs.x_caption, hashtags=vs.hashtags,
    )
    video = state.Video(script.slug)
    vid = f"{video.date}-{script.slug}"
    # A re-run must re-voice the new script, not reuse last run's audio files.
    old = config.OUTPUT / vid
    if old.exists() and old.parent == config.OUTPUT:
        shutil.rmtree(old, ignore_errors=True)

    produce.make(plan_obj.product_name, script=script, on_stage=say, clip_overrides=overrides)
    log(f"video ad ready: {vid} ({len(overrides)}/{len(vs.scenes)} scenes on your footage)")
    return vid
