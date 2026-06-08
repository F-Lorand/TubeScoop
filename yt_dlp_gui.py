#!/usr/bin/env python3
"""
TubeScoop — simple GUI frontend for yt-dlp.
Downloads audio/video from YouTube and hundreds of other sites.

HOW IT WORKS (for the curious):
─────────────────────────────────
This is a tkinter (GUI toolkit built into Python) app that wraps the
command-line tool yt-dlp. When you click "Scoop it!", it:

  1. Checks that yt-dlp is installed and up to date
  2. Downloads ffmpeg if missing (needed to convert audio to MP3)
  3. Spawns yt-dlp as a background process with your chosen options
  4. Reads yt-dlp's text output line by line to get progress %
  5. Pipes that progress into the UI via a thread-safe queue
  6. Reports "Done!" when the process exits cleanly

Everything runs on Python's standard library — no external frameworks.
"""


# ══════════════════════════════════════════════════════════════════════
#  BOOTSTRAP: X11 threading fix (Linux only, for PyInstaller builds)
# ══════════════════════════════════════════════════════════════════════
#
# On some Linux distros, PyInstaller's bootloader calls XInitThreads()
# at the wrong time, causing a crash like:
#   "[xcb] Unknown sequence number while appending request"
#
# We preempt that by calling XInitThreads() ourselves before any Tk
# code runs. The env vars silence Tk deprecation warnings too.
#
import os
import ctypes

os.environ.setdefault("TCL_NO_DEPRECATED_WARNINGS", "1")
os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

# Try loading libX11 and initialising threading — if it fails (e.g.
# headless or Wayland), we just carry on silently.
try:
    xlib = ctypes.cdll.LoadLibrary("libX11.so.6")
    xlib.XInitThreads()
except Exception:
    try:
        xlib = ctypes.cdll.LoadLibrary("libX11.so")
        xlib.XInitThreads()
    except Exception:
        pass
# ══════════════════════════════════════════════════════════════════════


import sys
import re               # Regular expressions — used to parse yt-dlp progress lines
import json              # (Reserved for future use — metadata handling)
import subprocess        # The heart of it — spawns yt-dlp as a child process
import threading         # Lets us run the download in the background so the GUI stays responsive
import queue             # Thread-safe message pipe between download worker and GUI
import time              # (Reserved for future use — rate limiting / retry delays)
import shutil            # Cross-platform "which" command — finds yt-dlp and ffmpeg on PATH
import urllib.request    # Downloads ffmpeg static binaries from GitHub / johnvansickle.com
import zipfile           # Extracts ffmpeg from ZIP archives (Windows & macOS)
import tarfile           # Extracts ffmpeg from .tar.xz archives (Linux)
import stat              # File permission constants — makes downloaded ffmpeg executable
import tkinter as tk     # The GUI framework — included with every Python install
from tkinter import ttk, filedialog, messagebox  # Themed widgets, file dialogs, popup messages

# Optional — font introspection; only used if you want to tweak fonts later
try:
    from tkinter import font as tkfont
except ImportError:
    tkfont = None


# ══════════════════════════════════════════════════════════════════════
#  RESOLVING FILE PATHS (when bundled by PyInstaller)
# ══════════════════════════════════════════════════════════════════════
#
# When this script is frozen into a standalone .exe by PyInstaller,
# files live inside a temporary _MEIPASS folder at runtime. This helper
# finds them whether we're running from source or from a frozen bundle.

def resource_path(rel_path):
    """
    Return the absolute path to a resource file.
    
    - Running from source (.py): returns path relative to this script
    - Running from PyInstaller bundle (.exe): returns path inside _MEIPASS
    
    Parameters
    ----------
    rel_path : str
        Relative path like "icon.ico" or "assets/logo.png"
    
    Returns
    -------
    str — absolute path to the resource
    """
    try:
        # PyInstaller creates a temp folder and stores its path in sys._MEIPASS
        base = sys._MEIPASS
    except AttributeError:
        # Normal Python execution — use the directory this script is in
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel_path)


# ══════════════════════════════════════════════════════════════════════
#  FFMPEG AUTO-DOWNLOAD
# ══════════════════════════════════════════════════════════════════════
#
# ffmpeg is required to convert downloaded audio streams to MP3
# (yt-dlp downloads webm/opus by default). Instead of asking the user
# to install it, we auto-download a static build for their OS.
#
# Static builds are self-contained executables that don't need any
# system libraries — they just work.
#
# Supported sources:
#   Linux:   johnvansickle.com  (static .tar.xz)
#   macOS:   evermeet.cx        (static .zip)
#   Windows: BtbN/FFmpeg-Builds on GitHub (static .zip)

# Where we store the downloaded ffmpeg binary — alongside the script/exe
FFMPEG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ffmpeg")


def _ffmpeg_binary():
    """
    Find the ffmpeg executable, checking bundled location first, then PATH.
    
    Returns
    -------
    str or None — absolute path to ffmpeg, or None if not found
    """
    # Step 1: look in our _ffmpeg/ folder (downloaded alongside the app)
    if sys.platform == "win32":
        name = "ffmpeg.exe"
    else:
        name = "ffmpeg"
    
    bundled = os.path.join(FFMPEG_DIR, name)
    if os.path.isfile(bundled):
        return bundled
    
    # Step 2: fall back to system PATH (user may have installed it)
    which = shutil.which("ffmpeg")
    if which:
        return which
    
    return None


