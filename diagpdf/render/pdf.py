"""PDF output built on fpdf2."""

from __future__ import annotations

import sys

from .. import __version__
from ..fen import fen_to_diagram, parse_fen
from ..fonts import (
    DIRECT_PDF_CHESS_FONTS,
    MERIDA_COMPATIBLE_FONTS,
    FontManager,
)
from ..geometry import (
    _PT,
    _compute_geometry,
)
from ..i18n import _answers_heading, _lichess_label, tr
from ..model import PositionDict
from ..options import RenderOptions
from ..parsers import _clean_moves
from ..resources import _resource
from .common import (
    _chapter_groups,
    _figurine_segments,
    _format_number,
    _has_embedded_side_indicator,
    _lichess_analysis_url,
    _make_title,
    _numbering,
    _side_indicator_text,
    _split_title_number_prefix,
)

# fpdf2 swaps this for the real page count when the document is written, so the
# header can carry {total} without a second rendering pass.
_TOTAL_ALIAS = '{nb}'


def _apply_pdf_metadata(pdf, opts: RenderOptions) -> None:
    """Fill in the document properties a reader shows in File > Properties."""
    title = opts.doc_title.strip()
    author = opts.doc_author.strip()
    subject = opts.doc_subject.strip()
    keywords = opts.doc_keywords.strip()
    if title:
        pdf.set_title(title)
    if author:
        pdf.set_author(author)
    if subject:
        pdf.set_subject(subject)
    if keywords:
        pdf.set_keywords(keywords)
    pdf.set_creator(f'DiagPDF {__version__}')
    language = (opts.doc_language.strip() or opts.lang).strip()
    if language:
        pdf.set_lang(language)


def _require_fpdf2():
    """Import the modern fpdf2 API and reject the legacy pyfpdf package."""
    try:
        import fpdf as fpdf_module
        from fpdf import FPDF
        from fpdf.enums import MethodReturnValue, XPos, YPos
    except ImportError as e:
        raise RuntimeError('fpdf2 >= 2.7.0 required — install with: pip install -U fpdf2') from e

    # The legacy `fpdf` package exposes `FPDF` too, but lacks the modern API
    # surface this project relies on.
    if not getattr(fpdf_module, '__version__', ''):
        raise RuntimeError(
            "Legacy 'fpdf' package detected. Uninstall 'fpdf' and install 'fpdf2'."
        )

    return FPDF, XPos, YPos, MethodReturnValue.LINES

def _draw_cover(pdf, opts: RenderOptions, text_font: str, g) -> None:
    """Draw a title page: title, optional subtitle and author, centred."""
    pdf.add_page()
    pdf.start_section(opts.doc_title.strip() or 'Cover', level=0)

    title = (opts.cover_title or opts.doc_title).strip()
    subtitle = opts.cover_subtitle.strip()
    author = (opts.cover_author or opts.doc_author).strip()

    y = g.PH * 0.32
    if title:
        pdf.set_font(text_font, 'B', size=max(18, g.txt_size * 2))
        pdf.set_xy(g.ML, y)
        pdf.multi_cell(w=g.USABLE_W, h=max(10.0, g.txt_size * 0.9), text=title, align='C')
        y = pdf.get_y() + 6
    if subtitle:
        pdf.set_font(text_font, size=max(11, g.txt_size))
        pdf.set_xy(g.ML, y)
        pdf.multi_cell(w=g.USABLE_W, h=7, text=subtitle, align='C')
        y = pdf.get_y() + 10
    if author:
        pdf.set_font(text_font, size=max(11, g.txt_size))
        pdf.set_xy(g.ML, max(y, g.PH * 0.6))
        pdf.multi_cell(w=g.USABLE_W, h=7, text=author, align='C')


