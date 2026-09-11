"""Batch convert local Word lyrics; outputs contain user material and stay local."""
import argparse
from pathlib import Path
import re
from auto_karaoke.docx_lyrics import convert_docx
from auto_karaoke.project import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='A DOCX file or directory of DOCX files')
    parser.add_argument('--output', required=True, type=Path, help='Local output directory')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    sources = sorted(args.input.glob('*.docx')) if args.input.is_dir() else [args.input]
    if not sources: parser.error('No DOCX files found')
    prepared = []
    for source in sources:
        doc = convert_docx(source)
        slug = re.sub(r'[^\w-]+', '-', source.stem.casefold()).strip('-')
        target = args.output / (slug + '.lyrics.json')
        if target.resolve() == source.resolve() or (target.exists() and not args.overwrite):
            parser.error(f'Refusing to overwrite {target}')
        if any(t == target for _, t in prepared): parser.error('Output filename collision')
        prepared.append((doc, target))
    summary = args.output / 'import-report.json'
    if summary.exists() and not args.overwrite: parser.error(f'Refusing to overwrite {summary}')
    args.output.mkdir(parents=True, exist_ok=True)
    reports = []
    for doc, target in prepared:
        write_json(target, doc)
        report = {'file': target.name, 'source': doc['source']['file'], **doc['import_report']}
        reports.append(report)
        print(target.name, report['line_count'], report['singer_counts'], 'mixed:', report['mixed_line_count'])
    write_json(summary, {'files': reports, 'document_count': len(reports),
                        'lyric_line_count': sum(r['line_count'] for r in reports)})


if __name__ == '__main__': main()
