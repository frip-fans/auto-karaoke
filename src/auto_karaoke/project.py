"""Paths and timeline conventions shared by every stage."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import shutil


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


class Project:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.config = read_json(self.path)
        if self.config.get("schema_version") != 1:
            raise ValueError("Project schema_version must be 1")
        self.root = self.path.parent
        self.work = self.resolve(self.config.get("work_dir", "work"))
        self.source = self.resolve(self.config["source"])
        self._lyrics = self.resolve(self.config["lyrics"]) if self.config.get("lyrics") else None
        self.start = float(self.config.get("clip_start_seconds", 0))
        self.duration = float(self.config.get("clip_duration_seconds", 30))
        if not math.isfinite(self.start) or self.start < 0 or not math.isfinite(self.duration) or self.duration <= 0:
            raise ValueError("Clip start must be nonnegative and duration must be positive")
        self.threads = int(self.config.get("threads", 4))
        if self.threads < 1:
            raise ValueError("threads must be positive")
        self.font = self.resolve(self.config["font_path"]) if self.config.get("font_path") else None
        self.font_family = self.config.get("font_family", "IPAGothic")
        if not self.font_family or any(c in self.font_family for c in ",\r\n"):
            raise ValueError("Invalid ASS font family")
        self.work.mkdir(parents=True, exist_ok=True)
        self.cache = self.work / "cache"
        self.cache.mkdir(exist_ok=True)
        # Output paths may never collide with an input/configuration file.
        self.inputs = {self.path, self.source}
        if self._lyrics is not None:
            self.inputs.add(self._lyrics)
        if self.font:
            self.inputs.add(self.font)
        for name in ("vocals", "instrumental"):
            if self.config.get(name):
                self.inputs.add(self.resolve(self.config[name]["path"]))
        if self.config.get("overrides"):
            self.inputs.add(self.resolve(self.config["overrides"]))

    @property
    def lyrics(self):
        if self._lyrics is None:
            raise ValueError("This stage needs lyrics; set lyrics in the project configuration")
        return self._lyrics

    def resolve(self, value):
        path = Path(value).expanduser()
        return (self.root / path).resolve() if not path.is_absolute() else path.resolve()

    def output(self, name):
        path = (self.work / name).resolve()
        if path in self.inputs or not path.is_relative_to(self.work):
            raise ValueError(f"Output would overwrite an input or escape work_dir: {name}")
        return path

    @property
    def ffmpeg(self):
        value = os.environ.get("AUTO_KARAOKE_FFMPEG") or self.config.get("ffmpeg", "ffmpeg")
        executable = shutil.which(value)
        if not executable:
            candidate = self.resolve(value)
            if candidate.is_file() and os.access(candidate, os.X_OK):
                executable = str(candidate)
        if not executable:
            raise ValueError("FFmpeg not found; set ffmpeg in project JSON or AUTO_KARAOKE_FFMPEG")
        return executable

    def model_environment(self):
        os.environ.setdefault("HF_HOME", str(self.cache / "hf"))
        os.environ.setdefault("TORCH_HOME", str(self.cache / "torch"))
        os.environ.setdefault("NUMBA_CACHE_DIR", str(self.cache / "numba"))
        os.environ.setdefault("OMP_NUM_THREADS", str(self.threads))
        os.environ.setdefault("OPENBLAS_NUM_THREADS", str(self.threads))
        os.environ["PATH"] = str(Path(self.ffmpeg).parent) + os.pathsep + os.environ.get("PATH", "")
