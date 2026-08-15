"""Standalone HTML output, and the document body shared with the EPUB export."""

from __future__ import annotations

import html
import re
from pathlib import Path

from ..fen import fen_to_diagram, parse_fen
from ..fonts import _font_data_uri, resolve_board_font
from ..i18n import _answers_heading, _lichess_label
from ..layouts import LAYOUTS
from ..log import _warn
from ..model import PositionDict
from ..options import RenderOptions
from ..page import PageSetup
from ..parsers import _clean_moves
from ..resources import _resource
from .common import (
    _anchor_id,
    _chapter_groups,
    _epub_document_title,
    _figurine_font_path,
    _figurine_segments,
    _format_number,
    _has_embedded_side_indicator,
    _layout_columns,
    _lichess_analysis_url,
    _make_title,
    _numbering,
    _side_indicator_text,
    _split_title_number_prefix,
)


def _html_font_url(opts: RenderOptions, font_path: Path, kind: str = 'board') -> str:
    """Return the ``src`` URL for a font in a standalone HTML file.

    A relative ``../Fonts/x.ttf`` only resolves when the HTML happens to sit one
    directory below the application, so the default is to inline the font.
    """
    mode = opts.html_font_mode
    if mode == 'none':
        return ''
    if not font_path.exists():
        if mode == 'embed':
            _warn(f'{font_path.name} not found - linking to it relatively instead of embedding')
        return f'../Fonts/{font_path.name}'
    if mode == 'embed':
        return _font_data_uri(font_path)
    return f'../Fonts/{font_path.name}'


def _board_font_path(opts: RenderOptions) -> Path:
    return _resource('Fonts') / resolve_board_font(opts.font)

def _css_font_family(font_name: str) -> str:
    """Return a CSS-safe font-family name for a chess font."""
    return font_name.lower().replace('chess', '') if font_name.startswith('Chess') else font_name.lower()


def _css_figurine_family(font_name: str) -> str:
    return f'fig-{re.sub(r"[^a-z0-9]+", "", font_name.lower()) or "figurine"}'


def _board_row_size_px(opts: RenderOptions) -> int:
    """Board row height in px, honouring --font-size.

    The PDF measures the board in points; on screen a point has no fixed size,
    so the pt value is treated as a request and scaled to a comfortable default
    (the built-in 36px matches roughly the 23pt of the default layout).
    """
    if opts.font_size > 0:
        return max(8, int(round(opts.font_size * 36 / 23)))
    return max(8, int(round(LAYOUTS[opts.layout_idx][6] * 36 / 23)))

