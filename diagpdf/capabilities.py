"""What each output format can honour.

Options used to be accepted everywhere and quietly dropped by the formats
that could not act on them. Declaring the matrix makes the gaps visible."""

from __future__ import annotations

from pathlib import Path

from .fonts import _default_figurine_font_name
from .layouts import DEFAULT_LAYOUT, LAYOUTS, custom_layout
from .log import _warn
from .options import RenderOptions
from .page import DEFAULT_MARGIN_LR, DEFAULT_MARGIN_TB, DEFAULT_PAGE_SIZE

CAPABILITY_LABELS: dict[str, str] = {
    'lines':         'notation lines (--lines)',
    'header_footer': 'page header/footer (--header/--footer)',
    'page_numbers':  '{page} and {total} in the header/footer',
    'columns':       'multi-column diagram grid (--layout)',
    'chapters':      'chapter sections ([Chapter] tag)',
    'answers_cols':  'multi-column answers (--answers-cols)',
    'answers_upside_down': 'upside-down answers (--answers-upside-down)',
    'figurine':      'figurine font in the answers (--figurine-font)',
    'font_size':     'board font size (--font-size)',
    'page_setup':    'page size, orientation and margins (--page-size/--landscape/--margin-*)',
    'cover':         'a cover page (--cover)',
    'contents':      'a table of contents (--contents)',
    'outline':       'document outline entries per chapter',
    'metadata':      'document metadata (--title/--author/--subject/--keywords)',
    'watermark':     'a page watermark (--watermark)',
}

FORMAT_CAPABILITIES: dict[str, frozenset[str]] = {
    # A paginated format can do everything.
    '.pdf':  frozenset(CAPABILITY_LABELS),
    # Printed HTML has pages, but a browser cannot number them from markup:
    # CSS paged-media margin boxes are what carry counter(page), and browsers
    # do not implement them.
    # Printed HTML has pages, but nothing in the markup can number them, build
    # an outline, or place a generated cover.
    '.html': frozenset(CAPABILITY_LABELS) - {'page_numbers', 'cover', 'contents', 'outline'},
    '.htm':  frozenset(CAPABILITY_LABELS) - {'page_numbers', 'cover', 'contents', 'outline'},
    # EPUB is reflowable — the reader paginates, so the document has no pages
    # of its own to put a running header on.
    # A reflowable book has no pages of its own: no running header, no page
    # numbers, and no fixed page setup. Its navigation document is the outline.
    '.epub': frozenset(CAPABILITY_LABELS) - {
        'header_footer', 'page_numbers', 'page_setup', 'cover', 'contents', 'watermark',
    },
    # Word can rotate text only inside a drawing shape, and RTF has no turned
    # text at all, so neither can print the answers upside down. A watermark is
    # a drawing shape, which is exactly why both of them *can* do that one.
    '.docx': frozenset(CAPABILITY_LABELS) - {
        'cover', 'contents', 'outline', 'answers_upside_down',
    },
    '.rtf':  frozenset(CAPABILITY_LABELS) - {
        'cover', 'contents', 'outline', 'answers_upside_down',
    },
    # LaTeX is a typesetter: it does everything the PDF does, with two
    # exceptions. The figurine font has no counterpart -- the movetext is set in
    # the document font, because the piece symbols would have to come from the
    # chess package rather than from a font this program ships. And a turned box
    # cannot break across pages, so answers long enough to need a second page
    # would run off the first one rather than continue.
    '.tex':  frozenset(CAPABILITY_LABELS) - {'figurine', 'answers_upside_down'},
    # Markdown is a stream of text with no pages, no sheet and no fonts, so
    # everything about the printed page falls away. Its diagram is written with
    # the Unicode chess pieces, which is also how the answers get their
    # figurines, and its metadata is the YAML front matter.
    '.md':   frozenset({'lines', 'chapters', 'figurine', 'metadata'}),
    '.markdown': frozenset({'lines', 'chapters', 'figurine', 'metadata'}),
}


def requested_capabilities(opts: RenderOptions | dict) -> set[str]:
    """Return the capability keys the given options actually ask for."""
    opts = RenderOptions.coerce(opts)
    wanted: set[str] = set()
    if opts.lines_count > 0:
        wanted.add('lines')

    running = opts.header_text + opts.footer_text
    if running:
        wanted.add('header_footer')
        if any(tag in running for tag in ('{page}', '{total}')):
            wanted.add('page_numbers')

    # Both front ends always fill the layout in, so a request means a grid or a
    # preset that differs from the default one - the same rule the page setup
    # below already follows. Without it a format with no columns would report
    # the option on every single run, including runs that never chose it.
    layout = custom_layout(*opts.grid) if opts.grid else LAYOUTS[opts.layout_idx]
    if (opts.grid is not None or opts.layout_idx != DEFAULT_LAYOUT) and layout.cols > 1:
        wanted.add('columns')
    if opts.font_size > 0:
        wanted.add('font_size')
    if opts.answers_section:
        # Asking for an answers section is not the same as asking for a figurine
        # font; only a font other than the default one is a request for it.
        if opts.figurine_font != _default_figurine_font_name():
            wanted.add('figurine')
        if opts.answers_cols > 1:
            wanted.add('answers_cols')
        if opts.answers_upside_down:
            wanted.add('answers_upside_down')

    # The CLI always fills the margin keys, so a request means a value that
    # actually differs from the default sheet.
    if (opts.page_size != DEFAULT_PAGE_SIZE
            or opts.landscape
            or opts.margin_lr != DEFAULT_MARGIN_LR
            or opts.margin_tb != DEFAULT_MARGIN_TB):
        wanted.add('page_setup')
    if opts.watermark.strip():
        wanted.add('watermark')
    if opts.cover:
        wanted.add('cover')
    if opts.contents:
        wanted.add('contents')
    if any(getattr(opts, key).strip()
           for key in ('doc_title', 'doc_author', 'doc_subject', 'doc_keywords')):
        wanted.add('metadata')
    return wanted


def unsupported_options(opts: RenderOptions | dict, suffix: str, has_chapters: bool = False) -> list[str]:
    """Return human-readable labels for options *suffix* cannot honour."""
    supported = FORMAT_CAPABILITIES.get(suffix.lower(), FORMAT_CAPABILITIES['.pdf'])
    wanted = requested_capabilities(opts)
    if has_chapters:
        wanted.add('chapters')
    return [CAPABILITY_LABELS[key] for key in sorted(wanted - supported)]


def warn_unsupported_options(opts: RenderOptions | dict, out_path, positions=None) -> list[str]:
    """Warn about every requested option the target format cannot honour."""
    suffix = Path(out_path).suffix.lower()
    has_chapters = bool(positions) and any(p.get('chapter') for p in positions)
    missing = unsupported_options(opts, suffix, has_chapters)
    fmt = (suffix.lstrip('.') or 'pdf').upper()
    for label in missing:
        _warn(f'{fmt} does not support {label} - the option will be ignored')
    return missing
