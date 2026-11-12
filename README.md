# shortsforge

**One long clip in, one vertical short out.** Cut the dead air, reframe to 9:16, burn word-accurate captions, and draft a cover + caption kit — from a single command.

```bash
shortsforge cut talk.mp4          # → out/talk_short.mp4  (1080×1920, captions burned in)
shortsforge pack talk.mp4         # → out/cover_01..03.jpg + title candidates + hashtags
```

No editor. No timeline. No system ffmpeg install — the binary ships with `pip install imageio-ffmpeg`, and on a clean machine that is the *only* hard dependency.

<img src="docs/demo.jpg" width="320" alt="A 4:3 source reframed to 1080x1920 with burned-in captions">

[中文快速开始](#中文快速开始) · [How it works](#how-it-works) · [Write your own style](#write-your-own-style) · [Limitations](#limitations)

---

## What it actually does

| Step | What happens | Why it matters |
|---|---|---|
| **Plan** | Whisper finds the spoken segments; long pauses become cut points | Removes the 30–50% of a raw talking clip that is silence, filler air, or camera fumbling |
| **Pick** | Keeps the densest contiguous window that fits `--max-dur` | You say "30 seconds", you get the 30 seconds with the most words in them — not the first 30 seconds |
| **Reframe** | `scale` + `crop` to 1080×1920, `setsar=1` | A landscape source becomes a vertical one without letterboxing |
| **Caption** | ASS track generated from ASR timings, remapped across every cut | Captions stay in sync even though the timeline was rebuilt from pieces |
| **Encode** | libx264 CRF 20, `+faststart`, AAC 128k | Uploads start playing immediately on every platform |

The cut is not a trim: the timeline is rebuilt from N keep-ranges in one `filter_complex` graph, so a 10-minute interview collapses into a 60-second short with clean cuts on both video and audio.

## Install

```bash
pip install shortsforge            # core: ffmpeg via imageio-ffmpeg, no ASR
pip install "shortsforge[asr]"     # + faster-whisper (captions) and jieba (hashtags)
```

Python 3.9+. Nothing else. macOS, Linux, Windows.

The first `cut` that uses speech downloads a Whisper model from Hugging Face (`small` is ~500 MB) and caches it — later runs are offline. `--model tiny` is a ~75 MB alternative for drafts.

## Quick start

```bash
# 1. What am I dealing with?
shortsforge probe raw.mp4

# 2. Cut on silence only — no model download, works on any clip
shortsforge cut raw.mp4 --no-asr

# 3. Cut on speech, with burned captions (downloads a Whisper model on first run)
shortsforge cut raw.mp4 --max-dur 45 --style douyin_fast

# 4. Music bed, ducked under the voice
shortsforge cut raw.mp4 --bgm lofi.mp3 --style vlog_clean

# 5. Publishing kit: 3 cover frames + title candidates + hashtags
shortsforge pack raw.mp4
```

Hashtags use `jieba` word segmentation when it is installed (it comes with the `asr` extra) and degrade to whitespace tokens without it — an n-gram guess would produce tags like `#时间美军`, which nobody would actually use.

`cut` prints a JSON summary (`duration`, `ranges`, `captions`, `ass`) so it drops into a script:

```bash
for f in raw/*.mp4; do shortsforge cut "$f" --max-dur 60 --no-subs; done
```

### Options that matter

| Flag | Default | Effect |
|---|---|---|
| `--max-dur` | `60` | Hard cap on output length in seconds |
| `--style` | `douyin_fast` | Built-in style name, or a path to your own JSON |
| `--no-asr` | off | Skip Whisper entirely — cut on `silencedetect` |
| `--no-subs` | off | Use speech to find the cut, but don't burn captions |
| `--model` | `small` | `tiny`/`base`/`small`/`medium`/`large-v3` — bigger is slower and better |
| `--lang` | `zh` | Spoken language; pass `en`, `ja`, … for other material |
| `--bgm` | none | Looped and volume-ducked under the voice |

## Built-in styles

```
$ shortsforge styles
douyin_fast    Microsoft YaHei 72px  gap=0.18s     # big bold auto-caption look
knowledge      Microsoft YaHei 60px  gap=0.25s     # calmer, smaller, quieter music
vlog_clean     Microsoft YaHei 56px  gap=0.35s     # relaxed pacing, soft shadow
```

A style is just a JSON file: font, size, colours (ASS `&HAABBGGRR`), outline, margins, characters per line, and the cut/merge thresholds (`silence_min`, `gap_merge`, `bgm_volume`, `crf`, `preset`).

## Write your own style

```bash
shortsforge cut raw.mp4 --style ./my_style.json
```

```json
{
  "font": "Inter",
  "font_size": 58,
  "primary": "&H00FFFFFF",
  "outline": 4,
  "margin_v": 360,
  "max_chars_per_line": 19,
  "gap_merge": 0.28,
  "bgm_volume": 0.12
}
```

Unknown keys are rejected rather than silently ignored — a typo in `gap_merge` should fail loudly, not ship a video with the wrong pacing.

## How it works

```
raw.mp4
  ├─ ffmpeg.probe ────────────────► duration / size / streams
  ├─ faster-whisper ──────────────► [{start, end, text}, …]
  │     └ plan.pick_window ───────► densest window under --max-dur
  │     └ plan.segments_to_ranges ► padded keep-ranges, close ones merged
  ├─ render ──────────────────────► filter_complex:
  │     split → trim×N → concat → scale+crop → subtitles(ASS) → libx264
  └─ pack ────────────────────────► 3 stills, title candidates, hashtags
```

Pure arithmetic lives in `plan.py` (no ffmpeg, no model) and is covered by unit tests; the ffmpeg layer is thin and raises with the last 2 KB of stderr instead of swallowing it.

## Limitations

Being honest up front saves you a bad upload:

- **One speaker, one language.** No diarization, no per-speaker colours. Whisper picks the dominant voice.
- **Cropping is centre-weighted.** A subject who stands off to one side will get clipped at 9:16. There is no face tracking yet.
- **"Densest window" is character count**, a cheap proxy for "most interesting". It does not understand what is actually worth keeping.
- **CPU is slow.** `small` on an int8 CPU runs at roughly 5× realtime; a 5-minute clip takes a while. Use `tiny`/`base` for drafts or a GPU build of faster-whisper for volume.
- **Fonts must exist locally.** `Microsoft YaHei` ships on Windows; on Linux/macOS set `"font"` to something installed (e.g. `Noto Sans CJK SC`, `PingFang SC`).
- **No auto-posting.** This is deliberately local: it produces files, not uploads. Every platform has different rules about first-publication and watermarking — those are your call, not a flag.

## Roadmap

- [ ] `--clip N` to emit the top N windows instead of one
- [ ] keyword highlights (`--grep "定价"`) to bias the window selection
- [ ] `--srt` to export sidecar subtitles for platforms that prefer them
- [ ] optional face-aware crop
- [ ] `--json` output for every command

Issues and PRs are welcome. Small, focused patches with a test are merged fastest.

## License

MIT — see [LICENSE](LICENSE).

---

## 中文快速开始

**一条长视频进，一条竖屏短视频出**：自动剪掉废话和空白、重构为 1080×1920 竖屏、烧入准确字幕，并顺手生成封面帧、标题候选和话题标签。

```bash
pip install "shortsforge[asr]"

shortsforge cut 原片.mp4                      # → out/原片_short.mp4
shortsforge cut 原片.mp4 --max-dur 45 --style douyin_fast
shortsforge cut 原片.mp4 --no-asr              # 不下载模型，纯按静音切
shortsforge pack 原片.mp4                      # → 3 张封面 + 标题候选 + 标签
```

要点：

- **不需要装 ffmpeg**，随 `imageio-ffmpeg` 一起装好，Windows/macOS/Linux 通用。
- **切点由语音决定**：先跑 Whisper 找说话段，长停顿成为切点；再在 `--max-dur` 内挑「字数最多」的连续窗口——不是简单取前 30 秒。
- **字幕跟着重排后的时间轴走**，剪过的片子字幕也不会错位。
- **内置三种字幕风格**（`douyin_fast` / `knowledge` / `vlog_clean`），也可以用自己的 JSON；写错键名会直接报错，不会静默出片。
- **字体要本地有**：Windows 默认微软雅黑；Linux/macOS 改成系统已装的字体（如 `Noto Sans CJK SC`、`PingFang SC`）。
- **默认中文识别**（`--lang zh`），其它语言加 `--lang en` 等。
- **只出文件，不自动发布**：各平台对首发/水印规则不同，这一步留给你决定。

CPU 上 `small` 模型大约 5 倍实时，赶时间用 `--model base` 或 `--no-asr`。
