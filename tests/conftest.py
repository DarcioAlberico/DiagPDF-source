"""Shared fixtures for the DiagPDF test suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import fen2rtf as F  # noqa: E402  (needs the path insert above)

# ── A name no font answers to ─────────────────────────────────────────────────
# Every test that checks the unknown-font path used to spell it 'AlphaDG', which
# worked only for as long as that font was missing. When 0.16.0 rebuilt it, the
# twelve tests that name it went from testing the error path to testing nothing
# — the same trap the figurine tests fell into with 'Zurich' in 0.15.0. This
# name is asserted absent, so adding a font called it fails here and nowhere
# else.
MISSING_FONT = 'NoSuchBoardFontDG'
assert MISSING_FONT not in F.FONT_NAMES, (
    f'{MISSING_FONT} is installed now — pick another name for the unknown-font tests'
)

# ── Sample positions ──────────────────────────────────────────────────────────

START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
KINGS_FEN = '4k3/8/8/8/8/8/8/4K3 w - - 0 1'
BLACK_TO_MOVE_FEN = '8/8/8/8/8/5k2/8/5K2 b - - 0 1'

PGN_SIMPLE = '''[Event "Test 1"]
[Site "Somewhere"]
[Date "1895.01.03"]
[White "Steinitz, W."]
[Black "Lasker, Em."]
[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]

{White to move and win} 1. Ke2 Kd7 1-0
'''

PGN_THREE_GAMES = '''[Event "One"]
[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]
{First} 1.Ke2 *

[Event "Two"]
[FEN "8/8/8/8/8/5k2/8/5K2 b - - 0 1"]
{Second} 1...Kg3 *

[Event "Three"]
[FEN "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"]
{Third} 1.e4 e5 2.Nf3 *
'''

PGN_WITH_CHAPTERS = '''[Chapter "Pins"]
[Event "1.1"]
[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]
{A} 1.Ke2 *

[Chapter "Forks"]
[Event "2.1"]
[FEN "8/8/8/8/8/5k2/8/5K2 w - - 0 1"]
{B} 1.Kf2 *
'''

FEN_FILE = '''[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]
[FEN "8/8/8/8/8/5k2/8/5K2 b - - 0 1"]
'''

EPD_FILE = '''4k3/8/8/8/8/8/8/4K3 w - - bm Ke2; id "position one";
8/8/8/8/8/5k2/8/5K2 b - - bm Kg3; id "position two";
'''


@pytest.fixture(scope='session')
def diagpdf():
    """The module under test."""
    return F


@pytest.fixture
def base_opts() -> dict:
    """A complete, valid options dict — tests override only what they exercise."""
    return {
        'layout_idx': F.DEFAULT_LAYOUT,
        'font': F._default_board_font_name(),
        'font_size': 0,
        'text_size': 0,
        'coords': True,
        'flip': False,
        'flip_auto': True,
        'symbol': 'square',
        'border_style': 'simple',
        'lines_count': 0,
        'lines_mode': 'plain',
        'title_template': '{number} {comment}',
        'header': '',
        'footer': '',
        'show_header': False,
        'show_footer': False,
        'lichess_link': False,
        'answers_section': False,
        'answers_title': 'Solutions',
        'answers_cols': 1,
        'figurine_font': F._default_figurine_font_name(),
        'number_offset': 0,
        'lang': 'en',
    }


@pytest.fixture
def positions() -> list[dict]:
    """Three positions with solutions, parsed from PGN."""
    return F.parse_pgn(PGN_THREE_GAMES)


@pytest.fixture
def one_position() -> list[dict]:
    return [{'fen': KINGS_FEN, 'comment': 'Smoke', 'moves': '1.Ke2 Kd7'}]


@pytest.fixture(params=['.pdf', '.html', '.epub', '.docx', '.rtf', '.md', '.tex'])
def out_format(request) -> str:
    """Every supported output extension, one per test run."""
    return request.param


# ── Helpers shared between test modules ───────────────────────────────────────

MERIDA_TO_PIECE = {v: k[0] for k, v in F.CHESS_MERIDA.items() if k[0] is not None}
ALPHA_TO_PIECE = {v: k[0] for k, v in F.ALPHA_DG.items() if k[0] is not None}


def board_from_diagram(lines: list[str], font_name: str, has_border: bool) -> list[list[str | None]]:
    """Decode rendered diagram rows back into an 8x8 board.

    Lets tests assert that FEN -> diagram -> board round-trips, which catches
    character-map and square-colour errors that a golden-file comparison would
    only show as an opaque diff.
    """
    mapping = MERIDA_TO_PIECE if font_name in F.MERIDA_COMPATIBLE_FONTS else ALPHA_TO_PIECE
    rows = lines[1:-1] if has_border else lines
    board: list[list[str | None]] = []
    for row in rows:
        cells = row[1:-1] if has_border else row
        board.append([mapping.get(ch) if ch not in (' ', '+') else None for ch in cells])
    return board
