"""Two-line ASS karaoke: word sweep plus mora-by-mora furigana."""
import hashlib
import math
from pathlib import Path
import re
import struct
import unicodedata
from .alignment import reviewed_timing
from .project import write_json
from .singers import ass_color, singer_styles
from .rhythm import project_cues

WIDTH, HEIGHT = 1280, 720
KANJI_RUN = re.compile(r'[\u3400-\u9fff々〆〇]+')


def kanji_ruby_spans(surface, reading):
    """Use written kana as anchors, assigning ruby only to kanji runs."""
    runs = list(KANJI_RUN.finditer(surface))
    if not runs:
        return []

    def kana(text):
        return ''.join(chr(ord(c) - 0x60) if 'ァ' <= c <= 'ヶ' else c for c in text
                       if not unicodedata.category(c).startswith(('P', 'Z')))

    pattern, previous = '', 0
    for run in runs:
        pattern += re.escape(kana(surface[previous:run.start()])) + r'([ぁ-ゖ]+?)'
        previous = run.end()
    pattern += re.escape(kana(surface[previous:]))
    match = re.fullmatch(pattern, reading)
    if not match:
        raise ValueError(f'Cannot map kanji ruby for {surface!r} / {reading!r}; check reading and tokenization')
    return [{'surface_start': run.start(), 'surface_end': run.end(),
             'reading_start': match.start(i), 'reading_end': match.end(i),
             'reading': match.group(i)} for i, run in enumerate(runs, 1)]


def ass_font_scale(font_path):
    """libass uses OS/2 Win ascent+descent, while Pillow measures em size."""
    data = Path(font_path).read_bytes()
    if data[:4] == b'ttcf':
        raise ValueError('Font collections are not supported; choose a single TTF/OTF font')
    tables = {}
    for i in range(struct.unpack_from('>H', data, 4)[0]):
        tag, _, offset, length = struct.unpack_from('>4sIII', data, 12 + i * 16)
        tables[tag] = data[offset:offset + length]
    units = struct.unpack_from('>H', tables[b'head'], 18)[0]
    ascent, descent = struct.unpack_from('>HH', tables[b'OS/2'], 74)
    if not ascent + descent:
        raise ValueError('Font needs an explicit libass metric calibration')
    return units / (ascent + descent)


def ass_time(sec):
    cs = round(sec * 100)
    return f'{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}'


def ass_escape(text):
    return text.replace('\\', '＼').replace('{', '｛').replace('}', '｝').replace('\n', r'\N')


def singer_change_lines(lines, assignments):
    result, previous = set(), None
    for line in lines:
        singer = assignments[line['id']]['singer']
        if singer != 'unknown' and singer != previous:
            result.add(line['id'])
        previous = singer
    return result


def lyric_appearances(lines, duration, reset_gap=6):
    """Fixed alternating rows within a section; restart upper after a long gap."""
    shows, rows = [], []
    section_start = 0
    for i, line in enumerate(lines):
        new_section = i == 0 or line['start'] - lines[i - 1]['end'] >= reset_gap
        if new_section:
            section_start = i
            show = max(0, line['start'] - (8 if line['start'] >= reset_gap else 0.85)) if i == 0 else max(lines[i - 1]['end'] + 0.16, line['start'] - 8)
        elif i == section_start + 1:
            show = max(shows[section_start], line['start'] - 8)
        else:
            show = max(lines[i - 2]['end'] + 0.16, line['start'] - 8)
        shows.append(min(line['start'], show))
        rows.append('upper' if (i - section_start) % 2 == 0 else 'lower')
    appearances, next_show = [], {}
    for i in range(len(lines) - 1, -1, -1):
        line, row = lines[i], rows[i]
        hide = min(duration, line['end'] + 0.16, next_show.get(row, duration))
        appearances.append((line, shows[i], hide, row))
        next_show[row] = shows[i]
    return list(reversed(appearances))


