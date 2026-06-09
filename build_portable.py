#!/usr/bin/env python3
"""
Build a standalone / portable executable of TubeScoop using PyInstaller.

Downloads yt-dlp.exe (standalone binary) at build time and bundles it
inside the .exe so users don't need Python or pip to run TubeScoop.

Usage:
    python build_portable.py          (one-file exe in dist/)
    python build_portable.py --onedir (directory-based -- faster startup)
"""

import os
import sys
import shutil
import urllib.request
import subprocess
import platform
import json

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_DIR, "dist")
BUNDLE_DIR = os.path.join(PROJECT_DIR, "_bundle")  # temp dir for bundled assets


def _download_ytdlp():
    """Download the standalone yt-dlp binary for the current platform."""
    os.makedirs(BUNDLE_DIR, exist_ok=True)

    # Determine platform download URL
    if sys.platform == "win32":
        url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
        out_name = "yt-dlp.exe"
    elif sys.platform == "darwin":
        url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos"
        out_name = "yt-dlp_macos"
    else:
        url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
        out_name = "yt-dlp"

    out_path = os.path.join(BUNDLE_DIR, out_name)

    # Skip if already downloaded (build was re-run)
    if os.path.isfile(out_path):
        print(f"  yt-dlp already cached: {out_path}")
        return out_path

    print(f"  Downloading yt-dlp from {url} ...")
    urllib.request.urlretrieve(url, out_path)
    # Make executable on Unix
    if not sys.platform.startswith("win"):
        os.chmod(out_path, 0o755)
    size = os.path.getsize(out_path)
    print(f"  Downloaded: {out_path} ({size / 1024 / 1024:.1f} MB)")
    return out_path


def main():
    onefile = "--onedir" not in sys.argv

    # Ensure PyInstaller is installed
    try:
        import PyInstaller  # noqa
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            stdout=subprocess.DEVNULL,
        )

    # Clean previous builds
    for d in ["build", "dist", BUNDLE_DIR]:
        p = os.path.join(PROJECT_DIR, d)
        if os.path.isdir(p):
            shutil.rmtree(p)

    # Download yt-dlp standalone binary to bundle inside the .exe
    print("Downloading yt-dlp binary for bundling...")
    yt_dlp_path = _download_ytdlp()
    yt_dlp_name = os.path.basename(yt_dlp_path)

    # -- Build command ------------------------------------------
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
    ]

    name = "TubeScoop"

    if onefile:
        cmd.append("--onefile")
        ext = ".exe" if sys.platform == "win32" else ""
        final = os.path.join(DIST_DIR, f"{name}{ext}")
    else:
        cmd.append("--onedir")
        final = os.path.join(DIST_DIR, name)

    # Bundle the yt-dlp binary alongside the app
    cmd.extend([
        f"--name={name}",
        "--windowed",                # no console window on Windows/macOS
        "--icon=NONE",               # no icon for now
        "--add-data", f"requirements.txt{os.pathsep}.",  # bundle for reference
        "--add-data", f"{yt_dlp_path}{os.pathsep}.",     # bundle yt-dlp binary
    ])

    # Platform-specific options
    if sys.platform == "darwin":
        cmd.append("--onedir")       # macOS .app can't be onefile
        cmd.extend(["--osx-bundle-identifier", "com.tubescoop.app"])

    cmd.append(os.path.join(PROJECT_DIR, "yt_dlp_gui.py"))

    print("Building...")
    subprocess.check_call(cmd)

    # -- Post-build ---------------------------------------------
    # Clean up bundle temp dir
    if os.path.isdir(BUNDLE_DIR):
        shutil.rmtree(BUNDLE_DIR)

    print(f"\nBuilt successfully!")
    print(f"   {final}")
    print("\nWhat to distribute:")
    if os.path.isdir(final):
        print(f"   The '{name}/' folder -- portable, no install needed.")
    else:
        print(f"   The '{os.path.basename(final)}' file -- a single portable executable.")

    oname = "TubeScoop.exe" if sys.platform == "win32" else "TubeScoop"
    print(f"\nRun:  {os.path.join(DIST_DIR, oname)}")


if __name__ == "__main__":
    main()