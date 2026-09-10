"""CTC timing and explicit human corrections, adapted from the working preview."""
import hashlib
import math
import time
from .project import read_json, write_json


def validate_lyrics(doc):
    if doc.get("schema_version") != 1 or not doc.get("lines"):
        raise ValueError("Lyrics require schema_version 1 and nonempty lines")
    ids = set()
    for line in doc["lines"]:
        if not isinstance(line.get("id"), str) or not line["id"] or line["id"] in ids or not line.get("tokens"):
            raise ValueError("Each lyric line needs a unique ID and tokens")
        ids.add(line["id"])
        for token in line["tokens"]:
            if not isinstance(token, list) or len(token) not in (2, 3) or any(not isinstance(v, str) or not v.strip() for v in token):
                raise ValueError("Token format is [surface, hiragana, optional single-mora Latin pronunciation]")
            if any(not ('ぁ' <= c <= 'ゖ') for c in token[1]):
                raise ValueError("Write pronunciation in hiragana; expand long vowels explicitly")


def morae(reading):
    result = []
    for c in reading:
        if c in 'ゃゅょぁぃぅぇぉゎ' and result:
            result[-1] += c
        else:
            result.append(c)
    return result


def ctc_viterbi(log_probs, labels, blank):
    """Exact CTC state path, retaining frame evidence for every target letter."""
    import numpy as np
    log_probs = np.asarray(log_probs)
    labels = np.asarray(labels, dtype=np.int64)
    if log_probs.ndim != 2 or not len(log_probs) or not len(labels):
        raise ValueError('Nonempty emissions and target labels are required')
    if not 0 <= blank < log_probs.shape[1] or np.any(labels < 0) or np.any(labels >= log_probs.shape[1]) or np.any(labels == blank):
        raise ValueError('Invalid CTC label or blank ID')
    if np.isnan(log_probs).any() or np.isposinf(log_probs).any():
        raise ValueError('Invalid emission values')
    states = np.full(2 * len(labels) + 1, blank, dtype=np.int64)
    states[1::2] = labels
    skip = np.zeros(len(states), dtype=bool)
    skip[2:] = (states[2:] != blank) & (states[2:] != states[:-2])
    previous = np.full(len(states), -np.inf, dtype=np.float32)
    previous[0] = 0
    back = np.zeros((len(log_probs), len(states)), dtype=np.uint8)
    for frame, emission in enumerate(log_probs):
        advance1 = np.concatenate(([-np.inf], previous[:-1]))
        advance2 = np.concatenate(([-np.inf, -np.inf], previous[:-2]))
        advance2[~skip] = -np.inf
        options = np.stack((previous, advance1, advance2))
        choice = options.argmax(axis=0)
        previous = options[choice, np.arange(len(states))] + emission[states]
        back[frame] = choice
    state = len(states) - 1 if previous[-1] >= previous[-2] else len(states) - 2
    if not np.isfinite(previous[state]):
        raise ValueError('Audio is too short for the supplied transcript')
    path = np.empty(len(log_probs), dtype=np.int32)
    for frame in range(len(log_probs) - 1, -1, -1):
        path[frame] = state
        state -= int(back[frame, state])
    spans = []
    for i, label in enumerate(labels):
        frames = np.flatnonzero(path == 2 * i + 1)
        if not len(frames):
            raise ValueError(f'Unaligned target letter {i}')
        spans.append({'start_frame': int(frames[0]), 'end_frame': int(frames[-1] + 1), 'confidence': float(np.exp(log_probs[frames, label].mean()))})
    return spans


