"""Small, explicit stages for local karaoke previews."""
import argparse
import json
import platform
import subprocess

from .project import Project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Project JSON; relative paths resolve beside this file")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor").add_argument("--ml", action="store_true", help="Also inspect installed ML backends without downloading models")
    for name in ("prepare", "align", "subtitles", "render"):
        commands.add_parser(name)
    for name in ("emit", "transcribe"):
        commands.add_parser(name).add_argument("--offline", action="store_true")
    commands.add_parser("separate").add_argument("--model", default="UVR-MDX-NET-Inst_HQ_3.onnx")
    replace = commands.add_parser("replace-audio")
    replace.add_argument("--video", required=True)
    replace.add_argument("--audio", required=True)
    replace.add_argument("--output", required=True)
    replace.add_argument("--audio-origin", type=float, default=0, help="Source timeline time corresponding to audio sample zero")
    args = parser.parse_args()
    try:
        project = Project(args.project)
        if args.command == "doctor":
            filters = subprocess.check_output([project.ffmpeg, "-hide_banner", "-filters"], text=True, stderr=subprocess.STDOUT)
            from .subtitles import ass_font_scale
            font_scale = ass_font_scale(project.font) if project.font and project.font.is_file() else None
            report = {"platform": platform.platform(), "python": platform.python_version(), "ffmpeg": project.ffmpeg,
                              "ass_filter": any(line.split()[1:2] == ["ass"] for line in filters.splitlines()),
                              "font_present": font_scale is not None, "font_metric_factor": font_scale}
            if args.ml:
                for name in ("torch", "ctranslate2", "onnxruntime"):
                    try:
                        module = __import__(name)
                        if name == "torch":
                            report[name] = {"version": module.__version__, "cuda_available": module.cuda.is_available(),
                                            "gpu": module.cuda.get_device_name(0) if module.cuda.is_available() else None}
                        elif name == "ctranslate2":
                            report[name] = {"version": module.__version__, "cuda_devices": module.get_cuda_device_count()}
                        else:
                            report[name] = {"version": module.__version__, "providers": module.get_available_providers()}
                    except (ImportError, RuntimeError, OSError) as exc:
                        report[name] = {"unavailable": str(exc)}
            print(json.dumps(report, indent=2))
        elif args.command in ("prepare", "render"):
            from . import media
            getattr(media, args.command)(project)
        elif args.command == "replace-audio":
            from .media import replace_audio
            replace_audio(project, project.resolve(args.video), project.resolve(args.audio), project.resolve(args.output),
                          project.start, args.audio_origin)
        elif args.command in ("emit", "transcribe", "separate"):
            from . import ml
            if args.command == "separate":
                ml.separate(project, args.model)
            else:
                getattr(ml, args.command)(project, offline=args.offline)
        elif args.command == "align":
            from .alignment import align
            align(project)
        elif args.command == "subtitles":
            from .subtitles import subtitles
            subtitles(project)
    except (ValueError, FileNotFoundError, ImportError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"{args.command} failed: {exc}\nCheck the project configuration, optional dependencies and work/*.log.\n")