def subtitles(project):
    from PIL import ImageFont
    doc = reviewed_timing(project)
    if abs(doc['source_duration_seconds'] - project.duration) > 0.01 or doc['source_offset_seconds'] != project.start:
        raise ValueError('Timing belongs to a different clip')
    FONT = project.font
    if FONT is None or not FONT.is_file():
        raise ValueError('Set font_path to a Japanese TTF/OTF font')
    font_factor = ass_font_scale(FONT)
    visible = [l for l in doc['lines'] if l.get('display', True)]
    profiles, assignments = singer_styles(project, doc['lines'])
    cues = project_cues(project, visible)
    font_scale = project.config.get('subtitle_font_scale', 1.2)
    if isinstance(font_scale, bool) or not isinstance(font_scale, (int, float)) or not math.isfinite(font_scale) or not 0.5 <= font_scale <= 2:
        raise ValueError('subtitle_font_scale must be between 0.5 and 2')
    main_outline = project.config.get('subtitle_outline', 4.0)
    ruby_outline = project.config.get('ruby_outline', 2.2)
    for value in (main_outline, ruby_outline):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 8:
            raise ValueError('Subtitle outlines must be between 0 and 8 pixels')
    header = '''[Script Info]
Title: Auto Karaoke Preview
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,IPAGothic,48,&H005ADEFF,&H00FFFFFF,&H00100B08,&H80000000,0,0,0,0,100,100,0,0,1,2.2,0,7,0,0,0,1
Style: Ruby,IPAGothic,23,&H005ADEFF,&H00FFFFFF,&H00100B08,&H80000000,0,0,0,0,100,100,0,0,1,1.3,0,7,0,0,0,1
Style: Label,IPAGothic,20,&H00EAEAEA,&H00EAEAEA,&H00100B08,&H80000000,0,0,0,0,100,100,0,0,1,1,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    header = header.replace('IPAGothic', project.font_family)
    events, layout = [], []

    def event(start, end, style, tags, text, layer=1):
        if round(end * 100) <= round(start * 100):
            return
        events.append(f'Dialogue: {layer},{ass_time(start)},{ass_time(end)},{style},,0,0,0,,{{{tags}}}{text}')

    event(0, project.duration, 'Label', r'\an7\pos(34,25)', ass_escape(project.config.get('title', 'Karaoke preview')))
    if project.config.get('show_preview_label', True):
        event(0, project.duration, 'Label', r'\an9\pos(1246,25)\fs16', 'KARAOKE PREVIEW')
    if profiles:
        legend = '    '.join('{\\1c' + ass_color(profile['color']) + '}' + ass_escape(profile['label'])
                             for profile in profiles.values())
        event(0, project.duration, 'Label', r'\an7\pos(34,55)\fs18', legend)
    title_cards = []
    intro_end = 0
    for kind in ('intro', 'outro'):
        card = project.config.get(kind + '_card')
        if not card:
            continue
        if not isinstance(card, dict):
            raise ValueError(kind + '_card must be an object')
        if kind == 'outro':
            card = {**(project.config.get('intro_card') or {}), **card}
        seconds = card.get('seconds', 10)
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError(kind + '_card.seconds must be positive')
        start = 0 if kind == 'intro' else max(intro_end, project.duration - seconds)
        end = min(project.duration, seconds) if kind == 'intro' else project.duration
        if kind == 'intro':
            intro_end = end
        if end <= start:
            continue
        title_cards.append({'kind': kind, 'start': start, 'end': end})
        event(start, end, 'Main', r'\an7\pos(150,205)\p1\bord0\shad0\1c&H000000&\1a&H66&\fad(250,500)',
              'm 0 0 l 980 0 980 230 0 230', layer=4)
        fields = [(card.get('title', project.config.get('title', '')), 70, 270),
                  (card.get('artist', ''), 38, 335), (card.get('album', ''), 28, 378),
                  (card.get('vocals', ''), 25, 413)]
        for text, size, ypos in fields:
            if not isinstance(text, str):
                raise ValueError('Title card text must be strings')
            if not text:
                continue
            measured = ImageFont.truetype(str(FONT), size).getlength(text) * font_factor
            fit = min(1.0, 900 / max(1, measured)) * 100
            event(start, end, 'Label', fr'\an5\pos(640,{ypos})\fs{size}\fscx{fit:.2f}\fscy{fit:.2f}\bord2.5\shad1\1c&HFFFFFF&\3c&H000000&\fad(250,500)',
                  ass_escape(text), layer=5)
    cue_by_line = {cue['line_id']: cue for cue in cues}
    if profiles:
        for line in visible:
            voices = list(dict.fromkeys(t.get('singer') for t in line['tokens'] if t.get('singer') in profiles))
            if len(voices) > 1:
                assignments[line['id']] = {**assignments[line['id']], 'singer': '+'.join(voices),
                    'label': ' / '.join(profiles[sid]['label'] for sid in voices)}
    singer_changes = singer_change_lines(visible, assignments) if profiles else set()
    reset_gap = project.config.get('countdown', {}).get('min_gap_seconds', 6)
    for line, show, hide, row in lyric_appearances(visible, project.duration, reset_gap):
        singer = assignments[line['id']]
        pending_color, sung_color = ass_color(singer['pending_color']), ass_color(singer['color'])
        main_size, ruby_size = 48, 23
        gap = 4
        mf = ImageFont.truetype(str(FONT), main_size)
        rf = ImageFont.truetype(str(FONT), ruby_size)
        widths, ruby_layouts = [], []
        for t in line['tokens']:
            spans = kanji_ruby_spans(t['surface'], t['reading'])
            left, right = 0.0, mf.getlength(t['surface']) * font_factor
            for span in spans:
                begin = mf.getlength(t['surface'][:span['surface_start']]) * font_factor
                end = mf.getlength(t['surface'][:span['surface_end']]) * font_factor
                ruby_width = rf.getlength(span['reading']) * font_factor
                span['x'] = (begin + end - ruby_width) / 2
                left, right = min(left, span['x']), max(right, span['x'] + ruby_width)
            widths.append(right - left + gap)
            ruby_layouts.append((left, spans))
        # Latin words need a visible word space in addition to token padding.
        # Keep this outside the highlighted text so timing stays on each word.
        word_spaces = [0.0] * len(widths)
        for j, (left, right) in enumerate(zip(line['tokens'], line['tokens'][1:])):
            if re.search(r'[A-Za-z0-9][,.!?;:]*$', left['surface']) and re.match(r'[A-Za-z0-9]', right['surface']):
                word_spaces[j] = mf.getlength(' ') * font_factor
        total_width = sum(widths) + sum(word_spaces)
        cue = cue_by_line.get(line['id'])
        prefix_width = 90 if cue else 0
        scale = min(font_scale, (1160 - prefix_width) / total_width)
        group_width = prefix_width + total_width * scale
        group_x = 60 if row == 'upper' else WIDTH - 60 - group_width
        x = group_x + prefix_width
        y = 530 if row == 'upper' else 640
        if cue:
            # Reserve the prefix for the entire line so its text does not jump
            # horizontally as dots disappear. Dots and lyric share the row.
            cue.update(row=row, x=group_x, y=y + 10, prefix_width=prefix_width)
            ends = [cue['marks'][3], cue['marks'][2], cue['marks'][1]]
            circle = 'm 9 0 b 14 0 18 4 18 9 b 18 14 14 18 9 18 b 4 18 0 14 0 9 b 0 4 4 0 9 0'
            for j, end in enumerate(ends):
                tags = fr'\an7\pos({group_x + j * 28:.2f},{y + 10})\p1\bord1.5\shad0\1c&H5ADEFF&\3c&H101010&\fad(0,60)'
                event(cue['marks'][0], end, 'Main', tags, circle, layer=3)
        singer_label = f'【{singer["label"]}】' if line['id'] in singer_changes else None
        if singer_label:
            label_x, anchor = (x, 7) if row == 'upper' else (WIDTH - 60, 9)
            label_y = y - 28 * scale - 40
            event(show, hide, 'Label', fr'\an{anchor}\pos({label_x},{label_y:.2f})\fs44\bord3\shad1\3c&H000000&\1c{sung_color}',
                  ass_escape(singer_label), layer=2)
        line_layout = {'id': line['id'], 'show': show, 'hide': hide, 'row': row,
                       'singer_label': singer_label, 'countdown_prefix_width': prefix_width,
                       'font_scale': scale, 'x': x, 'width': total_width * scale, 'tokens': []}
        for token, width, word_space, (left, spans) in zip(line['tokens'], widths, word_spaces, ruby_layouts):
            has_kanji = bool(spans)
            token_profile = profiles.get(token.get('singer'), singer) if profiles else singer
            pending_color, sung_color = ass_color(token_profile['pending_color']), ass_color(token_profile['color'])
            token_x = x + (gap / 2 - left) * scale
            base_tags = fr'\an7\pos({token_x:.2f},{y})\fs{main_size}\fscx{scale * 100:.2f}\fscy{scale * 100:.2f}\bord{main_outline}\shad1\3c&H000000&'
            event(show, hide, 'Main', base_tags + fr'\1c{pending_color}', ass_escape(token['surface']))
            sweep_tags = base_tags + fr'\1c{sung_color}\2c{pending_color}'
            if has_kanji or token['surface'] != token['reading']:
                duration_cs = round(token['end'] * 100) - round(token['start'] * 100)
                event(token['start'], hide, 'Main', sweep_tags + fr'\kf{duration_cs}', ass_escape(token['surface']), layer=2)
                if not has_kanji:
                    line_layout['tokens'].append({'id': token['id'], 'left': x, 'right': x + width * scale, 'main_y': y, 'ruby': False})
                    x += (width + word_space) * scale
                    continue
                ruby_y = y - 28 * scale
                mora_offsets, offset = [], 0
                for syllable in token['syllables']:
                    mora_offsets.append((offset, offset + len(syllable['kana']), syllable))
                    offset += len(syllable['kana'])
                boundaries = {0, *(end for _, end, _ in mora_offsets)}
                for span in spans:
                    if span['reading_start'] not in boundaries or span['reading_end'] not in boundaries:
                        raise ValueError(f'Ruby boundary splits a mora: {token["surface"]}')
                    ruby_x = token_x + span['x'] * scale
                    event(show, hide, 'Ruby', fr'\an7\pos({ruby_x:.2f},{ruby_y})\fscx{scale * 100:.2f}\fscy{scale * 100:.2f}\bord{ruby_outline}\shad0.5\3c&H000000&\1c{pending_color}', ass_escape(span['reading']))
                    for begin, end, syllable in mora_offsets:
                        if begin < span['reading_start'] or end > span['reading_end']:
                            continue
                        cs = max(1, round(syllable['end'] * 100) - round(syllable['start'] * 100))
                        event(syllable['start'], hide, 'Ruby', fr'\an7\pos({ruby_x:.2f},{ruby_y})\fscx{scale * 100:.2f}\fscy{scale * 100:.2f}\bord{ruby_outline}\shad0.5\3c&H000000&\1c{sung_color}\2c{pending_color}\kf{cs}', ass_escape(syllable['kana']), layer=2)
                        ruby_x += rf.getlength(syllable['kana']) * font_factor * scale
            else:
                # Kana-only words expose the mora timing directly on the main line.
                syllable_x = token_x
                for syllable in token['syllables']:
                    cs = max(1, round(syllable['end'] * 100) - round(syllable['start'] * 100))
                    event(syllable['start'], hide, 'Main', fr'\an7\pos({syllable_x:.2f},{y})\fs{main_size}\fscx{scale * 100:.2f}\fscy{scale * 100:.2f}\bord{main_outline}\shad1\3c&H000000&\1c{sung_color}\2c{pending_color}\kf{cs}', ass_escape(syllable['kana']), layer=2)
                    syllable_x += mf.getlength(syllable['kana']) * font_factor * scale
            line_layout['tokens'].append({'id': token['id'], 'left': x, 'right': x + width * scale, 'main_y': y, 'ruby': has_kanji, 'ruby_spans': spans})
            x += (width + word_space) * scale
        if line_layout['x'] < 40 or x > WIDTH - 40 + 0.001:
            raise ValueError('Subtitle line exceeds safe margins')
        layout.append(line_layout)
    (project.output('karaoke.ass')).write_text(header + '\n'.join(events) + '\n', encoding='utf-8-sig')
    write_json(project.output('layout.json'), {'width': WIDTH, 'height': HEIGHT, 'font': str(FONT), 'font_sha256': hashlib.sha256(FONT.read_bytes()).hexdigest(), 'libass_font_metric_factor': font_factor, 'lines': layout, 'event_count': len(events), 'title_cards': title_cards})
    write_json(project.output('countdown-report.json'), {'cues': cues, 'beat_source': 'measured local musical beats'})
    print(f'Wrote {len(events)} ASS events; {len(visible)} lyric lines.')
