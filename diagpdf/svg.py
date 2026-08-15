"""Vector export of one diagram.

The PNG export rasterises the board through Pillow at a chosen pixel size. This
one writes the glyph *outlines* instead, so the diagram scales to any size and
needs no chess font at the other end -- which is what a publisher or a web page
usually wants from a diagram.

Only the title and the notation numbers stay as text: those are ordinary words,
set in whatever the viewer has. Everything that carries chess meaning -- the
squares, the pieces, the border, the coordinates, the side-to-move marker -- is
a path or a shape, so it cannot come out wrong for want of a font.

Addressing the glyphs
---------------------
A board character has to be turned into a glyph, and these fonts disagree about
where their glyphs live. Three maps are consulted, in this order:

1. the Windows *Symbol* table at U+F020-U+F0EF, where the legacy chess fonts
   keep the whole board;
2. an ordinary Unicode table, which is what a modern one like ``chess-alpha``
   carries;
3. the Macintosh table -- but **only** for a font that offers neither of the
   above.

That last condition is the important one. ``ChessMerida`` has no Unicode table
at all, and its Macintosh table is the only thing that maps plain ASCII onto its
squares, so it must be read. ``chess-alpha`` has a Unicode table *and* a
Macintosh one that maps the space -- an empty light square -- onto the glyph for
a white rook. Reading it there would put pieces on the board that the position
does not have.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from .fen import fen_to_diagram, parse_fen
from .fonts import get_chess_font_path
from .log import _warn_once
from .model import PositionDict
from .options import RenderOptions
from .render.common import _has_embedded_side_indicator, _make_title, _position_number
from .resources import _resource

# The title and the notation numbers are the only text left in the file.
TEXT_FONT_STACK = "'Segoe UI', 'DejaVu Sans', Helvetica, Arial, sans-serif"


class SvgUnavailable(RuntimeError):
    """Raised when the diagram cannot be drawn as vectors (unreadable font)."""


UNICODE_TABLES = ((3, 10), (3, 1), (0, 6), (0, 4), (0, 3), (0, 2), (0, 1), (0, 0))


def _glyph_maps(font) -> tuple[dict[int, str], dict[int, str], dict[int, str]]:
    """Return the (symbol, unicode, macintosh) character maps of a font."""
    symbol: dict[int, str] = {}
    unicode_map: dict[int, str] = {}
    macintosh: dict[int, str] = {}
    for table in (font['cmap'].tables if 'cmap' in font else []):
        where = (table.platformID, table.platEncID)
        if where == (3, 0):
            symbol.update(table.cmap)
        elif where in UNICODE_TABLES:
            unicode_map.update(table.cmap)
        elif table.platformID == 1:
            macintosh.update(table.cmap)
    return symbol, unicode_map, macintosh


class _Outlines:
    """The outlines of one chess font, addressed the way the board addresses it."""

    def __init__(self, font_path: str) -> None:
        try:
            from fontTools import ttLib
            self._font = ttLib.TTFont(str(font_path))
            self._glyphs = self._font.getGlyphSet()
            self.upem = int(self._font['head'].unitsPerEm) or 1000
            self._hmtx = self._font['hmtx']
        except Exception as exc:                        # unreadable or truncated TTF
            raise SvgUnavailable(f'could not read {Path(font_path).name}: {exc}') from exc
        self._symbol, self._unicode, self._mac = _glyph_maps(self._font)
        self._paths: dict[str, str] = {}                # glyph name -> path data
        self._ids: dict[str, str] = {}                  # glyph name -> id in <defs>

    def close(self) -> None:
        self._font.close()

    def _glyph_name(self, char: str) -> str | None:
        """Resolve one board character, see the module docstring for the order."""
        code = ord(char)
        name = self._symbol.get(0xF000 + code)
        if name is None:
            name = self._unicode.get(code)
        if name is None and not self._symbol and not self._unicode:
            name = self._mac.get(code)
        return name

    def advance(self, char: str) -> float:
        """Width of *char* in font units; one em when the font has no such glyph."""
        name = self._glyph_name(char)
        if name is None:
            return float(self.upem)
        try:
            return float(self._hmtx[name][0])
        except (KeyError, TypeError):
            return float(self.upem)

    def reference(self, char: str) -> str | None:
        """Return the id of *char*'s outline, drawing it into the defs once.

        None means the font has nothing for this character. For a space that is
        the whole truth -- an empty square is empty -- so it is not reported.
        """
        name = self._glyph_name(char)
        if name is None:
            if char != ' ':
                _warn_once(f'the board font has no glyph for {char!r} - '
                           'that square is left blank in the SVG')
            return None
        if name in self._ids:
            return self._ids[name]
        from fontTools.pens.svgPathPen import SVGPathPen
        pen = SVGPathPen(self._glyphs, ntos=lambda value: f'{value:.0f}')
        try:
            self._glyphs[name].draw(pen)
        except Exception:                               # pragma: no cover - broken outline
            return None
        commands = pen.getCommands()
        if not commands:                                # a blank glyph, e.g. the space
            return None
        ident = f'g{len(self._ids)}'
        self._ids[name] = ident
        self._paths[ident] = commands
        return ident

    def defs(self) -> list[str]:
        """The outlines used so far, as one <defs> block."""
        if not self._paths:
            return []
        return (['  <defs>']
                + [f'    <path id="{ident}" d="{data}"/>' for ident, data in self._paths.items()]
                + ['  </defs>'])


def _num(value: float) -> str:
    """Format a coordinate: short, and without a trailing '.0'."""
    return f'{value:.2f}'.rstrip('0').rstrip('.') or '0'


def _indicator_shape(symbol: str, x: float, y: float, size: float, filled: bool) -> str:
    """Draw the side-to-move marker as a shape rather than as a character.

    The PNG export borrows the symbol from a text font. Here it is the shape
    itself, so it cannot fall back to a missing-glyph box.
    """
    fill = '#000' if filled else 'none'
    common = f'fill="{fill}" stroke="#000" stroke-width="{_num(max(1.0, size / 10))}"'
    if symbol == 'circle':
        r = size / 2
        return f'<circle cx="{_num(x + r)}" cy="{_num(y + r)}" r="{_num(r)}" {common}/>'
    if symbol == 'triangle':
        points = f'{_num(x + size / 2)},{_num(y)} {_num(x + size)},{_num(y + size)} {_num(x)},{_num(y + size)}'
        return f'<polygon points="{points}" {common}/>'
    return (f'<rect x="{_num(x)}" y="{_num(y)}" width="{_num(size)}" '
            f'height="{_num(size)}" {common}/>')


def render_diagram_svg(
    opts: RenderOptions | dict,
    position: PositionDict | None = None,
    *,
    row_px: int = 40,
    number: int | None = None,
) -> str:
    """Return one diagram as a standalone SVG document.

    Args:
        opts: the render options; the board font, coordinates, flip, border
            style, title and notation lines are all honoured.
        position: the position to draw.
        row_px: height of one board row in user units. Everything else is
            proportional to it, so the picture is the same at any size.
        number: the diagram number for the title; taken from the numbering
            options when not given.

    Raises:
        SvgUnavailable: when the board font cannot be read.
    """
    opts = RenderOptions.coerce(opts)
    position = position or {}
    fen = str(position.get('fen', '') or '').strip()
    font_name = opts.font
    try:
        font_path = get_chess_font_path(font_name, _resource('Fonts'))
    except Exception as exc:
        raise SvgUnavailable(str(exc)) from exc

    rows = fen_to_diagram(
        fen,
        coords=opts.coords,
        flip=opts.flip,
        flip_auto=opts.flip_auto,
        symbol=opts.symbol,
        font_name=font_name,
        border_style=opts.border_style,
    )
    side = parse_fen(fen)[1]
    number = _position_number(0, opts) if number is None else number
    title = _make_title(position, number, opts.title_template, opts.title_mode,
                        opts.title_custom, opts)

    outlines = _Outlines(font_path)
    try:
        scale = row_px / outlines.upem
        margin = max(6.0, row_px / 3)
        title_size = row_px * 0.6
        title_h = row_px * 0.9 if title else 0.0
        line_h = row_px * 0.55
        notation_h = opts.lines_count * line_h

        board_w = max(
            (sum(outlines.advance(ch) for ch in row) * scale for row in rows),
            default=row_px * 10,
        )
        indicator = not _has_embedded_side_indicator(font_name)
        indicator_size = row_px * 0.5
        indicator_w = row_px * 0.8 if indicator else 0.0

        width = board_w + margin * 2 + indicator_w
        height = title_h + len(rows) * row_px + notation_h + margin * 2

        body: list[str] = []
        y = margin
        if title:
            body.append(
                f'  <text x="{_num(width / 2)}" y="{_num(y + title_size)}" '
                f'text-anchor="middle" font-family="{TEXT_FONT_STACK}" '
                f'font-size="{_num(title_size)}" fill="#000">{escape(title)}</text>'
            )
            y += title_h

        board_top = y
        for row in rows:
            x = margin
            baseline = y + row_px           # the square glyphs sit on the baseline
            for char in row:
                ident = outlines.reference(char)
                if ident is not None:
                    body.append(
                        f'  <use href="#{ident}" xlink:href="#{ident}" '
                        f'transform="translate({_num(x)} {_num(baseline)}) '
                        f'scale({_num(scale)} {_num(-scale)})"/>'
                    )
                x += outlines.advance(char) * scale
            y += row_px

        if indicator:
            # Beside the bottom rank: the last row is the file coordinates when
            # they are drawn, the board itself when they are not.
            bottom = board_top + (len(rows) - (1 if len(rows) == 8 else 2)) * row_px
            body.append('  ' + _indicator_shape(
                opts.symbol, margin + board_w + row_px * 0.15,
                bottom + (row_px - indicator_size) / 2, indicator_size, side == 'b',
            ))

        if opts.lines_count:
            body.extend(_notation_lines(opts, side, margin, y, board_w, line_h, row_px))

        head = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{_num(width)}" height="{_num(height)}" '
            f'viewBox="0 0 {_num(width)} {_num(height)}" role="img">',
        ]
        if title:
            head.append(f'  <title>{escape(title)}</title>')
        head.append(f'  <rect width="{_num(width)}" height="{_num(height)}" fill="#fff"/>')
        return '\n'.join(head + outlines.defs() + body + ['</svg>', ''])
    finally:
        outlines.close()


def _notation_lines(opts: RenderOptions, side: str, left: float, top: float,
                    board_w: float, line_h: float, row_px: float) -> list[str]:
    """Draw the blank notation lines under the board.

    Numbered lines are split in two, one blank per side to move. Black to move
    means White has no move to write on the first line, so that half is left
    without a rule -- the same rule every other renderer follows.
    """
    out: list[str] = []
    right = left + board_w
    numbered = opts.lines_mode == 'numbered'
    label_size = row_px * 0.45
    for index in range(opts.lines_count):
        base = top + index * line_h + line_h - 2
        if numbered:
            out.append(
                f'  <text x="{_num(left)}" y="{_num(base - 1)}" '
                f'font-family="{TEXT_FONT_STACK}" font-size="{_num(label_size)}" '
                f'fill="#000">{index + 1}.</text>'
            )
            start = left + row_px * 0.8
            middle = (start + right) / 2
            if not (index == 0 and side == 'b'):
                out.append(_rule(start, base, middle - 3))
            out.append(_rule(middle + 3, base, right))
        else:
            out.append(_rule(left, base, right))
    return out


def _rule(x1: float, y: float, x2: float) -> str:
    return (f'  <line x1="{_num(x1)}" y1="{_num(y)}" x2="{_num(x2)}" y2="{_num(y)}" '
            f'stroke="#000" stroke-width="1"/>')
