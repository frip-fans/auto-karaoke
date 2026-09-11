"""Import user-supplied Word lyrics, retaining section-local formatting legends."""
from collections import Counter
from pathlib import Path
import hashlib
import re
import unicodedata
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from .singers import DEFAULT_PROFILES

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
ARTISTS = re.compile(r'Mao\s+Uesugi|Hisayo\s+Abe|上杉真央|阿部寿世|Both|二人合唱|合唱', re.I)


def singer_id(name):
    key = re.sub(r'\s+', '', name).casefold()
    if key in {'maouesugi', '上杉真央'}: return 'mao'
    if key in {'hisayoabe', '阿部寿世'}: return 'hisayo'
    return 'duet'


def flags(props):
    result = {}
    if props is not None:
        for key in ('b', 'i'):
            node = props.find(W + key)
            if node is not None:
                result[key] = node.get(W + 'val', 'true').lower() not in {'0', 'false', 'off'}
    return result


def style_key(bold, italic):
    return 'bold_italic' if bold and italic else 'bold' if bold else 'italic' if italic else 'plain'


def formatted_lines(path):
    """Respect Word paragraphs AND manual line breaks, including within runs."""
    with ZipFile(path) as archive:
        def read(name):
            info = archive.getinfo(name)
            if info.file_size > 20 * 1024 * 1024: raise ValueError('Word XML part exceeds 20 MB')
            return ET.fromstring(archive.read(name))
        document = read('word/document.xml')
        styles = read('word/styles.xml') if 'word/styles.xml' in archive.namelist() else None
    defaults = flags(styles.find(f'{W}docDefaults/{W}rPrDefault/{W}rPr')) if styles is not None else {}
    definitions = {s.get(W + 'styleId'): s for s in styles.findall(W + 'style')} if styles is not None else {}
    normal = next((s.get(W + 'styleId') for s in definitions.values()
                   if s.get(W+'type') == 'paragraph' and s.get(W+'default') == '1'), None)

    def apply_style(sid, current, seen=None):
        seen = set() if seen is None else seen
        if sid not in definitions or sid in seen: return dict(current)
        seen.add(sid); node = definitions[sid]; base = node.find(W+'basedOn')
        result = apply_style(base.get(W+'val'), current, seen) if base is not None else dict(current)
        # Bold/italic are toggle properties in style inheritance, but direct
        # run properties below explicitly set or clear the final value.
        for key, value in flags(node.find(W+'rPr')).items():
            if value: result[key] = not result.get(key, False)
        return result

    output, blank_lines = [], 0
    for pi, paragraph in enumerate(document.iter(W+'p'), 1):
        pstyle = paragraph.find(f'{W}pPr/{W}pStyle')
        base = apply_style(pstyle.get(W+'val') if pstyle is not None else normal, defaults)
        current = []
        def append(text, props):
            if not text: return
            item = {'text': text, 'bold': props.get('b', False), 'italic': props.get('i', False)}
            if current and all(current[-1][key] == item[key] for key in ('bold', 'italic')):
                current[-1]['text'] += text
            else: current.append(item)
        def flush():
            nonlocal blank_lines
            if current:
                current[0]['text'] = current[0]['text'].lstrip()
                current[-1]['text'] = current[-1]['text'].rstrip()
                parts = [dict(p) for p in current if p['text']]
                if parts:
                    output.append({'paragraph': pi, 'runs': parts, 'blank_lines_before': blank_lines})
                    blank_lines = 0
                else:
                    blank_lines += 1
                current.clear()
            else:
                blank_lines += 1
        for run in paragraph.iter(W+'r'):
            props = run.find(W+'rPr'); rstyle = props.find(W+'rStyle') if props is not None else None
            effective = {**apply_style(rstyle.get(W+'val') if rstyle is not None else None, base), **flags(props)}
            for child in run:
                if child.tag == W+'t': append(child.text or '', effective)
                elif child.tag == W+'tab': append('\t', effective)
                elif child.tag in {W+'br', W+'cr'}: flush()
        flush()
    return output


