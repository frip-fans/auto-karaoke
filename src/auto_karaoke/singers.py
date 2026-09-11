"""Optional manual singer annotations, independent of acoustic timing."""
import copy
import math
import re
from .project import read_json, write_json

DEFAULT_PROFILES = {
    'A': {'label': '歌手 A', 'color': '#FF76B5'},
    'B': {'label': '歌手 B', 'color': '#FFE45C'},
    'mao': {'label': '上杉真央', 'color': '#FF76B5'},
    'hisayo': {'label': '阿部寿世', 'color': '#FFE45C'},
    'duet': {'label': '二人合唱', 'color': '#FF9D45'},
    'unknown': {'label': '未标注', 'color': '#FFDE5A', 'pending_color': '#FFFFFF'},
}


def ass_color(rgb):
    if not isinstance(rgb, str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}', rgb):
        raise ValueError('Singer colors must use #RRGGBB')
    return f'&H{rgb[5:7]}{rgb[3:5]}{rgb[1:3]}&'


def map_path(project):
    return project.resolve(project.config['singer_map']) if project.config.get('singer_map') else project.output('singer-map.json')


def profiles(project, imported=None):
    result = copy.deepcopy(DEFAULT_PROFILES)
    extra = project.config.get('singers', {})
    if not isinstance(extra, dict):
        raise ValueError('singers must be an object')
    result.update(extra)
    if imported is not None:
        if not isinstance(imported, dict):
            raise ValueError('Imported singers must be an object')
        result.update(imported)
    for sid, profile in result.items():
        if not isinstance(profile, dict) or not isinstance(profile.get('label'), str):
            raise ValueError('Singer profiles need a label and color')
        color = profile.get('color'); ass_color(color)
        pending = profile.get('pending_color') or '#' + ''.join(
            f'{round(int(color[i:i+2], 16) * .35 + 255 * .65):02X}' for i in (1, 3, 5))
        ass_color(pending); profile['pending_color'] = pending
    return result


def validate_map(doc, lines, available):
    if doc.get('schema_version') != 1 or not isinstance(doc.get('lines'), dict):
        raise ValueError('Singer map needs schema_version 1 and a lines mapping')
    if set(doc['lines']) - {line['id'] for line in lines}:
        raise ValueError('Singer map contains unknown/stale line IDs')
    if 'singer_legend' in doc and (not isinstance(doc['singer_legend'], list) or any(
            not isinstance(sid, str) or sid not in available for sid in doc['singer_legend'])):
        raise ValueError('Invalid imported singer_legend')
    aliases = doc.get('voice_mapping', {})
    if not isinstance(aliases, dict) or any(not isinstance(v, str) or k not in available or v not in available for k, v in aliases.items()):
        raise ValueError('Invalid voice_mapping')
    for value in doc['lines'].values():
        sid = value if isinstance(value, str) else value.get('singer') if isinstance(value, dict) else None
        if not isinstance(sid, str) or sid not in available:
            raise ValueError(f'Unknown singer: {sid!r}')


def singer_styles(project, lines):
    neutral = DEFAULT_PROFILES['unknown']
    if not project.config.get('singer_colors_enabled', False):
        return {}, {line['id']: {'singer': 'unknown', 'status': 'disabled', **neutral} for line in lines}
    doc = read_json(map_path(project))
    available = profiles(project, doc.get('singers'))
    validate_map(doc, lines, available)
    aliases = doc.get('voice_mapping', {})
    resolved = {}
    for line in lines:
        value = doc['lines'].get(line['id'], 'unknown')
        sid = value if isinstance(value, str) else value['singer']
        identity = aliases.get(sid, sid)
        status = value.get('status', 'confirmed') if isinstance(value, dict) else 'confirmed'
        resolved[line['id']] = {'singer': identity, 'voice': sid,
            'status': 'unassigned' if sid == 'unknown' else status, **available[identity]}
    legend_ids = doc.get('singer_legend', project.config.get('singer_legend', ['mao', 'hisayo', 'duet']))
    if not isinstance(legend_ids, list) or any(not isinstance(sid, str) or sid not in available for sid in legend_ids):
        raise ValueError('Invalid singer_legend')
    return {sid: available[aliases.get(sid, sid)] for sid in legend_ids}, resolved


def template(lines):
    return {'schema_version': 1, 'voice_mapping': {}, 'lines': {
        line['id']: {'singer': 'unknown', 'text': line['text'], 'start': line['start'],
                     'end': line['end'], 'status': 'unassigned', 'note': ''} for line in lines}}


def check_target(project, target):
    if target in project.inputs or target == project.output('timing.json'):
        raise ValueError('Singer map would overwrite an input or timing')


