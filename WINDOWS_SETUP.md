# Running AI Shorts Generator on Windows — complete beginner steps

Follow these in order. Every step is something to click or type — nothing is assumed.

## 1. Install Python

1. Open your web browser and go to **https://www.python.org/downloads/**
2. Click the big yellow **"Download Python"** button.
3. Once it's downloaded (it'll be in your **Downloads** folder, something like
   `python-3.12.x-amd64.exe`), double-click it to run it.
4. On the very first install screen, **check the box at the bottom that says
   "Add python.exe to PATH"** before clicking Install. This step is easy to
   miss and everything below depends on it.
5. Click **Install Now**, wait for it to finish, then click **Close**.

## 2. Install FFmpeg

1. Go to **https://www.gyan.dev/ffmpeg/builds/** in your browser.
2. Under "release builds," click **ffmpeg-release-essentials.zip** to download it.
3. Find the zip in your **Downloads** folder, right-click it, and choose
   **Extract All...**, then **Extract**.
4. You'll get a folder like `ffmpeg-7.x-essentials_build`. Rename it to just
   `ffmpeg` and drag/move that whole folder to `C:\ffmpeg` (so the path is
   `C:\ffmpeg\bin\ffmpeg.exe`).
5. Add it to your PATH:
   - Click the **Start menu**, type `env`, and open **"Edit the system environment variables."**
   - Click the **"Environment Variables..."** button.
   - Under the top box ("User variables"), click **Path**, then **Edit...**
   - Click **New**, type `C:\ffmpeg\bin`, press Enter.
   - Click **OK** on all three windows to close them.
6. Close any open terminal/PowerShell windows so the change takes effect.

## 3. Download the project

1. Go to the project's GitHub page in your browser.
2. Click the green **"Code"** button, then **"Download ZIP."**
3. It lands in your **Downloads** folder as something like
   `ai-shorts-generator-main.zip`.
4. Right-click it → **Extract All...** → **Extract.** You'll get a folder,
   e.g. `Downloads\ai-shorts-generator-main`.

## 4. Open a terminal in that folder

1. Open the extracted folder in File Explorer (so you can see files like
   `run.py` and `README.md` inside it).
2. Click once on the address bar at the top of the File Explorer window
   (where the folder path is shown), type `cmd`, and press **Enter.**
   A black terminal window opens, already "in" that folder.
   - (If that doesn't work: Start menu → type `cmd` → open **Command Prompt**,
     then type `cd ` followed by a space, drag the folder from File Explorer
     into the terminal window to paste its path, and press Enter.)

Every command below is typed into that terminal window, one at a time,
pressing **Enter** after each.

## 5. Create a virtual environment and install everything

```
python -m venv .venv
.venv\Scripts\activate
```

Your terminal prompt should now start with `(.venv)`. Then:

```
pip install -r requirements.txt
python -m playwright install chromium
```

This installs all the Python packages the project needs (this can take a
few minutes — that's normal).

## 6. Start the app

```
python run.py serve
```

You should see a message like `Shorts Studio -> http://127.0.0.1:5000`.
Open your browser and go to **http://127.0.0.1:5000** — the dashboard loads.

Leave this terminal window open while you use the app; closing it stops the
app. To stop it on purpose, click into the terminal window and press
**Ctrl+C**.

## 7. Add your API keys — no file editing required

1. In the dashboard, click **Settings** in the top nav bar.
2. Paste in the keys you already have:
   - **Anthropic API key** (for Claude to write scripts) — also set
     **Script writer → Provider** to **Claude (Anthropic)**.
   - **fal.ai key** (for AI images/motion).
   - **Pexels key** (for free stock footage).
3. For voice: either pick an **OpenAI voice** from the dropdown (needs an
   OpenAI key), or scroll to **"Clone your own voice"** — drop in a clear
   10–30 second audio recording, leave the dropdown on **"via fal.ai"**
   (this reuses the fal key you already pasted in above — no extra
   account needed), give it a name, and click **Clone voice**.
4. Click **Save settings** at the bottom. That's it — no `.env` file to
   open or edit by hand. (Behind the scenes it writes one for you in the
   project folder, but you never need to touch it.)

## 8. Make your first video

1. Click **Create** in the top nav.
2. Type a topic (or leave it blank to let it pick one) and follow the
   on-screen steps: write the script, review it, produce the video.
3. Once it's done, find it under **Videos** on the home page to preview,
   grab captions/hashtags, and download the MP4.

## Advertising a product (the Ad Planner)

Separate from the video pipeline, this dashboard also has an **Ads** tab that
writes ad copy and a photo shot list for anything you want to sell:

1. Add your **Anthropic API key** in Settings (Script writer section) — the ad
   planner uses Claude to write the messaging brief and shot list.
2. Click **Ads** in the nav bar, describe the product, pick an audience and
   platform, click **Plan the ad**. You'll get a messaging brief and 2-4 shots,
   each with a labeled diagram showing camera angle, framing, and lighting —
   made for someone who isn't a photographer.
3. Take the photos it asks for (or upload one composite/collage photo and it's
   split into individual shots automatically), upload them on the ad's page,
   pick 1-3 in order (first = hero image), click **Assemble the ad**.
4. Download the finished ad PNG.

## Coming back later

Every time you want to use it again:

1. Open the project folder, click the address bar, type `cmd`, press Enter
   (same as step 4).
2. Run:
   ```
   .venv\Scripts\activate
   python run.py serve
   ```
3. Go to **http://127.0.0.1:5000** in your browser.

(Or just double-click **`start.bat`** inside the project folder — it does
the same thing. Double-click **`stop.bat`** to shut it down.)

## About hosting this online (Vercel, etc.)

This app is built to run **on your own computer**, not as a hosted website.
It calls `ffmpeg` and other tools that only work on a machine with them
installed and with disk space to write video files to — a serverless host
like Vercel doesn't provide either, which is why deploying there fails.
If you later want it reachable from anywhere (not just your PC), that needs
a different kind of host (a small always-on server, e.g. Railway, Render, or
Fly.io) — ask and I'll walk you through that separately; it's a different
setup from what's above.
