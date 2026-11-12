"""Thin ffmpeg wrapper: locate the binary, probe media, detect silence."""
from __future__ import annotations

import re
import shutil
import subprocess

_FF = None


def ffmpeg_path():
    global _FF
    if _FF:
        return _FF
    p = shutil.which("ffmpeg")
    if p:
        _FF = p
        return p
    try:
        import imageio_ffmpeg

        _FF = imageio_ffmpeg.get_ffmpeg_exe()
        return _FF
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "ffmpeg not found. Install it (`winget install Gyan.FFmpeg` / `brew install ffmpeg` / "
            "`apt install ffmpeg`) or `pip install imageio-ffmpeg`."
        ) from exc


def run(args, cwd=None):
    cmd = [ffmpeg_path(), "-hide_banner", "-loglevel", "error", *[str(a) for a in args]]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("ffmpeg failed (%d):\n%s" % (r.returncode, (r.stderr or "")[-2000:]))
    return r


def _banner(path):
    r = subprocess.run([ffmpeg_path(), "-hide_banner", "-i", str(path)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stderr or ""


def probe(path):
    info = _banner(path)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", info)
    if not m:
        raise RuntimeError("cannot read media (is it a video?): %s" % path)
    duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    vm = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", info)
    width, height = (int(vm.group(1)), int(vm.group(2))) if vm else (0, 0)
    return {
        "path": str(path),
        "duration": round(duration, 3),
        "width": width,
        "height": height,
        "has_audio": "Audio:" in info,
        "has_video": "Video:" in info,
    }


def detect_silence(path, noise_db=-30, min_dur=0.35):
    """Return [(start, end_or_None), ...] of silent stretches (seconds)."""
    r = subprocess.run(
        [ffmpeg_path(), "-hide_banner", "-i", str(path),
         "-af", "silencedetect=noise=%sdB:d=%s" % (noise_db, min_dur),
         "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    err = r.stderr or ""
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([\d.]+)", err)]
    out = []
    for i, s in enumerate(starts):
        out.append((max(0.0, s), ends[i] if i < len(ends) else None))
    return out


def extract_frame(path, t, out, size=None):
    """Grab one still at ``t`` seconds; ``size=(w, h)`` crops to that aspect."""
    args = ["-y", "-ss", "%.3f" % t, "-i", str(path), "-frames:v", "1"]
    if size:
        w, h = size
        args += ["-vf", "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d"
                 % (w, h, w, h)]
    args += ["-q:v", "2", str(out)]
    run(args)
    return str(out)
