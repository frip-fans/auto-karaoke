---
name: karaoke-setup
description: Check a computer's suitability for auto-karaoke and propose task-specific environment setup; install or repair dependencies only with explicit user authorization. Use for first-time setup, missing dependencies, GPU/backend errors or deciding whether separation, alignment or rendering can run locally.
---

# Set up auto-karaoke

Help the user assess their environment first. Infer the requested stage from the task and existing artifacts. Detection may run automatically; setup must wait for explicit user authorization.

## Obtain authorization before changing the environment

Read-only checks may run without installation approval. Before creating a virtual environment, cloning/downloading the production engine, installing/upgrading/removing packages, downloading models or fonts, or changing drivers, PATH or persistent configuration:

1. Present a concrete plan: components and purpose, target environment/path, whether the change is project-local or system-wide, downloads and approximate size if known, and any replacement of existing software. State unknown download sizes rather than inventing them.
2. Ask a direct question, for example: "I propose creating `.venv` here and installing the separation dependencies and MDX23C model. FFmpeg is already available. May I proceed with this installation?"
3. Wait for an affirmative reply approving that plan. Invoking a production skill, asking whether the machine is suitable, or broadly asking to set up karaoke does not authorize unspecified installation. A pre-existing explicit approval covering the same components, location and changes remains valid; do not ask again for unchanged scope.
4. Execute only the approved plan. New dependencies, another environment, driver/system changes or replacement of existing packages outside that plan require a new explanation and approval. Do not treat silence, a tool's technical permission, or an installation failure as consent to a broader workaround.

If the user declines or has not replied, continue only read-only checks or work supported by existing dependencies. Report what remains unavailable. Never trigger a model's first-run download as a way around the installation question.

## Inspect before installing

Run the bundled standard-library diagnostic with an available Python interpreter:

```bash
python3 /path/to/this/skill/scripts/check_environment.py --stage separate --workspace /path/to/workspace
```

Stages are `base`, `separate`, `align`, `transcribe`, `rhythm`, `render`. Once the target virtual environment exists, rerun using **that environment's Python**, adding `--backends` for model tasks or `--encoder libx264` / `--encoder h264_nvenc` for an encoder smoke test. `--font /path/to/font.ttf` checks a single-font file header; visual glyph coverage and family matching still need a preview.

The diagnostic does not install anything, download models or require a project/lyrics file. If Python itself is missing, inspect the OS, package manager and GPU with available shell tools before installing Python. An unsuccessful command means that capability is unverified, not that the computer is incapable.

Interpret the evidence by stage:

- Core production needs Python 3.11+ (3.12 preferred), FFmpeg and a writable workspace. First installation and model download require network access; cached models can later be used offline.
- Rendering needs FFmpeg `ass`, a working `libx264` or explicitly selected NVENC encoder, and a Japanese single TTF/OTF font. TTC collections are unsupported. Core rendering does not require PyTorch; rhythm analysis additionally needs librosa if a beat file is missing.
- NVIDIA is the tested acceleration path. MDX23C/RoFormer and alignment use PyTorch; MDX ONNX models use ONNX Runtime; ASR uses CTranslate2. Check the selected backend, not just `nvidia-smi`. Do not install both ONNX Runtime CPU and GPU distributions into the same environment.
- The production device selector supports CPU/CUDA; do not promise Apple MPS, ROCm or VideoToolbox support. macOS can use CPU paths; the independent player requires no production models.
- GPU encoding being listed by FFmpeg does not prove the driver works: use the synthetic encoder test. CUDA visibility does not prove a particular model fits VRAM: verify with a short task-specific sample after installation.
- Report free disk space and actual GPU memory. The project's 12 GB NVIDIA test machine is a tested example, not a universal minimum. Avoid invented fixed RAM/VRAM guarantees; model, clip length and other running jobs matter.

## Install the approved plan

Locate the core checkout containing `pyproject.toml` and `src/auto_karaoke`. An installed plugin cache only contains instructions and helpers, **not the production engine**. Use an existing checkout when available; otherwise include obtaining `https://github.com/frip-fans/auto-karaoke.git` in the installation plan and proceed only after approval, using the user's available access. Do not assume the repository is public or install an unrelated same-name PyPI package.

Create/reuse a project virtual environment. Invoke its interpreter explicitly so later commands do not accidentally use another Python:

```bash
python3 -m venv /path/to/checkout/.venv
/path/to/checkout/.venv/bin/python -m pip install -e /path/to/checkout
```

On Windows use `.venv\Scripts\python.exe`. Preserve working environments and existing task files. If Linux lacks ensurepip, use the distribution's matching venv package or an already available pip that can target the new environment; do not install into system Python to bypass the issue.

Choose extras: `separate` for separation, `align` for emissions, `transcribe` only for ASR, `rhythm` for missing beat analysis. Example: `python -m pip install -e '/path/to/checkout[separate]'`. Installing all extras by default wastes downloads and may introduce backend conflicts. For GPU-specific wheels/libraries, consult the current official PyTorch, ONNX Runtime, audio-separator or CTranslate2 instructions for the detected OS and driver; do not reuse a remembered CUDA installation command blindly.

Use the platform's available package manager for Python/FFmpeg (for example Homebrew on macOS, the detected Linux package manager, or an existing Windows installation). Check actual FFmpeg filters/encoders afterward. Driver replacement and OS-level changes are separate from a project venv: explain any necessary system change and follow the host's permissions. Authorization must cover the concrete plan above; approval for project-local packages does not also approve system packages or driver changes.

Find installed Japanese fonts before fetching another. Confirm family and glyph coverage with the renderer. Keep font files and model weights outside Git. Do not install or select an unrelated language font merely to pass a path check.

## Verify and continue

Rerun diagnostics in the chosen environment, run `python -m pip check`, and verify `auto-karaoke --help`. Test only the selected backend with a short sample when model execution is needed. Existing approved timing can go straight to a synthetic/render preview without loading ASR models. Never rerun or overwrite real work just to test setup.

Summarize the usable stages, interpreter/CLI path, selected CPU/GPU backend and any concrete remaining blocker. Distinguish installed, importable and actually exercised components. Save reusable local configuration where the task expects it, then continue the original separation/authoring/render request. Model quality, lyric correctness and singer identity are not environment checks.
