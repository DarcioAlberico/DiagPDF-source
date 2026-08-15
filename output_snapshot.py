#!/usr/bin/env python3
"""Prove a refactor did not change what the program writes.

Renders a fixed corpus through the real command line — every option group, in
every format — and digests the results. Run it before a change and after, then
compare: anything that differs is a behaviour change, wanted or not.

Usage:
    python output_snapshot.py save before        # before the change
    python output_snapshot.py save after         # after it
    python output_snapshot.py compare            # before vs after
    python output_snapshot.py compare a b        # any two saved labels

    python output_snapshot.py compare --ignore-version   # across a release bump

`compare` exits non-zero when anything differs, so it can gate a release.
A full run is 182 documents and takes a few minutes.

Why the digest is not a plain checksum
--------------------------------------
Every format stamps something fresh into each build, so two runs of *identical*
code never match byte for byte. Those fields — and only those — are blanked
before hashing, which keeps the surrounding metadata under comparison instead
of excluding whole files:

    PDF     /CreationDate, /ID                    time, and a per-build hash
    EPUB    dcterms:modified, urn:uuid:...        required to be unique per build
    DOCX    fontKey="{GUID}", the .odttf payload  font obfuscation, random GUID

The .odttf entry is skipped outright: it is the font scrambled with that GUID,
so its bytes change wholesale.

Before trusting a comparison, save the *same* code under two labels and compare
those. If that does not come out identical, the normalisation above is
incomplete and no later result means anything.

The PDF carries /Creator (DiagPDF <version>) and the LaTeX a comment saying the
same. That is real output, not noise, so it is compared like everything else —
but a release bump changes it in every such file and drowns out anything else.
Each snapshot therefore stores a second digest with the version blanked as well,
and --ignore-version compares those.
It is stored at save time so the choice can be made after seeing the diff,
without re-rendering the corpus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / 'fen2rtf.py'
PGN = ROOT / 'Example' / 'examples.pgn'
CHAPTERS = ROOT / 'Example' / 'chapters.pgn'
FEN = ROOT / 'test.fen'
OUT_ROOT = ROOT / 'snapshot_out'

FORMATS = ('pdf', 'html', 'epub', 'docx', 'rtf', 'tex', 'md')

# One entry per capability group, so a change anywhere shows up somewhere.
CASES: dict[str, list[str]] = {
    'plain':      [],
    'answers':    ['--answers', '--answers-cols', '2'],
    'lines':      ['--lines', '3', '--lines-numbered'],
    'layout6':    ['--layout', '6'],
    'grid':       ['--grid', '3x4'],
    'hdrftr':     ['--header', 'H {page}/{total}', '--footer', 'F {chapter}'],
    'noheader':   ['--no-header', '--no-footer'],
    'coords':     ['--no-coords', '--border', 'none'],
    'flip':       ['--flip'],
    'fontsize':   ['--font-size', '14', '--text-size', '9'],
    'lichess':    ['--lichess-link'],
    'numbers':    ['--number-start', '5', '--number-format', '#{n}'],
    'titles':     ['--title-template', '{number} - {white} vs {black}'],
    'page':       ['--page-size', 'a5', '--landscape', '--margin-lr', '20', '--margin-tb', '25'],
    'meta':       ['--title', 'T', '--author', 'A', '--subject', 'S', '--keywords', 'K'],
    'cover':      ['--cover', '--cover-subtitle', 'Sub', '--contents'],
    'symbol':     ['--symbol', 'circle'],
    'font':       ['--font', 'Chess Kingdom', '--figurine-font', 'Hastings'],
    'lang_pt':    ['--lang', 'pt'],
    'htmlfont':   ['--html-font-mode', 'link'],
    'fromto':     ['--from', '2', '--to', '4', '--keep-numbers'],
    'watermark':  ['--watermark', 'SAMPLE', '--watermark-opacity', '35'],
    'everything': ['--answers', '--answers-cols', '2', '--lines', '2', '--lichess-link',
                   '--header', 'H {page}', '--footer', '{page}/{total}', '--cover',
                   '--contents', '--page-size', 'letter', '--title', 'Book',
                   '--author', 'Me', '--number-start', '3'],
}

# Inputs other than the main PGN, each with the options that only make sense
# for it: a .fen carries no solutions, which is a different path through every
# renderer, and only a chaptered file gives the per-chapter options anything to
# act on.
EXTRA_INPUTS: dict[str, tuple[Path, list[str]]] = {
    'fenfile':       (FEN, []),
    'chapters':      (CHAPTERS, ['--answers', '--contents']),
    'chapters_each': (CHAPTERS, ['--answers', '--answers-after-chapter',
                                 '--number-restart-per-chapter', '--contents']),
}

SKIP_ENTRIES = ('.odttf',)
OBFUSCATED = '<obfuscated with a per-build guid>'

# (pattern, replacement) for the fields each format writes afresh every build.
VOLATILE: list[tuple[re.Pattern[bytes], bytes]] = [
    (re.compile(rb'/CreationDate\s*\(D:[^)]*\)'), b'/CreationDate (D:<ts>)'),
    (re.compile(rb'/ID\s*\[\s*(<[0-9A-Fa-f]*>\s*)+\]'), b'/ID [<id><id>]'),
    (re.compile(rb'urn:uuid:[0-9a-fA-F-]{36}'), b'urn:uuid:<uuid>'),
    (re.compile(rb'<meta property="dcterms:modified">[^<]*</meta>'),
     b'<meta property="dcterms:modified"><ts></meta>'),
    (re.compile(rb'fontKey="\{[0-9A-Fa-f-]*\}"'), b'fontKey="{<guid>}"'),
]

# Where the release number is written: /Creator in the PDF, a comment at the top
# of the LaTeX. Both are real output, so they are compared like everything else
# -- but a release bump changes them in every such file and drowns out the rest,
# which is what --ignore-version is for.
VERSION_RE: list[tuple[re.Pattern[bytes], bytes]] = [
    (re.compile(rb'/Creator \(DiagPDF [^)]*\)'), b'/Creator (DiagPDF <version>)'),
    (re.compile(rb'% Generated by DiagPDF [0-9][^\n]*'), b'% Generated by DiagPDF <version>'),
]


def _hash(data: bytes, drop_version: bool) -> str:
    """Hash *data* with the per-build fields blanked."""
    for pattern, replacement in VOLATILE:
        data = pattern.sub(replacement, data)
    if drop_version:
        for pattern, replacement in VERSION_RE:
            data = pattern.sub(replacement, data)
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> tuple[object, object]:
    """Return (digest, digest with the version stamp blanked too).

    Zip formats are digested entry by entry, so a difference names the part of
    the package that moved rather than just the archive.
    """
    if path.suffix.lower() in ('.epub', '.docx'):
        strict: dict[str, str] = {}
        loose: dict[str, str] = {}
        with zipfile.ZipFile(path) as archive:
            for name in sorted(archive.namelist()):
                if name.lower().endswith(SKIP_ENTRIES):
                    strict[name] = loose[name] = OBFUSCATED
                    continue
                data = archive.read(name)
                strict[name] = _hash(data, False)
                loose[name] = _hash(data, True)
        return strict, loose
    data = path.read_bytes()
    return _hash(data, False), _hash(data, True)


def _corpus() -> list[tuple[str, Path, list[str]]]:
    """Return every (name, input file, extra arguments) the corpus is made of."""
    work = [(f'{case}.{fmt}', PGN, extra)
            for case, extra in CASES.items() for fmt in FORMATS]
    work += [(f'{name}.{fmt}', source, extra)
             for name, (source, extra) in EXTRA_INPUTS.items() for fmt in FORMATS]
    return work


def save(label: str) -> int:
    """Render the whole corpus and store its digest under *label*."""
    sources = [source for source, _extra in EXTRA_INPUTS.values()]
    missing = [str(p) for p in (ENTRY, PGN, *sources) if not p.exists()]
    if missing:
        print('Error: missing input(s): ' + ', '.join(missing), file=sys.stderr)
        return 1

    out_dir = OUT_ROOT / label
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.iterdir():
        if stale.is_file():
            stale.unlink()

    strict: dict[str, object] = {}
    loose: dict[str, object] = {}
    failures: dict[str, str] = {}

    work = _corpus()
    live = sys.stdout.isatty()   # a redirected run must not collect 115 progress lines
    for index, (name, source, extra) in enumerate(work, 1):
        if live:
            print(f'\r  {index}/{len(work)}  {name:<30}', end='', flush=True)
        target = out_dir / name
        proc = subprocess.run(
            [sys.executable, str(ENTRY), str(source), '-o', str(target), *extra],
            cwd=ROOT, capture_output=True, text=True,
        )
        if proc.returncode != 0 or not target.exists():
            failures[name] = f'exit {proc.returncode}: {proc.stderr.strip()[-300:]}'
            continue
        strict[name], loose[name] = digest_file(target)

    print(f'\r{label}: {len(strict)} documents digested, {len(failures)} failed'.ljust(58)
          if live else f'{label}: {len(strict)} documents digested, {len(failures)} failed')
    for name, why in failures.items():
        print(f'  FAILED {name}: {why}', file=sys.stderr)

    _digest_path(label).write_text(
        json.dumps({'results': strict, 'results_no_version': loose, 'failures': failures},
                   indent=1, sort_keys=True),
        encoding='utf-8')
    return 1 if failures else 0


def compare(before: str, after: str, ignore_version: bool = False) -> int:
    """Report every document whose digest changed between two saved labels."""
    for label in (before, after):
        if not _digest_path(label).exists():
            print(f"Error: no snapshot called '{label}' - run: "
                  f'python {Path(__file__).name} save {label}', file=sys.stderr)
            return 1

    old = json.loads(_digest_path(before).read_text(encoding='utf-8'))
    new = json.loads(_digest_path(after).read_text(encoding='utf-8'))
    key = 'results_no_version' if ignore_version else 'results'
    if key not in old or key not in new:
        print('Error: these snapshots predate --ignore-version; save them again',
              file=sys.stderr)
        return 1
    old_results, new_results = old[key], new[key]

    note = ' (ignoring the version stamp)' if ignore_version else ''
    print(f'{before}: {len(old_results)} documents   '
          f'{after}: {len(new_results)} documents{note}')

    problems = 0
    if old['failures'] != new['failures']:
        print(f'!! different documents failed to build: '
              f'{sorted(old["failures"])} -> {sorted(new["failures"])}')
        problems += 1
    for gone in sorted(set(old_results) - set(new_results)):
        print(f'!! no longer produced: {gone}')
        problems += 1
    for added in sorted(set(new_results) - set(old_results)):
        print(f'!! newly produced: {added}')
        problems += 1

    changed = sorted(name for name in set(old_results) & set(new_results)
                     if old_results[name] != new_results[name])
    for name in changed:
        print(f'!! changed: {name}')
        one, two = old_results[name], new_results[name]
        if isinstance(one, dict) and isinstance(two, dict):
            for entry in sorted(set(one) | set(two)):
                if one.get(entry) != two.get(entry):
                    print(f'     entry {entry}')

    if changed or problems:
        print(f'\n{len(changed)} of {len(old_results)} documents differ.')
        if changed and not ignore_version:
            print('If the release number changed, retry with --ignore-version.')
        print(f'The documents themselves are under {OUT_ROOT.name}/ for inspection.')
        return 1
    print('IDENTICAL - every document matches')
    return 0


def _digest_path(label: str) -> Path:
    return OUT_ROOT / f'digest_{label}.json'


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Prove a refactor did not change what the program writes.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Save the same code under two labels first: if those two differ,\n'
               'the normalisation is incomplete and no later comparison means\n'
               'anything. See the module docstring for what gets normalised.',
    )
    sub = parser.add_subparsers(dest='command', required=True)

    saver = sub.add_parser('save', help='Render the corpus and store its digest')
    saver.add_argument('label', help='A name for this snapshot, e.g. before')

    comparer = sub.add_parser('compare', help='Compare two stored digests')
    comparer.add_argument('before', nargs='?', default='before')
    comparer.add_argument('after', nargs='?', default='after')
    comparer.add_argument('--ignore-version', action='store_true',
                          help='Also blank /Creator (DiagPDF x.y.z), which a release changes')

    args = parser.parse_args()
    if args.command == 'save':
        return save(args.label)
    return compare(args.before, args.after, ignore_version=args.ignore_version)


if __name__ == '__main__':
    raise SystemExit(main())
