#!/usr/bin/env python3
"""Chess Diagram Generator — compatibility entry point.

The implementation now lives in the ``diagpdf`` package. This module keeps the
old import surface working, so existing scripts and the frozen executable carry
on unchanged:

    python fen2rtf.py input.pgn [options]
    python fen2rtf.py --gui

New code should import from the package instead::

    from diagpdf import generate_output, parse_pgn
"""

from __future__ import annotations

import sys
from pathlib import Path

# Running the script directly from a checkout must find the sibling package.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from diagpdf import __version__
from diagpdf.capabilities import (
    CAPABILITY_LABELS,
    FORMAT_CAPABILITIES,
    requested_capabilities,
    unsupported_options,
    warn_unsupported_options,
)
from diagpdf.chars import (
    ALPHA_DG,
    BORDER_STYLE_KEYS,
    CHESS_MERIDA,
    FIGURINE_PIECE_CHARS,
    MERIDA_BORDER_SETS,
    MERIDA_DOUBLE_FILE_CHARS,
    MERIDA_DOUBLE_RANK_CHARS,
    MERIDA_SIMPLE_FILE_CHARS,
    MERIDA_SIMPLE_RANK_CHARS,
    SYMBOL_CHARS,
    SYMBOL_KEYS,
)
from diagpdf.cli import main
from diagpdf.config import _load_config, _save_config
from diagpdf.errors import FenError, UnknownFontError
from diagpdf.fen import fen_to_diagram, parse_fen, validate_fen
from diagpdf.fonts import (
    DIRECT_PDF_CHESS_FONTS,
    FIGURINE_FILES,
    FIGURINE_NAMES,
    FONT_FILES,
    FONT_NAMES,
    FONTS_WITHOUT_EMBEDDED_INDICATOR,
    MERIDA_COMPATIBLE_FONTS,
    FontManager,
    _board_font_family_name,
    _BOARD_FONT_INFO,
    _default_board_font_file,
    _default_board_font_name,
    _default_figurine_font_name,
    _ensure_chess_font_patched,
    _font_data_uri,
    _font_family_name,
    _get_text_font_candidates,
    check_embedding_permitted,
    coerce_board_font,
    font_embedding_allowed,
    get_chess_font_path,
    resolve_board_font,
)
from diagpdf.geometry import (
    HDR_FTR_Y,
    MARGIN_LR,
    MARGIN_TB,
    MIN_FONT_PT,
    NOTATION_LINE_H,
    PAGE_H,
    PAGE_W,
    ROW_OVERHEAD,
    TITLE_LH_FACTOR,
    _compute_geometry,
    _Geometry,
    _PT,
)
from diagpdf.gui import run_gui
from diagpdf.i18n import (
    DEFAULT_LANG,
    LANGS,
    T,
    _answers_heading,
    _lang_index,
    _layout_label,
    _lichess_label,
    _next_lang,
    missing_translations,
    tr,
)
from diagpdf.layouts import DEFAULT_LAYOUT, LAYOUTS
from diagpdf.log import _WARNED_ONCE, _warn, _warn_once
from diagpdf.model import PositionDict
from diagpdf.options import RenderOptions
from diagpdf.output import GENERATORS, generate_output
from diagpdf.parsers import (
    _clean_moves,
    _comment_state_after,
    _first_text_comment,
    _split_pgn_games,
    _split_tags_and_movetext,
    apply_fen_policy,
    parse_epd,
    parse_fen_file,
    parse_pgn,
    read_chess_file,
)
from diagpdf.paths import (
    _default_output_path,
    _ext_from_save_filter,
    _normalize_output_path,
)
from diagpdf.render.common import (
    _anchor_id,
    _apply_title_template,
    _chapter_groups,
    _epub_document_title,
    _figurine_family_name,
    _figurine_font_path,
    _figurine_segments,
    _has_embedded_side_indicator,
    _layout_columns,
    _lichess_analysis_url,
    _make_title,
    _numbering,
    _position_number,
    _side_indicator_text,
    _split_title_number_prefix,
)
from diagpdf.render.docx import generate_docx
from diagpdf.render.epub import generate_epub
from diagpdf.render.html import (
    _board_row_size_px,
    _build_diagram_css,
    _css_figurine_family,
    _css_font_family,
    _html_font_url,
    _html_moves,
    _html_notation_lines,
    _render_html_document,
    generate_html,
)
from diagpdf.render.pdf import generate_pdf
from diagpdf.render.rtf import generate_rtf
from diagpdf.resources import _resource

__all__ = [name for name in dir() if not name.startswith('_') or name.startswith('_')]


if __name__ == '__main__':
    main()
