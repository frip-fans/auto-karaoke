---
name: karaoke-render
description: Render karaoke MP4 videos from existing reviewed lyric timing and synchronized instrumental/vocal stems, with kanji ruby, countdowns and configurable backgrounds. Use for previews, final rendering or changing subtitle style without redoing transcription.
---

# Karaoke rendering

If the environment has not been checked, use `karaoke-setup` when available for read-only diagnostics. Missing dependencies are a reason to propose installation, not permission to install. Before creating an environment, obtaining the engine, installing/upgrading/removing packages, downloading models/fonts or changing system configuration, list the components, location and scope, ask whether to proceed, and wait for explicit approval. Apply the same rule when this skill is installed alone. An unchanged plan already explicitly approved need not be approved again; additional changes require fresh consent. If approval is declined or pending, use only existing capabilities.

Use the installed `auto-karaoke` CLI and FFmpeg. Accept the user's reviewed text, readings and timing as inputs. Read [inputs and rendering options](references/rendering.md) before assembling a new render task.

## Validate the handoff

Check that source version, vocal/lyric fingerprints, offsets and durations match. Current rendering reads a project and multiple working files, not a standalone `karaoke.json`. Require the user-approved handoff for a final video; an explicitly requested preview can show unresolved work. Do not infer approval from a file name or validation success.

Preserve existing overrides and singer assignments. Resolve missing or invalid timing through authoring rather than silently regenerating it. Precompute or obtain matching `beats.json` when entrance cues are needed so the render does not unexpectedly perform rhythm analysis. Current subtitle generation can otherwise trigger that analysis.

## Render

Choose the user’s background or source video, font, title information, dimensions and singer-color setting. Fonts must be single TTF/OTF files with the matching font-family name; TTC collections are unsupported. Defaults and presets are configurable, including custom singers.

```bash
auto-karaoke --project /path/to/project.json subtitles
auto-karaoke --project /path/to/project.json render
```

Prefer an inexpensive preview for changed layouts; inspect long lines, ruby boundaries, English spaces, row changes after gaps, singer labels and title cards. Actual GPU availability determines whether `h264_nvenc` is usable; `libx264` works on CPU. NVENC does not move libass subtitle drawing to GPU. Rendering needs no ASR or alignment model when the handoff is complete.

## Verify and deliver

For mixable karaoke, set `dual_audio: true` and `dual_audio_source: "vocals"`. Deliver `work/karaoke-dual-audio.mp4`, with one video stream, default `Instrumental` and a non-default `Vocals` audio stream. `Original Mix` contains vocals plus instruments and is not interchangeable with the vocal-only track.

Check stream count, metadata, defaults, duration and timestamp alignment with ffprobe. Decode representative audio from the second track and compare it with the separated vocal input; labels alone do not establish audio identity. Verify video decoding and representative rendered frames. Keep `karaoke-original.mp4` as a clearly identified intermediate, not the mixable deliverable.

Report output paths, validation, chosen encoder and material limitations. Do not rerun separation/alignment for color, background or font changes. A playback-volume adjustment belongs to the independent player, not this stage.
