"""Page and grid geometry for the paginated PDF output."""

from __future__ import annotations

from dataclasses import dataclass

from .fonts import MERIDA_COMPATIBLE_FONTS
from .layouts import LAYOUTS, custom_layout
from .options import RenderOptions
from .page import (
    DEFAULT_HDR_FTR_Y,
    DEFAULT_MARGIN_LR,
    DEFAULT_MARGIN_TB,
    PAGE_SIZES,
    PageSetup,
)

_PT = 25.4 / 72   # 1 pt in mm

# Kept as names for the callers that still refer to the A4 defaults; the sheet
# actually used comes from the PageSetup in the options.
PAGE_W          = PAGE_SIZES['a4'][0]
PAGE_H          = PAGE_SIZES['a4'][1]
MARGIN_LR       = DEFAULT_MARGIN_LR
MARGIN_TB       = DEFAULT_MARGIN_TB
HDR_FTR_Y       = DEFAULT_HDR_FTR_Y
NOTATION_LINE_H = 6.0     # mm per notation line below diagram
ROW_OVERHEAD    = 3.0     # extra mm per row (inter-row spacing)
MIN_FONT_PT     = 8       # minimum chess font size (pt)
TITLE_LH_FACTOR = 1.1     # title line-height multiplier

@dataclass
class _Geometry:
    """Computed page/layout geometry passed between PDF rendering functions."""
    # sheet
    PW: float; PH: float
    ML: float; MR: float; MT: float
    HY: float; FY: float
    USABLE_W: float; USABLE_H: float
    LINE_H: float
    # layout grid
    cols: int; max_rows: int; per_page: int
    col_w: float; x_pad: float; y_top: float; row_h: float
    lines_h: float
    # chess font
    chess_pt: int; chess_mm: float
    diag_w: float; char_w: float; inner_w: float
    # text
    txt_size: int; title_lh: float
    title_offset: float   # vertical nudge for the title inside the top border
    page: PageSetup = PageSetup()


def _compute_geometry(opts: RenderOptions | dict) -> _Geometry:
    """Parse opts and compute all layout/geometry values (pure, no side effects)."""
    opts = RenderOptions.coerce(opts)
    grid = opts.grid
    lines_count = opts.lines_count
    txt_size_opt = opts.text_size
    font_name = opts.font
    border_style = opts.border_style
    lichess_link = opts.lichess_link

    page = opts.page
    PW, PH   = page.dimensions
    ML = MR  = page.margin_lr
    MT       = page.margin_tb
    HY = FY  = page.header_offset
    USABLE_W = page.usable_width
    USABLE_H = page.usable_height
    LINE_H   = NOTATION_LINE_H

    lay      = custom_layout(*grid) if grid else LAYOUTS[opts.layout_idx]
    cols     = lay.cols
    max_rows = lay.rows_lined if lines_count > 0 else lay.rows_plain
    per_page = cols * max_rows

    lines_h   = lines_count * LINE_H
    txt_size = txt_size_opt if txt_size_opt > 0 else lay.title_pt
    title_lh = txt_size * _PT * TITLE_LH_FACTOR
    title_above_board = font_name in MERIDA_COMPATIBLE_FONTS and border_style == 'none'
    board_rows = 8 if title_above_board else 10
    board_cols = 8 if title_above_board else 10
    extra_top_h = title_lh + 0.8 if title_above_board else 0.0
    extra_bottom_h = 5.0 if lichess_link else 0.0

    requested = opts.font_size
    chess_pt_v = (
        USABLE_H / max_rows - ROW_OVERHEAD - lines_h - extra_top_h - extra_bottom_h
    ) / (board_rows * _PT)
    chess_pt_h = (USABLE_W / cols) / board_cols / _PT
    chess_pt_fit = max(1, int(min(chess_pt_v, chess_pt_h)))
    chess_pt_base = requested if requested > 0 else lay.chess_pt
    # A requested size is a request: the sheet still decides the ceiling.
    chess_pt = min(chess_pt_base, chess_pt_fit)

    chess_mm = chess_pt * _PT
    col_w    = USABLE_W / cols
    row_h    = extra_top_h + board_rows * chess_mm + lines_h + extra_bottom_h + ROW_OVERHEAD
    content_h = max_rows * row_h
    y_top    = MT + max(0.0, (USABLE_H - content_h) / 2)

    # diag_w and char_w require font metrics — set to 0 as placeholders;
    # generate_pdf fills them after loading the chess font into the PDF.
    return _Geometry(
        PW=PW, PH=PH, ML=ML, MR=MR, MT=MT, HY=HY, FY=FY,
        USABLE_W=USABLE_W, USABLE_H=USABLE_H, LINE_H=LINE_H,
        cols=cols, max_rows=max_rows, per_page=per_page,
        col_w=col_w, x_pad=0.0, y_top=y_top, row_h=row_h, lines_h=lines_h,
        chess_pt=chess_pt, chess_mm=chess_mm,
        diag_w=0.0, char_w=0.0, inner_w=0.0,
        txt_size=txt_size, title_lh=title_lh,
        title_offset=lay.title_offset,
        page=page,
    )
