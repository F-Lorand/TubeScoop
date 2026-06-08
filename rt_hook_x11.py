"""
PyInstaller runtime hook — called by the bootloader BEFORE any Python code runs.
This prevents the "[xcb] Unknown sequence number" + XInitThreads crash on Linux.
"""
import os
import ctypes

# Tell Tk to be thread-safe from the very start
os.environ["TCL_NO_DEPRECATED_WARNINGS"] = "1"
os.environ["TK_SILENCE_DEPRECATION"] = "1"

# Try to force XInitThreads before Tk can grab the display
try:
    xlib = ctypes.cdll.LoadLibrary("libX11.so")
    xlib.XInitThreads()
except Exception:
    pass  # Safe to ignore — may already be called or headless