def export_singer_map(project):
    from .alignment import reviewed_timing
    target = map_path(project); check_target(project, target)
    if target.exists():
        raise ValueError(f'Singer map already exists; edit it directly: {target}')
    write_json(target, template(reviewed_timing(project)['lines']))
    print(target)


def import_singers(project, source, enable=False):
    from .alignment import reviewed_timing
    lines = reviewed_timing(project)['lines']
    target = map_path(project); check_target(project, target)
    incoming = read_json(source)
    if not isinstance(incoming, dict):
        raise ValueError('Singer import must be a JSON object')
    # The standalone editor saves a complete lyric file. Extract annotations
    # without replacing lyrics, mora timings or the alignment fingerprint.
    if isinstance(incoming.get('lines'), list):
        target_lines = {line['id']: line for line in lines}
        assignments = {}
        for line in incoming['lines']:
            if not isinstance(line, dict) or not isinstance(line.get('id'), str) or line['id'] not in target_lines or line['id'] in assignments:
                raise ValueError('Annotated lyric file contains missing, duplicate or unknown line IDs')
            tokens = line.get('tokens')
            if tokens is not None and (not isinstance(tokens, list) or any(
                    not (isinstance(t, list) and t and isinstance(t[0], str)) and
                    not (isinstance(t, dict) and isinstance(t.get('surface'), str)) for t in tokens)):
                raise ValueError('Annotated lyric tokens must retain their original surface text')
            text = ''.join(t[0] if isinstance(t, list) else t['surface'] for t in tokens) if tokens else line.get('text', '')
            if not isinstance(text, str):
                raise ValueError('Annotated lyric text must be a string')
            target_text = ''.join(t['surface'] for t in target_lines[line['id']]['tokens'])
            if ''.join(text.split()) != ''.join(target_text.split()):
                raise ValueError(f'Annotated lyric text differs for {line["id"]}; use the matching project')
            assignments[line['id']] = {'singer': line.get('singer', 'unknown'),
                'status': line.get('singer_status', 'confirmed'), 'note': line.get('singer_note', '')}
        incoming = {**incoming, 'lines': assignments}
    if incoming.get('schema_version') != 1 or not isinstance(incoming.get('lines', {}), dict):
        raise ValueError('Import needs schema_version 1 and optional lines/ranges')
    result = read_json(target) if target.exists() else template(lines)
    imported_profiles = incoming.get('singers', {})
    if not isinstance(imported_profiles, dict):
        raise ValueError('Imported singers must be an object')
    combined_profiles = {**result.get('singers', {}), **imported_profiles}
    available = profiles(project, combined_profiles)
    validate_map(result, lines, available)
    updates = {}
    ranges = incoming.get('ranges', [])
    if not isinstance(ranges, list):
        raise ValueError('ranges must be an array')
    for span in ranges:
        if not isinstance(span, dict):
            raise ValueError('Each range needs start, end and singer')
        start, end, sid = span.get('start'), span.get('end'), span.get('singer')
        if any(isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) for t in (start, end)) or not 0 <= start < end <= project.duration:
            raise ValueError('Invalid singer range times; use project-relative seconds')
        hits = 0
        for line in lines:
            if start < line['end'] and end > line['start']:
                if start > line['start'] + .02 or end < line['end'] - .02:
                    raise ValueError(f'Range cuts lyric {line["id"]}; use complete lines or line IDs')
                if line['id'] in updates:
                    raise ValueError('Singer ranges overlap the same lyric line')
                updates[line['id']] = {'singer': sid, 'status': 'confirmed', 'note': span.get('note', '')}; hits += 1
        if not hits:
            raise ValueError('Singer range does not contain any lyric lines')
    updates.update(incoming.get('lines', {}))
    for lid, value in updates.items():
        item = {'singer': value} if isinstance(value, str) else value
        if not isinstance(item, dict):
            raise ValueError('Each line assignment must be a singer ID or an object')
        previous = result['lines'].get(lid, {})
        if isinstance(previous, str): previous = {'singer': previous}
        result['lines'][lid] = {**previous, **item, 'status': item.get('status', 'confirmed')}
    if 'voice_mapping' in incoming:result['voice_mapping'] = incoming['voice_mapping']
    if combined_profiles:result['singers'] = combined_profiles
    if 'singer_legend' in incoming:result['singer_legend'] = incoming['singer_legend']
    validate_map(result, lines, available)
    # Validate everything before writing; preserve a backup of the preceding map.
    if target.exists():write_json(project.output('singer-map-before-import.json'), read_json(target))
    write_json(target, result)
    if enable:
        project.config['singer_colors_enabled'] = True
        write_json(project.path, project.config)
    print(f'Imported {len(updates)} manual assignments into {target}')