def _stamp_watermark(pdf, opts: RenderOptions, g, text_font: str) -> None:
    """Stamp the watermark diagonally across every page.

    Run last, once every page exists, for two reasons: the mark then sits over
    the content rather than under it, which is what makes it visible on a busy
    diagram page, and there is one place that knows about it instead of a hook
    in each of the four routines that start a page.
    """
    text = opts.watermark.strip()
    if not text:
        return

    opacity = opts.watermark_opacity / 100
    # Big enough to cross the sheet corner to corner, whatever the text is.
    span = (g.PW ** 2 + g.PH ** 2) ** 0.5 * 0.75
    pdf.set_font(text_font, 'B', size=100)
    at_100 = pdf.get_string_width(text) or 1.0
    size = max(8, min(400, int(100 * span / at_100)))

    saved_page = pdf.page
    for page in range(1, len(pdf.pages) + 1):
        pdf.page = page
        with (pdf.local_context(fill_opacity=opacity, stroke_opacity=opacity),
              pdf.rotation(45, g.PW / 2, g.PH / 2)):
            pdf.set_font(text_font, 'B', size=size)
            pdf.set_text_color(128, 128, 128)
            height = size * _PT
            pdf.set_xy(0, g.PH / 2 - height / 2)
            pdf.cell(w=g.PW, h=height, text=text, align='C')
    pdf.set_text_color(0, 0, 0)
    pdf.page = saved_page


def _contents_capacity(g) -> int:
    """How many entries fit on one contents page."""
    line_h = max(6.0, g.txt_size * 0.55)
    return max(1, int((g.USABLE_H - 16) / line_h))


def _draw_contents(pdf, entries: list[tuple[str, int]], opts: RenderOptions, text_font: str,
                   g, first_page: int) -> None:
    """Fill the reserved pages with the contents, using leader dots.

    The pages are reserved before the diagrams are laid out and written here at
    the end, once the chapter page numbers are known. fpdf2 keeps an index
    inside each page object, so pages cannot be reordered after the fact —
    reserving is what makes a front-of-document contents possible at all.
    """
    if not entries:
        return
    pdf.page = first_page
    heading = opts.contents_title.strip() or tr('contents', opts.lang)
    pdf.set_font(text_font, 'B', size=g.txt_size + 4)
    pdf.set_xy(g.ML, g.MT)
    pdf.cell(w=g.USABLE_W, h=10, text=heading, align='C')

    line_h = max(6.0, g.txt_size * 0.55)
    y = g.MT + 16
    pdf.set_font(text_font, size=g.txt_size)
    for label, page_number in entries:
        if y + line_h > g.PH - g.MT:
            pdf.page += 1
            y = g.MT
        number = str(page_number)
        number_w = pdf.get_string_width(number) + 2
        label_w = pdf.get_string_width(label)
        pdf.set_xy(g.ML, y)
        pdf.cell(w=label_w, h=line_h, text=label)
        pdf.set_xy(g.ML + g.USABLE_W - number_w, y)
        pdf.cell(w=number_w, h=line_h, text=number, align='R')
        dot_start = g.ML + label_w + 1
        dot_end = g.ML + g.USABLE_W - number_w - 1
        if dot_end > dot_start:
            pdf.set_line_width(0.1)
            pdf.set_dash_pattern(dash=0.4, gap=1.2)
            pdf.line(dot_start, y + line_h * 0.72, dot_end, y + line_h * 0.72)
            pdf.set_dash_pattern()
        y += line_h


