# AI Shorts Generator — Automated Short-Form Video Pipeline

> Turn a single topic into a finished, captioned vertical video for **YouTube Shorts, TikTok, and Instagram Reels** — script, AI visuals, voiceover, karaoke captions, music, and an optional watermark, fully automated.

**AI Shorts Generator** is an open-source, faceless short-form video maker. Give it a topic (or let it pick one) and it writes the script, generates the visuals, narrates it, burns in word-by-word captions, lays a music bed, and exports a ready-to-post `1080×1920` MP4 with per-platform titles, descriptions, and hashtags — plus a local review dashboard to preview and publish.

It works **two ways**, and you can mix them per video:

- 🎨 **Generate with AI** — cinematic images via **Flux** and motion clips via **Wan** on [fal.ai](https://fal.ai).
- 🎞️ **Pull from a clip library** — free real stock footage from **Pexels / Pixabay**, plus a reusable semantic library so you generate a shot once and reuse it forever (**match-then-generate**).

> 🛠️ *A weekend project, shared openly in case it's useful to you too. Fork it, break it, build on it.*

<p align="center">
  <img alt="MIT License" src="https://img.shields.io/badge/license-MIT-blue.svg">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue.svg">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg">
  <img alt="PRs Welcome" src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg">
</p>

---

## ✨ Features

- **Topic → finished video**, end to end, in one command.
- **Two visual modes:** AI generation (fal Flux + Wan) and/or free stock footage (Pexels/Pixabay).
- **Reusable clip library** with semantic matching — reuse a good shot across videos instead of paying to regenerate it.
- **AI voiceover** (OpenAI `gpt-4o-mini-tts`, or clone your own voice via fal.ai/ElevenLabs) with a tunable, punchy delivery.
- **Script writer: OpenAI or Claude** — pick either from the dashboard's Settings page.
- **In-dashboard Settings page** — add/rotate all API keys from a form, no `.env` editing needed.
- **Word-by-word karaoke captions** auto-aligned with `faster-whisper`.
- **Music bed** with automatic ducking under the voice.
- **Optional watermark** (your logo + disclaimer) and an **optional branded outro / end card**.
- **Per-platform metadata** — YouTube title + description, TikTok caption, X caption, and hashtags.
- **Batch mode** — generate a week of content from a topic backlog.
- **Local review dashboard** (Flask) — preview, swap clips, pick music, copy captions, download.
- **Niche-agnostic** — set `CONTENT_NICHE` for any subject (finance, fitness, tech, motivation…), or stay purely topic-driven, and swap the writer's whole voice with **prompt presets**.
- **Graceful degradation** — missing an API key or a GPU? The pipeline falls back instead of crashing.

## 🧠 How it works

```
topic ─▶ script (OpenAI, structured JSON)
      ─▶ visuals:  match clip library ──hit──▶ reuse clip
                                     └─miss─▶ generate (Flux image ─▶ Wan motion) ─▶ add to library
      ─▶ voiceover (gpt-4o-mini-tts)
      ─▶ captions (faster-whisper, word-level)
      ─▶ assemble (ffmpeg): Ken Burns / motion + music + watermark + outro
      ─▶ output/{date}-{slug}/final.mp4  +  per-platform titles/descriptions/hashtags
```

Each scene is a cinematic moving image; the only on-screen text is the karaoke captions, so the **voice carries the message**. Output lands in `output/{date}-{slug}/final.mp4` (1080×1920) alongside a `script.json` with all the platform copy.

> 🪟 **New to the terminal / on Windows?** See [`WINDOWS_SETUP.md`](WINDOWS_SETUP.md) for
> complete step-by-step instructions, including how to add API keys from the
> dashboard's **Settings** page instead of editing `.env` by hand.

## 🚀 Quickstart

**Prerequisites:** Python 3.10+ and [FFmpeg](https://ffmpeg.org/download.html) on your `PATH`.

```bash
git clone https://github.com/AbdullahNaveed/ai-shorts-generator.git
cd ai-shorts-generator

python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

pip install -r requirements.txt
python -m playwright install chromium      # for crisp HTML-rendered overlays

cp .env.example .env                        # then add your API keys
python run.py setup                         # one-time: Chromium + overlays
```

Add at least an `OPENAI_API_KEY` to `.env`. Add `FAL_KEY` for AI visuals and/or a free `PEXELS_API_KEY` for stock footage. (No keys at all? The pipeline still runs in an offline smoke-test mode with a sample script and silent timing.)

```bash
python run.py make "why your mornings decide the rest of your day"
# → output/2026-06-24-why-your-mornings.../final.mp4
```

## 🎬 Usage

```bash
python run.py make ["topic"]     # one video on a topic (or auto-pick if omitted)
python run.py batch 7            # a week's worth from data/topics.txt
python run.py topics import      # load the backlog from data/topics.txt
python run.py fetch-library 20   # pull FREE Pexels/Pixabay stock into the library
python run.py gen-library 10     # AI-generate library clips from library/inventory.csv (fal)
python run.py library-stats      # show library counts / usage
python run.py list               # list generated videos
python run.py serve              # open the review dashboard at http://127.0.0.1:5000
```

On Windows you can also double-click **`start.bat`** to launch the dashboard and **`stop.bat`** to shut it down.

### The review dashboard

`python run.py serve` opens a local web app where you can:

- write/approve/regenerate a script with your own notes,
- **preview which library clip each scene will use and swap it**,
- fetch stock or AI-generate new clips into the library,
- fit a music track over a video and adjust its volume,
- copy the per-platform caption + hashtags and download the MP4.

## 🎨 Two ways to get footage

| Mode | How | Cost | Set in `.env` |
|---|---|---|---|
| **Free Ken Burns** | AI/stock still + zoom/pan motion | free motion | `ANIMATE=none` (default) |
| **Free stock footage** | Pull real clips from Pexels/Pixabay | free | `PEXELS_API_KEY=...` |
| **AI images** | Flux stills via fal.ai | ~$0.025 / image | `IMAGE_BACKEND=fal` |
| **AI motion** | Wan image-to-video via fal.ai | ~$0.15 / clip | `ANIMATE=all` |
| **Local images** | SDXL-Turbo on your GPU | free | `IMAGE_BACKEND=local` (+ `requirements-gpu.txt`) |

The **clip library** ties it together: every generated/fetched clip is embedded and cataloged, so the next time a scene is similar enough it **reuses an existing clip** instead of paying to make a new one (tune `MATCH_THRESHOLD`).

## 💧 Watermark & outro

- **Watermark** (on by default): drop a square `assets/logo/logo.png` and it's overlaid bottom-right on every video; add `BRAND_DISCLAIMER=` for a footer line. Set `WATERMARK=false` to disable. With no logo and no disclaimer, nothing is stamped.
- **Outro / end card** (off by default): set `OUTRO=true` with your `BRAND_NAME`, `BRAND_URL`, `BRAND_TAGLINE`, and `logo.png` to stitch a 3-second branded end card (with a spoken call-to-action) onto every video.

## ⚙️ Configuration

Everything is environment-driven — see [`.env.example`](.env.example) for the full list. Highlights:

| Variable | Default | What it does |
|---|---|---|
| `OPENAI_API_KEY` | – | Script, voiceover, captions alignment, embeddings |
| `FAL_KEY` | – | AI images (Flux) + AI motion (Wan) |
| `PEXELS_API_KEY` / `PIXABAY_API_KEY` | – | Free stock footage |
| `IMAGE_BACKEND` | `fal` | `fal` (Flux) or `local` (SDXL on GPU) |
| `ANIMATE` | `none` | `none` (free Ken Burns), `all`, or `N` |
| `CONTENT_NICHE` | – | Focus the writer (e.g. `personal finance`) |
| `SCRIPT_PROMPT` | – | Swap in a custom writer preset from `prompts/presets/` |
| `TTS_VOICE` | `onyx` | OpenAI TTS voice |
| `WHISPER_DEVICE` | `cpu` | `cpu` or `cuda` for captions |
| `WATERMARK` / `OUTRO` | `true` / `false` | Toggle the overlays |
| `TARGET_SECONDS` | `20` | Spoken length target |

Deeper defaults (palette, timings, models, caption styling) live in [`pipeline/config.py`](pipeline/config.py).

### ✍️ Custom script presets

The scriptwriter's persona lives in [`prompts/scriptgen_system.md`](prompts/scriptgen_system.md). Want a different voice or framework? Drop a Markdown file in [`prompts/presets/`](prompts/presets/) and select it by setting `SCRIPT_PROMPT` in `.env` (the filename, without `.md`). One generic example ships there — copy it, make it yours, and switch presets per run. `CONTENT_NICHE` layers a subject focus on top of whichever preset is active.

## 🗂️ Project layout

```
run.py              CLI orchestrator
pipeline/           config, models, scriptgen, images, animate, stock,
                    library, match, voice, captions, assemble, cards, outro
dashboard/          Flask review UI (app.py + templates)
templates/          HTML/CSS for the watermark + outro overlays
prompts/            scriptwriter system prompt + presets/ (swap the writer's voice)
assets/             fonts, your logo, music, generated brand overlays
library/            clip catalog (index.db) + clips/ + images/ + inventory CSVs
data/topics.txt     your topic backlog
output/             generated videos
```

## 💰 Cost per video (rough)

| Setup | What | Approx |
|---|---|---|
| Script + voice + captions only | OpenAI text + TTS | **~$0.02** |
| + free stock or local SDXL stills | Pexels / GPU | ~$0.02 |
| + Flux AI images (5 scenes) | fal images | ~$0.15 |
| + Wan AI motion (5 scenes) | fal motion | ~$0.75 |

Start cheap (`ANIMATE=none`, stock footage) and turn the dials up where it matters.

## ❓ FAQ

**Do I need a GPU?** No. Use `IMAGE_BACKEND=fal` and `WHISPER_DEVICE=cpu`. A GPU only helps for free local SDXL images and faster captions.

**Can I run it 100% free?** Mostly — OpenAI text/TTS is cents per video, and stock footage + Ken Burns motion are free. AI images/motion are the only paid pieces, and they're opt-in.

**Is auto-posting included?** No — you review and post manually (the dashboard makes it one click to grab captions + the MP4). A publishing backend is a welcome PR.

**What content niche is it for?** Any. Set `CONTENT_NICHE` or just pass topics. The bundled examples are niche-neutral.

## 🤝 Contributing

This started as a weekend project and is shared as-is for anyone to use, fork, or build on. Issues and PRs are welcome — auto-posting backends, new image/i2v models, extra stock sources, and caption styles are all great starting points.

Want to contribute, collaborate, or just say hi? Reach out on **[LinkedIn](https://www.linkedin.com/in/abdullahnaveed0007/)**.

## 📄 License

[MIT](LICENSE) © AbdullahNaveed. Bundled fonts (Inter, Sora) are under the SIL Open Font License — see [`assets/fonts/README.md`](assets/fonts/README.md). You are responsible for the licensing of any stock footage, music, or AI-generated media you produce or redistribute.

---

<sub>Keywords: AI video generator · faceless video generator · short-form video automation · YouTube Shorts generator · TikTok video maker · Instagram Reels automation · text-to-video · AI voiceover · auto captions · fal.ai · Flux · Wan · Stable Diffusion · Pexels stock footage · Python content pipeline.</sub>
