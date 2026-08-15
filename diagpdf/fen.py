"""FEN parsing, validation and conversion to diagram rows."""

from __future__ import annotations

from .chars import (
    ALPHA_DG,
    BDR_E,
    BDR_N,
    BDR_NE,
    BDR_NW,
    BDR_S,
    BDR_SE,
    BDR_SW,
    BDR_W,
    CHESS_MERIDA,
    FILE_CHARS,
    MERIDA_BORDER_SETS,
    RANK_CHARS,
    SYMBOL_CHARS,
)
from .errors import FenError
from .fonts import (
    BOARD_TOP_FILL,
    FONTS_WITHOUT_EMBEDDED_INDICATOR,
    MERIDA_COMPATIBLE_FONTS,
    _default_board_font_name,
)
from .log import _warn_once

_FEN_PIECES = frozenset('pnbrqkPNBRQK')


def validate_fen(fen_str: str) -> list[str]:
    """Return the list of problems found in *fen_str* (empty list means valid).

    Checks the placement field only — castling rights, en-passant square and the
    move counters are tolerated in any form, because DiagPDF never uses them.
    """
    problems: list[str] = []
    parts = (fen_str or '').strip().split()
    if not parts:
        return ['empty FEN']

    ranks = parts[0].split('/')
    if len(ranks) != 8:
        problems.append(f'expected 8 ranks, found {len(ranks)}')

    for idx, rank in enumerate(ranks):
        rank_no = 8 - idx
        width = 0
        for ch in rank:
            if ch.isdigit():
                if ch == '0':
                    problems.append(f"rank {rank_no}: '0' is not a valid skip count")
                width += int(ch)
            elif ch in _FEN_PIECES:
                width += 1
            else:
                problems.append(f'rank {rank_no}: invalid character {ch!r}')
        if width != 8:
            problems.append(f'rank {rank_no}: {width} square(s) instead of 8')

    if len(parts) > 1 and parts[1].lower() not in ('w', 'b'):
        problems.append(f'side to move must be "w" or "b", found {parts[1]!r}')

    for piece, colour in (('K', 'white'), ('k', 'black')):
        count = parts[0].count(piece)
        if count != 1:
            problems.append(f'{colour} has {count} king(s), expected exactly 1')

    return problems


def parse_fen(fen_str: str) -> tuple[list[list[str | None]], str]:
    """Parse a FEN string into an 8x8 board array and side-to-move ('w'/'b').

    Raises:
        FenError: when the string carries no placement field at all.
    """
    parts = (fen_str or '').strip().split()
    if not parts:
        raise FenError('empty FEN string')
    board_str = parts[0]
    side = parts[1].lower() if len(parts) > 1 else 'w'
    if side not in ('w', 'b'):
        side = 'w'
    board: list[list[str | None]] = [[None] * 8 for _ in range(8)]
    rank, file = 7, 0
    for ch in board_str:
        if ch == '/':
            rank -= 1; file = 0
        elif ch.isdigit():
            file += int(ch)
        else:
            if 0 <= rank <= 7 and 0 <= file <= 7:
                board[rank][file] = ch
            file += 1
    return board, side


def board_is_flipped(side: str, flip: bool, flip_auto: bool) -> bool:
    """Return True when the board is drawn from Black's side.

    Every renderer has to reach the same answer for the same position, so the
    rule lives here rather than being restated per format.
    """
    return (not flip) if (flip_auto and side == 'b') else flip


def fen_to_diagram(
    fen_str: str,
    coords: bool = True,
    flip: bool = False,
    flip_auto: bool = False,
    symbol: str = 'square',
    font_name: str = '',
    border_style: str = 'simple',
) -> list[str]:
    """Convert a FEN string to diagram rows for the selected chess font."""
    board, side = parse_fen(fen_str)
    actual_flip = board_is_flipped(side, flip, flip_auto)
    sym_w, sym_b = SYMBOL_CHARS.get(symbol, SYMBOL_CHARS['square'])
    hg_char = sym_w if side == 'w' else sym_b
    rank_order = range(7, -1, -1) if not actual_flip else range(0, 8)
    file_order = list(range(0, 8)) if not actual_flip else list(range(7, -1, -1))
    file_labels = FILE_CHARS if not actual_flip else list(reversed(FILE_CHARS))

    visual_bottom_ri = 0 if not actual_flip else 7
    lines = []

    if not font_name:
        font_name = _default_board_font_name()

    is_merida = font_name in MERIDA_COMPATIBLE_FONTS
    char_map = CHESS_MERIDA if is_merida else ALPHA_DG

    if is_merida:
        style = MERIDA_BORDER_SETS.get(border_style, MERIDA_BORDER_SETS['simple'])
        rank_chars = style['rank_chars']
        file_chars = style['file_chars'] if not actual_flip else list(reversed(style['file_chars']))

        if border_style == 'none':
            # The Merida coordinate glyphs carry a border segment, so they
            # cannot be drawn on a borderless board. Say so instead of silently
            # ignoring the option.
            if coords:
                _warn_once(
                    'coordinates are not available with border style "none" - '
                    'use --border simple or --border double to show them'
                )
            for ri in rank_order:
                row = ''
                for fi in file_order:
                    piece = board[ri][fi]
                    dark = (fi + ri) % 2 == 0
                    row += char_map.get((piece, dark), ' ')
                lines.append(row)
        else:
            lines.append(style['top_left'] + style['top_fill'] * 8 + style['top_right'])
            for ri in rank_order:
                left = rank_chars[ri] if coords else style['left']
                row = left
                for fi in file_order:
                    piece = board[ri][fi]
                    dark = (fi + ri) % 2 == 0
                    row += char_map.get((piece, dark), ' ')
                row += style['right']
                lines.append(row)
            if coords:
                lines.append(style['bottom_left'] + ''.join(file_chars) + style['bottom_right'])
            else:
                lines.append(style['bottom_left'] + style['bottom_fill'] * 8 + style['bottom_right'])
    else:
        # AlphaDG draws the top edge with 'z'; plain Chess Alpha has no such
        # glyph and uses the double quote, so the fill comes from the font.
        top_fill = BOARD_TOP_FILL.get(font_name, BDR_N)
        # The to-move symbol sits in the board's right edge — but only in the
        # fonts that carry a glyph for it. Where they do not, the edge is drawn
        # plain and the renderers add a Unicode symbol beside the board.
        draws_indicator = font_name not in FONTS_WITHOUT_EMBEDDED_INDICATOR
        if coords:
            lines.append(BDR_NW + top_fill * 8 + BDR_NE)
            for ri in rank_order:
                row = RANK_CHARS[ri]
                for fi in file_order:
                    piece = board[ri][fi]
                    dark = (fi + ri) % 2 == 0
                    row += char_map.get((piece, dark), ' ')
                row += hg_char if (ri == visual_bottom_ri and draws_indicator) else BDR_E
                lines.append(row)
            lines.append(BDR_SW + ''.join(file_labels) + BDR_SE)
        else:
            lines.append('!' + top_fill * 8 + '#')
            for ri in rank_order:
                row = BDR_W
                for fi in file_order:
                    piece = board[ri][fi]
                    dark = (fi + ri) % 2 == 0
                    row += char_map.get((piece, dark), ' ')
                row += hg_char if (ri == visual_bottom_ri and draws_indicator) else BDR_E
                lines.append(row)
            lines.append('&' + BDR_S * 8 + '(')
    return lines
