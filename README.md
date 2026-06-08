# 🍨 TubeScoop

[![GitHub](https://img.shields.io/badge/GitHub-F--Lorand/TubeScoop-89b4fa?logo=github)](https://github.com/F-Lorand/TubeScoop)
[![License](https://img.shields.io/badge/license-MIT-brightgreen)](LICENSE)
![Status](https://img.shields.io/badge/status-working-brightgreen)

A dead-simple GUI for downloading audio/video from YouTube and hundreds of other sites (YouTube, Vimeo, Twitch, TikTok, SoundCloud, Bandcamp, and more).

No terminal needed. Paste a link, pick a format, click **Scoop it!**

---

## One-Line Install

```bash
pip install yt-dlp && curl -sLO https://raw.githubusercontent.com/F-Lorand/TubeScoop/main/yt_dlp_gui.py && python3 yt_dlp_gui.py
```

Or grab the **[latest portable release](https://github.com/F-Lorand/TubeScoop/releases/latest)** — no Python needed.

## Features

- **Scoop MP3** from any video URL or playlist
- Scoop best-quality audio (OPUS/M4A) or best-quality video (MP4)
- **Playlist support** — processes every video in a playlist and extracts audio
- Pick a range: scoop items 3–8 of a 50-video playlist
- Fully **self-contained** — auto-downloads ffmpeg if missing (needed for MP3 conversion)
- **Auto-updates yt-dlp** — checks for updates before every scoop
- **Manual update button** — "🔄 Update yt-dlp" lets you force a check anytime
- Embed thumbnail & metadata in MP3 files
- **+Folder button** — create new sub-folders right from the app
- Simple, teen-friendly interface — paste URL, pick format, scoot

## How to Use

1. **Paste a URL** — YouTube, SoundCloud, whatever
2. **Pick a format**
   - **MP3 Audio** (recommended) — extracts audio as MP3 with embedded cover art
   - **Best Audio** — highest quality audio (could be OPUS, M4A, etc.)
   - **Best Video** — downloads the best video + audio as MP4
3. **Set a folder** (default: `~/Downloads/TubeScoop`)
4. **Click Scoop it!** — watch progress in real-time

### Playlists

Paste a playlist URL and TubeScoop will download every video. To get only a subset, fill in the **Items** box:
- Leave blank → all videos
- `1` to `5` → items 1 through 5
- `3` (start) to blank → items 3 to the end

## Installation

### Option 1: Run from Source (any OS with Python)

```bash
pip install yt-dlp
python3 yt_dlp_gui.py
```

### Option 2: Portable Build (no Python needed)

```bash
python build_portable.py
```

This creates a standalone `TubeScoop` executable (or `TubeScoop.exe` on Windows) in the `dist/` folder. It includes everything — yt-dlp and ffmpeg auto-download on first run.

**To distribute:** just zip the `dist/TubeScoop` folder (or the single .exe) and share it. Recipients don't need Python or any dependencies.

## Dependencies

- **Python 3.8+** (to run from source) — or nothing (portable build)
- **yt-dlp** — auto-installed or bundled
- **ffmpeg** — auto-downloaded on first MP3 download (static build)
- **tkinter** — included with Python on all platforms

## Project Structure

```
TubeScoop/
├── yt_dlp_gui.py        # The application (1143 lines, heavily commented)
├── build_portable.py     # Creates standalone executable
├── TubeScoop.spec        # PyInstaller spec for portable builds
├── logo.svg              # Ice cream logo 🍨
├── requirements.txt      # Python dependencies
├── launcher.sh           # One-click launch script
└── README.md             # This file
```

## Tips

- **MP3 quality:** TubeScoop uses best quality (`-aq 0` = ~320kbps VBR). Resulting files are large but pristine.
- **Playlist URLs:** Just paste the playlist URL. TubeScoop detects it automatically.
- **Slow download?** YouTube throttles non-browser downloads. Use the "Best Audio" format for smaller, faster downloads.
- **Embedded cover art:** MP3s get the video thumbnail embedded as album art.

## The Logo 🍨

The icon is a strawberry ice cream scoop with chocolate chips, melty drips, and a cherry on top — because you *scoop* the good stuff out of the web.