"""Character maps of the chess diagram fonts.

Square dark = (file + rank) % 2 == 0; file 0=a..7=h, rank 0=rank1..7=rank8."""

from __future__ import annotations

from typing import Any

ALPHA_DG: dict[tuple, str] = {
    ('K', False): 'k',  ('K', True): 'K',
    ('Q', False): 'q',  ('Q', True): 'Q',
    ('R', False): 'r',  ('R', True): 'R',
    ('B', False): 'b',  ('B', True): 'B',
    ('N', False): 'h',  ('N', True): 'H',
    ('P', False): 'p',  ('P', True): 'P',
    ('k', False): 'l',  ('k', True): 'L',
    ('q', False): 'w',  ('q', True): 'W',
    ('r', False): 't',  ('r', True): 'T',
    ('b', False): 'n',  ('b', True): 'N',
    ('n', False): 'j',  ('n', True): 'J',
    ('p', False): 'o',  ('p', True): 'O',
    (None, False): ' ', (None, True): '+',
}

CHESS_MERIDA: dict[tuple, str] = {
    ('K', False): 'k',  ('K', True): 'K',
    ('Q', False): 'q',  ('Q', True): 'Q',
    ('R', False): 'r',  ('R', True): 'R',
    ('B', False): 'b',  ('B', True): 'B',
    ('N', False): 'n',  ('N', True): 'N',
    ('P', False): 'p',  ('P', True): 'P',
    ('k', False): 'l',  ('k', True): 'L',
    ('q', False): 'w',  ('q', True): 'W',
    ('r', False): 't',  ('r', True): 'T',
    ('b', False): 'v',  ('b', True): 'V',
    ('n', False): 'm',  ('n', True): 'M',
    ('p', False): 'o',  ('p', True): 'O',
    (None, False): ' ', (None, True): '+',
}

BDR_NW = '!'; BDR_N = 'z'; BDR_NE = '#'
BDR_SW = '&'; BDR_S = "'"; BDR_SE = '('
BDR_E  = '%'
RANK_CHARS = [chr(0xE0 + i) for i in range(8)]   # rank 1..8 with left border
FILE_CHARS = [chr(0xE8 + i) for i in range(8)]   # file a..h with bottom border
MERIDA_SIMPLE_RANK_CHARS = [chr(0xC0 + i) for i in range(8)]
MERIDA_SIMPLE_FILE_CHARS = [chr(0xC8 + i) for i in range(8)]
MERIDA_DOUBLE_RANK_CHARS = [chr(0xE0 + i) for i in range(8)]
MERIDA_DOUBLE_FILE_CHARS = [chr(0xE8 + i) for i in range(8)]

MERIDA_BORDER_SETS: dict[str, dict[str, Any]] = {
    'simple': {
        'top_left': '1', 'top_fill': '2', 'top_right': '3',
        'left': '4', 'right': '5',
        'bottom_left': '7', 'bottom_fill': '8', 'bottom_right': '9',
        'rank_chars': MERIDA_SIMPLE_RANK_CHARS,
        'file_chars': MERIDA_SIMPLE_FILE_CHARS,
    },
    'double': {
        'top_left': '!', 'top_fill': '"', 'top_right': '#',
        'left': '$', 'right': '%',
        'bottom_left': '/', 'bottom_fill': '(', 'bottom_right': ')',
        'rank_chars': MERIDA_DOUBLE_RANK_CHARS,
        'file_chars': MERIDA_DOUBLE_FILE_CHARS,
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# To-move symbol chars  (white-to-move, black-to-move)
# Verified: 'square' = I/M.  Others are best-guess from font path analysis.
# ─────────────────────────────────────────────────────────────────────────────
SYMBOL_CHARS: dict[str, tuple[str, str]] = {
    # sym_w = hollow/outline (visually white) = white to move
    # sym_b = solid/filled  (visually black) = black to move
    'square':   ('I', 'M'),   # confirmed: I=hollow□ white, M=solid■ black
    'circle':   ('F', 'G'),   # F=hollow○ white, G=solid● black (font analysis)
    'triangle': ('f', 'i'),   # f=hollow△ white, i=solid△ black (font analysis)
}
SYMBOL_KEYS = list(SYMBOL_CHARS.keys())
BORDER_STYLE_KEYS = ('simple', 'double', 'none')

_ALPHA_REQUIRED_CHARS = (
    set(ALPHA_DG.values())
    | {BDR_NW, BDR_N, BDR_NE, BDR_SW, BDR_S, BDR_SE, BDR_E}
    | set(RANK_CHARS)
    | set(FILE_CHARS)
    | {ch for pair in SYMBOL_CHARS.values() for ch in pair}
)
_MERIDA_REQUIRED_CHARS = (
    set(CHESS_MERIDA.values())
    | {ch for pair in SYMBOL_CHARS.values() for ch in pair}
    | {v for border in MERIDA_BORDER_SETS.values() for k, v in border.items() if isinstance(v, str)}
    | set(MERIDA_SIMPLE_RANK_CHARS)
    | set(MERIDA_SIMPLE_FILE_CHARS)
    | set(MERIDA_DOUBLE_RANK_CHARS)
    | set(MERIDA_DOUBLE_FILE_CHARS)
)

FIGURINE_PIECE_CHARS = frozenset('KQRBN')