def _build_diagram_css(
    font_url: str,
    css_font_name: str,
    *,
    figurine_url: str = '',
    figurine_name: str = '',
    columns: int = 1,
    answers_columns: int = 1,
    answers_upside_down: bool = False,
    answers_new_page: bool = False,
    watermark_opacity: int = 0,
    board_row_size: int = 36,
    page: PageSetup | None = None,
) -> str:
    """Return the shared stylesheet used by HTML and EPUB exports."""
    page = page or PageSetup()
    page_size_css = f'{page.width:g}mm {page.height:g}mm'
    page_margin_css = f'{page.margin_tb:g}mm {page.margin_lr:g}mm'
    face: list[str] = []
    if font_url:
        face += [
            '@font-face {',
            f'  font-family: "{css_font_name}";',
            f'  src: url("{font_url}");',
            '}',
            '',
        ]
    if figurine_url and figurine_name:
        face += [
            '@font-face {',
            f'  font-family: "{figurine_name}";',
            f'  src: url("{figurine_url}");',
            '}',
            '',
        ]

    return '\n'.join(face + [
        ':root {',
        f'  --board-row-size: {board_row_size}px;',
        f'  --columns: {columns};',
        f'  --answers-columns: {answers_columns};',
        '  --side-indicator-scale: 0.8;',
        '  --side-indicator-gap: 0.12rem;',
        # Card colours used below. Without these the border and background
        # declarations are invalid and silently dropped by every browser.
        '  --card-bg: #ffffff;',
        '  --card-border: #cbd5e1;',
        '  --text: #111111;',
        '  --link: #0645ad;',
        '}',
        '',
        '@media (prefers-color-scheme: dark) {',
        '  :root {',
        '    --card-bg: #1e1e1e;',
        '    --card-border: #3f3f46;',
        '    --text: #e5e5e5;',
        '    --link: #6ea8fe;',
        '  }',
        '}',
        '',
        'body {',
        '  color: var(--text);',
        '}',
        '',
        '.container {',
        '  display: grid;',
        '  grid-template-columns: repeat(var(--columns), minmax(0, 1fr));',
        '  gap: 1rem;',
        '  align-items: start;',
        '}',
        '',
        '.chapter-title {',
        '  margin: 1.5rem 0 0.5rem;',
        '  text-align: center;',
        '  break-before: page;',
        '  page-break-before: always;',
        '}',
        '',
        '.chapter:first-of-type .chapter-title {',
        '  break-before: auto;',
        '  page-break-before: auto;',
        '}',
        '',
        '.diagram-block {',
        '  text-align: center;',
        '  margin: 0;',
        '  break-inside: avoid;',
        '  page-break-inside: avoid;',
        '}',
        '',
        '.diagram {',
        '  width: fit-content;',
        '  max-width: 100%;',
        '  margin: 0 auto;',
        '  padding: 0.75rem;',
        '  border: 1px solid var(--card-border);',
        '  background: var(--card-bg);',
        '  box-sizing: border-box;',
        '  display: flex;',
        '  flex-direction: column;',
        '  align-items: center;',
        '}',
        '',
        '.board-wrap {',
        '  display: flex;',
        '  align-items: flex-end;',
        '  justify-content: center;',
        '  gap: var(--side-indicator-gap);',
        '  width: 100%;',
        '}',
        '',
        '.title {',
        '  width: 100%;',
        '  text-align: center;',
        '}',
        '',
        '.title a,',
        '.moves a {',
        '  color: var(--link);',
        '}',
        '',
        '.title a {',
        '  text-decoration: none;',
        '}',
        '',
        '.moves a {',
        '  text-decoration: underline;',
        '}',
        '',
        '.board {',
        f'  font-family: "{css_font_name}";',
        '  font-size: var(--board-row-size);',
        '  line-height: 1;',
        '  white-space: pre;',
        '  margin: 0;',
        '  color: var(--text);',
        '  display: flex;',
        '  flex-direction: column;',
        '}',
        '',
        '.board-row {',
        '  display: block;',
        '  height: var(--board-row-size);',
        '  line-height: var(--board-row-size);',
        '}',
        '',
        '.side-indicator {',
        '  font-size: calc(var(--board-row-size) * var(--side-indicator-scale));',
        '  line-height: 1;',
        '  margin-bottom: var(--board-row-size);',
        '}',
        '',
        '.notation {',
        '  width: 100%;',
        '  margin-top: 0.4rem;',
        '}',
        '',
        '.notation-line {',
        '  display: flex;',
        '  align-items: flex-end;',
        '  gap: 0.35rem;',
        '  height: 1.45rem;',
        '}',
        '',
        '.move-no {',
        '  font-size: 0.75rem;',
        '  line-height: 1.45rem;',
        '  min-width: 1.3rem;',
        '  text-align: right;',
        '}',
        '',
        '.blank {',
        '  flex: 1 1 0;',
        '  border-bottom: 1px solid var(--text);',
        '}',
        '',
        '.blank.skip {',
        '  border-bottom: none;',
        '}',
        '',
        '.lichess-link {',
        '  margin-top: 0.25rem;',
        '  font-size: 1rem;',
        '  width: 100%;',
        '  text-align: center;',
        '}',
        '',
        '.answers {',
        '  column-count: var(--answers-columns);',
        '  column-gap: 1.5rem;',
        # Printing only: on screen the answers simply follow the diagrams, the
        # way every other section does.
        *(['  break-before: page;',
           '  page-break-before: always;'] if answers_new_page else []),
        '}',
        '',
        '.answers .moves {',
        '  break-inside: avoid;',
        '  page-break-inside: avoid;',
        '  margin-bottom: 0.35rem;',
        '}',
        '',
        '.answers-title {',
        '  column-span: all;',
        '  text-align: center;',
        '}',
        '',
        # Turned over as one block, so the reader rotates the page and reads it
        # in the usual order. Rotating each line about itself would leave them
        # running bottom to top once the page was turned.
        # Fixed rather than absolute so it stays put while the page scrolls.
        # In print it lands on the sheet the browser is composing; browsers
        # differ on whether a fixed box repeats on every printed page.
        *(['.watermark {',
           '  position: fixed;',
           '  top: 50%;',
           '  left: 50%;',
           '  transform: translate(-50%, -50%) rotate(-45deg);',
           '  transform-origin: center center;',
           '  font-size: 18vw;',
           '  font-weight: bold;',
           '  white-space: nowrap;',
           '  color: var(--text);',
           f'  opacity: {watermark_opacity / 100:g};',
           '  pointer-events: none;',
           '  user-select: none;',
           '  z-index: 1000;',
           '}',
           ''] if watermark_opacity else []),
        *(['.answers.upside-down {',
           '  transform: rotate(180deg);',
           '  transform-origin: center center;',
           '}',
           ''] if answers_upside_down else []),
        f'.figurine {{ font-family: "{figurine_name}"; }}' if figurine_name else '',
        '',
        '.page-header,',
        '.page-footer {',
        '  display: none;',
        '}',
        '',
        '@media print {',
        '  :root {',
        '    --card-bg: #ffffff;',
        '    --card-border: #000000;',
        '    --text: #000000;',
        '    --link: #000000;',
        '  }',
        '  @page {',
        f'    size: {page_size_css};',
        f'    margin: {page_margin_css};',
        '  }',
        '  body {',
        '    margin: 0;',
        '  }',
        # position: fixed repeats an element on every printed sheet in the
        # browsers that matter, which is the closest a document can get to a
        # running header without paged-media margin boxes.
        '  .page-header,',
        '  .page-footer {',
        '    display: block;',
        '    position: fixed;',
        '    left: 0;',
        '    right: 0;',
        '    text-align: center;',
        '    font-size: 0.8rem;',
        '  }',
        '  .page-header { top: 0; }',
        '  .page-footer { bottom: 0; }',
        '  .diagram-block,',
        '  .diagram,',
        '  .board-wrap,',
        '  .board,',
        '  .notation,',
        '  .lichess-link {',
        '    break-inside: avoid-page;',
        '    page-break-inside: avoid;',
        '  }',
        '}',
    ])


