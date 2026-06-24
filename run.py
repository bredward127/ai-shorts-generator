"""AI short-form video pipeline — CLI (clip library + match-then-generate).

Usage:
  python run.py setup                 one-time: install Chromium, build overlays
  python run.py fetch-library [N]     fill the library with FREE Pexels/Pixabay footage (N = limit)
  python run.py gen-library [N]       AI-generate library clips from inventory.csv (fal)
  python run.py library-stats         show library counts / usage
  python run.py make ["topic"]        generate one short (reuses library, generates on miss)
  python run.py batch N               generate N shorts from the backlog
  python run.py topics import|add ... manage the topic backlog
  python run.py build-outro [--force] (re)build the optional branded outro clip
  python run.py build-watermark       (re)build the watermark overlay
  python run.py list                  list generated videos
  python run.py serve                 launch the review/workflow dashboard
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from pipeline import cards, config, library, state
from pipeline.produce import make
from pipeline.util import log, step


def batch(n: int) -> None:
    for i in range(n):
        step(f"=== video {i+1}/{n} ===")
        final = make(None)
        print(f"[DONE] {final}")


def setup() -> None:
    step("Setup")
    import subprocess
    log("installing Playwright Chromium ...")
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
    if config.LOGO_PNG.exists():
        cards.render_watermark()
    else:
        log(f"no logo at {config.LOGO_PNG} — drop a square PNG there for a watermark "
            "(or set WATERMARK=false / a BRAND_DISCLAIMER in .env).")
    if config.ENABLE_OUTRO:
        from pipeline.outro import build_outro
        build_outro(force=True)
    log("setup done.")


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else "make"
    if cmd == "setup":
        setup()
    elif cmd == "fetch-library":
        from pipeline.stock import fetch_library
        fetch_library(limit=int(args[1]) if len(args) > 1 else None)
    elif cmd == "gen-library":
        from pipeline.generate_library import generate
        generate(limit=int(args[1]) if len(args) > 1 else None)
    elif cmd == "library-stats":
        print(library.stats())
    elif cmd == "make":
        final = make(args[1] if len(args) > 1 else None)
        print(f"\n[DONE] {final}")
    elif cmd == "batch":
        batch(int(args[1]) if len(args) > 1 else 1)
    elif cmd == "build-outro":
        from pipeline.outro import build_outro
        build_outro(force="--force" in args)
    elif cmd == "build-watermark":
        cards.render_watermark()
    elif cmd == "topics" and len(args) > 1 and args[1] == "add":
        print(f"added {state.add_topics(args[2:])} topics")
    elif cmd == "topics" and len(args) > 1 and args[1] == "import":
        f = config.DATA / "topics.txt"
        lines = [ln.strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
        print(f"imported {state.add_topics(lines)} topics from {f.name}")
    elif cmd == "list":
        for v in state.list_videos():
            print(f"{v['date']}  {v['status']:10}  {v['slug']}")
    elif cmd == "serve":
        from dashboard.app import run_server
        run_server()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
