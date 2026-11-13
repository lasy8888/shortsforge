# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-11-13

First public release.

### Added

- `shortsforge cut <file>` — rebuilds the timeline from N keep-ranges in a single
  `filter_complex` graph, reframes to 1080×1920, and burns an ASS caption track
  whose timings are remapped across every cut.
- Two planners: `--no-asr` cuts on silence only (no model download, works on any
  clip); the default transcribes with faster-whisper and keeps the densest window
  that fits `--max-dur`.
- `shortsforge pack <file>` — three cover stills, title candidates and hashtags
  (jieba keyword extraction) for the publish step.
- `shortsforge probe` and `shortsforge styles` for inspecting an input and the
  available caption styles.
- Three built-in styles (`douyin_fast`, `knowledge`, `vlog_clean`) plus user
  styles loaded from a JSON file passed to `--style`.
- `--bgm` music bed, looped and ducked under the voice.
- ffmpeg is resolved through `imageio-ffmpeg`, so there is no system ffmpeg
  install and no PATH setup.

### Notes

- First captioning run downloads a Whisper model (`small`, ~500 MB) from Hugging
  Face and caches it; later runs are offline. `--model tiny` is ~75 MB.
- Known limitations (one speaker, centre-weighted crop, character-count window
  heuristic, no face tracking) are listed in the README.

[0.1.0]: https://github.com/lasy8888/shortsforge/releases/tag/v0.1.0