def _download_ffmpeg(log_fn=print):
    """
    Download a static ffmpeg build into _ffmpeg/ directory.
    
    Picks the right URL per-platform (see sources above). Extracts the
    single binary and marks it executable.
    
    Parameters
    ----------
    log_fn : callable(str)
        Function to call with status messages (e.g. print or GUI log)
    
    Returns
    -------
    bool — True if ffmpeg is now available
    """
    # Already have it? Done.
    if _ffmpeg_binary():
        return True
    
    # Create the _ffmpeg/ folder
    os.makedirs(FFMPEG_DIR, exist_ok=True)
    
    if sys.platform == "win32":
        # ── Windows: BtbN static build ────────────────────────────
        url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        log_fn("Downloading ffmpeg (Windows build) …")
        try:
            zip_path = os.path.join(FFMPEG_DIR, "ffmpeg.zip")
            urllib.request.urlretrieve(url, zip_path)
            with zipfile.ZipFile(zip_path, "r") as z:
                for member in z.namelist():
                    if member.endswith("ffmpeg.exe"):
                        z.extract(member, FFMPEG_DIR)
                        src = os.path.join(FFMPEG_DIR, member)
                        dst = os.path.join(FFMPEG_DIR, "ffmpeg.exe")
                        if src != dst:
                            os.rename(src, dst)
                        break
            os.unlink(zip_path)  # Delete the zip after extraction
            # Clean up any leftover folder structure from the archive
            for root, dirs, files in os.walk(FFMPEG_DIR, topdown=False):
                for d in dirs:
                    try:
                        os.rmdir(os.path.join(root, d))
                    except OSError:
                        pass
            log_fn("ffmpeg downloaded.")
            return True
        except Exception as e:
            log_fn(f"ffmpeg download failed: {e}")
            return False
    
    elif sys.platform == "darwin":
        # ── macOS: evermeet.cx static build ──────────────────────
        url = "https://evermeet.cx/ffmpeg/ffmpeg-7.1.zip"
        log_fn("Downloading ffmpeg (macOS build) …")
        try:
            zip_path = os.path.join(FFMPEG_DIR, "ffmpeg.zip")
            urllib.request.urlretrieve(url, zip_path)
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extract("ffmpeg", FFMPEG_DIR)
            os.unlink(zip_path)
            os.chmod(os.path.join(FFMPEG_DIR, "ffmpeg"), 0o755)
            log_fn("ffmpeg downloaded.")
            return True
        except Exception as e:
            log_fn(f"ffmpeg download failed: {e}")
            return False
    
    else:
        # ── Linux: johnvansickle.com static build ────────────────
        url = "https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz"
        log_fn("Downloading ffmpeg (Linux static build) …")
        try:
            tbz_path = os.path.join(FFMPEG_DIR, "ffmpeg.tar.xz")
            urllib.request.urlretrieve(url, tbz_path)
            with tarfile.open(tbz_path, "r:xz") as t:
                for member in t.getmembers():
                    if member.name.endswith("ffmpeg"):
                        t.extract(member, FFMPEG_DIR)
                        src = os.path.join(FFMPEG_DIR, member.name)
                        dst = os.path.join(FFMPEG_DIR, "ffmpeg")
                        if src != dst:
                            os.rename(src, dst)
                        break
            os.unlink(tbz_path)  # Delete archive after extraction
            # Clean up empty folder tree from the tarball
            for root, dirs, files in os.walk(FFMPEG_DIR, topdown=False):
                for d in dirs:
                    try:
                        os.rmdir(os.path.join(root, d))
                    except OSError:
                        pass
            # Mark the binary as executable (Linux needs +x)
            fp = os.path.join(FFMPEG_DIR, "ffmpeg")
            if os.path.isfile(fp):
                st = os.stat(fp)
                os.chmod(fp, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            log_fn("ffmpeg downloaded.")
            return True
        except Exception as e:
            log_fn(f"ffmpeg download failed: {e}")
            return False


# ══════════════════════════════════════════════════════════════════════
#  YT-DLP: INSTALL & AUTO-UPDATE
# ══════════════════════════════════════════════════════════════════════
#
# yt-dlp changes frequently because YouTube (and other sites) tweak
# their APIs. We check for updates every time the user clicks Download.
# 
# Two update mechanisms (tried in order):
#   1. yt-dlp --update  — downloads a precompiled binary (fast, reliable)
#   2. pip install --upgrade yt-dlp — fallback for pip/system installs

def _ensure_ytdlp(log_fn=print):
    """
    Make sure yt-dlp is installed on this system AND running the latest version.
    
    If yt-dlp isn't found, installs via pip. If found, runs --update
    to check for a newer version.
    
    Parameters
    ----------
    log_fn : callable(str)
        Status logger (usually self._log_append from the GUI)
    
    Returns
    -------
    bool — True if yt-dlp is available and usable
    """
    # Try to locate yt-dlp on the system PATH
    found = shutil.which("yt-dlp")
    
    # ── Not installed? Install via pip ──
    if not found:
        log_fn("yt-dlp not found — installing via pip …")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "yt-dlp", "--quiet"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return shutil.which("yt-dlp") is not None
        except Exception as e:
            log_fn(f"yt-dlp install failed: {e}")
            return False

    # ── Already installed? Check for updates ──
    log_fn("📡  Checking for yt-dlp update …")
    try:
        # yt-dlp --update is the built-in self-updater (downloads a new binary)
        result = subprocess.run(
            [found, "--update"],
            capture_output=True, text=True, timeout=30,
        )
        out = (result.stdout + result.stderr).strip()
        
        if "Already up to date" in out:
            log_fn("✅  yt-dlp is already the latest version.")
        elif "Updated" in out or result.returncode == 0:
            log_fn("✅  yt-dlp updated to the latest version.")
            # The --update flag may replace the binary; re-resolve PATH
            found = shutil.which("yt-dlp") or found
        else:
            # --update may fail on pip-installed versions → try pip upgrade
            log_fn("⚠️  yt-dlp self-update unavailable — trying pip upgrade …")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp", "--quiet"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            log_fn("✅  yt-dlp upgraded via pip.")
    except Exception as e:
        # Timeout, network error, etc. — not critical, carry on
        log_fn(f"⚠️  yt-dlp update check failed: {e}")

    return shutil.which("yt-dlp") is not None


# ══════════════════════════════════════════════════════════════════════
#  DOWNLOAD WORKER (background thread)
# ══════════════════════════════════════════════════════════════════════
#
# This class runs yt-dlp in a subprocess and parses its text output
# to extract progress information. It runs on a daemon thread so it
# doesn't block the GUI.
#
# Communication back to the GUI happens through a queue.Queue — the
# worker puts (kind, data) tuples, and the main thread polls the queue
# every 100ms to update the progress bar and log.

class DownloadWorker:
    """Runs yt-dlp in a subprocess, parsing progress lines into a queue."""
    
    def __init__(self, url, out_dir, fmt, playlist_start, playlist_end, log_q):
        """
        Parameters
        ----------
        url : str
            Video or playlist URL to download
        out_dir : str
            Directory to save files in
        fmt : str
            Format key: "mp3", "best-audio", "best-video", or "best"
        playlist_start : int or None
            First playlist item to download (1-based, None = start)
        playlist_end : int or None
            Last playlist item to download (None = end)
        log_q : queue.Queue
            Thread-safe queue for (kind, data) messages to the GUI
        """
        self.url = url
        self.out_dir = out_dir
        self.fmt = fmt
        self.playlist_start = playlist_start
        self.playlist_end = playlist_end
        self.log_q = log_q      # queue.Queue for (type, data) messages
        self._proc = None       # subprocess.Popen handle
    
    def _log(self, kind, msg):
        """Send a message to the GUI thread via the queue."""
        self.log_q.put((kind, msg))
    
    def run(self):
        """
        This is the main entry point — called from the background thread.
        
        Builds the yt-dlp command line, spawns the process, reads
        stdout line by line, parses progress, and reports completion.
        """
        # ── Ensure ffmpeg is in PATH (needed for MP3 conversion) ──
        ff = _ffmpeg_binary()
        env = os.environ.copy()
        if ff:
            # Prepend ffmpeg's directory to PATH so yt-dlp can find it
            env["PATH"] = os.path.dirname(ff) + os.pathsep + env.get("PATH", "")
        
        # ── Build the yt-dlp command ─────────────────────────────
        cmd = ["yt-dlp", "--no-warnings", "--progress", "--newline"]
        
        # Output template: save files as "Title.ext" in the chosen folder
        cmd.extend(["-o", os.path.join(self.out_dir, "%(title)s.%(ext)s")])
        
        # ── Format selection ─────────────────────────────────────
        # These flags tell yt-dlp what quality/format to download.
        #
        #   -x           = extract audio (discard video stream)
        #   --audio-format = convert to this container
        #   -f           = format selection string (yt-dlp's syntax)
        #
        if self.fmt == "mp3":
            # Extract audio as high-quality MP3 (quality 0 = ~320kbps VBR)
            cmd.extend(["-x", "--audio-format", "mp3", "--audio-quality", "0",
                        "-f", "bestaudio/best"])
        elif self.fmt == "best-audio":
            # Best available audio (could be OPUS, M4A, etc.) — no conversion
            cmd.extend(["-x", "--audio-format", "best",
                        "-f", "bestaudio/best"])
        elif self.fmt == "best-video":
            # Best video + best audio, merged into MP4 container
            cmd.extend(["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"])
        else:  # "best" (default fallback)
            cmd.extend(["-f", "best"])
        
        # ── Playlist range ───────────────────────────────────────
        # If the user specified a subset of items, add range flags
        if self.playlist_start:
            cmd.extend(["--playlist-start", str(self.playlist_start)])
        if self.playlist_end:
            cmd.extend(["--playlist-end", str(self.playlist_end)])
        
        # ── Metadata for MP3 ─────────────────────────────────────
        # Embed video thumbnail as cover art + write metadata tags
        if self.fmt == "mp3":
            cmd.extend(["--embed-thumbnail", "--add-metadata"])
        
        # Finally, add the URL
        cmd.append(self.url)
        
        self._log("status", "starting")
        
        # ── Spawn yt-dlp as a subprocess ─────────────────────────
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, env=env,
            )
        except FileNotFoundError:
            self._log("error", "yt-dlp not found. Run: pip install yt-dlp")
            return
        
        # ── Parse yt-dlp's output line by line ───────────────────
        # yt-dlp prints progress lines like:
        #   [download]  45.2% of ~12.34MiB at 3.45MiB/s ETA 00:02
        #
        # We use three regexes to pull out the info we need:
        
        # Full progress line with percentage, size, speed, and ETA
        prog_re = re.compile(
            r"\[download\]\s+([\d.]+)%\s+of\s+~?([\d.]+)(KiB|MiB|GiB)"
            r" at\s+([\d.]+)(KiB|MiB)/s"
            r".*?ETA\s+([\d.:]+)",
        )
        
        # Simpler line — just the percentage (no speed/ETA)
        simple_prog = re.compile(r"\[download\]\s+([\d.]+)%")
        
        # Detects when a new file starts downloading
        title_re = re.compile(r"\[download\]\s+Destination:\s+(.+)")
        
        # Detects when audio extraction starts
        extract_re = re.compile(r"\[ExtractAudio\]\s+Destination:\s+(.+)")
        
        current_file = ""
        for line in self._proc.stdout:
            line = line.rstrip("\n")
            self._log("raw", line)  # Store the raw line for debugging
            
            # ── Detect current file being downloaded ─────────────
            m = title_re.search(line)
            if m:
                current_file = os.path.basename(m.group(1))
                self._log("file", current_file)
            m = extract_re.search(line)
            if m:
                current_file = os.path.basename(m.group(1))
                self._log("file", current_file)
            
            # ── Extract progress percentage ──────────────────────
            m = prog_re.search(line)
            if m:
                pct = float(m.group(1))
                self._log("progress", pct)
            else:
                m = simple_prog.search(line)
                if m:
                    pct = float(m.group(1))
                    self._log("progress", pct)
            
            # ── Detect completion of an individual file ──────────
            if "[download] 100%" in line or "[download] 100.0%" in line:
                self._log("progress", 100.0)
            if "has already been downloaded" in line:
                self._log("progress", 100.0)
            
            # ── Detect playlist item index ───────────────────────
            idx_re = re.search(r"\[download\] Downloading item\s+(\d+)", line)
            if idx_re:
                self._log("item", int(idx_re.group(1)))
        
        # ── Process finished — report result ─────────────────────
        self._proc.wait()
        if self._proc.returncode == 0:
            self._log("status", "done")
        else:
            self._log("status", "error")


