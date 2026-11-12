"""shortsforge — turn one long clip into a vertical short, with captions.

Pure-Python orchestration on top of ffmpeg; the only hard dependency is a
bundled ffmpeg binary (``pip install imageio-ffmpeg``), so it works on a clean
machine with no system packages. Speech recognition is optional and lazy.
"""
from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["ffmpeg", "plan", "render", "pack", "transcribe"]
