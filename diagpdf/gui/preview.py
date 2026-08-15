"""Rendering a single diagram for the preview panel.

Kept free of Tk so it can be exercised without a display: the panel only has to
turn the returned PNG bytes into a PhotoImage.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from ..fen import fen_to_diagram, parse_fen
from ..fonts import _font_codepoints, get_chess_font_path, resolve_board_font
from ..model import PositionDict
from ..options import RenderOptions
from ..render.common import (
    _has_embedded_side_indicator,
    _make_title,
    _position_number,
    _side_indicator_text,
)
from ..resources import _resource

PREVIEW_FEN = 'r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4'
PREVIEW_POSITION: PositionDict = {
    'fen': PREVIEW_FEN,
    'comment': 'Preview',
    'moves': '1. Ng5 Nh6 2. Nxf7',
}


class PreviewUnavailable(RuntimeError):
    """Raised when the preview cannot be drawn (Pillow missing, bad options)."""


def _drawable(row: str, codepoints: set[int]) -> str:
    """Map diagram characters onto the codepoints the font actually exposes."""
    return ''.join(
        chr(0xF000 + ord(ch)) if (0xF000 + ord(ch)) in codepoints else ch
        for ch in row
    )


def _load_board_font(path: str, size: int):
    """Load a chess font for Pillow, selecting its symbol character map.

    These fonts carry no Unicode cmap: they ship a Macintosh Roman table plus a
    Windows *Symbol* one whose glyphs sit at U+F020-U+F0EF. Loaded the ordinary
    way, FreeType resolves every character to an empty glyph — correct advance
    widths, no ink — so the board renders as a blank rectangle. Asking for the
    symbol charmap and addressing the glyphs at their U+F0xx codepoints is what
    makes them draw.
    """
    from PIL import ImageFont

    try:
        return ImageFont.truetype(path, size=size, encoding='symb')
    except Exception:
        return ImageFont.truetype(path, size=size)


def render_preview_png(
    opts: RenderOptions | dict,
    position: PositionDict | None = None,
    *,
    row_px: int = 30,
    max_width: int = 320,
    number: int | None = None,
) -> bytes:
    """Render one diagram as PNG bytes, using the current settings.

    *number* is the diagram number to put in the title. The preview panel shows
    a single position and leaves it out; an export passes the real number, which
    it has to, or every exported picture would be titled after the first one.

    Raises:
        PreviewUnavailable: when Pillow is not installed or the font cannot be
            loaded — the panel shows a short message instead of a picture.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:                              # pragma: no cover - env dependent
        raise PreviewUnavailable('Pillow is required for the preview') from exc

    opts = RenderOptions.coerce(opts)
    position = position or PREVIEW_POSITION
    fen = str(position.get('fen', '') or PREVIEW_FEN).strip()
    font_name = opts.font
    try:
        resolve_board_font(font_name)
        board_font_path = get_chess_font_path(font_name, _resource('Fonts'))
    except Exception as exc:
        raise PreviewUnavailable(str(exc)) from exc

    side = parse_fen(fen)[1]
    rows = fen_to_diagram(
        fen,
        coords=opts.coords,
        flip=opts.flip,
        flip_auto=opts.flip_auto,
        symbol=opts.symbol,
        font_name=font_name,
        border_style=opts.border_style,
    )
    indicator = (
        _side_indicator_text(side, opts.symbol)
        if not _has_embedded_side_indicator(font_name) else ''
    )

    # Fit the board to the panel rather than to the printed page.
    columns = max(len(row) for row in rows) if rows else 10
    row_px = max(10, min(row_px, max_width // max(1, columns)))
    try:
        board_font = _load_board_font(board_font_path, row_px)
    except Exception as exc:
        raise PreviewUnavailable(f'could not load {Path(board_font_path).name}') from exc
    label_font = _load_label_font(int(row_px * 0.6))
    codepoints = _font_codepoints(Path(board_font_path))
    drawn_rows = [_drawable(row, codepoints) for row in rows]

    margin = max(6, row_px // 3)
    probe = ImageDraw.Draw(Image.new('RGB', (1, 1), 'white'))
    boxes = [probe.textbbox((0, 0), row, font=board_font) for row in drawn_rows]
    board_w = max((box[2] - box[0]) for box in boxes) if boxes else row_px * columns

    title = _make_title(
        position, _position_number(0, opts) if number is None else number,
        opts.title_template, opts.title_mode, opts.title_custom, opts,
    )
    title_h = int(row_px * 0.9) if title else 0

    lines_count = opts.lines_count
    line_h = int(row_px * 0.55)
    notation_h = lines_count * line_h

    indicator_w = int(row_px * 0.9) if indicator else 0
    width = board_w + margin * 2 + indicator_w
    height = title_h + len(rows) * row_px + notation_h + margin * 2

    image = Image.new('RGB', (max(1, width), max(1, height)), 'white')
    draw = ImageDraw.Draw(image)

    y = margin
    if title:
        draw.text((width // 2, y), title, fill='black', font=label_font, anchor='ma')
        y += title_h

    board_top = y
    for row, box in zip(drawn_rows, boxes, strict=True):
        draw.text((margin - box[0], y - box[1]), row, fill='black', font=board_font)
        y += row_px

    if indicator:
        bottom_row = board_top + (len(rows) - (1 if len(rows) == 8 else 2)) * row_px
        draw.text((margin + board_w + 2, bottom_row), indicator, fill='black', font=label_font)

    if lines_count:
        numbered = opts.lines_mode == 'numbered'
        left, right = margin, margin + board_w
        for index in range(lines_count):
            base = y + index * line_h + line_h - 2
            if numbered:
                label = f'{index + 1}.'
                draw.text((left, base - line_h + 2), label, fill='black', font=label_font)
                start = left + int(row_px * 0.8)
                middle = (start + right) // 2
                if not (index == 0 and side == 'b'):
                    draw.line((start, base, middle - 3, base), fill='black')
                draw.line((middle + 3, base, right, base), fill='black')
            else:
                draw.line((left, base, right, base), fill='black')

    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def _load_label_font(size: int):
    """Return a system font for the title and notation numbers."""
    from PIL import ImageFont

    from ..fonts import _get_text_font_candidates

    for candidate in _get_text_font_candidates():
        try:
            return ImageFont.truetype(candidate, size=max(8, size))
        except Exception:
            continue
    return ImageFont.load_default()