# ══════════════════════════════════════════════════════════════════════
#  GUI APPLICATION
# ══════════════════════════════════════════════════════════════════════
#
# The main window is built with ttk (themed tkinter). It uses a dark
# colour scheme inspired by Catppuccin Mocha.
#
# LAYOUT (top to bottom):
#
#   🍨  TubeScoop                    ← header
#   [URL input        ]             ← paste link here
#   [MP3] [Best Audio] [Best Video]  ← format picker
#   Items: [1] to [5]  ☐ Embed thumbnail
#   Save to: [~/Downloads/…] [Browse] [+Folder]
#   [🍨 Scoop it!  ]              ← big download button
#   [🔄 Update yt-dlp] ✅ Up to date  ← update button
#   [████████████░░░░░]             ← progress bar
#   Ready                          ← status text
#   ┌─────────────────────────────┐
#   │ Progress log...             │  ← scrollable log area
#   │ ...                         │
#   └─────────────────────────────┘

class TubeScoopApp(ttk.Frame):
    """Main application window — contains all UI widgets and logic."""

    # ── Colour palette (Catppuccin Mocha-inspired) ────────────────
    BG = "#1e1e2e"      # Window background (dark base)
    FG = "#cdd6f4"      # Default text colour (off-white)
    ACCENT = "#89b4fa"  # Accent colour for buttons and headers (soft blue)
    SURFACE = "#313244" # Input fields and card backgrounds (slightly lighter)
    RED = "#f38ba8"     # Error / failure messages (soft red)
    GREEN = "#a6e3a1"   # Success messages (soft green)

    def __init__(self, root):
        """
        Set up the application.
        
        Parameters
        ----------
        root : tk.Tk
            The root Tk window that contains everything
        """
        super().__init__(root)
        self.root = root
        self._workers = []             # List of background workers (reserved for multi-download)
        self._download_thread = None   # Currently running download thread
        self._log_q = queue.Queue()    # Thread-safe queue from worker → GUI
        self._poll_id = None           # ID of the recurring UI poll timer
        
        self._setup_styles()           # Configure the dark colour theme
        self._build_ui()               # Create all the widgets
        self._start_poller()           # Start checking the message queue
    
    # ═══════════════════════════════════════════════════════════════
    #  STYLING — where the dark theme is defined
    # ═══════════════════════════════════════════════════════════════
    #
    # ttk uses "styles" instead of raw colour options. Think of them
    # like CSS classes — you define a style name, then apply it to
    # widgets with style="Header.TLabel".
    #
    # The "clam" theme is used as a base because it supports the most
    # customisation (unlike "default" or "alt").
    
    def _setup_styles(self):
        """Configure ttk styles for the dark theme."""
        style = ttk.Style(self)
        try:
            style.theme_use("clam")   # "clam" = most customisable theme
        except tk.TclError:
            pass  # If clam isn't available, fall back to whatever is
        
        # ── Global defaults (applied to all widgets) ─────────────
        style.configure(".", background=self.BG, foreground=self.FG,
                        fieldbackground=self.SURFACE, font=("Segoe UI", 10))
        
        # ── Layout containers ────────────────────────────────────
        style.configure("TFrame", background=self.BG)
        style.configure("TLabel", background=self.BG, foreground=self.FG)
        
        # ── Headers ──────────────────────────────────────────────
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"),
                        foreground=self.ACCENT)
        style.configure("Sub.TLabel", font=("Segoe UI", 9), foreground="#a6adc8")
        
        # ── Text input ───────────────────────────────────────────
        style.configure("TEntry", fieldbackground=self.SURFACE,
                        foreground=self.FG, insertcolor=self.FG,
                        borderwidth=0, padding=6)
        
        # ── Buttons ──────────────────────────────────────────────
        style.configure("TButton", background=self.ACCENT, foreground="#11111b",
                        borderwidth=0, padding=(10, 6), font=("Segoe UI", 10, "bold"))
        style.map("TButton",
                  background=[("active", "#74c7ec"), ("disabled", "#585b70")],
                  foreground=[("disabled", "#585b70")])
        
        # Secondary buttons (Browse, Update, New Folder) — more subtle
        style.configure("Browse.TButton", background=self.SURFACE,
                        foreground=self.FG, font=("Segoe UI", 9))
        style.map("Browse.TButton",
                  background=[("active", "#45475a")])
        
        # ── Status labels ────────────────────────────────────────
        style.configure("Status.TLabel", font=("Segoe UI", 9))
        style.configure("Green.TLabel", foreground=self.GREEN)
        style.configure("Red.TLabel", foreground=self.RED)
        
        # ── Progress bar ─────────────────────────────────────────
        style.configure("Accent.Horizontal.TProgressbar",
                        background=self.ACCENT, troughcolor=self.SURFACE,
                        borderwidth=0, thickness=12)
        
        # ── Checkboxes ───────────────────────────────────────────
        style.configure("TCheckbutton", background=self.BG, foreground=self.FG)
        style.map("TCheckbutton",
                  background=[("active", self.BG)],
                  foreground=[("active", self.FG)])
        
        # ── Group boxes (LabelFrames) ─────────────────────────────
        style.configure("TLabelframe", background=self.BG, foreground=self.FG,
                        bordercolor=self.SURFACE, lightcolor=self.SURFACE,
                        darkcolor=self.SURFACE)
        style.configure("TLabelframe.Label", background=self.BG, foreground=self.FG)
    
    # ═══════════════════════════════════════════════════════════════
    #  BUILD UI — creates every widget in the window
    # ═══════════════════════════════════════════════════════════════
    #
    # tkinter uses a "pack" layout manager (similar to stacking boxes).
    # side=tk.LEFT stacks horizontally, side=tk.TOP (the default)
    # stacks vertically. fill=tk.X stretches to fill available width.
    
    def _build_ui(self):
        """Create and arrange all widgets in the main window."""
        self.root.title("TubeScoop")
        self.root.configure(bg=self.BG)
        self.root.minsize(560, 520)   # Minimum window size
        self.root.resizable(True, True)  # Allow resizing
        
        # Windows only: try to set a custom taskbar icon
        try:
            if sys.platform == "win32":
                self.root.iconbitmap(default=resource_path("icon.ico"))
        except Exception:
            pass
        
        # The outer container (self = ttk.Frame) fills the whole window
        # with 20px of padding on every side
        self.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # ── Header row ───────────────────────────────────────────
        hdr = ttk.Label(self, text="🍨  TubeScoop", style="Header.TLabel")
        hdr.pack(anchor="w")
        sub = ttk.Label(self, text="Download audio / video from YouTube & hundreds more sites",
                        style="Sub.TLabel")
        sub.pack(anchor="w", pady=(0, 16))
        
        # ── URL input row ────────────────────────────────────────
        url_frame = ttk.Frame(self)
        url_frame.pack(fill=tk.X, pady=(0, 8))
        
        ttk.Label(url_frame, text="URL or Playlist URL:").pack(anchor="w")
        self.url_var = tk.StringVar()           # Holds the current URL text
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var)
        self.url_entry.pack(fill=tk.X, pady=(4, 0))
        self.url_entry.focus()                  # Put keyboard focus here on launch
        
        # ── Format & options row ─────────────────────────────────
        opts_frame = ttk.Frame(self)
        opts_frame.pack(fill=tk.X, pady=(0, 12))
        
        # ─ Format selector (left side) ────
        fmt_lf = ttk.LabelFrame(opts_frame, text="Format", padding=8)
        fmt_lf.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Radio buttons — only one format can be selected at a time
        self.fmt_var = tk.StringVar(value="mp3")  # Default: MP3
        fmts = [("🎵 MP3 Audio  (recommended)", "mp3"),
                ("🎧 Best Audio (opus/m4a)", "best-audio"),
                ("🎬 Best Video (mp4)", "best-video")]
        for text, val in fmts:
            ttk.Radiobutton(fmt_lf, text=text, variable=self.fmt_var,
                            value=val).pack(anchor="w")
        
        # ─ Options panel (right side) ────
        opt_lf = ttk.LabelFrame(opts_frame, text="Options", padding=8)
        opt_lf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Playlist range — lets you download e.g. items 3 to 8 only
        range_row = ttk.Frame(opt_lf)
        range_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(range_row, text="Items:").pack(side=tk.LEFT)
        self.pl_start_var = tk.StringVar()      # Start item number
        pl_start = ttk.Entry(range_row, textvariable=self.pl_start_var,
                              width=5)
        pl_start.pack(side=tk.LEFT, padx=4)
        ttk.Label(range_row, text="to").pack(side=tk.LEFT)
        self.pl_end_var = tk.StringVar()         # End item number
        pl_end = ttk.Entry(range_row, textvariable=self.pl_end_var,
                            width=5)
        pl_end.pack(side=tk.LEFT, padx=4)
        ttk.Label(range_row, text="(leave blank for all)",
                  style="Sub.TLabel").pack(side=tk.LEFT, padx=6)
        
        # Embed thumbnail checkbox
        self.thumb_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_lf, text="Embed thumbnail & metadata",
                        variable=self.thumb_var).pack(anchor="w")
        
        # ── Output directory row ─────────────────────────────────
        out_frame = ttk.Frame(self)
        out_frame.pack(fill=tk.X, pady=(0, 12))
        
        ttk.Label(out_frame, text="Save to:").pack(side=tk.LEFT)
        self.out_dir_var = tk.StringVar(
            value=os.path.expanduser("~/Downloads/TubeScoop")
        )
        self.out_entry = ttk.Entry(out_frame, textvariable=self.out_dir_var)
        self.out_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        
        # Browse button — opens a system folder picker
        self.browse_btn = ttk.Button(
            out_frame, text="Browse…", style="Browse.TButton",
            command=self._browse_dir,
        )
        self.browse_btn.pack(side=tk.RIGHT)
        
        # New Folder button — creates a new subfolder in the current directory
        self.newfolder_btn = ttk.Button(
            out_frame, text="+Folder", style="Browse.TButton",
            command=self._new_folder,
        )
        self.newfolder_btn.pack(side=tk.RIGHT, padx=(0, 4))
        
        # ── Download button (big, prominent) ─────────────────────
        self.dl_btn = ttk.Button(self, text="🍨  Scoop it!", command=self._start_download)
        self.dl_btn.pack(fill=tk.X, pady=(0, 4), ipady=4)
        
        # ── Update row ───────────────────────────────────────────
        update_row = ttk.Frame(self)
        update_row.pack(fill=tk.X, pady=(0, 12))
        self.update_btn = ttk.Button(
            update_row, text="🔄  Update yt-dlp", style="Browse.TButton",
            command=self._update_ytdlp,
        )
        self.update_btn.pack(side=tk.LEFT)
        self.update_status_var = tk.StringVar(value="")
        ttk.Label(update_row, textvariable=self.update_status_var,
                  style="Status.TLabel").pack(side=tk.LEFT, padx=8)
        
        # ── Progress bar ─────────────────────────────────────────
        self.progress = ttk.Progressbar(
            self, mode="determinate",
            style="Accent.Horizontal.TProgressbar",
        )
        self.progress.pack(fill=tk.X, pady=(0, 4))
        
        # ── Status text ──────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready")
        self.status_lbl = ttk.Label(self, textvariable=self.status_var,
                                     style="Status.TLabel")
        self.status_lbl.pack(anchor="w", pady=(0, 8))
        
        # ── Log area (scrollable text box) ───────────────────────
        log_lf = ttk.LabelFrame(self, text="Progress Log", padding=6)
        log_lf.pack(fill=tk.BOTH, expand=True)
        
        log_frame = ttk.Frame(log_lf)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        # The Text widget shows all yt-dlp output and status messages
        self.log_text = tk.Text(
            log_frame, height=8, wrap=tk.WORD,
            bg=self.SURFACE, fg=self.FG,
            insertbackground=self.FG,
            font=("Consolas", 9) if sys.platform == "win32"
                 else ("Noto Mono", 9) if sys.platform == "darwin"
                 else ("Monospace", 9),
            borderwidth=0, highlightthickness=0,
            state=tk.DISABLED,          # Read-only — users can't edit the log
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbar for the log
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL,
                                    command=self.log_text.yview)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        
        # ── Keyboard shortcut ────────────────────────────────────
        # Pressing Enter anywhere in the window starts the download
        self.root.bind("<Return>", lambda e: self._start_download())
    
    # ═══════════════════════════════════════════════════════════════
    #  ACTIONS
    # ═══════════════════════════════════════════════════════════════
    
    def _new_folder(self):
        """
        Create a new subfolder inside the current output directory.
        
        This pops up a simple dialog asking for a folder name, then
        creates it and updates the "Save to:" path.
        """
        # Get the current output directory (or default to Downloads)
        current_dir = self.out_dir_var.get().strip()
        if not current_dir:
            current_dir = os.path.expanduser("~/Downloads/TubeScoop")
        
        # Ask the user what to name the new folder
        # Use a simple popup dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("New Folder")
        dialog.configure(bg=self.BG)
        dialog.geometry("360x160")
        dialog.resizable(False, False)
        dialog.transient(self.root)     # Stay on top of main window
        dialog.grab_set()               # Modal — block interaction with main window
        
        # Centre the dialog over the main window
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 360) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 160) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # ── Dialog contents ──
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="New folder name:",
                  style="Sub.TLabel").pack(anchor="w")
        
        name_var = tk.StringVar(value="New Folder")
        name_entry = ttk.Entry(frame, textvariable=name_var, font=("Segoe UI", 12))
        name_entry.pack(fill=tk.X, pady=(4, 12))
        name_entry.select_range(0, tk.END)  # Pre-select the default name
        name_entry.focus()
        
        # ── Buttons ──
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        
        def do_create():
            folder_name = name_var.get().strip()
            if not folder_name:
                return
            new_path = os.path.join(current_dir, folder_name)
            try:
                os.makedirs(new_path, exist_ok=True)
                self.out_dir_var.set(new_path)
                self._log_append(f"📁  Created folder: {new_path}")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Could not create folder:\n{e}")
        
        def do_cancel():
            dialog.destroy()
        
        ttk.Button(btn_frame, text="Cancel", style="Browse.TButton",
                   command=do_cancel).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(btn_frame, text="Create", command=do_create).pack(side=tk.RIGHT)
        
        # Enter key creates the folder
        dialog.bind("<Return>", lambda e: do_create())
        dialog.bind("<Escape>", lambda e: do_cancel())
    
    def _browse_dir(self):
        """
        Open a system folder picker and update the "Save to:" path.
        
        Uses tkinter's built-in filedialog — looks native on every OS.
        """
        d = filedialog.askdirectory(
            title="Select Download Folder",
            initialdir=self.out_dir_var.get() or os.path.expanduser("~"),
        )
        if d:  # User picked a folder (didn't cancel)
            self.out_dir_var.set(d)
    
    def _log_append(self, text, tag=None):
        """
        Append a line of text to the scrollable log area.
        
        Parameters
        ----------
        text : str
            The message text
        tag : str or None
            Optional style tag for colouring ("red" or "green")
        """
        self.log_text.configure(state=tk.NORMAL)  # Temporarily enable editing
        self.log_text.insert(tk.END, text + "\n", tag)
        self.log_text.see(tk.END)                 # Auto-scroll to bottom
        self.log_text.configure(state=tk.DISABLED)  # Lock it again
    
    def _set_status(self, text, tag=None):
        """Update the status text below the progress bar."""
        self.status_var.set(text)
    
    def _set_ui_enabled(self, enabled):
        """
        Enable or disable interactive elements (prevents double-clicks during download).
        
        Parameters
        ----------
        enabled : bool
            True = normal operation, False = greyed out during download
        """
        state = tk.NORMAL if enabled else tk.DISABLED
        self.url_entry.configure(state=state)
        self.browse_btn.configure(state=state)
        self.newfolder_btn.configure(state=state)
        self.dl_btn.configure(state=state)
    
    # ═══════════════════════════════════════════════════════════════
    #  MANUAL YT-DLP UPDATE
    # ═══════════════════════════════════════════════════════════════
    #
    # Runs in a background thread so the GUI doesn't freeze while
    # checking for updates.
    
    def _update_ytdlp(self):
        """Check for and apply yt-dlp updates — triggered by the button."""
        self.update_btn.configure(state=tk.DISABLED)
        self.update_status_var.set("⏳  Checking …")
        self._log_append("🔄  Manual yt-dlp update check …")
        
        def _do_update():
            # Capture log messages and pipe them to the GUI log
            msgs = []
            def capture(msg):
                msgs.append(msg)
                self.after(0, lambda: self._log_append(f"  {msg}"))
            ok = _ensure_ytdlp(log_fn=capture)
            self.after(0, lambda: self._finish_update(ok, msgs))
        
        t = threading.Thread(target=_do_update, daemon=True)
        t.start()
    
    def _finish_update(self, ok, msgs):
        """
        Called on the GUI thread after the update check completes.
        
        Parameters
        ----------
        ok : bool
            Did the update succeed?
        msgs : list of str
            All log messages from the update process
        """
        self.update_btn.configure(state=tk.NORMAL)
        if not ok:
            self.update_status_var.set("❌  Update failed — check log")
            return
        # Find the last meaningful status line (not debug noise)
        status_line = "✅  Up to date"
        for m in reversed(msgs):
            if "updated" in m.lower() or "latest" in m.lower() or "up to date" in m.lower():
                status_line = m.strip("✅ ⚠️ ")
                break
        self.update_status_var.set(f"✅  {status_line}")
    
    # ═══════════════════════════════════════════════════════════════
    #  START DOWNLOAD
    # ═══════════════════════════════════════════════════════════════
    #
    # Validates inputs, ensures dependencies are installed, then spawns
    # a DownloadWorker in a background thread.
    
    def _start_download(self):
        """Validate input and kick off the download process."""
        # ── Validate URL ─────────────────────────────────────────
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("No URL", "Please paste a video or playlist URL first.")
            return
        
        # ── Validate output directory ────────────────────────────
        out_dir = self.out_dir_var.get().strip()
        if not out_dir:
            out_dir = os.path.expanduser("~/Downloads/TubeScoop")
            self.out_dir_var.set(out_dir)
        
        # Ensure the output directory exists
        os.makedirs(out_dir, exist_ok=True)
        
        # ── Check dependencies ───────────────────────────────────
        self._log_append("🔧 Checking dependencies …")
        if not _ensure_ytdlp(self._log_append):
            messagebox.showerror("Missing Dependency",
                                 "yt-dlp could not be installed.\n"
                                 "Try: pip install yt-dlp")
            return
        
        if not _ffmpeg_binary():
            self._log_append("📥 ffmpeg not found — downloading …")
            if not _download_ffmpeg(self._log_append):
                if not messagebox.askyesno(
                    "ffmpeg Required",
                    "Could not auto-download ffmpeg (needed for MP3 conversion).\n\n"
                    "Install it manually and restart, or continue without MP3 support?\n"
                    "Continue anyway?"):
                    return
        
        self._log_append("")
        self._log_append(f"🎯  {url}")
        
        # ── Reset UI for new download ────────────────────────────
        self.progress["value"] = 0
        self._set_ui_enabled(False)
        self._log_append("⚡ Starting download …")
        self.dl_btn.configure(text="🍨  Scooping…")
        
        # ── Parse playlist range ─────────────────────────────────
        ps = self.pl_start_var.get().strip()
        pe = self.pl_end_var.get().strip()
        ps = int(ps) if ps.isdigit() else None
        pe = int(pe) if pe.isdigit() else None
        
        # ── Create and start the worker ──────────────────────────
        worker = DownloadWorker(
            url=url,
            out_dir=out_dir,
            fmt=self.fmt_var.get(),
            playlist_start=ps,
            playlist_end=pe,
            log_q=self._log_q,
        )
        self._download_thread = threading.Thread(target=worker.run, daemon=True)
        self._download_thread.start()
    
    # ═══════════════════════════════════════════════════════════════
    #  POLLER — reads messages from the worker thread
    # ═══════════════════════════════════════════════════════════════
    #
    # Tkinter is NOT thread-safe — you can't update GUI widgets from
    # a background thread. Instead, the worker puts messages into a
    # queue.Queue, and this poller (running on the main GUI thread)
    # checks the queue every 100ms and updates the UI.
    #
    # This is the standard tkinter pattern for background tasks.
    
    def _start_poller(self):
        """Begin the recurring queue-check loop."""
        self._poll_logs()
    
    def _poll_logs(self):
        """
        Check the message queue and update UI elements.
        
        Called every 100ms via self.after(). Re-schedules itself
        automatically.
        """
        # Drain all messages currently in the queue
        try:
            while True:
                kind, data = self._log_q.get_nowait()
                self._handle_message(kind, data)
        except queue.Empty:
            pass  # No messages — that's fine
        
        # Check if the download thread has finished
        if self._download_thread and not self._download_thread.is_alive():
            self._download_thread = None
            self._set_ui_enabled(True)
            self.dl_btn.configure(text="🍨  Scoop it!")
            self.progress["value"] = 100
        
        # Re-schedule this check in 100ms
        self._poll_id = self.after(100, self._poll_logs)
    
    def _handle_message(self, kind, data):
        """
        Process a single message from the download worker.
        
        Parameters
        ----------
        kind : str
            Message type: "raw", "progress", "file", "status", "item", "error"
        data : varies
            Message payload (string percentage, status text, etc.)
        """
        if kind == "raw":
            # Raw yt-dlp output line — not shown by default
            pass
        
        elif kind == "progress":
            # Update the progress bar (value is 0.0 to 100.0)
            self.progress["value"] = data
        
        elif kind == "file":
            # Show which file is currently being downloaded
            self._set_status(f"📥  {data}")
        
        elif kind == "status":
            if data == "done":
                self._set_status("✅  Complete!", tag="green")
                self._log_append("✅  Done!")
                self._log_append(f"📂  Files saved to: {self.out_dir_var.get()}")
            elif data == "error":
                self._set_status("❌  An error occurred — check the log above.",
                                 tag="red")
                self._log_append("❌  Download failed. See red messages above.")
        
        elif kind == "item":
            # Playlist item number — "Processing item 3 …"
            self._set_status(f"📦  Processing item {data} …")
        
        elif kind == "error":
            # Error message from the worker
            self._log_append(f"❌  {data}")
            self._set_status(f"❌  {data}", tag="red")


# ══════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════
#
# Python scripts start here when run directly (python3 yt_dlp_gui.py).
# If imported as a module, this code doesn't run.

def main():
    """Create the Tk root window and start the application."""
    root = tk.Tk()
    app = TubeScoopApp(root)
    root.mainloop()   # Main event loop — runs until the window is closed


if __name__ == "__main__":
    main()