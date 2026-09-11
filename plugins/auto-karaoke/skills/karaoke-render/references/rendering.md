# Current render inputs

The core CLI must be installed separately. Basic Python dependencies plus FFmpeg with `ass` and `libx264` support are sufficient for rendering precomputed data. `.[rhythm]` is only needed if beats must still be calculated.

The project references original `source`, `lyrics`, `work_dir`, clip start/duration, `font_path` and `font_family`. The work directory contains synchronized `original.wav`, `instrumental.wav`, `vocals.wav`, `timing.json`, and applicable beat/singer/override files. Current code merges review files during `subtitles`; a standalone frozen subtitle bundle remains a planned interface.

Useful settings:

| Setting | Meaning |
| --- | --- |
| `background_image` | Optional static background; absent means retain source video or use a plain background for audio-only sources |
| `render_width`, `render_height` | Positive even dimensions; defaults 1280 × 720 |
| `video_encoder` | `libx264` (default) or `h264_nvenc` |
| `video_quality` | Integer 0–51, default 20; CRF or CQ depending on encoder, not equivalent quality across encoders |
| `subtitle_font_scale` | Default 1.2 |
| `subtitle_outline`, `ruby_outline` | Default 4 and 2.2 |
| `show_preview_label` | Set false for final delivery if the draft label is unwanted |
| `singer_colors_enabled`, `singer_map` | Enable reviewed singer colors and map location |
| `intro_card` | Title metadata: `title`, `artist`, `album`, `vocals`, `seconds` |
| `outro_card` | End title card; may set `seconds` separately |
| `dual_audio`, `dual_audio_source` | Use true and `vocals` for the mixable output |

Ten-second title cards overlay the existing timeline and do not append 20 seconds to the media. Countdown stages follow beat-derived spacing with a final empty interval before entry; no countdown enable/disable switch is currently provided. Use a matching `countdown.beats_file` when supplying already-reviewed beats.

Current working outputs include `karaoke.ass`, `layout.json`, `karaoke-original.mp4`, `karaoke-instrumental.mp4`, optionally `karaoke-dual-audio.mp4`, and render reports. Keep media and reports local; portable player libraries should import the final MP4, not the entire working directory.
