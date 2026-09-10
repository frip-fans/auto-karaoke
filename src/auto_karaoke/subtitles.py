"""Two-line ASS karaoke: word sweep plus mora-by-mora furigana."""
import hashlib
from pathlib import Path
import re
import struct
from .alignment import reviewed_timing
from .project import write_json

WIDTH, HEIGHT = 1280, 720


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
    event(0, project.duration, 'Label', r'\an9\pos(1246,25)\fs16', 'KARAOKE PREVIEW')
    event(0, project.duration, 'Main', r'\an7\pos(0,503)\p1\bord0\shad0\1c&H120C08&\1a&H52&', 'm 0 0 l 1280 0 1280 217 0 217', layer=0)
    for i, line in enumerate(visible):
        show = max(0, line['start'] - 0.85)
        if i >= 2:
            show = max(show, visible[i - 2]['end'] + 0.16)
        hide = min(project.duration, line['end'] + 0.28)
        if i + 2 < len(visible):
            hide = min(hide, max(line['end'], visible[i + 2]['start'] - 0.85))
        main_size, ruby_size = 48, 23
        gap = 4
        mf = ImageFont.truetype(str(FONT), main_size)
        rf = ImageFont.truetype(str(FONT), ruby_size)
        widths = []
        for t in line['tokens']:
            has_kanji = bool(re.search(r'[\u3400-\u9fff]', t['surface']))
            widths.append(max(mf.getlength(t['surface']), rf.getlength(t['reading']) if has_kanji else 0) * font_factor + gap)
        scale = min(1, 1160 / sum(widths))
        x = (WIDTH - sum(widths) * scale) / 2
        y = 544 if i % 2 == 0 else 637
        line_layout = {'id': line['id'], 'show': show, 'hide': hide, 'x': x, 'width': sum(widths) * scale, 'tokens': []}
        for token, width in zip(line['tokens'], widths):
            has_kanji = bool(re.search(r'[\u3400-\u9fff]', token['surface']))
            main_width = mf.getlength(token['surface']) * font_factor * scale
            token_x = x + (width * scale - main_width) / 2
            base_tags = fr'\an7\pos({token_x:.2f},{y})\fs{main_size}\fscx{scale * 100:.2f}\fscy{scale * 100:.2f}'
            event(show, hide, 'Main', base_tags + r'\1c&HFFFFFF&', ass_escape(token['surface']))
            if has_kanji or token['surface'] != token['reading']:
                duration_cs = round(token['end'] * 100) - round(token['start'] * 100)
                event(token['start'], hide, 'Main', base_tags + fr'\kf{duration_cs}', ass_escape(token['surface']), layer=2)
                if not has_kanji:
                    line_layout['tokens'].append({'id': token['id'], 'left': x, 'right': x + width * scale, 'main_y': y, 'ruby': False})
                    x += width * scale
                    continue
                ruby_width = rf.getlength(token['reading']) * font_factor * scale
                ruby_x = x + (width * scale - ruby_width) / 2
                ruby_y = y - 28
                event(show, hide, 'Ruby', fr'\an7\pos({ruby_x:.2f},{ruby_y})\fscx{scale * 100:.2f}\fscy{scale * 100:.2f}\1c&HFFFFFF&', ass_escape(token['reading']))
                for syllable in token['syllables']:
                    cs = max(1, round(syllable['end'] * 100) - round(syllable['start'] * 100))
                    event(syllable['start'], hide, 'Ruby', fr'\an7\pos({ruby_x:.2f},{ruby_y})\fscx{scale * 100:.2f}\fscy{scale * 100:.2f}\kf{cs}', ass_escape(syllable['kana']), layer=2)
                    ruby_x += rf.getlength(syllable['kana']) * font_factor * scale
            else:
                # Kana-only words expose the mora timing directly on the main line.
                syllable_x = token_x
                for syllable in token['syllables']:
                    cs = max(1, round(syllable['end'] * 100) - round(syllable['start'] * 100))
                    event(syllable['start'], hide, 'Main', fr'\an7\pos({syllable_x:.2f},{y})\fs{main_size}\fscx{scale * 100:.2f}\fscy{scale * 100:.2f}\kf{cs}', ass_escape(syllable['kana']), layer=2)
                    syllable_x += mf.getlength(syllable['kana']) * font_factor * scale
            line_layout['tokens'].append({'id': token['id'], 'left': x, 'right': x + width * scale, 'main_y': y, 'ruby': has_kanji})
            x += width * scale
        if line_layout['x'] < 40 or x > WIDTH - 40 + 0.001:
            raise ValueError('Subtitle line exceeds safe margins')
        layout.append(line_layout)
    (project.output('karaoke.ass')).write_text(header + '\n'.join(events) + '\n', encoding='utf-8-sig')
    write_json(project.output('layout.json'), {'width': WIDTH, 'height': HEIGHT, 'font': str(FONT), 'font_sha256': hashlib.sha256(FONT.read_bytes()).hexdigest(), 'libass_font_metric_factor': font_factor, 'lines': layout, 'event_count': len(events)})
    print(f'Wrote {len(events)} ASS events; {len(visible)} lyric lines.')
