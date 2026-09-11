"""Install self-contained skills without changing Codex settings or overwriting skills."""
import argparse
from pathlib import Path
import shutil
import tempfile

SOURCE = Path(__file__).resolve().parent / 'skills'
NAMES = ('karaoke-setup', 'audio-separate', 'karaoke-author', 'karaoke-render')


def install(destination, names):
    destination = Path(destination).expanduser().resolve()
    for name in names:
        if name not in NAMES:
            raise ValueError('Unknown skill: ' + name)
        target = destination / name
        if target.exists() or target.is_symlink():
            raise ValueError(f'Refusing to overwrite {target}; move the existing skill aside first')
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.karaoke-install-', dir=destination) as tmp:
        staged = Path(tmp)
        for name in names:
            shutil.copytree(SOURCE / name, staged / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            shutil.copyfile(SOURCE.parent / "LICENSE", staged / name / "LICENSE")
        # All requested skills are staged before publishing any of them.
        for name in names:
            (staged / name).rename(destination / name)
            print(destination / name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=Path.home() / '.agents/skills')
    parser.add_argument('--skill', action='append', choices=NAMES, help='Repeat to select skills; defaults to all skills')
    args = parser.parse_args()
    try:
        install(args.destination, list(dict.fromkeys(args.skill or NAMES)))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
