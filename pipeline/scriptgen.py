"""Topic -> validated image-first scene JSON via OpenAI structured outputs.

Niche-agnostic: set CONTENT_NICHE in .env to focus the writer on a subject
(e.g. "personal finance", "fitness"), or leave it blank for purely topic-driven
scripts. Falls back to a bundled sample script when no OPENAI_API_KEY is set.
"""
from __future__ import annotations

from . import config
from .models import Script
from .util import log, slugify, step


def _sample_script(topic: str) -> Script:
    """Offline sample (no API key). Niche-neutral so it works for any project."""
    return Script(
        topic=topic,
        slug=slugify(topic),
        scenes=[
            dict(index=1,
                 image_prompt="extreme close-up of a person waking in dim morning light, eyes opening, hand reaching toward a phone on the nightstand, cinematic",
                 narration="The first thing you touch in the morning runs your whole day.",
                 motion_prompt="slow push in, soft light growing", hero=False),
            dict(index=2,
                 image_prompt="a person lying in bed bathed in cold blue phone glow, face tense, scrolling, dark room",
                 narration="Reach for the phone and you hand your focus to strangers.",
                 motion_prompt="subtle screen flicker, slow drift", hero=False),
            dict(index=3,
                 image_prompt="hands placing a phone face-down in another room on a wooden shelf, warm daylight through a window",
                 narration="So put it in another room before you sleep.",
                 motion_prompt="hand setting the phone down, light warming", hero=True),
            dict(index=4,
                 image_prompt="a person sitting calmly by a sunlit window with a glass of water and a notebook, unhurried, serene",
                 narration="Now the first hour is yours, not the algorithm's.",
                 motion_prompt="gentle morning haze, slow breathing", hero=False),
            dict(index=5,
                 image_prompt="wide shot of the same person stepping out a door into bright daylight, composed and clear, cinematic",
                 narration="Win the first hour and you've already won the day.",
                 motion_prompt="light blooming as the door opens", hero=False),
        ],
        youtube_title="Win the first hour, win the day #habits #shorts",
        youtube_description=(
            "The first thing you touch in the morning sets your focus for the day. "
            "One small change: keep the phone out of reach overnight."
        ),
        tiktok_caption="Put your phone in another room before bed. #productivity",
        x_caption="The first thing you touch in the morning runs your whole day.",
        hashtags=["productivity", "habits", "focus", "morningroutine",
                  "discipline", "selfimprovement"],
    )


def _load_system_prompt() -> str:
    """Load the scriptwriter system prompt. Set SCRIPT_PROMPT in .env to use a preset
    from prompts/presets/ (by name, with or without .md); otherwise the default
    prompts/scriptgen_system.md is used."""
    name = config.SCRIPT_PROMPT
    if name:
        for p in (config.PROMPTS / "presets" / name,
                  config.PROMPTS / "presets" / f"{name}.md",
                  config.PROMPTS / name,
                  config.PROMPTS / f"{name}.md"):
            if p.exists():
                log(f"script preset: {p.relative_to(config.PROMPTS).as_posix()}")
                return p.read_text(encoding="utf-8")
        log(f"SCRIPT_PROMPT='{name}' not found in prompts/presets — using default")
    return (config.PROMPTS / "scriptgen_system.md").read_text(encoding="utf-8")


def _build_prompts(topic: str, instruction: str, auto: bool) -> tuple[str, str]:
    from . import state

    system = _load_system_prompt()
    niche = config.CONTENT_NICHE
    if niche:
        system += f"\n\n# Your focus\nWrite specifically within this niche/subject: {niche}."

    covered = [v["topic"] for v in state.list_videos() if v.get("topic")][:40]
    covered_block = ("\n\nAlready covered (do NOT repeat these or their close "
                     "neighbors):\n- " + "\n- ".join(covered)) if covered else ""
    base = f"Target spoken length: ~{config.TARGET_SECONDS} seconds total.{covered_block}"

    if auto:
        focus = f"{niche} " if niche else ""
        user = (f"Choose the single best fresh, specific {focus}angle to make next — "
                "something genuinely useful that fills a gap in what's already been "
                "covered. Put your chosen angle in the 'topic' field, then write the "
                f"short.\n\n{base}")
    else:
        user = (f"Topic for this short: {topic}\nMake it fresh and specific; if this "
                f"overlaps something already covered, find a new angle on it.\n\n{base}")
    if instruction:
        user += f"\n\nIMPORTANT revision note from the creator: {instruction}"
    return system, user


def _generate_openai(system: str, user: str) -> Script:
    from openai import OpenAI

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    kwargs = dict(
        model=config.SCRIPT_MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        response_format=Script,
    )
    # GPT-5 / reasoning models only allow the default temperature.
    if not config.SCRIPT_MODEL.startswith(("gpt-5", "o1", "o3", "o4")):
        kwargs["temperature"] = 0.9
    completion = client.beta.chat.completions.parse(**kwargs)
    return completion.choices[0].message.parsed


def _generate_claude(system: str, user: str) -> Script:
    """Same job as _generate_openai, but via the Anthropic API. Claude has no
    built-in structured-output mode, so we hand it the Script schema as a tool
    and force a call to it, then validate the tool input with the same
    pydantic model."""
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    schema = Script.model_json_schema()
    tool = {"name": "write_short_script", "description":
            "Submit the finished short-form video script.", "input_schema": schema}
    resp = client.messages.create(
        model=config.CLAUDE_SCRIPT_MODEL,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
        tools=[tool],
        tool_choice={"type": "tool", "name": "write_short_script"},
    )
    tool_use = next(b for b in resp.content if b.type == "tool_use")
    return Script(**tool_use.input)


def generate(topic: str = "", instruction: str = "") -> Script:
    auto = not (topic or "").strip()
    step(f"Scriptgen — {'(auto topic)' if auto else topic!r}")

    use_claude = config.LLM_PROVIDER == "claude" and config.ANTHROPIC_API_KEY
    if not use_claude and not config.OPENAI_API_KEY:
        log("no script-writer API key configured — using offline sample script")
        return _sample_script(topic or config.DEFAULT_TOPIC)

    system, user = _build_prompts(topic, instruction, auto)
    script = _generate_claude(system, user) if use_claude else _generate_openai(system, user)
    script.slug = slugify(script.slug or topic)
    log(f"{len(script.scenes)} scenes · slug={script.slug} · provider="
        f"{'claude' if use_claude else 'openai'}")
    return script
