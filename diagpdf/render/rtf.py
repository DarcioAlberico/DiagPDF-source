"""Rich Text Format output."""

from __future__ import annotations

import re
from pathlib import Path

from ..fen import fen_to_diagram, parse_fen
from ..fonts import _board_font_family_name, resolve_board_font
from ..i18n import _answers_heading, _lichess_label
from ..layouts import LAYOUTS
from ..model import PositionDict
from ..options import RenderOptions
from ..parsers import _clean_moves
from .common import (
    _anchor_id,
    _chapter_groups,
    _figurine_family_name,
    _figurine_segments,
    _format_number,
    _has_embedded_side_indicator,
    _lichess_analysis_url,
    _make_title,
    _numbering,
    _side_indicator_text,
    _split_title_number_prefix,
)


def _rtf_escape(text: str) -> str:
    """Escape Unicode text for RTF output."""
    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if ch == '\\':
            out.append(r'\\')
        elif ch == '{':
            out.append(r'\{')
        elif ch == '}':
            out.append(r'\}')
        elif ch == '\n':
            out.append(r'\line ')
        elif ch == '\t':
            out.append(r'\tab ')
        elif 0x20 <= code <= 0x7E:
            out.append(ch)
        else:
            raw = ch.encode('utf-16le')
            for idx in range(0, len(raw), 2):
                unit = int.from_bytes(raw[idx:idx + 2], 'little')
                if unit >= 0x8000:
                    unit -= 0x10000
                out.append(f'\\u{unit}?')
    return ''.join(out)


def _rtf_bookmark(name: str) -> str:
    """Return an RTF bookmark marker."""
    return f'{{\\*\\bkmkstart {name}}}{{\\*\\bkmkend {name}}}'


def _rtf_styled_text(text: str, *, color_idx: int = 0, bold: bool = False, underline: bool = False) -> str:
    """Return styled RTF text wrapped in a group."""
    prefix: list[str] = []
    suffix: list[str] = []
    if color_idx:
        prefix.append(f'\\cf{color_idx}')
        suffix.insert(0, r'\cf0')
    if underline:
        prefix.append(r'\ul')
        suffix.insert(0, r'\ulnone')
    if bold:
        prefix.append(r'\b')
        suffix.insert(0, r'\b0')
    prefix_str = ''.join(prefix)
    suffix_str = ''.join(suffix)
    return '{' + prefix_str + ' ' + _rtf_escape(text) + suffix_str + '}'


def _rtf_internal_link(text: str, anchor: str, *, blue: bool = True, bold: bool = False, underline: bool = False) -> str:
    """Return an internal RTF hyperlink field."""
    color_idx = 1 if blue else 0
    result = _rtf_styled_text(text, color_idx=color_idx, bold=bold, underline=underline)
    return f'{{\\field{{\\*\\fldinst HYPERLINK \\\\l "{anchor}"}}{{\\fldrslt {result}}}}}'


def _rtf_external_link(text: str, url: str, *, blue: bool = True, bold: bool = False, underline: bool = True) -> str:
    """Return an external RTF hyperlink field."""
    color_idx = 1 if blue else 0
    result = _rtf_styled_text(text, color_idx=color_idx, bold=bold, underline=underline)
    return f'{{\\field{{\\*\\fldinst HYPERLINK "{url}"}}{{\\fldrslt {result}}}}}'


def _rtf_empty_cell() -> str:
    return r'\pard\intbl\ql\par\cell'


def _rtf_font_name(name: str) -> str:
    """Sanitize a font name for an RTF font table entry."""
    return name.replace('\\', '').replace('{', '').replace('}', '').strip() or 'Calibri'


def _rtf_para(
    text: str = '',
    *,
    align: str = 'ql',
    font_idx: int = 0,
    font_size: int = 22,
    space_after: int = 0,
    exact_line: int = 0,
) -> str:
    """Return a basic RTF table-cell paragraph."""
    line_part = f'\\sl{exact_line}\\slmult0' if exact_line > 0 else ''
    return (
        rf'\pard\intbl\{align}\sb0\sa{space_after}\f{font_idx}\fs{font_size}{line_part} '
        f'{text}\\par'
    )