def generate_pdf(positions: list[PositionDict], opts: RenderOptions | dict,
                 out_path, progress=None) -> None:
    """Render a list of chess positions to a PDF file.

    Args:
        positions: List of dicts from parse_pgn / parse_fen_file / parse_epd.
                   Each dict must have a 'fen' key; 'comment' is used for titles.
        opts:      A :class:`~diagpdf.options.RenderOptions`, which documents
                   every setting and its default. A plain dict is still accepted
                   and converted here.
        out_path:  Output PDF path (str or Path).
    """
    FPDF, XPos, YPos, _LINES = _require_fpdf2()

    opts = RenderOptions.coerce(opts)
    coords      = opts.coords
    flip        = opts.flip
    flip_auto   = opts.flip_auto
    header      = opts.header_text
    footer      = opts.footer_text
    symbol       = opts.symbol
    font_name    = opts.font
    border_style = opts.border_style
    lines_count  = opts.lines_count
    lines_mode   = opts.lines_mode
    title_template  = opts.title_template
    title_mode      = opts.title_mode     # superseded by title_template
    title_custom    = opts.title_custom   # superseded by title_template
    lichess_link    = opts.lichess_link
    answers_section = opts.answers_section
    figurine_font   = opts.figurine_font
    answers_cols    = opts.answers_cols

    script_dir = _resource('.')   # works in both .py and frozen .exe
    fm = FontManager(script_dir)
    g  = _compute_geometry(opts)

    # Unpack geometry into local names (matches rest of function)
    PW, PH   = g.PW, g.PH
    ML, MR   = g.ML, g.MR
    MT       = g.MT
    HY, FY   = g.HY, g.FY
    USABLE_W = g.USABLE_W
    LINE_H   = g.LINE_H
    cols     = g.cols
    per_page = g.per_page
    col_w    = g.col_w
    y_top    = g.y_top
    row_h    = g.row_h
    chess_pt     = g.chess_pt
    chess_mm     = g.chess_mm
    txt_size     = g.txt_size
    title_lh     = g.title_lh
    title_offset = g.title_offset

    def chess_str(s: str) -> str:
        # Legacy DG fonts expose glyphs on the Private Use Area for fpdf2.
        # Some newer fonts ship only direct ASCII/MacRoman mappings, so feeding
        # U+F0xx would trigger missing-glyph warnings and blank output.
        if font_name in DIRECT_PDF_CHESS_FONTS:
            return s
        return ''.join(chr(0xF000 + ord(c)) for c in s)

    pdf = FPDF(**g.page.fpdf_kwargs())
    pdf.set_margins(ML, MT, MR)
    pdf.set_auto_page_break(auto=False)
    # fpdf2 substitutes this at output time, which replaces the old trick of
    # painting white rectangles over the header and redrawing it — that only
    # worked while the page background stayed white.
    pdf.alias_nb_pages(_TOTAL_ALIAS)
    _apply_pdf_metadata(pdf, opts)
    fm.load_chess(pdf, font_name)

    # Measure actual board width from a representative rendered row.
    pdf.set_font('Chess', size=chess_pt)
    _sample_lines = fen_to_diagram(
        '8/8/8/8/8/8/8/8 w - - 0 1',
        coords=coords,
        flip=False,
        flip_auto=False,
        symbol=symbol,
        font_name=font_name,
        border_style=border_style,
    )
    _sample_row = chess_str(max(_sample_lines, key=len))
    _board_cols = max(len(ln) for ln in _sample_lines) if _sample_lines else 10
    diag_w  = pdf.get_string_width(_sample_row) or (_board_cols * chess_mm)
    x_pad   = (col_w - diag_w) / 2
    char_w  = diag_w / _board_cols if _board_cols else chess_mm
    inner_w = char_w * 8

    _text_font     = fm.load_text(pdf)
    _fig_font_name = fm.load_figurine(pdf, figurine_font, _text_font) if answers_section else _text_font

    pgnum = 0

    def _running_text(template: str, chapter: str) -> str:
        return (template.replace('{chapter}', chapter)
                        .replace('{page}', str(pgnum))
                        .replace('{total}', _TOTAL_ALIAS))

    def draw_decorations(chapter: str = '') -> None:
        # header/footer are already blank when switched off, so one test covers
        # both "not asked for" and "nothing to say" — as in every other renderer.
        if header:
            pdf.set_font(_text_font, 'B', size=txt_size)
            pdf.set_xy(ML, HY - 1)
            pdf.cell(w=USABLE_W, h=4, text=_running_text(header, chapter), align='C')
        if footer:
            pdf.set_font(_text_font, size=txt_size)
            pdf.set_xy(ML, PH - FY - 1)
            pdf.cell(w=USABLE_W, h=4, text=_running_text(footer, chapter), align='C')

    valid = [p for p in positions if p.get('fen', '').strip()]

    # Pre-create link IDs so both directions (diag→ans, ans→diag) can reference each other.
    # ans_links[i] == 0 means the position has no moves → no link created.
    # fpdf2 raises ValueError if pdf.cell(link=id) is called before pdf.set_link(id, page, y),
    # so we assign a placeholder (page=1) immediately; the answers section overwrites with real page.
    diag_links: list[int] = []
    ans_links:  list[int] = []
    if answers_section:
        for _p in valid:
            diag_links.append(pdf.add_link())
            _al = pdf.add_link() if _clean_moves(_p.get('moves', '')) else 0
            if _al:
                pdf.set_link(_al, page=1, y=0)   # placeholder; updated in answers section
            ans_links.append(_al)

    total = len(valid)
    numbers = _numbering(valid, opts)
    slot = 0
    current_chapter = ''
    _contents: list[tuple[str, int]] = []
    _page_chapters: dict[int, str] = {}   # pgnum -> chapter name
    # Indices whose solutions have not been written out yet. With
    # --answers-after-chapter the list is emptied at every chapter boundary;
    # otherwise it is emptied once, at the end of the document.
    _pending_answers: list[int] = []

    def _draw_answers(entries: list[int]) -> None:
        """Write the solutions for *entries*, then empty the list.

        Called once at the end of the document, or once per chapter when
        --answers-after-chapter asks for the solutions to follow the diagrams
        they belong to. Everything it needs -- the page counter, the outline,
        the running decorations -- lives in the enclosing render, so the same
        code produces the section wherever it is asked for.
        """
        nonlocal pgnum
        if not any(_clean_moves(valid[i].get('moves', '')) for i in entries):
            entries.clear()
            return
        _ans_fsize = txt_size
        _ans_lh    = title_lh + 0.5   # slightly taller line height
        _col_w     = USABLE_W / answers_cols

        def _ans_col_x(ci: int) -> float:
            return ML + ci * _col_w

        def _set_ans_margins(ci: int) -> None:
            pdf.set_left_margin(_ans_col_x(ci))
            pdf.set_right_margin(PW - (_ans_col_x(ci) + _col_w))

        # Section heading text — also used as {chapter} on all answers pages
        _head = _answers_heading(opts)

        # Turning the answers over: the whole block is rotated 180 degrees about
        # the centre of the sheet, so the reader turns the page and reads it
        # normally, top to bottom. Rotating each line about itself instead would
        # leave the lines in reverse order once the page was turned.
        #
        # The running header and footer stay upright, so the rotation is opened
        # after they are drawn and closed before the page ends. fpdf2 offers it
        # as a context manager only, and the region it has to cover is opened
        # and closed from inside the layout loops -- hence driving it by hand.
        _turned = None

        def _start_turned() -> None:
            nonlocal _turned
            if opts.answers_upside_down and _turned is None:
                _turned = pdf.rotation(180, PW / 2, PH / 2)
                _turned.__enter__()

        def _stop_turned() -> None:
            nonlocal _turned
            if _turned is not None:
                _turned.__exit__(None, None, None)
                _turned = None

        def _turn_last_link() -> None:
            """Turn the link fpdf2 has just recorded over with its text.

            A link rectangle is a page-space annotation, which the content
            transform does not touch: left alone, the text moves and the
            clickable area stays behind. Rebuilding the rectangle would mean
            reproducing how fpdf2 sizes it — it wraps the glyphs, not the cell —
            so the one it just wrote is mirrored in place instead, whatever it
            chose.
            """
            if not opts.answers_upside_down:
                return
            annots = pdf.pages[pdf.page].annots
            if not annots:
                return
            x0, y0, x1, y1 = (float(v) for v in str(annots[-1].rect).strip('[]').split())
            right, top = PW * pdf.k, PH * pdf.k
            annots[-1].rect = (f'[{right - x1:.2f} {top - y1:.2f} '
                               f'{right - x0:.2f} {top - y0:.2f}]')

        def _ans_new_page() -> None:
            nonlocal pgnum
            _stop_turned()
            pgnum += 1
            _page_chapters[pgnum] = _head
            pdf.add_page()
            draw_decorations(_head)
            pdf.set_y(MT)
            _start_turned()

        # A page of its own by default. Continuing where the diagrams stopped
        # still needs a break when there is no room left for the heading and a
        # first line — otherwise the section would start off the bottom edge.
        _head_y = MT
        if opts.answers_new_page or pdf.get_y() + _ans_lh * 3 > PH - MT:
            pgnum += 1
            _page_chapters[pgnum] = _head
            pdf.add_page()
            draw_decorations(_head)
        else:
            _head_y = pdf.get_y() + _ans_lh

        pdf.start_section(_head, level=0)
        _contents.append((_head, pgnum))
        _start_turned()
        pdf.set_font(_text_font, 'B', size=_ans_fsize + 2)
        pdf.set_xy(ML, _head_y)
        pdf.cell(
            w=USABLE_W,
            h=_ans_lh + 2,
            text=_head,
            align='C',
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.ln(3)

        _cur_col   = 0
        _col_top_y = pdf.get_y()   # content start Y (after heading on first page)
        _set_ans_margins(_cur_col)
        _ans_bottom = PH - MT      # last Y a line may start at

        def _ans_next_column() -> None:
            """Move to the next answers column, adding a page when needed."""
            nonlocal _cur_col, _col_top_y
            if answers_cols > 1 and _cur_col == 0:
                _cur_col = 1
                _set_ans_margins(_cur_col)
                pdf.set_y(_col_top_y)
            else:
                _ans_new_page()
                _cur_col = 0
                _col_top_y = MT
                _set_ans_margins(_cur_col)

        for _ai in entries:
            _pos = valid[_ai]
            _moves = _clean_moves(_pos.get('moves', ''))
            if not _moves:
                continue

            _num_label = f'{_format_number(numbers[_ai], opts)}. '
            _diag_link: int | str = diag_links[_ai] if diag_links else ''
            pdf.set_font(_text_font, 'B', size=_ans_fsize)
            _nl_w = pdf.get_string_width(_num_label) + 1.0

            # Wrap the moves ourselves so the answer can be split across
            # columns and pages. Auto page break is off for the whole document
            # (the diagram grid needs it off), so pdf.write() would otherwise
            # keep drawing past the bottom edge and lose the text.
            _text_w = max(10.0, _col_w - _nl_w - 2.0)
            pdf.set_font(_text_font, size=_ans_fsize)
            pdf.set_xy(_ans_col_x(_cur_col) + _nl_w, pdf.get_y())
            _wrapped = pdf.multi_cell(
                w=_text_w, h=_ans_lh, text=_moves,
                dry_run=True, output=_LINES,
            ) or [_moves]

            # A new answer always starts a fresh line; move on if it cannot even
            # begin here.
            if pdf.get_y() + _ans_lh > _ans_bottom:
                _ans_next_column()

            # Set answer anchor (links from diagram titles point here)
            if ans_links and ans_links[_ai]:
                _anchor_y = pdf.get_y()
                if opts.answers_upside_down:
                    _anchor_y = PH - _anchor_y      # it is drawn turned over
                pdf.set_link(ans_links[_ai], page=pgnum, y=_anchor_y)

            for _li, _line in enumerate(_wrapped):
                if pdf.get_y() + _ans_lh > _ans_bottom:
                    _ans_next_column()

                _y = pdf.get_y()
                if _li == 0:
                    # Number label — bold, links back to the diagram
                    pdf.set_font(_text_font, 'B', size=_ans_fsize)
                    pdf.set_xy(_ans_col_x(_cur_col), _y)
                    pdf.set_text_color(0, 0, 255)
                    pdf.cell(w=_nl_w, h=_ans_lh, text=_num_label, link=_diag_link)
                    if _diag_link:
                        _turn_last_link()
                    pdf.set_text_color(0, 0, 0)

                # Hanging indent: continuation lines align under the moves.
                _x = _ans_col_x(_cur_col) + _nl_w
                for _seg_font, _seg_text in _figurine_segments(
                    _line, _text_font, _fig_font_name
                ):
                    pdf.set_font(_seg_font, size=_ans_fsize)
                    _seg_w = pdf.get_string_width(_seg_text)
                    pdf.set_xy(_x, _y)
                    pdf.cell(w=_seg_w, h=_ans_lh, text=_seg_text)
                    _x += _seg_w
                pdf.set_y(_y + _ans_lh)

        _stop_turned()
        # Restore page margins
        pdf.set_left_margin(ML)
        pdf.set_right_margin(MR)
        entries.clear()

    if opts.cover:
        _draw_cover(pdf, opts, _text_font, g)
        pgnum += 1
        _page_chapters[pgnum] = ''

    _contents_first = 0
    _contents_pages = 0
    if opts.contents:
        _expected = len({p.get('chapter', '') for p in valid if p.get('chapter')})
        if answers_section:
            # One heading at the end, or one per chapter that has a solution to
            # show. Under-counting here would leave the contents short of pages.
            _expected += sum(
                1 for _c, _idx in _chapter_groups(valid)
                if any(_clean_moves(valid[i].get('moves', '')) for i in _idx)
            ) if opts.answers_after_chapter else int(
                any(_clean_moves(v.get('moves', '')) for v in valid))
        if _expected:
            _contents_pages = -(-_expected // _contents_capacity(g))   # ceil
            _contents_first = pgnum + 1
            for _ in range(_contents_pages):
                pgnum += 1
                _page_chapters[pgnum] = ''
                pdf.add_page()

    for pos_idx, pos in enumerate(valid):
        if progress and total > 0:
            progress(int((pos_idx + 1) * 100 / total))

        pos_chapter = pos.get('chapter', '')
        _new_chapter = bool(pos_chapter) and pos_chapter != current_chapter
        if _new_chapter:
            # The solutions of the chapter that is ending belong here, between
            # the two chapters, rather than at the back of the book. Asking for
            # that without asking for an answers section at all is not a request
            # for one: the moves are printed under their diagrams instead.
            if pos_idx > 0 and answers_section and opts.answers_after_chapter:
                _draw_answers(_pending_answers)
            current_chapter = pos_chapter
            if pos_idx > 0:
                slot = 0   # force page break on chapter change

        if slot == 0:
            pgnum += 1
            _page_chapters[pgnum] = current_chapter
            pdf.add_page()
            draw_decorations(current_chapter)
        if _new_chapter:
            pdf.start_section(current_chapter, level=0)
            _contents.append((current_chapter, pgnum))

        col_idx = slot % cols
        row_idx = slot // cols
        x = ML + col_idx * col_w + x_pad
        y = y_top + row_idx * row_h

        # ── Title (above diagram) ─────────────────────────────────────────────
        fen     = pos.get('fen', '').strip()
        num     = numbers[pos_idx]
        _pending_answers.append(pos_idx)
        title = _make_title(pos, num, title_template, title_mode, title_custom, opts)

        _needs_side_indicator = not _has_embedded_side_indicator(font_name)
        _side = parse_fen(fen)[1] if (lichess_link or lines_count > 0 or _needs_side_indicator) else ''
        link_url = _lichess_analysis_url(fen) if lichess_link else ''

        _title_above_board = font_name in MERIDA_COMPATIBLE_FONTS and border_style == 'none'
        y_diag = y + title_lh + 0.8 if _title_above_board else y

        # Set diagram anchor (for links from answers section back to this diagram)
        if diag_links:
            pdf.set_link(diag_links[pos_idx], page=pgnum, y=y_diag)

        # ── Diagram ───────────────────────────────────────────────────────────
        try:
            diag_lines = fen_to_diagram(fen, coords=coords, flip=flip,
                                        flip_auto=flip_auto, symbol=symbol, font_name=font_name,
                                        border_style=border_style)
            _board_h = len(diag_lines) * chess_mm
            pdf.set_font('Chess', size=chess_pt)
            for i, ln in enumerate(diag_lines):
                pdf.set_xy(x, y_diag + i * chess_mm)
                pdf.cell(w=diag_w, h=chess_mm, text=chess_str(ln))
            if _needs_side_indicator and _side:
                _marker = _side_indicator_text(_side, symbol)
                _marker_pt = max(8, int(chess_pt * 0.72))
                _marker_mm = _marker_pt * _PT
                _board_start_idx = 0 if len(diag_lines) == 8 else 1
                pdf.set_font(_text_font, size=_marker_pt)
                pdf.set_xy(
                    x + diag_w + 0.6,
                    y_diag + (_board_start_idx + 7) * chess_mm + (chess_mm - _marker_mm) / 2,
                )
                pdf.cell(w=4, h=_marker_mm, text=_marker)
            # Lichess link has been moved to be an explicit text label under the board
        except Exception as e:
            print(f'Warning: FEN render error ({fen!r}): {e}', file=sys.stderr)
            pdf.set_font(_text_font, size=8)
            pdf.set_xy(x, y_diag)
            pdf.cell(w=diag_w, h=5, text='[FEN error]')
            _board_h = len(_sample_lines) * chess_mm

        # ── Title ──────────────────────────────────────────────────────────────
        # With an answers section the title links to its solution; otherwise it
        # links to Lichess when that option is on. The Lichess link itself is
        # drawn as a labelled line under the board (see below).
        # ans_links[i] is 0 for positions that have no solution — those titles
        # must stay black, or they look clickable without being clickable.
        _has_answer_link = bool(ans_links) and bool(ans_links[pos_idx])
        _title_link: int | str = ans_links[pos_idx] if _has_answer_link else link_url
        title_cy = y if _title_above_board else y_diag + (chess_mm - title_lh) / 2 + title_offset
        pdf.set_font(_text_font, 'B', size=txt_size)
        _title_x = x + (diag_w - inner_w) / 2
        if _has_answer_link and title:
            _prefix, _suffix = _split_title_number_prefix(title, num, opts)
            if _prefix:
                _full_w = pdf.get_string_width(title)
                _prefix_w = pdf.get_string_width(_prefix)
                _suffix_w = pdf.get_string_width(_suffix)
                _start_x = _title_x + max(0.0, (inner_w - _full_w) / 2)
                pdf.set_text_color(0, 0, 255)
                pdf.set_xy(_start_x, title_cy)
                pdf.cell(w=_prefix_w, h=title_lh, text=_prefix, link=_title_link)
                pdf.set_text_color(0, 0, 0)
                if _suffix:
                    pdf.set_xy(_start_x + _prefix_w, title_cy)
                    pdf.cell(w=_suffix_w, h=title_lh, text=_suffix)
            else:
                pdf.set_text_color(0, 0, 255)
                pdf.set_xy(_title_x, title_cy)
                pdf.cell(w=inner_w, h=title_lh, text=title, align='C', link=_title_link)
                pdf.set_text_color(0, 0, 0)
        else:
            pdf.set_xy(_title_x, title_cy)
            pdf.cell(w=inner_w, h=title_lh, text=title, align='C', link=_title_link)

        # ── Notation lines ───────────────────────────────────────────────────
        if lines_count > 0:
            base_y  = y_diag + _board_h + 0.5
            lx      = x + (diag_w - inner_w) / 2
            gap_w   = min(2.0, inner_w * 0.06)         # gap between the two blanks
            pdf.set_line_width(0.2)
            for li in range(lines_count):
                ly = base_y + li * LINE_H + LINE_H - 1
                if lines_mode == 'numbered':
                    move_num = li + 1
                    pdf.set_font(_text_font, size=7)
                    num_text = f'{move_num}.'
                    num_w = pdf.get_string_width(num_text) + 0.8   # +0.8mm gap after label
                    blank_w = (inner_w - num_w - gap_w) / 2
                    pdf.text(lx, ly, num_text)
                    x0 = lx + num_w
                    x1 = x0 + blank_w
                    x2 = x1 + gap_w
                    x3 = x2 + blank_w
                    if li == 0 and _side == 'b':
                        # Black to move: skip white's blank, draw only black's blank
                        pdf.line(x2, ly, x3, ly)
                    else:
                        pdf.line(x0, ly, x1, ly)
                        pdf.line(x2, ly, x3, ly)
                else:
                    # plain mode: single full-width line
                    pdf.line(lx, ly, lx + inner_w, ly)

        # ── Explicit Lichess Link ─────────────────────────────────────────────
        if lichess_link and link_url:
            link_y = y_diag + _board_h + (lines_count * LINE_H if lines_count > 0 else 0) + 1
            pdf.set_font(_text_font, 'U', size=8)
            pdf.set_text_color(0, 0, 255)
            pdf.set_xy(x, link_y)
            pdf.cell(w=diag_w, h=4, text=_lichess_label(opts), align='C', link=link_url)
            pdf.set_text_color(0, 0, 0)

        slot += 1
        if slot >= per_page:
            slot = 0

    if pgnum == 0:
        pdf.add_page()

    if answers_section:
        _draw_answers(_pending_answers)

    if _contents_pages and _contents:
        _draw_contents(pdf, _contents, opts, _text_font, g, _contents_first)

    _stamp_watermark(pdf, opts, g, _text_font)

    pdf.output(str(out_path))
