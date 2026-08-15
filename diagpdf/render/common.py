"""Helpers shared by every renderer."""

from __future__ import annotations

import re
from pathlib import Path

from ..chars import FIGURINE_PIECE_CHARS
from ..fen import parse_fen
from ..fonts import (
    FIGURINE_FILES,
    FONTS_WITHOUT_EMBEDDED_INDICATOR,
    _font_family_name,
)
from ..layouts import LAYOUTS, custom_layout
from ..model import PositionDict
from ..options import RenderOptions
from ..resources import _resource


def _apply_title_template(template: str, pos: PositionDict, num: int,
                          opts: RenderOptions | None = None) -> str:
    """Expand a title template with position metadata.

    Variables: {number}, {event}, {white}, {black}, {date}, {comment}.
    Empty substitutions collapse surrounding whitespace automatically.
    """
    vals = {
        'number':  _format_number(num, opts) if opts is not None else str(num),
        'event':   pos.get('event', ''),
        'white':   pos.get('white', ''),
        'black':   pos.get('black', ''),
        'date':    pos.get('date', ''),
        'comment': pos.get('comment', '').strip(),
    }
    result = template
    for key, val in vals.items():
        result = result.replace(f'{{{key}}}', val)
    return ' '.join(result.split())   # collapse whitespace from empty substitutions


def _make_title(pos: PositionDict, num: int, template: str, mode: str, custom: str,
                opts: RenderOptions | None = None) -> str:
    """Build the diagram title from position data."""
    if template:
        return _apply_title_template(template, pos, num, opts)
    comment = pos.get('comment', '').strip()
    if mode == 'number':
        return str(num)
    if mode == 'custom':
        return f'{num} {custom}' if custom else str(num)
    return f'{num} {comment}' if comment else str(num)  # 'comment' mode


def _split_title_number_prefix(title: str, num: int,
                               opts: RenderOptions | None = None) -> tuple[str, str]:
    """Split a leading diagram number from a title when present.

    The number must be followed by whitespace or end the title, so that a title
    such as ``'12 Mate'`` is not cut after its first digit when *num* is 1.
    The comparison uses the number as rendered, so a --number-format such as
    ``#{n}`` still yields a clickable prefix.
    """
    shown = _format_number(num, opts) if opts is not None else str(num)
    m = re.match(rf'^({re.escape(shown)}(?:[.)])?)(\s+|$)(.*)$', title)
    if not m:
        return '', title
    return m.group(1) + m.group(2), m.group(3)

def _position_number(idx: int, opts: RenderOptions) -> int:
    """Return the number shown for the position at *idx* (0-based).

    Shared by every renderer and by the answers section, so a diagram and its
    solution can never disagree. Where the numbering may restart -- inside a
    document with chapters -- use :func:`_numbering` instead, which is the same
    rule applied to the whole document at once.
    """
    return idx + opts.number_start + opts.number_offset


def _numbering(positions: list[PositionDict], opts: RenderOptions) -> list[int]:
    """Return the number shown for every position, in document order.

    Numbers normally run straight through the document. With
    ``--number-restart-per-chapter`` each chapter starts again from
    ``--number-start``, which is how a book of themed sections numbers its
    exercises: "Pins 1-12", then "Forks 1-15", rather than one run of 27.
    """
    base = opts.number_start + opts.number_offset
    if not opts.number_restart_per_chapter:
        return [index + base for index in range(len(positions))]
    numbers = [base] * len(positions)
    for _chapter, indices in _chapter_groups(positions):
        for offset, index in enumerate(indices):
            numbers[index] = offset + base
    return numbers


def _anchor_id(idx: int) -> int:
    """Return the identifier tying a diagram to its solution.

    Deliberately not the number on the page: once the numbering restarts per
    chapter that number comes round again in every chapter, and two anchors
    sharing a name would send every link in the book to the first of them.
    Positions are counted from one in document order -- which is what the
    number itself was by default, so an ordinary document keeps the anchors it
    always had.
    """
    return idx + 1


