"""Speech-to-text via faster-whisper (optional, lazily imported)."""
from __future__ import annotations

DEFAULT_MODEL = "small"

_CACHE = {}


def _model(name):
    if name in _CACHE:
        return _CACHE[name]
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # noqa: BLE001
        raise RuntimeError(
            "Speech recognition needs faster-whisper: pip install 'shortsforge[asr]'"
        ) from exc
    m = WhisperModel(name, device="cpu", compute_type="int8")
    _CACHE[name] = m
    return m


def transcribe(path, language="zh", model=None, vad=True):
    """Return [{"start", "end", "text"}, ...] in source time (seconds).

    ``vad=True`` drops non-speech stretches, which is exactly what we want
    before deciding where the cut points go.
    """
    m = _model(model or DEFAULT_MODEL)
    segments, _info = m.transcribe(str(path), language=language, vad_filter=vad, beam_size=5)
    out = []
    for s in segments:
        text = (s.text or "").strip()
        if text and s.end > s.start:
            out.append({"start": float(s.start), "end": float(s.end), "text": text})
    return out
