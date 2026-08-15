"""DiagPDF — convert PGN / FEN / EPD files into pages of chess diagrams.

Public entry points:

    from diagpdf import parse_pgn, generate_output, RenderOptions
    positions = parse_pgn(Path('puzzles.pgn').read_text())
    generate_output(positions, RenderOptions(layout_idx=2), 'book.pdf')

A plain dict of the same keys is still accepted and converted on the way in.

The legacy ``fen2rtf`` module re-exports this API unchanged.
"""

from __future__ import annotations

__version__ = '0.15.0'

from .capabilities import (
    CAPABILITY_LABELS,
    FORMAT_CAPABILITIES,
    requested_capabilities,
    unsupported_options,
    warn_unsupported_options,
)
from .errors import FenError, UnknownFontError
from .fen import fen_to_diagram, parse_fen, validate_fen
from .fonts import (
    FIGURINE_FILES,
    FIGURINE_NAMES,
    FONT_FILES,
    FONT_NAMES,
    check_embedding_permitted,
    coerce_board_font,
    font_embedding_allowed,
    get_chess_font_path,
    resolve_board_font,
)
from .images import export_images
from .layouts import DEFAULT_LAYOUT, LAYOUTS, custom_layout, parse_grid
from .model import PositionDict
from .moves import MoveSelection, expand_positions, parse_move_selection
from .options import RenderOptions
from .output import GENERATORS, generate_output
from .parsers import (
    apply_fen_policy,
    parse_epd,
    parse_fen_file,
    parse_pgn,
    read_chess_file,
)
from .render import (
    generate_docx,
    generate_epub,
    generate_html,
    generate_pdf,
    generate_rtf,
)

__all__ = [
    '__version__',
    'CAPABILITY_LABELS',
    'DEFAULT_LAYOUT',
    'FIGURINE_FILES',
    'FIGURINE_NAMES',
    'FONT_FILES',
    'FONT_NAMES',
    'FORMAT_CAPABILITIES',
    'FenError',
    'GENERATORS',
    'LAYOUTS',
    'PositionDict',
    'RenderOptions',
    'UnknownFontError',
    'apply_fen_policy',
    'check_embedding_permitted',
    'MoveSelection',
    'coerce_board_font',
    'custom_layout',
    'expand_positions',
    'export_images',
    'fen_to_diagram',
    'font_embedding_allowed',
    'generate_docx',
    'generate_epub',
    'generate_html',
    'generate_output',
    'generate_pdf',
    'generate_rtf',
    'get_chess_font_path',
    'parse_epd',
    'parse_grid',
    'parse_move_selection',
    'parse_fen',
    'parse_fen_file',
    'parse_pgn',
    'read_chess_file',
    'requested_capabilities',
    'resolve_board_font',
    'unsupported_options',
    'validate_fen',
    'warn_unsupported_options',
]