def align(project):
    import numpy as np
    from pykakasi import kakasi
    started = time.perf_counter()
    doc = read_json(project.lyrics)
    validate_lyrics(doc)
    doc['source_offset_seconds'] = project.start
    doc['source_duration_seconds'] = project.duration
    evidence = read_json(project.output('emissions-report.json'))
    if abs(evidence['seconds'] - project.duration) > 0.01 or evidence['source_offset_seconds'] != project.start:
        raise ValueError('Cached emissions belong to a different clip')
    if hashlib.sha256(project.output('vocals.wav').read_bytes()).hexdigest() != evidence['vocals_sha256']:
        raise ValueError('Vocals changed; rerun emit before align')
    emissions = np.load(project.output('emissions.npy'))
    vocab, blank = evidence['vocab'], evidence['blank_id']
    # Ignore tokenization differences at word boundaries by folding delimiter
    # probability into CTC blank; character/syllable timings remain acoustic.
    emissions[:, blank] = np.logaddexp(emissions[:, blank], emissions[:, vocab['|']])
    converter = kakasi()
    chars = []
    syllables = []
    for line in doc['lines']:
        tokens = []
        for j, item in enumerate(line['tokens']):
            surface, reading = item[:2]
            kana = morae(reading)
            roman = [''.join(s['hepburn'] for s in converter.convert(k)).lower() for k in kana]
            for k, value in enumerate(kana):
                if value == 'っ':
                    if k + 1 >= len(roman):
                        raise ValueError('Trailing small tsu requires a pronunciation override')
                    roman[k] = roman[k + 1][0]
            if len(item) == 3:
                if len(kana) != 1:
                    raise ValueError('This sample supports pronunciation overrides for one mora only')
                roman = [item[2]]
            token = {'id': f"{line['id']}-word-{j + 1:02}", 'surface': surface, 'reading': reading, 'reading_verified': False, 'syllables': []}
            for k, (ka, ro) in enumerate(zip(kana, roman)):
                if not ro or any(c not in vocab for c in ro):
                    raise ValueError(f'Unsupported pronunciation {ka}: {ro}')
                syllable = {'id': f"{token['id']}-mora-{k + 1:02}", 'kana': ka, 'alignment_text': ro, 'char_start': len(chars), 'char_end': len(chars) + len(ro)}
                chars.extend(ro)
                token['syllables'].append(syllable)
                syllables.append(syllable)
            tokens.append(token)
        line['tokens'] = tokens
    spans = ctc_viterbi(emissions, [vocab[c] for c in chars], blank)
    stride = evidence['frame_stride_seconds']
    for s in syllables:
        parts = spans[s['char_start']:s['char_end']]
        s['start'] = round(parts[0]['start_frame'] * stride, 4)
        s['raw_end'] = round(parts[-1]['end_frame'] * stride, 4)
        s['confidence'] = float(np.mean([p['confidence'] for p in parts]))
    # A short CTC blank between morae should not leave a visual flicker.
    # Only bounded blank extension is applied; never divide a line uniformly.
    for i, s in enumerate(syllables):
        next_start = syllables[i + 1]['start'] if i + 1 < len(syllables) else project.duration
        gap = next_start - s['raw_end']
        s['end'] = round(next_start if gap <= 0.22 else min(next_start, s['raw_end'] + 0.10), 4)
        s['needs_review'] = s['confidence'] < 0.25
    for line in doc['lines']:
        for token in line['tokens']:
            token['start'], token['end'] = token['syllables'][0]['start'], token['syllables'][-1]['end']
        line['start'], line['end'] = line['tokens'][0]['start'], line['tokens'][-1]['end']
        line['text'] = ''.join(t['surface'] for t in line['tokens'])
    doc['alignment'] = {'backend': evidence['model'], 'method': 'CTC Viterbi over acoustic emissions; word-delimiter folded into blank', 'frame_stride_seconds': stride, 'blank_extension_max_seconds': 0.22, 'fully_listening_reviewed': False, 'postprocess_seconds': time.perf_counter() - started, 'source_emissions_sha256': hashlib.sha256((project.output('emissions.npy')).read_bytes()).hexdigest(), 'lyrics_sha256': hashlib.sha256(project.lyrics.read_bytes()).hexdigest()}
    validate_timing(doc)
    write_json(project.output('timing.json'), doc)
    for line in doc['lines']:
        print(line['id'], f"{line['start']:.2f}–{line['end']:.2f}", line['text'])


def validate_timing(doc):
    if not doc.get('lines') or not math.isfinite(doc['source_duration_seconds']) or doc['source_duration_seconds'] <= 0:
        raise ValueError('Timing needs lines and a finite positive duration')
    if any(not line.get('tokens') or any(not token.get('syllables') for token in line['tokens']) for line in doc['lines']):
        raise ValueError('Empty line or token in timing')
    last = -1
    seen = set()
    for line in doc['lines']:
        for token in line['tokens']:
            for s in token['syllables']:
                if s['id'] in seen:
                    raise ValueError('Duplicate mora ID')
                seen.add(s['id'])
                if not (math.isfinite(s['start']) and math.isfinite(s['end']) and 0 <= s['start'] < s['end'] <= doc['source_duration_seconds']):
                    raise ValueError(f'Invalid timing: {s["id"]}')
                if s['start'] < last - 0.0001:
                    raise ValueError(f'Overlapping timing: {s["id"]}')
                last = s['end']


def reviewed_timing(project):
    doc = read_json(project.output('timing.json'))
    if doc.get('alignment', {}).get('lyrics_sha256') != hashlib.sha256(project.lyrics.read_bytes()).hexdigest():
        raise ValueError('Lyrics changed; rerun align and review timing overrides')
    override_path = project.resolve(project.config['overrides']) if project.config.get('overrides') else project.output('overrides.json')
    validate_timing(doc)
    overrides = read_json(override_path) if override_path.exists() else {}
    all_syllables = {s['id']: s for l in doc['lines'] for t in l['tokens'] for s in t['syllables']}
    for sid, values in overrides.get('syllables', {}).items():
        if sid not in all_syllables or set(values) - {'start', 'end', 'review_note'}:
            raise ValueError(f'Invalid timing override: {sid}')
        all_syllables[sid].update(values)
    for line in doc['lines']:
        for t in line['tokens']:
            t['start'], t['end'] = t['syllables'][0]['start'], t['syllables'][-1]['end']
        line['start'], line['end'] = line['tokens'][0]['start'], line['tokens'][-1]['end']
    validate_timing(doc)
    return doc
