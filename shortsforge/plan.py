"""Timeline planning: decide which stretches of the source survive the cut.

Everything here is pure arithmetic on seconds — no ffmpeg, no model — so the
rules are easy to reason about and cheap to unit-test.
"""
from __future__ import annotations

MIN_KEEP = 0.20   # never keep a sliver shorter than this
EDGE = 0.08       # how much silence to leave around speech so it doesn't feel clipped


def speech_from_silence(duration, silences, edge=EDGE):
    """Invert silencedetect output into the ranges that hold speech."""
    ranges = []
    cursor = 0.0
    for start, end in silences:
        start = max(0.0, min(float(start), duration))
        if start > cursor:
            ranges.append((cursor, start))
        cursor = max(cursor, min(duration, duration if end is None else float(end)))
    if cursor < duration:
        ranges.append((cursor, duration))
    out = []
    for a, b in ranges:
        a, b = max(0.0, a - edge), min(duration, b + edge)
        if b - a >= MIN_KEEP:
            out.append((a, b))
    return merge(out, 0.0)


def merge(ranges, gap=0.12):
    """Join ranges separated by less than ``gap`` seconds."""
    out = []
    for a, b in sorted(ranges):
        if out and a - out[-1][1] <= gap:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def segments_to_ranges(segs, pad=0.06, gap=0.25, duration=None):
    """Turn ASR segments into keep-ranges: pad each cue, merge close ones.

    A pause longer than ``gap`` survives as a real cut, which is what makes the
    result feel edited instead of just trimmed.
    """
    ranges = [(max(0.0, s["start"] - pad), s["end"] + pad) for s in segs]
    if duration is not None:
        ranges = [(a, min(duration, b)) for a, b in ranges]
    return merge([r for r in ranges if r[1] - r[0] >= MIN_KEEP], gap)


def pick_window(segs, max_dur):
    """Longest contiguous run of segments that fits in ``max_dur``.

    "Longest" is measured in characters spoken, not seconds: a dense 45s beats
    a sparse 60s when the goal is a tight short.
    """
    if not segs:
        return []
    if segs[-1]["end"] - segs[0]["start"] <= max_dur:
        return list(segs)
    best = (-1, 0, 0)
    chars, j = 0, 0
    for i in range(len(segs)):
        if j < i:
            j, chars = i, 0
        while j < len(segs) and segs[j]["end"] - segs[i]["start"] <= max_dur:
            chars += len(segs[j]["text"])
            j += 1
        if chars > best[0]:
            best = (chars, i, j)
        if j > i:
            chars -= len(segs[i]["text"])
    _, i, j = best
    return segs[i:j] or segs[:1]


def pick_window_by_duration(ranges, max_dur):
    """Same idea for silence-derived ranges: keep the fullest window."""
    if not ranges:
        return []
    if sum(b - a for a, b in ranges) <= max_dur:
        return list(ranges)
    best, total, j = (-1.0, 0, 0), 0.0, 0
    for i in range(len(ranges)):
        if j < i:
            j, total = i, 0.0
        while j < len(ranges) and ranges[j][1] - ranges[i][0] <= max_dur:
            total += ranges[j][1] - ranges[j][0]
            j += 1
        if total > best[0]:
            best = (total, i, j)
        if j > i:
            total -= ranges[i][1] - ranges[i][0]
    _, i, j = best
    if j <= i:
        a, b = ranges[0]
        return [(a, a + max_dur)]
    return ranges[i:j]


def clamp(ranges, max_dur):
    """Hard cap on total output length, trimming the tail if needed."""
    out, total = [], 0.0
    for a, b in ranges:
        room = max_dur - total
        if room <= MIN_KEEP:
            break
        out.append((a, min(b, a + room)))
        total += out[-1][1] - out[-1][0]
    return out


def total(ranges):
    return sum(b - a for a, b in ranges)
