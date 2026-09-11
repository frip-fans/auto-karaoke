"""Package code and optionally a portable library, excluding caches and environments."""
import argparse
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
CODE = ['server.py', 'requirements.txt', 'Start Karaoke.command', 'README.md',
        'static/index.html', 'static/styles.css', 'static/app.js', 'static/audio.js',
        'static/display.html', 'static/display.js']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pending = args.output.with_suffix('.tmp.zip')
    try:
        with zipfile.ZipFile(pending, 'w', compression=zipfile.ZIP_STORED) as archive:
            for name in CODE:
                archive.write(ROOT/name, 'Karaoke/'+name)
            if args.library:
                library = args.library.resolve()
                catalog = library/'library.json'
                data = json.loads(catalog.read_text('utf-8'))
                archive.write(catalog, 'Karaoke/songs/library.json')
                seen = set()
                for song in data['songs']:
                    path = (library/song['file']).resolve()
                    if not path.is_relative_to(library) or not path.is_file():
                        raise ValueError('Invalid/missing library media: '+song['file'])
                    if song['file'] not in seen:
                        archive.write(path, 'Karaoke/songs/'+song['file'])
                        seen.add(song['file'])
        pending.replace(args.output)
    except BaseException:
        pending.unlink(missing_ok=True)
        raise
    print(args.output.resolve())


if __name__ == '__main__':
    main()
