"""Read-only diagnostics; no model downloads, installations or project files required."""
import argparse
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

PACKAGES = {
    'base': ['numpy', 'Pillow', 'soundfile', 'av', 'pykakasi'],
    'separate': ['audio-separator', 'torch', 'onnxruntime'],
    'align': ['torch', 'transformers', 'scipy'],
    'transcribe': ['faster-whisper', 'ctranslate2'],
    'rhythm': ['librosa'],
    'render': [],
}


def run(args, timeout=20):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {'ok': result.returncode == 0, 'returncode': result.returncode,
                'output': (result.stdout + result.stderr).strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'ok': False, 'output': str(exc)}


def versions(stage):
    result = {}
    for name in dict.fromkeys(PACKAGES['base'] + PACKAGES[stage] + ['auto-karaoke']):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            # Both distributions expose the onnxruntime module; never install both.
            if name == 'onnxruntime':
                try:
                    result[name] = importlib.metadata.version('onnxruntime-gpu') + ' (GPU distribution)'
                    continue
                except importlib.metadata.PackageNotFoundError:
                    pass
            result[name] = None
    return result


def backend_check(stage):
    snippets = {
        'separate': "import torch, onnxruntime as ort; print({'torch_cuda': torch.cuda.is_available(), 'onnx_providers': ort.get_available_providers()})",
        'align': "import torch; print({'torch_cuda': torch.cuda.is_available(), 'torch_version': torch.__version__})",
        'transcribe': "import ctranslate2; print({'cuda_devices': ctranslate2.get_cuda_device_count()})",
    }
    if stage not in snippets:
        return None
    return run([sys.executable, '-c', snippets[stage]], timeout=45)


def collect(stage, workspace, font=None, backends=False, encoder=None):
    workspace = Path(workspace).expanduser().resolve()
    if not workspace.is_dir():
        raise ValueError('workspace must be an existing directory')
    ffmpeg = shutil.which('ffmpeg')
    packages = versions(stage)
    result = {'stage': stage, 'system': platform.system(), 'release': platform.release(),
              'architecture': platform.machine(), 'python': sys.version.split()[0],
              'python_executable': sys.executable, 'python_supported': sys.version_info >= (3, 11),
              'in_virtualenv': sys.prefix != sys.base_prefix,
              'pip_available': importlib.util.find_spec('pip') is not None,
              'ensurepip_available': importlib.util.find_spec('ensurepip') is not None,
              'workspace': str(workspace), 'workspace_writable': os.access(workspace, os.W_OK),
              'free_disk_gib': round(shutil.disk_usage(workspace).free / 1024**3, 2),
              'ffmpeg': ffmpeg, 'ffprobe': shutil.which('ffprobe'), 'packages': packages,
              'missing_packages': [name for name, value in packages.items() if value is None]}
    if ffmpeg:
        filters = run([ffmpeg, '-hide_banner', '-filters'])
        encoders = run([ffmpeg, '-hide_banner', '-encoders'])
        result['ffmpeg_filters_ok'] = filters['ok']
        result['ass_filter'] = filters['ok'] and any(line.split()[1:2] == ['ass'] for line in filters['output'].splitlines())
        result['compiled_encoders'] = {name: encoders['ok'] and any(line.split()[1:2] == [name] for line in encoders['output'].splitlines()) for name in ('libx264', 'h264_nvenc')}
        if encoder:
            result['encoder_smoke_test'] = run([ffmpeg, '-v', 'error', '-nostdin', '-f', 'lavfi', '-i',
                'color=c=black:s=64x64:r=1:d=1', '-frames:v', '1', '-an', '-c:v', encoder, '-f', 'null', '-'])
    nvidia = shutil.which('nvidia-smi')
    result['nvidia'] = run([nvidia, '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader']) if nvidia else None
    if font:
        path = Path(font).expanduser().resolve()
        valid = path.is_file() and path.suffix.lower() in {'.ttf', '.otf'}
        if valid:
            with path.open('rb') as stream:
                valid = stream.read(4) in {b'\x00\x01\x00\x00', b'OTTO', b'true'}
        result['font'] = {'path': str(path), 'single_font_header_valid': valid}
    if backends:
        result['backend_import'] = backend_check(stage)
    # No global "ready" boolean: imports, driver visibility and actual model execution differ.
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=PACKAGES, default='base')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--font')
    parser.add_argument('--backends', action='store_true', help='Import the selected backend in an isolated process')
    parser.add_argument('--encoder', choices=['libx264', 'h264_nvenc'], help='Test encoding one synthetic frame')
    args = parser.parse_args()
    try:
        print(json.dumps(collect(args.stage, args.workspace, args.font, args.backends, args.encoder), ensure_ascii=False, indent=2))
    except ValueError as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