RTF_FONT_TEXT = 0
RTF_FONT_BOARD = 1
RTF_FONT_FIGURINE = 2


def _rtf_moves(moves: str, *, figurine: bool) -> str:
    """Escape movetext, switching piece letters to the figurine font."""
    if not figurine:
        return _rtf_escape(moves)
    out: list[str] = []
    for font, run in _figurine_segments(moves, 'text', 'figurine'):
        if font == 'figurine':
            out.append(rf'{{\f{RTF_FONT_FIGURINE} {_rtf_escape(run)}}}')
        else:
            out.append(_rtf_escape(run))
    return ''.join(out)


def _rtf_notation_paragraph(index: int, numbered: bool, side: str, width_twips: int) -> str:
    """Return one blank notation line, drawn with underscore tab leaders."""
    # Black to move: the first move number belongs to White, so its blank is
    # left out and only Black's is offered.
    skip_first = numbered and index == 0 and side == 'b'
    if numbered:
        stops = [width_twips // 2, width_twips]
        leaders = ['' if skip_first else r'\tlul', r'\tlul']
    else:
        stops = [width_twips]
        leaders = [r'\tlul']
    tabs = ''.join(f'{leader}\\tx{pos}' for leader, pos in zip(leaders, stops, strict=True))
    label = _rtf_escape(f'{index + 1}.') if numbered else ''
    return (
        rf'\pard\intbl\ql\sb0\sa20{tabs}\f{RTF_FONT_TEXT}\fs16 '
        f'{label}' + r'\tab' * len(stops) + r'\par'
    )


def _rtf_running_text(template: str, chapter: str) -> str:
    """Return header/footer content, with live page-number fields."""
    out: list[str] = []
    text = template.replace('{chapter}', chapter)
    for piece in re.split(r'(\{page\}|\{total\})', text):
        if piece == '{page}':
            out.append(r'{\field{\*\fldinst PAGE}{\fldrslt \chpgn}}')
        elif piece == '{total}':
            out.append(r'{\field{\*\fldinst NUMPAGES}{\fldrslt 1}}')
        elif piece:
            out.append(_rtf_escape(piece))
    return ''.join(out)


def _rtf_watermark(text: str, opacity: int, page) -> str:
    """Return the watermark as a drawing object for the header.

    RTF has no turned text, so the mark is what it is in Word too: an OfficeArt
    text effect (shape type 136) anchored in the header, which is the only part
    that repeats on every page. Rotation is measured in 1/65536 of a degree and
    written signed, the way Office writes it: -45 degrees, the same diagonal the
    PDF uses.

    The box is measured from the margin, not from the page corner, and the
    centring is stated twice -- as coordinates and as ``posh``/``posv`` -- since
    readers differ on which of the two they honour. Anchored in a header, a box
    given from the page corner comes out measured from the header instead.
    """
    text = text.strip()
    if not text:
        return ''
    usable_w = int(page.usable_width * 56.6929)
    usable_h = int(page.usable_height * 56.6929)
    width = int(usable_w * 0.95)
    height = int(width / 4.5)
    left = (usable_w - width) // 2
    top = (usable_h - height) // 2
    properties = {
        'shapeType': '136',        # the WordArt text effect
        'fFlipH': '0',
        'fFlipV': '0',
        'rotation': str(-45 * 65536),
        'gtextUNICODE': _rtf_escape(text),
        'gtextFont': 'Calibri',
        'fGtext': '1',             # this shape draws text, not an outline
        'fillColor': str(0x808080),
        'fillOpacity': str(int(65536 * max(1, min(100, opacity)) / 100)),
        'fFilled': '1',
        'fLine': '0',
        'fLayoutInCell': '0',
        'fBehindDocument': '0',    # over the diagrams, as in the PDF
        'posh': '2',               # centred...
        'posrelh': '0',            # ...on the margin, horizontally
        'posv': '2',
        'posrelv': '0',
    }
    body = ''.join(f'{{\\sp{{\\sn {name}}}{{\\sv {value}}}}}'
                   for name, value in properties.items())
    return (r'{\shp{\*\shpinst'
            rf'\shpleft{left}\shptop{top}\shpright{left + width}\shpbottom{top + height}'
            r'\shpfhdr1\shpbxmargin\shpbymargin\shpwr3\shpwrk0\shpfblwtxt0\shpz0'
            + body + '}}')


def _rtf_board_paragraphs(
    diag_lines: list[str],
    *,
    font_idx: int,
    font_size: int,
    leading_bookmark: str = '',
) -> str:
    """Render diagram rows as RTF text in the chess font."""
    exact_line = max(120, font_size * 10)
    rows: list[str] = []
    for row_idx, line in enumerate(diag_lines):
        prefix = leading_bookmark if row_idx == 0 and leading_bookmark else ''
        rows.append(
            _rtf_para(
                prefix + _rtf_escape(line),
                align='qc',
                font_idx=font_idx,
                font_size=font_size,
                exact_line=exact_line,
            )
        )
    return ''.join(rows)


def _rtf_diagram_cell(
    pos: PositionDict,
    num: int,
    opts: dict,
    font_name: str,
    board_font_idx: int,
    board_font_size: int,
    *,
    cell_width_twips: int = 4800,
    figurine: bool = False,
    anchor: int | None = None,
) -> str:
    """Build one RTF table cell containing title, diagram text, links, and moves."""
    fen = pos.get('fen', '').strip()
    title_template = opts.title_template
    title_mode = opts.title_mode
    title_custom = opts.title_custom
    answers_section = opts.answers_section
    lichess_link = opts.lichess_link
    coords = opts.coords
    flip = opts.flip
    flip_auto = opts.flip_auto
    symbol = opts.symbol
    border_style = opts.border_style
    title = _make_title(pos, num, title_template, title_mode, title_custom, opts)
    moves = _clean_moves(pos.get('moves', ''))
    anchor = num if anchor is None else anchor
    diag_anchor = f'diag_{anchor}'
    ans_anchor = f'ans_{anchor}'
    side = parse_fen(fen)[1]
    side_indicator = _side_indicator_text(side, symbol) if not _has_embedded_side_indicator(font_name) else ''
    diag_lines = fen_to_diagram(
        fen,
        coords=coords,
        flip=flip,
        flip_auto=flip_auto,
        symbol=symbol,
        font_name=font_name,
        border_style=border_style,
    )

    parts: list[str] = []
    if title:
        if answers_section and moves:
            prefix, suffix = _split_title_number_prefix(title, num, opts)
            if prefix:
                title_text = _rtf_internal_link(prefix, ans_anchor, blue=True, bold=True, underline=False)
                if suffix:
                    title_text += _rtf_styled_text(suffix, bold=True)
            else:
                title_text = _rtf_internal_link(title, ans_anchor, blue=True, bold=True, underline=False)
            parts.append(_rtf_para(_rtf_bookmark(diag_anchor) + title_text, align='qc', font_size=28, space_after=90))
        else:
            parts.append(_rtf_para(_rtf_bookmark(diag_anchor) + _rtf_styled_text(title, bold=True), align='qc', font_size=28, space_after=90))

    parts.append(
        _rtf_board_paragraphs(
            diag_lines,
            font_idx=board_font_idx,
            font_size=board_font_size,
            leading_bookmark='' if title else _rtf_bookmark(diag_anchor),
        )
    )

    if side_indicator:
        parts.append(_rtf_para(_rtf_escape(side_indicator), align='qc', font_size=18, space_after=60))

    lines_count = opts.lines_count
    if lines_count > 0:
        numbered = opts.lines_mode == 'numbered'
        for line_index in range(lines_count):
            parts.append(_rtf_notation_paragraph(line_index, numbered, side, cell_width_twips - 400))

    if lichess_link and fen:
        parts.append(
            _rtf_para(
                _rtf_external_link(_lichess_label(opts), _lichess_analysis_url(fen), blue=True, underline=True),
                align='qc',
                space_after=60,
            )
        )

    if not answers_section and moves:
        moves_text = (_rtf_styled_text(f'{_format_number(num, opts)}. ', bold=True)
                      + _rtf_moves(moves, figurine=figurine))
        parts.append(_rtf_para(moves_text, align='ql', space_after=120))

    parts.append(r'\cell')
    return ''.join(parts)


def _rtf_answer_cell(num: int, moves: str, diag_anchor: str, ans_anchor: str,
                     *, figurine: bool = False) -> str:
    """Build one RTF answers cell."""
    num_link = _rtf_internal_link(f'{num}. ', diag_anchor, blue=True, bold=True, underline=False)
    return _rtf_para(
        _rtf_bookmark(ans_anchor) + num_link + _rtf_moves(moves, figurine=figurine),
        align='ql', space_after=120,
    ) + r'\cell'


def _rtf_table_row(cells: list[str], *, table_left_twips: int, cell_width_twips: int) -> str:
    """Return one complete RTF table row."""
    rights: list[int] = []
    edge = table_left_twips
    for _ in cells:
        edge += cell_width_twips
        rights.append(edge)
    row = [rf'\trowd\trgaph108\trleft{table_left_twips}']
    row.extend(rf'\cellx{right}' for right in rights)
    row.extend(cells)
    row.append(r'\row')
    return ''.join(row)

def generate_rtf(positions: list[PositionDict], opts: RenderOptions | dict,
                 out_path, progress=None) -> None:
    """Render an RTF document using the chess font directly for diagrams."""
    opts = RenderOptions.coerce(opts)
    valid = [p for p in positions if p.get('fen', '').strip()]
    total = len(valid)
    font_name = opts.font
    resolve_board_font(font_name)   # fail early on an unknown font name
    answers_section = opts.answers_section
    answers_title = _answers_heading(opts)
    answers_cols = opts.answers_cols

    lay = LAYOUTS[opts.layout_idx]
    cols = max(1, int(lay[3]))
    max_rows = lay[5] if opts.lines_count > 0 else lay[4]
    per_page = max(1, cols * max_rows)
    board_font_size = max(16, int((opts.font_size or lay[6]) * 2))

    page = opts.page
    twips = page.as_twips()
    paper_w, paper_h = twips['paperw'], twips['paperh']
    margin_l, margin_r = twips['margl'], twips['margr']
    margin_t, margin_b = twips['margt'], twips['margb']
    usable_w = paper_w - margin_l - margin_r
    cell_w = max(1600, usable_w // cols)
    board_font_name = _rtf_font_name(_board_font_family_name(font_name))
    figurine_family = _figurine_family_name(opts) if answers_section else ''
    use_figurine = bool(figurine_family)

    font_table = [
        r'{\f0\fnil\fcharset0 Calibri;}',
        # Board glyphs live outside the ANSI repertoire, so Word has to be told
        # this is a symbol font — the DOCX export already declares charset 2.
        rf'{{\f{RTF_FONT_BOARD}\fnil\fcharset2 {board_font_name};}}',
    ]
    if use_figurine:
        font_table.append(
            rf'{{\f{RTF_FONT_FIGURINE}\fnil\fcharset2 {_rtf_font_name(figurine_family)};}}'
        )

    parts = [
        r'{\rtf1\ansi\deff0',
        '{\\fonttbl' + ''.join(font_table) + '}',
        r'{\colortbl;\red0\green0\blue255;}',
        rf'\paperw{paper_w}\paperh{paper_h}\margl{margin_l}\margr{margin_r}'
        rf'\margt{margin_t}\margb{margin_b}' + (r'\landscape' if page.landscape else ''),
    ]

    header_text = opts.header_text
    footer_text = opts.footer_text
    first_chapter = next((p.get('chapter', '') for p in valid if p.get('chapter')), '')
    # The watermark travels in the header because that is the part Word repeats
    # on every page; it joins whatever running text is already there.
    watermark = _rtf_watermark(opts.watermark, opts.watermark_opacity, page)
    if header_text or watermark:
        parts.append(
            r'{\header\pard\qc\f0\fs18 '
            + (_rtf_running_text(header_text, first_chapter) if header_text else '')
            + watermark + r'\par}'
        )
    if footer_text:
        parts.append(
            r'{\footer\pard\qc\f0\fs18 ' + _rtf_running_text(footer_text, first_chapter) + r'\par}'
        )

    parts.append(r'\viewkind4\uc1\pard\lang1033\f0\fs22')

    numbers = _numbering(valid, opts)
    answers: list[tuple[int, str, str, str]] = []
    rendered = 0
    first_page = True
    answer_cell_w = max(2400, usable_w // answers_cols)

    def flush_answers() -> None:
        """Write out the solutions gathered so far, then forget them."""
        if not answers:
            return
        if opts.answers_new_page:
            parts.append(r'\page')
        parts.append(_rtf_para(_rtf_styled_text(answers_title, bold=True),
                               align='qc', font_size=30, space_after=180))
        for start in range(0, len(answers), answers_cols):
            row_answers = answers[start:start + answers_cols]
            cells = [_rtf_answer_cell(num, moves, diag_anchor, ans_anchor, figurine=use_figurine)
                     for num, moves, diag_anchor, ans_anchor in row_answers]
            while len(cells) < answers_cols:
                cells.append(_rtf_empty_cell())
            parts.append(_rtf_table_row(cells, table_left_twips=margin_l,
                                        cell_width_twips=answer_cell_w))
        answers.clear()

    for chapter, indices in _chapter_groups(valid):
        if chapter:
            if not first_page:
                parts.append(r'\page')
            parts.append(
                r'\pard\qc\sb0\sa180\f0\fs32'
                + _rtf_styled_text(chapter, bold=True) + r'\par'
            )
            first_page = False

        for start in range(0, len(indices), per_page):
            page_indices = indices[start:start + per_page]
            if not first_page and start:
                parts.append(r'\page')
            elif first_page:
                first_page = False
            for row_start in range(0, len(page_indices), cols):
                row_indices = page_indices[row_start:row_start + cols]
                cells: list[str] = []
                for pos_idx in row_indices:
                    pos = valid[pos_idx]
                    rendered += 1
                    if progress and total > 0:
                        progress(int(rendered * 100 / total))
                    num = numbers[pos_idx]
                    anchor = _anchor_id(pos_idx)
                    moves = _clean_moves(pos.get('moves', ''))
                    cells.append(_rtf_diagram_cell(
                        pos, num, opts, font_name, RTF_FONT_BOARD, board_font_size,
                        cell_width_twips=cell_w, figurine=use_figurine, anchor=anchor,
                    ))
                    if answers_section and moves:
                        answers.append((num, moves, f'diag_{anchor}', f'ans_{anchor}'))
                while len(cells) < cols:
                    cells.append(_rtf_empty_cell())
                parts.append(_rtf_table_row(cells, table_left_twips=margin_l, cell_width_twips=cell_w))

        if answers_section and opts.answers_after_chapter:
            flush_answers()

    if answers_section:
        flush_answers()

    parts.append('}')
    # _rtf_escape has already turned every non-ASCII character into a \uN escape,
    # so anything left outside ASCII would be a bug rather than something to drop.
    Path(out_path).write_text(''.join(parts), encoding='ascii')
