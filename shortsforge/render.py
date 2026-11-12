"""Cut, reframe to 9:16, burn captions, encode.

The whole timeline is expressed as one ``filter_complex`` graph: split the
source, trim each keep-range, concat them back, then scale+crop to vertical and
render the ASS subtitle track on top. Working in relative paths inside the
output directory avoids the colon-escaping mess the ``subtitles`` filter
otherwise needs on Windows.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import ffmpeg

OUT_W, OUT_H = 1080, 1920
FPS = 30

DEFAULT_STYLE = {
    "font": "Microsoft YaHei",
    "font_size": 62,
    "primary": "&H00FFFFFF",
    "outline_colour": "&H00000000",
    "back_colour": "&H80000000",
    "outline": 4,
    "shadow": 0,
    "bold": 0,
    "alignment": 2,          # bottom centre
    "margin_lr": 60,
    "margin_v": 400,         # clear of the platform UI at the bottom
    "max_chars_per_line": 15,
    "border_style": 1,
    "silence_db": -30,
    "silence_min": 0.35,
    "gap_merge": 0.25,
    "bgm_volume": 0.15,
    "crf": 20,
    "preset": "veryfast",
}

_PUNCT = "，。！？；：、,.!?;:）)」』"


# ---------------------------------------------------------------- styles ---

def styles_dir():
    return Path(__file__).resolve().parent / "styles"


def list_styles():
    return sorted(p.stem for p in styles_dir().glob("*.json"))


def load_style(name=None):
    """A style name (``douyin_fast``) or a path to a JSON file."""
    style = dict(DEFAULT_STYLE)
    if not name:
        return style
    path = Path(name)
    if not path.suffix:
        path = styles_dir() / (name + ".json")
    if not path.exists():
        raise RuntimeError(
            "unknown style %r; available: %s" % (name, ", ".join(list_styles()))
        )
    custom = json.loads(path.read_text(encoding="utf-8"))
    unknown = set(custom) - set(DEFAULT_STYLE)
    if unknown:
        raise RuntimeError("style %s has unknown keys: %s" % (path.name, ", ".join(sorted(unknown))))
    style.update(custom)
    return style


# -------------------------------------------------------------- captions ---

def _ass_time(t):
    t = max(0.0, float(t))
    h, rem = divmod(t, 3600.0)
    m, s = divmod(rem, 60.0)
    return "%d:%02d:%05.2f" % (int(h), int(m), s)


def _latin(ch):
    return ch.isascii() and ch.isalnum()


def wrap(text, n):
    """Break a line every ~n characters: punctuation first, then word boundaries."""
    text = " ".join((text or "").split())
    lines = []
    while len(text) > n:
        cut = next((k for k in range(n, max(0, n - 7), -1)
                    if k < len(text) and text[k - 1] in _PUNCT), None)
        if cut is None:
            cut = n
            # a digit or letter run shouldn't be sliced in half ("1 / 080x1920")
            while cut > 1 and _latin(text[cut - 1]) and _latin(text[cut]):
                cut -= 1
            if cut <= 1:                      # one token longer than the line
                cut = n
        lines.append(text[:cut])
        text = text[cut:].lstrip(_PUNCT + " ")
    if text:
        lines.append(text)
    return "\\N".join(lines)


def build_ass(cues, style, path):
    """Write an ASS subtitle file sized for 1080x1920."""
    head = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: %d" % OUT_W,
        "PlayResY: %d" % OUT_H,
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,%(font)s,%(font_size)d,%(primary)s,%(primary)s,%(outline_colour)s,"
        "%(back_colour)s,%(bold)d,0,0,0,100,100,0,0,%(border_style)d,%(outline)d,%(shadow)d,"
        "%(alignment)d,%(margin_lr)d,%(margin_lr)d,%(margin_v)d,1" % style,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    body = []
    for c in cues:
        text = wrap(c["text"], style["max_chars_per_line"]).replace("{", "(").replace("}", ")")
        if not text:
            continue
        body.append("Dialogue: 0,%s,%s,Default,,0,0,%d,,%s"
                    % (_ass_time(c["start"]), _ass_time(c["end"]), style["margin_v"], text))
    path = Path(path)
    path.write_text("\n".join(head + body) + "\n", encoding="utf-8")
    return path


def remap_cues(cues, ranges, min_piece=0.15):
    """Move cues from source time into output time, clipping at every cut."""
    out, offset = [], 0.0
    for a, b in ranges:
        for c in cues:
            s, e = max(c["start"], a), min(c["end"], b)
            if e - s >= min_piece:
                out.append({"start": offset + s - a, "end": offset + e - a, "text": c["text"]})
        offset += b - a
    out.sort(key=lambda c: c["start"])
    return out


# ---------------------------------------------------------------- render ---

def render(src, ranges, out, *, captions=None, style=None, bgm=None, ass_name="captions.ass"):
    """Render ``ranges`` of ``src`` into a vertical short at ``out``."""
    style = dict(DEFAULT_STYLE, **(style or {}))
    # ffmpeg runs with cwd=the output directory, so every path must be absolute
    src = str(Path(src).resolve())
    bgm = str(Path(bgm).resolve()) if bgm else None
    info = ffmpeg.probe(src)
    duration = info["duration"]

    ranges = [(max(0.0, float(a)), min(duration, float(b))) for a, b in ranges]
    ranges = [(a, b) for a, b in ranges if b - a >= 0.05]
    if not ranges:
        raise RuntimeError("nothing left to keep — every range was empty")

    out = Path(out).resolve()
    outdir = out.parent
    outdir.mkdir(parents=True, exist_ok=True)

    cues = remap_cues(captions, ranges) if captions else []
    ass = build_ass(cues, style, outdir / ass_name) if cues else None

    n = len(ranges)
    inputs = ["-i", str(src)]
    has_audio = info["has_audio"]
    audio_idx = 0
    if not has_audio:                       # keep the graph shape identical
        inputs += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
        audio_idx = 1
    bgm_idx = None
    if bgm:
        inputs += ["-stream_loop", "-1", "-i", str(bgm)]
        bgm_idx = 2 if not has_audio else 1

    graph = [
        "[0:v]split=%d%s" % (n, "".join("[v%d]" % i for i in range(n))),
        "[%d:a]asplit=%d%s" % (audio_idx, n, "".join("[a%d]" % i for i in range(n))),
    ]
    for i, (a, b) in enumerate(ranges):
        graph.append("[v%d]trim=start=%.3f:end=%.3f,setpts=PTS-STARTPTS,"
                     "fps=%d,format=yuv420p[vv%d]" % (i, a, b, FPS, i))
        graph.append("[a%d]atrim=start=%.3f:end=%.3f,asetpts=PTS-STARTPTS[aa%d]" % (i, a, b, i))
    graph.append("%sconcat=n=%d:v=1:a=1[vc][ac0]"
                 % ("".join("[vv%d][aa%d]" % (i, i) for i in range(n)), n))

    if bgm_idx is not None:
        graph.append("[%d:a]atrim=0:%.3f,asetpts=PTS-STARTPTS,volume=%.3f[bg]"
                     % (bgm_idx, sum(b - a for a, b in ranges), style["bgm_volume"]))
        graph.append("[ac0]aresample=44100[am]")
        graph.append("[am][bg]amix=inputs=2:duration=first:dropout_transition=0[aout]")
    else:
        graph.append("[ac0]aresample=44100[aout]")

    graph.append("[vc]scale=%d:%d:force_original_aspect_ratio=increase,"
                 "crop=%d:%d,setsar=1[vsc]" % (OUT_W, OUT_H, OUT_W, OUT_H))
    if ass is not None:
        graph.append("[vsc]subtitles=%s[vout]" % ass_name)
    else:
        graph.append("[vsc]null[vout]")

    cmd = [
        *inputs,
        "-filter_complex", ";".join(graph),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", style["preset"], "-crf", str(style["crf"]),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-c:a", "aac", "-b:a", "128k",
        "-y", out.name,
    ]
    ffmpeg.run(cmd, cwd=str(outdir))
    return {
        "path": str(out),
        "duration": round(sum(b - a for a, b in ranges), 3),
        "ranges": len(ranges),
        "captions": len(cues),
        "ass": str(ass) if ass else None,
        "width": OUT_W,
        "height": OUT_H,
    }
