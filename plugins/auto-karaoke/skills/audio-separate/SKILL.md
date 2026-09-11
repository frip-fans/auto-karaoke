---
name: audio-separate
description: Separate local music audio, MV or live video into synchronized instrumental and isolated vocal stems using the auto-karaoke CLI. Use for stem extraction even when no lyrics or karaoke video are needed.
---

# Audio separation

If the environment has not been checked, use `karaoke-setup` when available for read-only diagnostics. Missing dependencies are a reason to propose installation, not permission to install. Before creating an environment, obtaining the engine, installing/upgrading/removing packages, downloading models/fonts or changing system configuration, list the components, location and scope, ask whether to proceed, and wait for explicit approval. Apply the same rule when this skill is installed alone. An unchanged plan already explicitly approved need not be approved again; additional changes require fresh consent. If approval is declined or pending, use only existing capabilities.

Use the installed `auto-karaoke` CLI; do not rewrite separator inference. If unavailable, locate the user's auto-karaoke checkout and install its `.[separate]` extra into a task virtual environment. The skill does not include Python dependencies, GPU drivers or weights. Preserve the user's chosen model and existing external stems.

## Prepare a reusable task

Identify the exact source version and requested interval. Inspect its duration before setting `clip_duration_seconds`: the CLI default is only 30 seconds, not the full song. Keep generated files in a separate work directory. Minimal configuration (duration below is an example, not a default for all recordings):

```json
{
  "schema_version": 1,
  "source": "source.mp4",
  "clip_start_seconds": 0,
  "clip_duration_seconds": 30,
  "work_dir": "work"
}
```

Paths are relative to this configuration. No lyrics or font configuration is needed. For an already-running project, inspect current outputs first; preparing again can overwrite working stems. Use a new work directory when comparing models or source versions.

```bash
auto-karaoke --project /path/to/project.json prepare
auto-karaoke --project /path/to/project.json separate --model MDX23C-8KFFT-InstVoc_HQ.ckpt
```

MDX23C-InstVoc HQ is the tested project preference; the CLI's unspecified default remains a smaller MDX model. Model caches are local and the first use may download weights. Check for the selected cached model before invoking separation; if it is missing, include its download in the plan and obtain approval before executing the command. Check the actual model backend and GPU availability; PyTorch CUDA and ONNX providers are different execution paths. Do not install GPU packages merely because another backend uses them. CPU execution may be slow; report the actual device rather than claiming GPU usage.

## Deliver stems

Return `work/original.wav`, `work/instrumental.wav`, `work/vocals.wav` and available preparation/separation reports. Validate finite samples and matching duration, sample rate and time origin; provide representative excerpts for quality review when useful. `Vocals` means the separated vocal stem, never the complete original mix. Some instrumental leakage can remain.

Do not infer lyrics or singer identity here. A live version needs its own stems and timeline. If the user wants subtitles next, preserve the source offset and stem identity for that stage; do not force a karaoke workflow on a separation-only request.