def _html_notation_lines(opts: RenderOptions, side: str) -> list[str]:
    """Render the blank notation lines drawn under a diagram."""
    count = opts.lines_count
    if count <= 0:
        return []
    numbered = opts.lines_mode == 'numbered'
    parts = ["<div class='notation'>"]
    for index in range(count):
        parts.append("<div class='notation-line'>")
        if numbered:
            parts.append(f"<span class='move-no'>{index + 1}.</span>")
            # Black to move: the first move number belongs to White, so its
            # blank is skipped and only Black's is offered.
            skip_white = index == 0 and side == 'b'
            parts.append(f"<span class='blank{' skip' if skip_white else ''}'></span>")
            parts.append("<span class='blank'></span>")
        else:
            parts.append("<span class='blank'></span>")
        parts.append('</div>')
    parts.append('</div>')
    return parts


def _html_moves(moves: str, opts: RenderOptions) -> str:
    """Escape movetext, marking piece letters for the figurine font."""
    if not _figurine_font_path(opts):
        return html.escape(moves)
    out: list[str] = []
    for font, run in _figurine_segments(moves, 'text', 'figurine'):
        escaped = html.escape(run)
        out.append(f"<span class='figurine'>{escaped}</span>" if font == 'figurine' else escaped)
    return ''.join(out)

