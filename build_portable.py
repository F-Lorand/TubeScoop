#!/usr/bin/env python3
"""
Build a standalone / portable executable of TubeScoop using PyInstaller.

Usage:
    python build_portable.py          (one-file exe in dist/)
    python build_portable.py --onedir (directory-based — faster startup)
"""

import os
import sys
import shutil
import subprocess
import platform

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_DIR, "dist")


def main():
    onefile = "--onedir" not in sys.argv

    # Ensure PyInstaller is installed
    try:
        import PyInstaller  # noqa
    except ImportError:
        print("📦 Installing PyInstaller …")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            stdout=subprocess.DEVNULL,
        )

    # Clean previous builds
    for d in ["build", "dist"]:
        p = os.path.join(PROJECT_DIR, d)
        if os.path.isdir(p):
            shutil.rmtree(p)

    # ── Build command ──────────────────────────────
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

    cmd.extend([
        f"--name={name}",
        "--windowed",                # no console window on Windows/macOS
        "--icon=NONE",               # no icon for now
        "--add-data", f"requirements.txt{os.pathsep}.",  # bundle for reference
    ])

    # Platform-specific options
    if sys.platform == "darwin":
        cmd.append("--onedir")       # macOS .app can't be onefile
        cmd.extend(["--osx-bundle-identifier", "com.tubescoop.app"])

    cmd.append(os.path.join(PROJECT_DIR, "yt_dlp_gui.py"))

    print("🔨 Building…")
    subprocess.check_call(cmd)

    # ── Post-build ─────────────────────────────────
    print(f"\n✅  Built successfully!")
    print(f"   📁 {final}")
    print(f"\n📋  What to distribute:")
    if os.path.isdir(final):
        print(f"   The '{name}/' folder — portable, no install needed.")
    else:
        print(f"   The '{os.path.basename(final)}' file — a single portable executable.")

    oname = "TubeScoop.exe" if sys.platform == "win32" else "TubeScoop"
    print(f"\n🚀  Run:  {os.path.join(DIST_DIR, oname)}")


if __name__ == "__main__":
    main()