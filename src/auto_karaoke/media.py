"""FFmpeg stages; all timeline offsets refer to the original source."""
from pathlib import Path
import math
import shutil
import subprocess
import time

from .project import write_json


def run_ffmpeg(project, args, log_name):
    started = time.perf_counter()
    with project.output(log_name).open("w", encoding="utf-8") as log:
        subprocess.run([project.ffmpeg, "-hide_banner", "-nostdin", "-y", *map(str, args)], check=True,
                       stdout=log, stderr=subprocess.STDOUT, cwd=project.work)
    return time.perf_counter() - started


def inspect_media(path):
    import av
    with av.open(str(path)) as container:
        duration = container.duration / av.time_base if container.duration is not None else None
        video = container.streams.video[0] if container.streams.video else None
        return {"seconds": duration, "has_audio": bool(container.streams.audio), "has_video": video is not None,
                "width": video.width if video else None, "height": video.height if video else None}


def check_coverage(duration, offset, requested):
    if duration is None or not all(math.isfinite(n) for n in (duration, offset, requested)):
        raise ValueError("Media duration and offsets must be finite")
    if offset < 0 or requested <= 0 or offset + requested > duration + 0.05:
        raise ValueError(f"Audio/video does not cover interval {offset:.3f}–{offset + requested:.3f}s (duration {duration:.3f}s)")


def extract(project, source, offset, name):
    import soundfile as sf
    source = Path(source).resolve()
    info = inspect_media(source)
    if not info["has_audio"]:
        raise ValueError("Input has no audio stream")
    check_coverage(info["seconds"], offset, project.duration)
    target = project.output(name + ".wav")
    run_ffmpeg(project, ["-ss", offset, "-i", source, "-map", "0:a:0", "-t", project.duration,
                        "-ac", 2, "-ar", 44100, "-c:a", "pcm_f32le", target], name + "-extract.log")
    if abs(sf.info(target).duration - project.duration) > 0.05:
        raise ValueError("Extracted audio duration differs from the requested clip")
    return target


def prepare(project):
    report = {"source_offset_seconds": project.start, "seconds": project.duration, "stems": {}}
    extract(project, project.source, project.start, "original")
    for name in ("vocals", "instrumental"):
        stem = project.config.get(name)
        if stem:
            origin = float(stem.get("origin_seconds", 0))
            extract(project, project.resolve(stem["path"]), project.start - origin, name)
            report["stems"][name] = {"origin_seconds": origin, "imported": True}
    write_json(project.output("prepare-report.json"), report)


def replace_audio(project, video, audio, output, clip_start, audio_origin):
    import soundfile as sf
    video, audio, output = (Path(p).resolve() for p in (video, audio, output))
    if output in (video, audio) or output in project.inputs:
        raise ValueError("Output must differ from every input")
    if output.with_suffix(".json") in (video, audio) or output.with_suffix(".json") in project.inputs:
        raise ValueError("Report would overwrite an input")
    info = inspect_media(video)
    if not info["has_video"]:
        raise ValueError("Replacement input needs a video stream")
    duration = info["seconds"]
    offset = clip_start - audio_origin
    check_coverage(sf.info(audio).duration, offset, duration)
    output.parent.mkdir(parents=True, exist_ok=True)
    elapsed = run_ffmpeg(project, ["-i", video, "-ss", offset, "-i", audio, "-map", "0:v:0", "-map", "1:a:0",
                                  "-t", duration, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                                  "-movflags", "+faststart", output], "replace-audio.log")
    report = {**inspect_media(output), "source_clip_start_seconds": clip_start,
              "audio_origin_seconds": audio_origin, "audio_seek_seconds": offset,
              "video_stream_copied": True, "processing_seconds": elapsed}
    write_json(output.with_suffix(".json"), report)
    return report


def render(project):
    if project.font is None or not project.font.is_file():
        raise ValueError("Set font_path before rendering")
    if not project.output("karaoke.ass").is_file():
        raise ValueError("Run subtitles before rendering")
    # Fixed relative names keep arbitrary user paths out of FFmpeg filter syntax.
    fonts = project.output("fonts")
    fonts.mkdir(exist_ok=True)
    font_copy = project.output("fonts/selected" + project.font.suffix.lower())
    if font_copy != project.font:
        shutil.copyfile(project.font, font_copy)
    info = inspect_media(project.source)
    check_coverage(info["seconds"], project.start, project.duration)
    if info["has_video"]:
        inputs = ["-threads", project.threads, "-ss", project.start, "-i", project.source]
    else:
        inputs = ["-f", "lavfi", "-i", "color=c=0x101827:s=1280x720:r=24"]
    original = project.output("karaoke-original.mp4")
    vf = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,ass=karaoke.ass:fontsdir=fonts"
    elapsed = run_ffmpeg(project, [*inputs, "-i", project.output("original.wav"), "-map", "0:v:0", "-map", "1:a:0",
                                  "-t", project.duration, "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", 20,
                                  "-threads", project.threads, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                                  "-movflags", "+faststart", original], "render.log")
    report = {"original": inspect_media(original), "render_seconds": elapsed}
    instrumental = project.output("instrumental.wav")
    if instrumental.exists():
        report["instrumental"] = replace_audio(project, original, instrumental,
                                               project.output("karaoke-instrumental.mp4"), project.start, project.start)
    write_json(project.output("render-report.json"), report)
