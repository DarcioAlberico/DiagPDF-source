"""Page layout presets.

A NamedTuple rather than a plain tuple: index access (``lay[3]``) still works
for the existing call sites, but the fields now have names, so ``lay.cols``
replaces the opaque ``lay[3]`` and ``lay.chess_pt`` the even more opaque
``lay[6]``.

The label reads *columns - plain/lined diagrams per page*: preset 2 fits six
diagrams on a page, or four once they carry notation lines.
"""

from __future__ import annotations

import re
from typing import NamedTuple


class Layout(NamedTuple):
    label_en: str
    label_ru: str
    label_pt: str
    cols: int
    rows_plain: int
    rows_lined: int
    chess_pt: int          # board font size (pt) in plain mode; lined mode refits
    title_pt: int          # title font size (pt)
    title_offset: float    # vertical nudge (mm): + toward rank 8, - toward the frame
    label_es: str = ''     # falls back to the Portuguese label, which matches

    def label(self, lang: str) -> str:
        """Return this preset's label in *lang*."""
        if lang == 'ru':
            return self.label_ru
        if lang == 'pt':
            return self.label_pt
        if lang == 'es':
            return self.label_es or self.label_pt
        return self.label_en


LAYOUTS: list[Layout] = [
    Layout('1 - 1/1 dg/pg',    '1 - 1/1 на стр.',   '1 - 1/1 diag/pág',   1, 1, 1,  52,  20,  0.0),
    Layout('1 - 1/2 dg/pg',    '1 - 1/2 на стр.',   '1 - 1/2 diag/pág',   1, 1, 2,  52,  20,  0.0),
    Layout('2 - 6/4 dg/pg',    '2 - 6/4 на стр.',   '2 - 6/4 diag/pág',   2, 3, 2,  23,  10,  -1.0),
    Layout('3 - 12/9 dg/pg',   '3 - 12/9 на стр.',  '3 - 12/9 diag/pág',  3, 4, 3,  16,   8,  -1.0),
    Layout('4 - 20/16 dg/pg',  '4 - 20/16 на стр.', '4 - 20/16 diag/pág', 4, 5, 4,  13,   6,  -1.0),
    Layout('3 - 15/12 dg/pg',  '3 - 15/12 на стр.', '3 - 15/12 diag/pág', 3, 5, 4,  13,   6,  -1.0),
    Layout('3 - 12 max',       '3 - 12 макс.',      '3 - 12 máx.',        3, 4, 4,  16,   8,  -1.0),
]
DEFAULT_LAYOUT = 2  # "2 - 6/4 dg/pg"


def parse_grid(text: str) -> tuple[int, int]:
    """Parse a ``COLSxROWS`` grid such as ``3x4``.

    Raises:
        ValueError: when the text is not two positive numbers.
    """
    match = re.fullmatch(r'\s*(\d+)\s*[x×*]\s*(\d+)\s*', str(text or ''))
    if not match:
        raise ValueError(f'invalid grid {text!r} - expected COLSxROWS, for example 3x4')
    cols, rows = int(match.group(1)), int(match.group(2))
    if not (1 <= cols <= 12 and 1 <= rows <= 12):
        raise ValueError(f'grid {cols}x{rows} is out of range - each side must be 1 to 12')
    return cols, rows


def custom_layout(cols: int, rows: int) -> Layout:
    """Return a Layout for a free-form grid.

    The font sizes are only a starting point: _compute_geometry shrinks the
    board until the grid fits the sheet, so a 6x8 grid is legible rather than
    clipped.
    """
    label = f'{cols} - {cols * rows} dg/pg'
    chess_pt = max(6, int(52 / max(cols, rows)))
    title_pt = max(5, int(20 / max(cols, rows)))
    offset = 0.0 if cols == 1 else -1.0
    return Layout(label, label, label, cols, rows, rows, chess_pt, title_pt, offset, label)
