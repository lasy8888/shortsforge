"""Command line entry point: ``shortsforge <command>``."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, ffmpeg, pack, plan, render, transcribe


def _plan_asr(src, style, max_dur, model, lang):
    segs = transcribe.transcribe(src, language=lang, model=model)
    if not segs:
        return [], []
    window = plan.pick_window(segs, max_dur)
    ranges = plan.segments_to_ranges(window, gap=style["gap_merge"])
    return plan.clamp(ranges, max_dur), window


def _plan_silence(src, style, max_dur):
    info = ffmpeg.probe(src)
    silences = ffmpeg.detect_silence(src, noise_db=style["silence_db"], min_dur=style["silence_min"])
    speech = plan.speech_from_silence(info["duration"], silences)
    ranges = plan.pick_window_by_duration(speech, max_dur)
    return plan.clamp(ranges, max_dur), []


def _cmd_probe(args):
    info = ffmpeg.probe(args.input)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def _cmd_styles(args):
    for name in render.list_styles():
        style = render.load_style(name)
        print("%-14s %s %dpx  %s" % (name, style["font"], style["font_size"],
                                     "gap=%.2fs" % style["gap_merge"]))
    return 0


def _cmd_cut(args):
    src = str(Path(args.input).resolve())
    info = ffmpeg.probe(src)
    style = render.load_style(args.style)

    window = []
    if args.no_asr:
        ranges, _ = _plan_silence(src, style, args.max_dur)
        captions = []
        print("plan: silence-based", file=sys.stderr)
    else:
        ranges, window = _plan_asr(src, style, args.max_dur, args.model, args.lang)
        captions = [] if args.no_subs else window
        print("plan: speech-based (%d segments)" % len(window), file=sys.stderr)

    if not ranges:
        print("error: no speech found — is there audio? try --no-asr", file=sys.stderr)
        return 2

    out = args.out or str(Path("out") / (Path(src).stem + "_short.mp4"))
    result = render.render(src, ranges, out, captions=captions, style=style, bgm=args.bgm)
    result["source_duration"] = info["duration"]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_pack(args):
    src = str(Path(args.input).resolve())
    outdir = args.out or "out"
    captions = []
    if not args.no_asr:
        captions = transcribe.transcribe(src, language=args.lang, model=args.model)
    result = pack.kit(src, outdir, captions=captions)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="shortsforge",
        description="Turn one long clip into a vertical short: cut the dead air, "
                    "reframe to 9:16, burn captions, and draft a cover + caption kit.",
    )
    p.add_argument("--version", action="version", version="shortsforge " + __version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("probe", help="print duration / size / streams")
    sp.add_argument("input")
    sp.set_defaults(func=_cmd_probe)

    ss = sub.add_parser("styles", help="list the built-in caption styles")
    ss.set_defaults(func=_cmd_styles)

    sc = sub.add_parser("cut", help="cut, reframe to 1080x1920 and burn captions")
    sc.add_argument("input")
    sc.add_argument("-o", "--out", help="output file (default: out/<name>_short.mp4)")
    sc.add_argument("--style", default="douyin_fast", help="style name or path to JSON")
    sc.add_argument("--max-dur", type=float, default=60.0, help="max output seconds (default 60)")
    sc.add_argument("--no-asr", action="store_true", help="cut on silence only, skip Whisper")
    sc.add_argument("--no-subs", action="store_true", help="keep the cut, skip burned captions")
    sc.add_argument("--model", default=transcribe.DEFAULT_MODEL, help="Whisper model size")
    sc.add_argument("--lang", default="zh", help="spoken language code (default zh)")
    sc.add_argument("--bgm", help="background music file (looped, ducked)")
    sc.set_defaults(func=_cmd_cut)

    sk = sub.add_parser("pack", help="covers + title candidates + hashtags")
    sk.add_argument("input")
    sk.add_argument("-o", "--out", help="output directory (default: out)")
    sk.add_argument("--no-asr", action="store_true", help="skip Whisper (covers only)")
    sk.add_argument("--model", default=transcribe.DEFAULT_MODEL)
    sk.add_argument("--lang", default="zh")
    sk.set_defaults(func=_cmd_pack)
    return p


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
