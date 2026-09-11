# Current authoring interface

Install the core CLI from the user's checkout in a virtual environment. ASR needs `.[transcribe]`, acoustic emissions need `.[align]`, and beat analysis needs `.[rhythm]`. Existing reviewed data does not require reinstalling inference models. Inspect `auto-karaoke --help` and project files before choosing stages.

`project.json` uses schema version 1, `source`, `lyrics`, `work_dir`, clip start and clip duration. All relative paths resolve beside the project file. To import external stems, set `vocals` and `instrumental` to objects with `path` and `origin_seconds`, then run `prepare`; sample zero in an external stem corresponds to that original-source time. Do not prepare over edited working stems.

Current files:

- `lyrics.json`: schema version 1 and `lines`; each line has a stable `id` and `tokens` containing `[surface, reading]`. Japanese readings are hiragana; a third token item supports a one-mora pronunciation override. English may use line `language: "en"` or parallel `token_languages`, with supported lowercase alignment characters as readings.
- `work/emissions.npy` / report: model evidence, vocabulary, source offset and vocal fingerprint. Do not edit these to make an invalid alignment appear valid.
- `work/timing.json`: acoustic line/token/syllable positions, `raw_end`, source timeline and lyric fingerprint. `align` regenerates this file; keep manual timing edits in overrides.
- `work/overrides.json` by default, or configured `overrides`: `syllables` keyed by stable syllable ID, each supplying `start`, `end` and optional review note.
- Singer assignments: annotated lyrics imported with `import-singers`, written to the configured `singer_map` or `work/singer-map.json`. Retain custom profiles and token-level assignments.
- `work/beats.json`: original-audio beat times and fingerprint; optional `countdown.beats_file` overrides its location. Time is relative to the selected clip.

Choose only needed steps:

```bash
auto-karaoke --project /path/to/project.json transcribe --offline
auto-karaoke --project /path/to/project.json emit --offline
auto-karaoke --project /path/to/project.json align
auto-karaoke --project /path/to/project.json beats
auto-karaoke --project /path/to/project.json singer-review
auto-karaoke --project /path/to/project.json import-singers --file annotations.json --enable
```

`--offline` requires downloaded model caches. If a model is missing, ask for explicit approval of its download before omitting `--offline`; do not retry online automatically. Word import and the standalone annotation UI live in the core checkout at `scripts/import_docx_lyrics.py` and `tools/lyric-annotator.html`; they are not installed CLI subcommands. The UI preserves existing JSON metadata but is not a full graphical timing editor. Word import preserves local bold/italic singer legends and mixed-role segments; it does not create readings or timestamps.

For full-song projects, do not send more than 60 seconds through `emit`. Existing manually prepared full-song timing can be rendered, but general automatic sectioning/merging is still outside the CLI. Report that limitation when it blocks the requested workflow rather than fabricating a completed full-song alignment.
