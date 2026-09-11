# auto-karaoke

[中文](README.md) · **English** · [日本語](README.ja.md)

Create Japanese karaoke videos with audio separation, lyric alignment, kanji readings, word/mora highlighting, and singer colors. Export MP4 files with separate instrumental and isolated-vocal tracks.

## Samples

Japanese readings, alternating lyric rows, and singer labels:

![Japanese karaoke subtitles and singer colors](docs/images/sample-japanese.jpg)

<details>
<summary>Title card and English lyrics</summary>

![Opening title card](docs/images/sample-title.jpg)

![English karaoke lyrics over the original video](docs/images/sample-english.jpg)

</details>

[Sample sources](docs/images/README.md)

| Skill | Purpose |
| --- | --- |
| `karaoke-setup` | Check the environment; install or repair dependencies with your approval |
| `audio-separate` | Separate instrumental and vocal stems from audio or video |
| `karaoke-author` | Create and review lyric readings and timing |
| `karaoke-render` | Render videos from subtitle data and audio stems |

The player is a separate project: [auto-karaoke-player](https://github.com/frip-fans/auto-karaoke-player).

## Installation

Using Claude Code? See the [plugin installation instructions](plugins/auto-karaoke/README.md#claude-code). You can also follow the [manual CLI installation guide](docs/manual-install.md) (Chinese) to run the tools directly from your terminal.

You need a computer that runs Codex, available disk space, and internet access for the initial installation. Production uses Python 3.11+, FFmpeg, and a Japanese font for subtitle rendering. An NVIDIA GPU is recommended for separation and alignment; CPU execution is possible but slower. The plugin checks your hardware and the backend required by the selected model.

Install the plugin from this repository's root directory. You do not need to set up Python first:

```bash
codex plugin marketplace add .
codex plugin add auto-karaoke@frip-fans
```

Start a new Codex session:

```text
$karaoke-setup Check my computer and tell me what I need to install for audio separation.
```

Codex can run read-only checks first. Before installing dependencies, creating an environment, or downloading models, it lists the proposed changes and locations and asks for your explicit approval. The production skills follow the same rule.

## Usage

```text
$audio-separate Separate this music video into instrumental and vocals using MDX23C.
$karaoke-author Build a timeline from my lyrics and stems, and flag anything I need to review.
$karaoke-render Render a 1080p video using the reviewed timeline and background.png.
```

You can also use the `auto-karaoke` CLI directly; see [commands and subtitle options](docs/production.md) (Chinese). Lyrics and readings need human review. The acoustic alignment command currently supports clips of up to 60 seconds per run.

For dual-track output, set `dual_audio: true` and `dual_audio_source: "vocals"`: the first track is `Instrumental`, and the second is isolated `Vocals`.

[Plugin installation](plugins/auto-karaoke/README.md) (Chinese) · [Lyric annotator](tools/lyric-annotator.html)

## License

[GPLv3](LICENSE) (`GPL-3.0-only`). Third-party dependencies and model weights retain their own licenses. Third-party artwork and lyrics in the sample screenshots are not covered by the project's code license.