def _render_html_document(
    positions: list[PositionDict],
    opts: RenderOptions,
    progress=None,
    embedded_css: str | None = None,
    stylesheet_hrefs: list[str] | None = None,
    paginated: bool = True,
) -> tuple[str, list[tuple[str, str]]]:
    """Build the HTML/XHTML document shared by the HTML and EPUB exports.

    Returns the document and the list of (anchor id, chapter title) pairs, which
    the EPUB export turns into navigation entries.
    """
    font_name = opts.font
    resolve_board_font(font_name)   # fail early on an unknown font name

    html_parts = [
        '<!DOCTYPE html>',
        '<html xmlns="http://www.w3.org/1999/xhtml">',
        '<head>',
        '<meta charset="utf-8"/>',
        f'<title>{html.escape(_epub_document_title(opts))}</title>',
    ]

    if stylesheet_hrefs:
        for href in stylesheet_hrefs:
            html_parts.append(f'<link rel="stylesheet" type="text/css" href="{href}"/>')
    if embedded_css is not None:
        html_parts.extend(['<style>', embedded_css, '</style>'])

    html_parts.append('</head><body>')

    title_template = opts.title_template
    title_mode = opts.title_mode
    title_custom = opts.title_custom
    flip_flag = opts.flip
    flip_auto = opts.flip_auto
    answers_section = opts.answers_section
    coords = opts.coords
    symbol = opts.symbol
    border_style = opts.border_style
    lichess_link = opts.lichess_link

    valid = [p for p in positions if p.get('fen', '').strip()]
    total = len(valid)   # positions without a FEN are skipped, so they must
                         # not count towards progress or it never reaches 100%

    # Running header/footer, printed only. {page}/{total} cannot be resolved
    # from markup, so they are dropped here and reported by the capability check.
    # A reflowable book has no pages to stamp, so the mark rides with the
    # running header and footer: paginated output only.
    if paginated and opts.watermark.strip():
        html_parts.append(
            f"<div class='watermark' aria-hidden='true'>{html.escape(opts.watermark.strip())}</div>"
        )

    if paginated:
        for kind, raw in (
            ('page-header', opts.header_text),
            ('page-footer', opts.footer_text),
        ):
            text = re.sub(r'\{(page|total)\}', '', raw).strip()
            if text:
                html_parts.append(f"<div class='{kind}'>{html.escape(text)}</div>")

    answers_html: list[str] = []
    nav_points: list[tuple[str, str]] = []
    groups = _chapter_groups(valid)
    numbers = _numbering(valid, opts)
    rendered = 0
    answer_sections = 0

    def flush_answers(collected: list[str]) -> None:
        """Emit the solutions gathered so far as their own section."""
        nonlocal answer_sections
        if not collected:
            return
        answer_sections += 1
        # One section at the end keeps the plain id it has always had; a book
        # with a section per chapter needs an id each, or the links collide.
        section_id = f'answers-{answer_sections}' if opts.answers_after_chapter else 'answers'
        ans_title = _answers_heading(opts)
        nav_points.append((section_id, ans_title))
        turned = ' upside-down' if opts.answers_upside_down else ''
        html_parts.append(f"<section class='answers{turned}' id='{section_id}'>")
        html_parts.append(f"<h2 class='answers-title'>{html.escape(ans_title)}</h2>")
        html_parts.extend(collected)
        html_parts.append('</section>')
        collected.clear()

    for group_index, (chapter, indices) in enumerate(groups):
        if chapter:
            chapter_id = f'chapter-{group_index + 1}'
            nav_points.append((chapter_id, chapter))
            html_parts.append(f"<section class='chapter' id='{chapter_id}'>")
            html_parts.append(f"<h2 class='chapter-title'>{html.escape(chapter)}</h2>")
        else:
            html_parts.append("<section class='chapter'>")
        html_parts.append("<div class='container'>")

        for pos_idx in indices:
            pos = valid[pos_idx]
            rendered += 1
            if progress and total > 0:
                progress(int(rendered * 100 / total))

            fen = pos.get('fen', '').strip()
            num = numbers[pos_idx]
            title = _make_title(pos, num, title_template, title_mode, title_custom, opts)
            moves = _clean_moves(pos.get('moves', ''))
            has_answer = answers_section and bool(moves)
            anchor = _anchor_id(pos_idx)
            diag_id = f'diagram-{anchor}'
            ans_id = f'answer-{anchor}'
            side = parse_fen(fen)[1]
            side_indicator = (
                _side_indicator_text(side, symbol)
                if not _has_embedded_side_indicator(font_name) else ''
            )

            diag_lines = fen_to_diagram(
                fen,
                coords=coords,
                flip=flip_flag,
                flip_auto=flip_auto,
                symbol=symbol,
                font_name=font_name,
                border_style=border_style,
            )

            html_parts.append(f"<div class='diagram-block' id='{diag_id}'>")
            html_parts.append("<div class='diagram'>")
            if title:
                if has_answer:
                    prefix, suffix = _split_title_number_prefix(title, num, opts)
                    if prefix:
                        html_parts.append(
                            "<div class='title'>"
                            f"<a href='#{ans_id}'>{html.escape(prefix)}</a>{html.escape(suffix)}"
                            "</div>"
                        )
                    else:
                        html_parts.append(
                            "<div class='title'>"
                            f"<a href='#{ans_id}'>{html.escape(title)}</a>"
                            "</div>"
                        )
                else:
                    html_parts.append(f"<div class='title'>{html.escape(title)}</div>")

            if side_indicator:
                html_parts.append("<div class='board-wrap'>")
            html_parts.append("<div class='board'>")
            for ln in diag_lines:
                html_parts.append(f"<span class='board-row'>{html.escape(ln)}</span>")
            html_parts.append('</div>')
            if side_indicator:
                html_parts.append(f"<div class='side-indicator'>{html.escape(side_indicator)}</div>")
                html_parts.append('</div>')

            html_parts.extend(_html_notation_lines(opts, side))

            if lichess_link and fen:
                lnk = _lichess_analysis_url(fen)
                html_parts.append(
                    f"<div class='lichess-link'><a href='{html.escape(lnk, quote=True)}'>"
                    f"{html.escape(_lichess_label(opts))}</a></div>"
                )

            if not answers_section:
                if moves:
                    html_parts.append(
                        f"<div class='moves'><strong>{_format_number(num, opts)}.</strong> "f"{_html_moves(moves, opts)}</div>"
                    )
            elif moves:
                answers_html.append(
                    f"<div class='moves' id='{ans_id}'>"
                    f"<strong><a href='#{diag_id}'>{_format_number(num, opts)}.</a></strong> "f"{_html_moves(moves, opts)}"
                    "</div>"
                )

            html_parts.append('</div>')
            html_parts.append('</div>')

        html_parts.append('</div>')
        html_parts.append('</section>')

        if answers_section and opts.answers_after_chapter:
            flush_answers(answers_html)

    if answers_section:
        flush_answers(answers_html)

    html_parts.append('</body></html>')
    return '\n'.join(html_parts), nav_points


