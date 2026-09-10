"""Optional model stages. Imports and downloads happen only when called."""
import hashlib
import logging
import math
from pathlib import Path
import shutil
import sys
import time

from .project import write_json

ALIGNER = "NextFire/mms-300m-ForcedAligner-karaoke-ja-Latn"
ALIGNER_REVISION = "2ab2b5f46539ee284703c281f286b01d2410ee12"
MDX_MODEL = "UVR-MDX-NET-Inst_HQ_3.onnx"


def peak_rss_mib():
    try:
        import resource
    except ImportError:
        return None  # Windows has no stdlib resource module.
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / (1024 ** 2 if sys.platform == "darwin" else 1024)


def choose_device(requested, cuda_available):
    if requested not in {"auto", "cpu", "cuda"}:
        raise ValueError("Device must be auto, cpu or cuda")
    if requested == "cuda" and not cuda_available:
        raise ValueError("CUDA requested but unavailable; check GPU driver and this backend's dependencies")
    return ("cuda" if cuda_available else "cpu") if requested == "auto" else requested


def emit(project, offline=False):
    if project.duration > 60:
        raise ValueError("This prototype aligns clips of at most 60 seconds; split long songs first")
    project.model_environment()
    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly
    import torch
    from transformers import AutoModelForCTC, AutoProcessor
    torch.set_num_threads(project.threads)
    device = choose_device(project.config.get("align_device", "auto"), torch.cuda.is_available())
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    ref = project.config.get("aligner", ALIGNER)
    options = {"local_files_only": offline}
    if ref == ALIGNER:
        options["revision"] = ALIGNER_REVISION
    processor = AutoProcessor.from_pretrained(ref, **options)
    model = AutoModelForCTC.from_pretrained(ref, **options).to(device).eval()
    loaded = time.perf_counter()
    source = project.output("vocals.wav")
    wav, rate = sf.read(source, dtype="float32", always_2d=True)
    if abs(len(wav) / rate - project.duration) > 0.01 or not np.isfinite(wav).all():
        raise ValueError("Vocals must be finite and match the project duration")
    divisor = math.gcd(16000, rate)
    mono = resample_poly(wav.mean(axis=1), 16000 // divisor, rate // divisor)
    inputs = processor(mono, sampling_rate=16000, return_tensors="pt")
    inputs = {key: value.to(device) for key, value in inputs.items()}
    with torch.inference_mode():
        logits = model(**inputs).logits[0]
        emissions = logits.log_softmax(-1).cpu().numpy()
    np.save(project.output("emissions.npy"), emissions)
    report = {"model": ref, "revision": options.get("revision"), "device": device, "dtype": "float32",
              "model_parameter_count": sum(p.numel() for p in model.parameters()),
              "seconds": len(mono) / 16000, "source_offset_seconds": project.start,
              "vocals_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "frame_stride_seconds": math.prod(model.config.conv_stride) / 16000,
              "blank_id": model.config.pad_token_id, "vocab": processor.tokenizer.get_vocab(),
              "load_seconds": loaded - started, "inference_seconds": time.perf_counter() - loaded,
              "peak_rss_mib": peak_rss_mib(),
              "peak_cuda_allocated_mib": torch.cuda.max_memory_allocated() / 1024 ** 2 if device == "cuda" else None}
    write_json(project.output("emissions-report.json"), report)


def transcribe(project, offline=False):
    project.model_environment()
    import ctranslate2
    from faster_whisper import WhisperModel
    device = choose_device(project.config.get("transcribe_device", "auto"), ctranslate2.get_cuda_device_count() > 0)
    compute_type = "float16" if device == "cuda" else "int8"
    started = time.perf_counter()
    model = WhisperModel("small", device=device, compute_type=compute_type, cpu_threads=project.threads,
                         num_workers=1, download_root=str(project.cache / "whisper"), local_files_only=offline)
    loaded = time.perf_counter()
    segments, _ = model.transcribe(str(project.output("vocals.wav")), language="ja", beam_size=5,
                                   vad_filter=False, word_timestamps=True, condition_on_previous_text=False, temperature=0)
    rows = [{"start": s.start, "end": s.end, "text": s.text,
             "words": [{"start": w.start, "end": w.end, "word": w.word, "probability": w.probability}
                       for w in s.words or []]} for s in segments]
    write_json(project.output("asr-draft.json"), {"status": "draft_needs_review", "model": "faster-whisper small",
               "device": device, "compute_type": compute_type,
               "source_offset_seconds": project.start, "segments": rows, "load_seconds": loaded - started,
               "inference_seconds": time.perf_counter() - loaded, "peak_rss_mib": peak_rss_mib()})


def separate(project, model_name=MDX_MODEL):
    if Path(model_name).name != model_name:
        raise ValueError("Separator model must be a catalog filename")
    project.model_environment()
    import numpy as np
    import soundfile as sf
    import torch
    from audio_separator.separator import Separator
    torch.set_num_threads(project.threads)
    source = project.output("original.wav")
    duration = sf.info(source).duration
    outdir = project.output("separated")
    outdir.mkdir(exist_ok=True)
    separator = Separator(log_level=logging.INFO, model_file_dir=str(project.cache / "separator"),
                          output_dir=str(outdir), output_format="WAV", use_soundfile=True, normalization_threshold=0.9,
                          mdx_params={"hop_length": 1024, "segment_size": 256, "overlap": 0.25, "batch_size": 1, "enable_denoise": False},
                          mdxc_params={"segment_size": 256, "override_model_segment_size": False, "batch_size": 1,
                                       "overlap": None, "pitch_shift": 0})
    started = time.perf_counter()
    separator.load_model(model_name)
    loaded = time.perf_counter()
    names = separator.separate(str(source))
    separated = time.perf_counter()
    found = {}
    for name in names:
        path = Path(name)
        if not path.is_absolute():
            path = outdir / path
        label = path.name.casefold()
        kind = "vocals" if "(vocals)" in label else "instrumental" if "(instrumental)" in label else None
        if kind is None or kind in found:
            raise ValueError("Expected a two-stem vocals/instrumental model")
        data, rate = sf.read(path, always_2d=True)
        if not np.isfinite(data).all() or abs(len(data) / rate - duration) > 0.01:
            raise ValueError("Invalid separator output")
        found[kind] = path
    if set(found) != {"vocals", "instrumental"}:
        raise ValueError("Separator did not produce both required stems")
    for kind, path in found.items():
        shutil.copyfile(path, project.output(kind + ".wav"))
    write_json(project.output("separation-report.json"), {"model": model_name, "device": str(separator.torch_device),
               "onnx_providers": separator.onnx_execution_provider, "load_seconds": loaded - started,
               "separation_seconds": separated - loaded, "rtf": (separated - loaded) / duration,
               "peak_rss_mib": peak_rss_mib()})
