"""Offline karaoke library; no dependency on the rendering / ML pipeline."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
import uuid
import webbrowser

from flask import Flask, abort, jsonify, request, send_file

ROOT = Path(__file__).resolve().parent


def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                             '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    video = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
    if not video:
        raise ValueError('文件没有视频轨道')
    tracks = []
    for stream in data['streams']:
        if stream['codec_type'] != 'audio':
            continue
        tags = stream.get('tags', {})
        name = tags.get('title', tags.get('handler_name', '')).strip()
        normalized = name.lower()
        role = ('vocals' if normalized in {'vocals', 'vocal', 'vocal only', 'isolated vocals'}
                else 'instrumental' if normalized in {'instrumental', '伴奏'} else 'unknown')
        tracks.append({'index': stream['index'], 'name': name or '未标记音轨', 'role': role})
    if not tracks:
        raise ValueError('文件没有音轨')
    return {'duration': float(data['format']['duration']), 'tracks': tracks,
            'video_codec': video['codec_name']}


def create_app(library):
    library = Path(library).expanduser().resolve()
    library.mkdir(parents=True, exist_ok=True)
    cache = library / '.karaoke-cache'
    cache.mkdir(exist_ok=True)
    catalog = library / 'library.json'
    app = Flask(__name__, static_folder=str(ROOT / 'static'))
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024**3
    token = secrets.token_urlsafe(32)
    lock = threading.RLock()
    pool = ThreadPoolExecutor(max_workers=2)
    jobs = {}
    if catalog.exists():
        db = json.loads(catalog.read_text('utf-8'))
        if db.get('schema_version') != 1:
            raise ValueError('不支持的曲库版本')
    else:
        db = {'schema_version': 1, 'library_id': uuid.uuid4().hex, 'songs': []}

    def save():
        temp = catalog.with_suffix('.json.tmp')
        temp.write_text(json.dumps(db, ensure_ascii=False, indent=2), 'utf-8')
        temp.replace(catalog)

    def source(song):
        path = (library / song['file']).resolve()
        if not path.is_relative_to(library) or not path.is_file():
            raise ValueError('媒体文件缺失或位于曲库之外')
        return path

    def scan():
        with lock:
            known = {s['file'] for s in db['songs']}
            for path in sorted(library.rglob('*')):
                if path.suffix.lower() != '.mp4' or any(p.startswith('.') for p in path.relative_to(library).parts):
                    continue
                rel = path.relative_to(library).as_posix()
                if rel in known or path.is_symlink():
                    continue
                try:
                    info = probe(path)
                except (ValueError, subprocess.CalledProcessError):
                    continue
                db['songs'].append({'id': uuid.uuid4().hex, 'file': rel, 'title': path.stem,
                                    'artist': '', 'album': '未分类', 'version': '卡拉 OK', **info})
            save()

    def lookup(song_id):
        song = next((s for s in db['songs'] if s['id'] == song_id), None)
        if not song:
            abort(404)
        return song

    def roles(song):
        tracks = song['tracks']
        mapping = song.get('mapping', {})
        inst = mapping.get('instrumental', next((t['index'] for t in tracks if t['role'] == 'instrumental'), None))
        voc = mapping.get('vocals', next((t['index'] for t in tracks if t['role'] == 'vocals'), None))
        if inst is None and len(tracks) == 1:
            inst = tracks[0]['index']
        return inst, voc

    def public(song):
        inst, voc = roles(song)
        try:
            source(song)
            missing = False
        except ValueError:
            missing = True
        return {**song, 'instrumental': inst, 'vocals': voc, 'missing': missing,
                'playable': inst is not None and not missing}

    def signature(song):
        path = source(song)
        stat = path.stat()
        return hashlib.sha256(f'pcm-v1:{song["id"]}:{stat.st_size}:{stat.st_mtime_ns}:{roles(song)}'.encode()).hexdigest()[:24]

    def prepare(song, key):
        folder = cache / key
        folder.mkdir(exist_ok=True)
        try:
            path = source(song)
            inst, voc = roles(song)
            if inst is None:
                raise ValueError('请先在编辑中确认伴奏音轨')
            for role, index in [('instrumental', inst), ('vocals', voc)]:
                if index is None:
                    continue
                dest = folder / f'{role}.wav'
                if not dest.exists():
                    temp = folder / f'{role}.tmp.wav'
                    # Keep timestamps, including delayed stream starts. Both stems use the same zero and rate.
                    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-copyts', '-i', str(path),
                                    '-map', f'0:{index}', '-vn', '-af',
                                    f'aresample=44100:async=1:first_pts=0,apad,atrim=duration={song["duration"]}',
                                    '-ac', '2', '-ar', '44100', '-c:a', 'pcm_s16le', str(temp)],
                                   check=True, capture_output=True)
                    temp.replace(dest)
            with lock:
                jobs[key] = {'status': 'ready', 'instrumental': f'/audio/{key}/instrumental.wav',
                             'vocals': f'/audio/{key}/vocals.wav' if voc is not None else None}
        except Exception as exc:
            with lock:
                jobs[key] = {'status': 'error', 'error': str(exc)[:400]}

    @app.before_request
    def local_only():
        host = request.host.split(':')[0]
        if host not in {'127.0.0.1', 'localhost', '[::1]'}:
            abort(403)
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            if request.headers.get('X-Karaoke-Token') != token:
                abort(403)
            if request.headers.get('Origin') and request.headers['Origin'] != request.host_url.rstrip('/'):
                abort(403)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(ValueError)
    def bad_input(exc):
        return jsonify(error=str(exc)), 400

    @app.get('/')
    def index():
        return send_file(ROOT / 'static/index.html')

    @app.get('/display')
    def display():
        return send_file(ROOT / 'static/display.html')

    @app.get('/api/library')
    def get_library():
        with lock:
            return jsonify(token=token, library_id=db['library_id'], folder=str(library),
                           songs=[public(s) for s in db['songs']])

    @app.post('/api/scan')
    def rescan():
        scan()
        return get_library()

    @app.post('/api/import')
    def upload():
        files = request.files.getlist('files')
        if not files:
            raise ValueError('请选择 MP4 文件')
        imported, errors = [], []
        for item in files:
            filename = Path((item.filename or '').replace('\\', '/')).name
            if Path(filename).suffix.lower() != '.mp4':
                errors.append(f'{filename}: 只接受 MP4')
                continue
            uid = uuid.uuid4().hex
            temp = cache / f'{uid}.upload.mp4'
            try:
                item.save(temp)
                info = probe(temp)
                dest = library / 'media' / f'{uid}.mp4'
                dest.parent.mkdir(exist_ok=True)
                temp.replace(dest)
                song = {'id': uid, 'file': dest.relative_to(library).as_posix(),
                        'title': request.form.get('title', '').strip() or Path(filename).stem,
                        'artist': request.form.get('artist', '').strip(),
                        'album': request.form.get('album', '').strip() or '未分类',
                        'version': request.form.get('version', '').strip() or '卡拉 OK', **info}
                with lock:
                    db['songs'].append(song)
                    save()
                imported.append(public(song))
            except (ValueError, subprocess.CalledProcessError) as exc:
                errors.append(f'{filename}: 无法读取 MP4 ({type(exc).__name__})')
            finally:
                temp.unlink(missing_ok=True)
        return jsonify(songs=imported, errors=errors)

    @app.patch('/api/songs/<song_id>')
    def edit(song_id):
        data = request.get_json()
        with lock:
            song = lookup(song_id)
            changes = {}
            for field in ('title', 'artist', 'album', 'version'):
                if field in data:
                    value = str(data[field]).strip()[:300]
                    if not value and field != 'artist':
                        raise ValueError('曲名、专辑和版本不能为空')
                    changes[field] = value
            if 'mapping' in data:
                mapping = data['mapping']
                ids = {t['index'] for t in song['tracks']}
                if not isinstance(mapping, dict) or mapping.get('instrumental') not in ids:
                    raise ValueError('请选择有效的伴奏音轨')
                if mapping.get('vocals') is not None and mapping['vocals'] not in ids:
                    raise ValueError('请选择有效的人声音轨')
                if mapping.get('vocals') == mapping['instrumental']:
                    raise ValueError('伴奏与纯人声不能是同一条轨道')
                changes['mapping'] = {k: mapping.get(k) for k in ('instrumental', 'vocals')}
            song.update(changes)
            save()
            return jsonify(public(song))

    @app.route('/api/songs/<song_id>/prepare', methods=['GET', 'POST'])
    def prepare_route(song_id):
        with lock:
            song = lookup(song_id)
            key = signature(song)
            if request.method == 'POST' and (key not in jobs or jobs[key]['status'] == 'error'):
                jobs[key] = {'status': 'preparing'}
                pool.submit(prepare, dict(song), key)
            return jsonify(jobs.get(key, {'status': 'pending'}))

    @app.get('/video/<song_id>')
    def video(song_id):
        return send_file(source(lookup(song_id)), mimetype='video/mp4', conditional=True)

    @app.get('/audio/<key>/<name>')
    def audio(key, name):
        if key not in jobs or jobs[key]['status'] != 'ready' or name not in {'instrumental.wav', 'vocals.wav'}:
            abort(404)
        return send_file(cache / key / name, mimetype='audio/wav', conditional=True)

    scan()
    app.extensions['karaoke_pool'] = pool
    return app


def main():
    parser = argparse.ArgumentParser(description='离线卡拉 OK 曲库与双轨混音播放器')
    parser.add_argument('--library', type=Path, default=ROOT / 'songs')
    parser.add_argument('--port', type=int, default=8787)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    for program in ('ffmpeg', 'ffprobe'):
        if not shutil.which(program):
            parser.error(f'缺少 {program}，macOS 请先运行 brew install ffmpeg')
    app = create_app(args.library)
    url = f'http://127.0.0.1:{args.port}'
    print(f'曲库: {args.library.resolve()}\n打开: {url}\nCtrl+C 关闭服务', flush=True)
    if not args.no_browser:
        threading.Timer(1, lambda: webbrowser.open(url)).start()
    from waitress import serve
    serve(app, host='127.0.0.1', port=args.port, threads=8)


if __name__ == '__main__':
    main()