def generate_html(
    positions: list[PositionDict],
    opts: RenderOptions | dict,
    out_path,
    progress=None,
    font_url: str | None = None,
) -> None:
    """Write a standalone HTML file with the board fonts inlined by default."""
    opts = RenderOptions.coerce(opts)
    font_name = opts.font
    if font_url is None:
        font_url = _html_font_url(opts, _board_font_path(opts))

    figurine_url = ''
    figurine_name = ''
    figurine_path = _figurine_font_path(opts) if opts.answers_section else None
    if figurine_path is not None:
        figurine_name = _css_figurine_family(opts.figurine_font)
        figurine_url = _html_font_url(opts, figurine_path, kind='figurine')

    css = _build_diagram_css(
        font_url,
        _css_font_family(font_name),
        figurine_url=figurine_url,
        figurine_name=figurine_name if figurine_url else '',
        columns=_layout_columns(opts),
        answers_columns=opts.answers_cols,
        answers_upside_down=opts.answers_upside_down,
        answers_new_page=opts.answers_new_page,
        watermark_opacity=opts.watermark_opacity if opts.watermark.strip() else 0,
        board_row_size=_board_row_size_px(opts),
        page=opts.page,
    )
    html_text, _ = _render_html_document(positions, opts, progress=progress, embedded_css=css)
    Path(out_path).write_text(html_text, encoding='utf-8')
