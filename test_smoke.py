#!/usr/bin/env python3
"""
Smoke test: generates one file for each supported output format.

Usage:
    python test_smoke.py [output_dir]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fen2rtf import (
    DEFAULT_LAYOUT,
    _default_board_font_name,
    generate_output,
)


def run_smoke(out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)

    positions = [
        {
            'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1',
            'comment': 'Smoke',
            'moves': '1.Ke2',
        }
    ]

    opts = {
        'layout_idx': DEFAULT_LAYOUT,
        'font': _default_board_font_name(),
        'font_size': 14,
        'coords': True,
        'flip': False,
        'flip_auto': True,
        'symbol': 'square',
        'border_style': 'simple',
        'title_mode': 'comment',
        'answers_section': False,
        'lichess_link': False,
        'header': '',
        'footer': '',
        'show_header': False,
        'show_footer': False,
    }

    # Every format the program writes, through the same entry point the command
    # line uses -- so a format added there is covered here without being listed
    # twice.
    formats = ['.pdf', '.tex', '.html', '.epub', '.docx', '.rtf', '.md']

    failures = 0
    for ext in formats:
        out_path = out_dir / f'smoke{ext}'
        try:
            generate_output(positions, opts, out_path)
            if not out_path.exists() or out_path.stat().st_size <= 0:
                raise RuntimeError('output file missing or empty')
            print(f'OK  {out_path.name}')
        except Exception as exc:
            failures += 1
            print(f'ERR {out_path.name}: {exc}', file=sys.stderr)

    return failures


if __name__ == '__main__':
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / 'smoke_out'
    raise SystemExit(1 if run_smoke(out_dir) else 0)
