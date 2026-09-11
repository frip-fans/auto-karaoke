"""Local beat analysis and three-beat entrance cues after instrumental gaps."""
from bisect import bisect_left, bisect_right
import hashlib
import math
import time

from .project import read_json, write_json


def detect_beats(project):
    import librosa
    import numpy as np
    started = time.perf_counter()
    source = project.output('original.wav')
    y, rate = librosa.load(source, sr=22050, mono=True)
    if not len(y) or not np.isfinite(y).all():
        raise ValueError('Beat detection needs finite nonempty audio')
    tempo, beats = librosa.beat.beat_track(y=y, sr=rate, hop_length=256, units='time', trim=False)
    write_json(project.output('beats.json'), {
        'schema_version': 1, 'method': 'librosa onset-envelope dynamic-programming beat tracker',
        'tempo_bpm': float(np.asarray(tempo).reshape(-1)[0]),
        'beat_times': [round(float(t), 6) for t in beats],
        'source_offset_seconds': project.start, 'source_duration_seconds': len(y) / rate,
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'processing_seconds': time.perf_counter() - started})
    print(f'Detected {len(beats)} beats; estimated tempo {float(np.asarray(tempo).reshape(-1)[0]):.2f} BPM')


def entrance_cues(lines, beats, min_gap=6):
    """Three dot stages plus an empty preparatory stage, each at least one second."""
    if isinstance(min_gap, bool) or not isinstance(min_gap, (int, float)) or not math.isfinite(min_gap) or min_gap <= 0:
        raise ValueError('Countdown min_gap_seconds must be positive')
    if any(not isinstance(b, (int, float)) or not math.isfinite(b) or b < 0 for b in beats):
        raise ValueError('Beat times must be finite and nonnegative')
    if any(a >= b for a, b in zip(beats, beats[1:])):
        raise ValueError('Beat times must be strictly increasing')
    cues = []
    for i, line in enumerate(lines):
        previous_end = lines[i - 1]['end'] if i else 0
        if line['start'] - previous_end < min_gap:
            continue
        # Step backward by at least a second, rounding each stage out to a
        # musical beat. Fast songs therefore use several beats per stage.
        cursor, marks = line['start'], []
        for _ in range(4):
            index = bisect_right(beats, cursor - 1.0)
            if index == 0 or cursor - beats[index - 1] > 2.5:
                break
            cursor = beats[index - 1]
            marks.append(cursor)
        marks.reverse()
        if len(marks) != 4 or marks[0] < previous_end:
            continue
        local_beats = beats[bisect_left(beats, marks[0]):bisect_left(beats, line['start'])]
        intervals = [b - a for a, b in zip(local_beats, local_beats[1:])]
        if not intervals:
            continue
        if min(intervals) < 0.15 or max(intervals) > 1.5 or max(intervals) / min(intervals) > 1.5:
            continue
        cues.append({'line_id': line['id'], 'marks': marks, 'end': line['start']})
    return cues


def project_cues(project, lines):
    config = project.config.get('countdown', {})
    if not isinstance(config, dict):
        raise ValueError('countdown must be an object')
    min_gap = config.get('min_gap_seconds', 6)
    if isinstance(min_gap, bool) or not isinstance(min_gap, (int, float)) or not math.isfinite(min_gap) or min_gap <= 0:
        raise ValueError('Countdown min_gap_seconds must be positive')
    if not any(line['start'] - (lines[i - 1]['end'] if i else 0) >= min_gap for i, line in enumerate(lines)):
        return []
    path = project.resolve(config['beats_file']) if config.get('beats_file') else project.output('beats.json')
    if not path.exists():
        if config.get('beats_file'):
            raise ValueError('Configured beats_file does not exist; run beats or correct the path')
        detect_beats(project)
    doc = read_json(path)
    if doc.get('schema_version') != 1 or abs(doc.get('source_duration_seconds', -1) - project.duration) > 0.05 or doc.get('source_offset_seconds') != project.start:
        raise ValueError('Beat map belongs to a different timeline')
    if doc.get('source_sha256') != hashlib.sha256(project.output('original.wav').read_bytes()).hexdigest():
        raise ValueError('Audio changed; rerun beats')
    beats = doc.get('beat_times')
    if not isinstance(beats, list) or any(isinstance(b, (int, float)) and b > project.duration for b in beats):
        raise ValueError('Beat map contains invalid/out-of-range times')
    return entrance_cues(lines, beats, min_gap)