def convert_docx(path):
    path = Path(path)
    raw = formatted_lines(path)
    sections, lines, issues = [], [], []
    current_section, mapping, default_singer, solo = None, {}, None, None
    for source_line, entry in enumerate(raw, 1):
        runs = entry['runs']; text = ''.join(r['text'] for r in runs)
        matches = list(ARTISTS.finditer(text))
        if re.search(r'(?<![A-Za-z])solo\b|独唱', text, re.I) and len(matches) == 1 and len(text) < 50:
            solo = singer_id(matches[0].group()); default_singer = solo
            continue
        if text.startswith('[') and text.endswith(']'):
            if '歌詞' in text and not matches: continue
            current_section = f'section-{len(sections)+1:02d}'
            char_styles = []
            for r in runs: char_styles.extend([style_key(r['bold'], r['italic'])] * len(r['text']))
            mapping, conflicts = {}, set()
            if ':' in text: matches = [m for m in matches if m.start() > text.index(':')]
            for match in matches:
                name_styles = {char_styles[i] for i in range(match.start(), match.end()) if not text[i].isspace()}
                sid = singer_id(match.group())
                if len(name_styles) != 1:
                    issues.append({'source_line': source_line, 'reason': 'mixed formatting inside a singer name', 'heading': text})
                    continue
                key = next(iter(name_styles))
                if key in mapping and mapping[key] != sid: conflicts.add(key)
                else: mapping[key] = sid
            for key in conflicts: mapping.pop(key, None)
            named = {singer_id(m.group()) for m in matches}
            default_singer = next(iter(named)) if len(named) == 1 else solo if not matches else None
            sections.append({'id': current_section, 'heading': text, 'style_mapping': dict(mapping),
                             'default_singer': default_singer, 'source_line': source_line})
            if conflicts: issues.append({'source_line': source_line, 'reason': 'multiple singers share one heading style', 'styles': sorted(conflicts)})
            continue
        parts, offset, meaningful_singers = [], 0, set()
        for run in runs:
            key = style_key(run['bold'], run['italic'])
            sid = default_singer or mapping.get(key, 'unknown')
            end = offset + len(run['text'])
            parts.append({'text': run['text'], 'singer': sid, 'start_char': offset, 'end_char': end,
                          'bold': run['bold'], 'italic': run['italic']})
            if any(unicodedata.category(c)[0] in 'LN' for c in run['text']): meaningful_singers.add(sid)
            offset = end
        sid = next(iter(meaningful_singers)) if len(meaningful_singers) == 1 else 'unknown'
        mixed = len(meaningful_singers) > 1
        lid = f'line-{len(lines)+1:03d}'
        if sid == 'unknown':
            issues.append({'line_id': lid, 'source_line': source_line,
                           'reason': 'multiple singer assignments within one line' if mixed else 'no unambiguous singer legend'})
        lines.append({'id': lid, 'text': text, 'section': current_section, 'singer': sid,
                      'singer_status': 'from_document' if sid != 'unknown' else 'needs_review',
                      'singer_segments': parts, 'mixed_singers': mixed, 'needs_review': sid == 'unknown',
                      'source_line': source_line, 'source_paragraph': entry['paragraph'],
                      'source_blank_lines_before': entry['blank_lines_before']})
    if not lines: raise ValueError(f'No lyric lines found: {path.name}')
    return {'schema_version': 1, 'title': path.stem, 'status': 'needs_readings_and_alignment',
            'source': {'type': 'user_provided_docx', 'file': path.name,
                       'sha256': hashlib.sha256(path.read_bytes()).hexdigest()},
            'singers': {sid: dict(DEFAULT_PROFILES[sid]) for sid in ('mao', 'hisayo', 'duet', 'unknown')},
            'singer_legend': ['mao', 'hisayo', 'duet'], 'sections': sections, 'lines': lines,
            'import_report': {'line_count': len(lines), 'singer_counts': dict(Counter(l['singer'] for l in lines)),
                              'mixed_line_count': sum(l['mixed_singers'] for l in lines), 'issues': issues,
                              'whole_song_solo': solo, 'timestamps_generated': False}}
