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


def video_encoding_args(project):
    """Explicit encoder selection; unavailable hardware fails instead of falling back."""
    encoder = project.config.get("video_encoder", "libx264")
    quality = project.config.get("video_quality", 20)
    if isinstance(quality, bool) or not isinstance(quality, int) or not 0 <= quality <= 51:
        raise ValueError("video_quality must be an integer between 0 and 51")
    if encoder == "libx264":
        return ["-c:v", encoder, "-preset", "fast", "-crf", quality, "-threads", project.threads]
    if encoder == "h264_nvenc":
        return ["-c:v", encoder, "-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", quality, "-b:v", 0]
    raise ValueError("video_encoder must be libx264 or h264_nvenc")


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


def combine_audio_tracks(project, instrumental_video, original_video, output, secondary_role='original_mix'):
    """Copy video/accompaniment and add synchronized original-mix or vocal audio."""
    import av
    instrumental_video, original_video, output = map(lambda p: Path(p).resolve(),
                                                     (instrumental_video, original_video, output))
    if output in {instrumental_video, original_video} or output in project.inputs:
        raise ValueError('Dual-audio output must differ from every input')
    infos = [inspect_media(p) for p in (instrumental_video, original_video)]
    if secondary_role not in {'original_mix', 'vocals'}:
        raise ValueError('Secondary audio role must be original_mix or vocals')
    if not infos[0]['has_video'] or not all(info['has_audio'] for info in infos) or abs(infos[0]['seconds'] - infos[1]['seconds']) > .05:
        raise ValueError('Audio track source videos must share the same duration')
    with av.open(str(original_video)) as container:
        copy_secondary = container.streams.audio[0].codec_context.name == 'aac'
    secondary_encoding = [] if copy_secondary else ['-c:a:1', 'aac', '-b:a:1', '192k']
    secondary_name = 'Vocals' if secondary_role == 'vocals' else 'Original Mix'
    output.parent.mkdir(parents=True, exist_ok=True)
    elapsed = run_ffmpeg(project, ['-i', instrumental_video, '-i', original_video,
        '-map', '0:v:0', '-map', '0:a:0', '-map', '1:a:0', '-c', 'copy', *secondary_encoding,
        '-disposition:a:0', 'default', '-disposition:a:1', '0',
        '-metadata:s:a:0', 'title=Instrumental', '-metadata:s:a:0', 'handler_name=Instrumental',
        '-metadata:s:a:1', 'title=' + secondary_name, '-metadata:s:a:1', 'handler_name=' + secondary_name,
        '-metadata:s:a:0', 'language=und', '-metadata:s:a:1', 'language=und',
        '-movflags', '+faststart', output], 'dual-audio.log')
    with av.open(str(output)) as container:
        if len(container.streams.video) != 1 or len(container.streams.audio) != 2:
            raise ValueError('Expected exactly one video and two audio streams')
        tracks = [{'stream_index': stream.index, 'role': role,
                   'start_seconds': float(stream.start_time * stream.time_base) if stream.start_time is not None else None,
                   'sample_rate': stream.codec_context.sample_rate,
                   'default': role == 'instrumental'}
                  for stream, role in zip(container.streams.audio, ('instrumental', secondary_role))]
    return {'processing_seconds': elapsed, 'video_stream_copied': True, 'instrumental_stream_copied': True,
            'audio_streams_copied': copy_secondary, 'secondary_audio_encoded': not copy_secondary, 'audio_tracks': tracks}


def render(project):
    encoding = video_encoding_args(project)
    width, height = project.config.get('render_width', 1280), project.config.get('render_height', 720)
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 2 or v % 2 for v in (width, height)):
        raise ValueError('Render width and height must be positive even integers')
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
    background = project.config.get('background_image')
    if background:
        background = project.resolve(background)
        if not background.is_file():
            raise ValueError('background_image does not exist')
        inputs = ['-loop', 1, '-framerate', 24, '-i', background]
    elif info["has_video"]:
        inputs = ["-threads", project.threads, "-ss", project.start, "-i", project.source]
    else:
        inputs = ["-f", "lavfi", "-i", f"color=c=0x101827:s={width}x{height}:r=24"]
    original = project.output("karaoke-original.mp4")
    vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,ass=karaoke.ass:fontsdir=fonts"
    elapsed = run_ffmpeg(project, [*inputs, "-i", project.output("original.wav"), "-map", "0:v:0", "-map", "1:a:0",
                                  "-t", project.duration, "-vf", vf, *encoding,
                                  "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                                  "-movflags", "+faststart", original], "render.log")
    report = {"original": inspect_media(original), "render_seconds": elapsed,
              "video_encoder": project.config.get("video_encoder", "libx264"),
              "video_quality": project.config.get("video_quality", 20),
              "background_image": str(background) if background else None,
              "subtitle_renderer": "libass (CPU)"}
    instrumental = project.output("instrumental.wav")
    if instrumental.exists():
        report["instrumental"] = replace_audio(project, original, instrumental,
                                               project.output("karaoke-instrumental.mp4"), project.start, project.start)
        if project.config.get('dual_audio', False):
            role = project.config.get('dual_audio_source', 'vocals')
            secondary = project.output('vocals.wav') if role == 'vocals' else original
            report['dual_audio'] = combine_audio_tracks(project, project.output('karaoke-instrumental.mp4'),
                                                       secondary, project.output('karaoke-dual-audio.mp4'), secondary_role=role)
    write_json(project.output("render-report.json"), report)
