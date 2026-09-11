---
name: karaoke-author
description: Create and review Japanese karaoke lyrics, kanji readings, word or mora timing and singer annotations from supplied lyrics and vocal stems. Use for lyric authoring or correcting alignment, including English passages and live versions.
---

# Karaoke authoring

If the environment has not been checked, use `karaoke-setup` when available for read-only diagnostics. Missing dependencies are a reason to propose installation, not permission to install. Before creating an environment, obtaining the engine, installing/upgrading/removing packages, downloading models/fonts or changing system configuration, list the components, location and scope, ask whether to proceed, and wait for explicit approval. Apply the same rule when this skill is installed alone. An unchanged plan already explicitly approved need not be approved again; additional changes require fresh consent. If approval is declined or pending, use only existing capabilities.

Use `auto-karaoke` for model inference, alignment and validation. This skill contributes review decisions and workflow orchestration, not invented acoustic timestamps. Read [the current file contract and commands](references/workflow.md) when preparing or modifying a project.

Start from existing source lyrics and synchronized stems, including stems from other tools. Confirm the recording version: album, edited MV and live performances can have different words and ordering. ASR is an optional draft; do not replace supplied authoritative lyrics with an unreviewed transcription.

## Review loop

- Preserve stable line/token IDs and existing human corrections. Identify textual differences, ambiguous readings, suspicious timing and unknown singers separately so a change in one does not erase the rest.
- Distinguish displayed text from pronunciation. Japanese uses mora timing; English uses word timing and visible word spaces. Do not use uniform word lengths as a substitute for acoustic evidence.
- Check kanji readings against surrounding kana. Rendering puts ruby over kanji only; do not add duplicate readings over kana. Unusual sung readings require contextual evidence or human confirmation.
- Use acoustic alignment for starts and durations. Review repeated choruses, held syllables, inserted material, missing words and live improvisation. The CLI `emit` stage accepts at most 60 seconds; splitting and merging full songs is not yet a built-in general command. Preserve offsets when working in sections.
- Keep uncertain singer identity unknown. A known opening singer is a reference, not proof for all following lines. Similarity to two voices does not establish duet. Support user-defined singer profiles and colors; the bundled fripSide names are presets, not mandatory participants.
- Use original audio for beat context and inspect entrance cues. The project's countdown has three dots followed by an empty interval before singing, each interval at least one second.

Present unresolved points with line IDs and timestamps so the user can audit the relevant excerpts. AI suggestions are editable candidates. When cloud transcription is requested, use the configured provider only within the user's authorized data-sharing scope; the skill itself requires no cloud API and contains no credentials.

## Handoff

Provide the updated lyrics, timing, overrides, singer map and beat file with an explicit account of what was reviewed and what remains uncertain. Structural validation passing does not mean a human approved the content. Current files have no enforced `approved` state and no unified `karaoke.json` export: do not claim either exists.

A preview can be generated with the render skill to inspect appearance, followed by targeted corrections here. Keep production rendering separate from new semantic judgments.
