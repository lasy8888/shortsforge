"""Publishing kit: cover frames, title candidates, hashtags.

The point is to hand a creator something they can paste into a caption box
without opening an editor. Everything derives from the clip itself, so it
works for any language the ASR model handles.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from . import ffmpeg

# Words that carry no topic on their own; kept deliberately small.
STOP = set("""
我们 你们 他们 她们 这个 那个 什么 怎么 这样 那样 就是 然后 因为 所以 但是 可以 还是 不是
一个 没有 自己 现在 知道 觉得 时候 已经 真的 大家 如果 其实 可能 这些 那些 东西 事情 这种
那种 这里 那里 是不是 有没有 就会 都是 也是 这个 一下 一直 一样 出来 起来 上去 下来
""".split())

_PUNCT_SPLIT = re.compile(r"[。！？!?…\n]+")
_NON_CJK = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9]+")


def _sentences(text):
    return [s.strip() for s in _PUNCT_SPLIT.split(text or "") if s.strip()]


def titles(captions, limit=3, min_len=8, max_len=30):
    """Title candidates, built by joining the first few spoken phrases.

    Whisper often returns phrases without sentence punctuation, so we treat each
    cue as a unit and glue just enough of them together to read like a headline.
    """
    units = [s for c in captions for s in _sentences(c["text"])]
    if not units:
        return []
    total = sum(len(u) for u in units) or 1
    cjk = sum(1 for u in units for ch in u if "\u4e00" <= ch <= "\u9fff")
    sep = "，" if cjk > total * 0.3 else ", "
    out = []
    for i in range(len(units)):
        acc, j = units[i], i + 1
        while len(acc) < 16 and j < len(units) and len(acc) + len(units[j]) + 1 <= max_len:
            acc += sep + units[j]
            j += 1
        if len(acc) < min_len:
            if len(units[i]) < min_len // 2:
                continue
            acc = units[i]
        acc = acc.strip(" ，,、")[:max_len]
        if acc and acc not in out:
            out.append(acc)
        if len(out) >= limit:
            break
    return out


_JIEBA = None


def _words(text):
    """Segment Chinese if jieba is around; fall back to whitespace."""
    global _JIEBA
    if _JIEBA is None:
        try:
            import jieba

            _JIEBA = jieba
        except ImportError:
            _JIEBA = False
    if _JIEBA:
        return [w.strip() for w in _JIEBA.lcut(text) if w.strip()]
    return text.split()


MEASURE = set("人个次元天岁倍秒分斤米度")


def hashtags(captions, limit=6, min_count=None):
    """Topic words by frequency, cleaned of stopwords and quantity units.

    Segmenting beats n-grams here: bigrams off raw Chinese produce things like
    ``#时间美军``, which is noise no one would tag with.
    """
    text = _NON_CJK.sub(" ", " ".join(c["text"] for c in captions))
    words = [w for w in _words(text)
             if len(w) >= 2 and w not in STOP and not w.isdigit()
             and not (len(w) == 2 and w[1] in MEASURE)]
    if not words:
        return []
    if min_count is None:
        min_count = 2 if len(words) >= 40 else 1
    counts = Counter(words)
    picked = []
    for w, c in sorted(counts.items(), key=lambda kv: (-kv[1], -len(kv[0]))):
        if c < min_count:
            break
        if any(w in p or p in w for p in picked):
            continue
        picked.append(w)
        if len(picked) >= limit:
            break
    return ["#" + w for w in picked]


def covers(src, outdir, duration=None, times=(0.15, 0.5, 0.85), prefix="cover", size=(1080, 1920)):
    """Grab stills at relative positions, cropped to the same aspect as the short."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    if duration is None:
        duration = ffmpeg.probe(src)["duration"]
    out = []
    for idx, frac in enumerate(times):
        path = outdir / ("%s_%02d.jpg" % (prefix, idx + 1))
        ffmpeg.extract_frame(src, round(duration * frac, 3), path, size=size)
        out.append(str(path))
    return out


def kit(src, outdir, captions=None, duration=None, limit_tags=6):
    """One call: covers + titles + hashtags."""
    covers_ = covers(src, outdir, duration=duration)
    captions = captions or []
    return {
        "covers": covers_,
        "titles": titles(captions),
        "hashtags": hashtags(captions, limit=limit_tags),
    }
