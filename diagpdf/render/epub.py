"""EPUB 3 packaging around the shared HTML body."""

from __future__ import annotations

import html
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from ..fonts import check_embedding_permitted, resolve_board_font
from ..model import PositionDict
from ..options import RenderOptions
from ..resources import _resource
from .common import _epub_document_title, _figurine_font_path, _layout_columns
from .html import (
    _board_row_size_px,
    _build_diagram_css,
    _css_figurine_family,
    _css_font_family,
    _render_html_document,
)


def _epub_extra_css_info(css_path: str) -> tuple[str, str]:
    """Return the EPUB-internal filename and manifest id for an imported CSS file."""
    name = Path(css_path).name or 'custom.css'
    stem = re.sub(r'[^A-Za-z0-9_]+', '_', Path(name).stem).strip('_') or 'custom'
    if Path(name).name.lower() == 'diagram_confg.css':
        name = 'imported_custom.css'
    elif Path(name).suffix.lower() != '.css':
        name = f'{stem}.css'
    return name, f'css_{stem.lower()}'

def generate_epub(positions: list[PositionDict], opts: RenderOptions | dict,
                  out_path, progress=None) -> None:
    """Write an EPUB 3 package with the diagrams and the board font."""
    opts = RenderOptions.coerce(opts)
    font_name = opts.font
    fname = resolve_board_font(font_name)
    fonts_dir = _resource('.') / 'Fonts'
    font_path = fonts_dir / fname
    css_font_name = _css_font_family(font_name)
    css_name = 'diagram_confg.css'
    css_path_in_epub = f'Styles/{css_name}'
    extra_css_path = opts.epub_css_path.strip()
    stylesheet_hrefs = [css_path_in_epub]
    extra_css_name = ''
    extra_css_id = ''
    extra_css_text = ''

    allow_restricted = opts.allow_restricted_fonts
    embed_font = font_path.exists() and check_embedding_permitted(font_path, 'EPUB', allow_restricted)

    figurine_path = _figurine_font_path(opts) if opts.answers_section else None
    figurine_name = ''
    figurine_href = ''
    if figurine_path is not None and check_embedding_permitted(figurine_path, 'EPUB', allow_restricted):
        figurine_name = _css_figurine_family(opts.figurine_font)
        figurine_href = f'../Fonts/{figurine_path.name}'
    else:
        figurine_path = None

    # Without the packaged font the @font-face rule would point at nothing.
    css_text = _build_diagram_css(
        f'../Fonts/{fname}' if embed_font else '',
        css_font_name,
        figurine_url=figurine_href,
        figurine_name=figurine_name,
        columns=_layout_columns(opts),
        answers_columns=opts.answers_cols,
        answers_upside_down=opts.answers_upside_down,
        board_row_size=_board_row_size_px(opts),
    )

    if extra_css_path:
        extra_css_name, extra_css_id = _epub_extra_css_info(extra_css_path)
        extra_css_text = Path(extra_css_path).read_text(encoding='utf-8', errors='replace')
        stylesheet_hrefs.append(f'Styles/{extra_css_name}')

    doc_title = _epub_document_title(opts)
    doc_author = opts.doc_author.strip()
    doc_language = opts.doc_language.strip() or opts.lang
    book_id = f'urn:uuid:{uuid.uuid4()}'
    modified = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    html_content, nav_points = _render_html_document(
        positions,
        opts,
        progress=progress,
        stylesheet_hrefs=stylesheet_hrefs,
        paginated=False,   # a reflowable book has no pages to put a header on
    )

    with zipfile.ZipFile(out_path, 'w', compression=zipfile.ZIP_DEFLATED) as epub:
        epub.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)

        container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
        epub.writestr('META-INF/container.xml', container_xml)

        if embed_font:
            epub.writestr(f'OEBPS/Fonts/{fname}', font_path.read_bytes())
        if figurine_path is not None:
            epub.writestr(f'OEBPS/Fonts/{figurine_path.name}', figurine_path.read_bytes())
        epub.writestr(f'OEBPS/{css_path_in_epub}', css_text)
        if extra_css_text:
            epub.writestr(f'OEBPS/Styles/{extra_css_name}', extra_css_text)
        epub.writestr('OEBPS/content.xhtml', html_content)

        esc_title = html.escape(doc_title)
        esc_author = html.escape(doc_author)

        # One navigation entry per chapter, so a reader's table of contents is
        # useful instead of a single "Diagrams" line.
        entries = nav_points or [('', 'Diagrams')]
        nav_items = '\n'.join(
            f'            <li><a href="content.xhtml{"#" + anchor if anchor else ""}">'
            f'{html.escape(label)}</a></li>'
            for anchor, label in entries
        )

        # EPUB 3 requires a navigation document declared with properties="nav".
        nav_xhtml = f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
<meta charset="utf-8"/>
<title>{esc_title}</title>
</head>
<body>
    <nav epub:type="toc" id="toc">
        <h1>{esc_title}</h1>
        <ol>
{nav_items}
        </ol>
    </nav>
</body>
</html>'''
        epub.writestr('OEBPS/nav.xhtml', nav_xhtml)

        manifest_items = [
            '        <item id="content" href="content.xhtml" media-type="application/xhtml+xml"/>',
            '        <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
            f'        <item id="diagram_css" href="{css_path_in_epub}" media-type="text/css"/>',
            '        <item id="toc" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        ]
        if embed_font:
            media = 'font/otf' if fname.lower().endswith('.otf') else 'font/ttf'
            manifest_items.insert(2, f'        <item id="font" href="Fonts/{fname}" media-type="{media}"/>')
        if figurine_path is not None:
            media = 'font/otf' if figurine_path.suffix.lower() == '.otf' else 'font/ttf'
            manifest_items.append(
                f'        <item id="figurine_font" href="Fonts/{figurine_path.name}" media-type="{media}"/>'
            )
        if extra_css_text:
            manifest_items.append(f'        <item id="{extra_css_id}" href="Styles/{extra_css_name}" media-type="text/css"/>')

        creator_tag = f'\n        <dc:creator>{esc_author}</dc:creator>' if esc_author else ''

        content_opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="BookId">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>{esc_title}</dc:title>
        <dc:language>{html.escape(doc_language)}</dc:language>
        <dc:identifier id="BookId">{book_id}</dc:identifier>{creator_tag}
        <meta property="dcterms:modified">{modified}</meta>
    </metadata>
    <manifest>
{chr(10).join(manifest_items)}
    </manifest>
    <spine toc="toc">
        <itemref idref="content"/>
    </spine>
</package>'''
        epub.writestr('OEBPS/content.opf', content_opf)

        toc_ncx = f'''<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
    <head>
        <meta name="dtb:uid" content="{book_id}"/>
        <meta name="dtb:depth" content="1"/>
        <meta name="dtb:totalPageCount" content="0"/>
        <meta name="dtb:maxPageNumber" content="0"/>
    </head>
    <docTitle><text>{esc_title}</text></docTitle>
    <navMap>
        <navPoint id="navPoint-1" playOrder="1">
            <navLabel><text>Diagrams</text></navLabel>
            <content src="content.xhtml"/>
        </navPoint>
    </navMap>
</ncx>'''
        epub.writestr('OEBPS/toc.ncx', toc_ncx)