def _format_number(number: int, opts: RenderOptions) -> str:
    """Render a diagram number through the --number-format template."""
    template = opts.number_format.strip()
    if not template:
        return str(number)
    try:
        return template.format(n=number, number=number)
    except (KeyError, IndexError, ValueError):
        return str(number)


def _lichess_analysis_url(fen: str) -> str:
    """Build a Lichess analysis URL for a FEN, preserving side-to-move orientation."""
    fen = fen.strip()
    if not fen:
        return ''
    side = parse_fen(fen)[1]
    color = 'black' if side == 'b' else 'white'
    return f'https://lichess.org/analysis/{fen.replace(" ", "_")}?color={color}'


def _has_embedded_side_indicator(font_name: str) -> bool:
    """Return True when the chess font already draws the side-to-move marker in-board."""
    return font_name not in FONTS_WITHOUT_EMBEDDED_INDICATOR


def _side_indicator_text(side: str, symbol: str) -> str:
    """Return a Unicode fallback symbol for side-to-move when the chess font lacks one."""
    glyphs = {
        'square': ('□', '■'),
        'circle': ('○', '●'),
        'triangle': ('△', '▲'),
    }
    white_glyph, black_glyph = glyphs.get(symbol, glyphs['square'])
    return black_glyph if side == 'b' else white_glyph


def _figurine_segments(
    text: str, text_font: str, figurine_font: str
) -> list[tuple[str, str]]:
    """Split *text* into (font, run) pairs, using the figurine font for pieces."""
    segments: list[tuple[str, str]] = []
    current_font = text_font
    buf = ''
    for ch in text:
        want = figurine_font if ch in FIGURINE_PIECE_CHARS else text_font
        if want != current_font:
            if buf:
                segments.append((current_font, buf))
            buf = ch
            current_font = want
        else:
            buf += ch
    if buf:
        segments.append((current_font, buf))
    return segments

def _figurine_font_path(opts: RenderOptions) -> Path | None:
    """Return the figurine font file backing the answers section, if any."""
    file_name = FIGURINE_FILES.get(opts.figurine_font) or next(iter(FIGURINE_FILES.values()), '')
    if not file_name:
        return None
    path = _resource('Fonts') / file_name
    return path if path.exists() else None

def _layout_for(opts: RenderOptions):
    """Return the layout preset in force, honouring a custom --grid."""
    # layout_idx is clamped to a valid index when the options are built.
    return custom_layout(*opts.grid) if opts.grid else LAYOUTS[opts.layout_idx]


def _layout_rows(opts: RenderOptions) -> int:
    """Return the rows per page for the layout in force."""
    lay = _layout_for(opts)
    return lay.rows_lined if opts.lines_count > 0 else lay.rows_plain


def _layout_columns(opts: RenderOptions) -> int:
    return max(1, int(_layout_for(opts).cols))

def _chapter_groups(positions: list[PositionDict]) -> list[tuple[str, list[int]]]:
    """Group position indices into chapters, in order.

    A position carries a chapter name only when its game had a ``[Chapter]``
    tag, so a chapter of twelve studies usually names the first one and leaves
    the other eleven blank. An unnamed position therefore continues the chapter
    before it -- which is what every renderer already assumed when it drew the
    running header and broke the page, and what decides where the numbering
    restarts and where a per-chapter answers section ends.

    Positions appearing before the first tag belong to no chapter, and stay a
    group of their own.
    """
    groups: list[tuple[str, list[int]]] = []
    for index, pos in enumerate(positions):
        name = pos.get('chapter', '') or ''
        if groups and (groups[-1][0] == name or not name):
            groups[-1][1].append(index)
        else:
            groups.append((name, [index]))
    return groups

def _figurine_family_name(opts: RenderOptions) -> str:
    """Return the internal family name of the figurine font used for answers."""
    path = _figurine_font_path(opts)
    return _font_family_name(path) if path is not None else ''

def _epub_document_title(opts: RenderOptions) -> str:
    """Return the publication title for EPUB metadata."""
    return opts.doc_title.strip() or 'Chess Diagrams'
