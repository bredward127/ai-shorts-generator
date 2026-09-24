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
from .ad_models import AdPlan
from .util import log, slugify, step

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


# --- stage 1: plan --------------------------------------------------------------
def plan(description: str, audience: str, platform: str = "Instagram/Facebook feed (4:5)") -> AdPlan:
    """Generate the messaging brief + shot list via Claude. Requires ANTHROPIC_API_KEY."""
    step("Planning ad")
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("Add your Anthropic API key in Settings first — the ad planner needs it "
                            "to write the messaging brief and shot list.")

    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
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
        "window to the side, no direct sun' is what they need."
    )
    user = f"Product: {description}\nAudience for this ad: {audience}\nPlatform: {platform}"

    schema = AdPlan.model_json_schema()
    tool = {"name": "write_ad_plan", "description": "Submit the finished ad plan.",
            "input_schema": schema}
    resp = client.messages.create(
        model=config.CLAUDE_SCRIPT_MODEL,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
        tools=[tool],
        tool_choice={"type": "tool", "name": "write_ad_plan"},
    )
    tool_use = next(b for b in resp.content if b.type == "tool_use")
    result = AdPlan(**tool_use.input)
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
