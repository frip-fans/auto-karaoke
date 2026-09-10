"""Audit staged/tracked text only. This cannot determine copyright ownership."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_SUFFIXES = {'.py', '.md', '.toml', '.yaml', '.yml'}
ALLOWED_NAMES = {'.gitignore', 'examples/project.example.json', 'examples/lyrics.example.json'}
FORBIDDEN_PARTS = {'.local', 'work', 'input', 'output', 'models', 'cache', '.venv', '__pycache__'}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def inspect(name, data):
    path = Path(name)
    problems = []
    if name not in ALLOWED_NAMES and path.suffix.lower() not in ALLOWED_SUFFIXES:
        problems.append('file type outside the code/document whitelist')
    if any(part in FORBIDDEN_PARTS for part in path.parts):
        problems.append('local data/cache path')
    if len(data) > 256 * 1024:
        problems.append('file exceeds 256 KiB; review manually')
    try:
        text = data.decode('utf-8-sig')
        if '\x00' in text:
            problems.append('binary content')
        if re.search(r'(?:ghp_|github_pat_)[A-Za-z0-9_]{30,}', text):
            problems.append('possible GitHub credential')
    except UnicodeDecodeError:
        problems.append('not UTF-8 text')
    return [f'{name}: {problem}' for problem in problems]


def main():
    errors = []
    files = git('ls-files', '-z', '--stage').split(b'\0')
    seen = set()
    for entry in files:
        if not entry:
            continue
        metadata, name = entry.split(b'\t', 1)
        mode, oid, stage = metadata.split()
        name = name.decode()
        if mode not in (b'100644', b'100755') or stage != b'0':
            errors.append(f'{name}: unexpected Git mode/stage')
            continue
        errors.extend(inspect(name, git('cat-file', 'blob', oid.decode())))
        seen.add((name, oid))
    # Include every reachable historical tree: deleting media in a later commit is insufficient.
    for commit in git('rev-list', '--all').decode().splitlines():
        for entry in git('ls-tree', '-r', '-z', commit).split(b'\0'):
            if not entry:
                continue
            metadata, name_bytes = entry.split(b'\t', 1)
            mode, kind, oid = metadata.split()
            name = name_bytes.decode()
            if (name, oid) in seen:
                continue
            seen.add((name, oid))
            if kind != b'blob' or mode not in (b'100644', b'100755'):
                errors.append(f'{name}: unexpected historical entry')
                continue
            errors.extend(inspect(name, git('cat-file', 'blob', oid.decode())))
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    if not seen:
        print('No indexed files to audit; stage the intended source files first.', file=sys.stderr)
        return 1
    print(f'Checked {len(seen)} unique indexed/historical file versions: UTF-8 code/docs only.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
