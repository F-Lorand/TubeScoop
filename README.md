# 🍨 TubeScoop

[![GitHub](https://img.shields.io/badge/GitHub-F--Lorand/TubeScoop-89b4fa?logo=github)](https://github.com/F-Lorand/TubeScoop)
[![License](https://img.shields.io/badge/license-MIT-brightgreen)](LICENSE)
![Status](https://img.shields.io/badge/status-working-brightgreen)

A dead-simple GUI for downloading audio/video from YouTube and hundreds of other sites (YouTube, Vimeo, Twitch, TikTok, SoundCloud, Bandcamp, and more).

No terminal needed. Paste a link, pick a format, click **Scoop it!**

> I built this so that my kids could get music without having to download sketchy software, and now I'm sharing it with the world! 🍨

**[⬇️ Download for Windows](https://github.com/F-Lorand/TubeScoop/releases/latest)** – no Python required.

---

## Quick Start

```bash
pip install yt-dlp && curl -sLO https://raw.githubusercontent.com/F-Lorand/TubeScoop/main/yt_dlp_gui.py && python3 yt_dlp_gui.py
```

## Features

- **Scoop MP3** from any video URL or playlist
- Scoop best-quality audio (OPUS/M4A) or best-quality video (MP4)
- **Playlist support** — processes every video in a playlist and extracts audio
- Pick a range: scoop items 3–8 of a 50-video playlist
- Fully **self-contained** — auto-downloads ffmpeg if missing (needed for MP3 conversion)
- **Auto-updates** — checks for yt-dlp updates before every scoop
- **Manual update button** — "🔄 Check for Updates" lets you force a check anytime
- Embed thumbnail & metadata in MP3 files
- **+Folder button** — create new sub-folders right from the app
- Simple, teen-friendly interface — paste URL, pick format, scoop

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

### 🪟 Windows: Download the latest release

Grab **[TubeScoop.exe](https://github.com/F-Lorand/TubeScoop/releases/latest)** from the latest release — **no Python needed.** Just download, unzip, and double-click.

[![Latest Release](https://img.shields.io/github/v/release/F-Lorand/TubeScoop?label=latest&color=89b4fa)](https://github.com/F-Lorand/TubeScoop/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/F-Lorand/TubeScoop/total?color=cba6f7)](https://github.com/F-Lorand/TubeScoop/releases)

### 🐧 Mac / Linux: Run from Source

```bash
pip install yt-dlp
python3 yt_dlp_gui.py
```

### 🔧 Build from Source (developers)

To build your own `TubeScoop.exe` from the source code:

```bash
python build_portable.py
```

This creates a standalone executable in `dist/` that includes everything — yt-dlp and ffmpeg auto-download on first run.

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