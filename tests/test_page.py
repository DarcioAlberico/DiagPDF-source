"""Paper size, margins, document metadata, outline, cover and contents."""

from __future__ import annotations

import re
import subprocess
import sys
import zipfile

import pytest
from conftest import PGN_WITH_CHAPTERS, PROJECT_ROOT

import diagpdf
from diagpdf import page as page_mod
from diagpdf.geometry import _compute_geometry
from diagpdf.options import RenderOptions

PAGE_RE = re.compile(rb'/Type\s*/Page(?![s])')
MEDIABOX_RE = re.compile(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)')
MM_PER_PT = 25.4 / 72


def media_box_mm(path) -> tuple[float, float]:
    match = MEDIABOX_RE.search(path.read_bytes())
    return (float(match.group(1)) * MM_PER_PT, float(match.group(2)) * MM_PER_PT)


def page_count(path) -> int:
    return len(PAGE_RE.findall(path.read_bytes()))


# ── PageSetup ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('size', page_mod.PAGE_SIZE_KEYS)
def test_every_size_is_portrait_by_default(size):
    setup = page_mod.PageSetup(size=size)
    assert setup.height > setup.width


@pytest.mark.parametrize('size', page_mod.PAGE_SIZE_KEYS)
def test_landscape_swaps_the_dimensions(size):
    portrait = page_mod.PageSetup(size=size)
    landscape = page_mod.PageSetup(size=size, landscape=True)
    assert (landscape.width, landscape.height) == (portrait.height, portrait.width)


def test_a4_matches_the_iso_dimensions():
    assert page_mod.PageSetup(size='a4').dimensions == (210.0, 297.0)


def test_usable_area_subtracts_both_margins():
    setup = page_mod.PageSetup(size='a4', margin_lr=15, margin_tb=20)
    assert setup.usable_width == 210.0 - 30
    assert setup.usable_height == 297.0 - 40


def test_an_unknown_size_falls_back_to_a4():
    assert RenderOptions(page_size='foolscap').page.size == 'a4'
    assert RenderOptions(page_size='A5').page.size == 'a5'


def test_a_negative_margin_becomes_zero():
    assert RenderOptions(margin_lr=-10).page.margin_lr == 0


def test_a_margin_cannot_swallow_the_page():
    """Half the sheet per side would leave nothing to print on."""
    setup = RenderOptions(page_size='a5', margin_lr=500).page
    assert setup.usable_width >= 40


def test_a_nonsense_margin_falls_back():
    assert RenderOptions(margin_tb='wide').page.margin_tb == page_mod.DEFAULT_MARGIN_TB


def test_fpdf_kwargs_describe_the_sheet():
    kwargs = page_mod.PageSetup(size='letter', landscape=True).fpdf_kwargs()
    assert kwargs['orientation'] == 'L'
    assert kwargs['format'] == page_mod.PAGE_SIZES['letter']   # portrait dimensions


def test_twips_conversion_is_about_right():
    twips = page_mod.PageSetup(size='a4').as_twips()
    assert abs(twips['paperw'] - 11906) <= 2      # the classic A4 value
    assert abs(twips['paperh'] - 16838) <= 2


# ── Geometry follows the sheet ────────────────────────────────────────────────

@pytest.mark.parametrize('size', page_mod.PAGE_SIZE_KEYS)
def test_geometry_uses_the_requested_sheet(size):
    g = _compute_geometry({'page_size': size})
    assert page_mod.PageSetup(size=size).dimensions == (g.PW, g.PH)


def test_a_smaller_sheet_gets_a_smaller_board():
    a4 = _compute_geometry({'page_size': 'a4', 'layout_idx': 2})
    a5 = _compute_geometry({'page_size': 'a5', 'layout_idx': 2})
    assert a5.chess_pt < a4.chess_pt


@pytest.mark.parametrize('size', page_mod.PAGE_SIZE_KEYS)
@pytest.mark.parametrize('landscape', [False, True])
def test_content_fits_on_every_sheet(size, landscape):
    for layout_idx in range(len(diagpdf.LAYOUTS)):
        g = _compute_geometry({'page_size': size, 'landscape': landscape,
                               'layout_idx': layout_idx, 'lines_count': 3})
        assert g.max_rows * g.row_h <= g.USABLE_H + 1e-6, (size, landscape, layout_idx)


def test_wider_margins_leave_less_room():
    tight = _compute_geometry({'margin_lr': 5, 'margin_tb': 5})
    loose = _compute_geometry({'margin_lr': 30, 'margin_tb': 30})
    assert loose.USABLE_W < tight.USABLE_W
    assert loose.chess_pt <= tight.chess_pt


# ── The PDF really is that size ───────────────────────────────────────────────

@pytest.mark.parametrize('size', page_mod.PAGE_SIZE_KEYS)
def test_the_pdf_media_box_matches(size, tmp_path, base_opts, positions):
    out = tmp_path / f'{size}.pdf'
    diagpdf.generate_pdf(positions, {**base_opts, 'page_size': size}, out)
    width, height = media_box_mm(out)
    expected = page_mod.PageSetup(size=size).dimensions
    assert abs(width - expected[0]) < 0.5 and abs(height - expected[1]) < 0.5


def test_landscape_reaches_the_pdf(tmp_path, base_opts, positions):
    out = tmp_path / 'landscape.pdf'
    diagpdf.generate_pdf(positions, {**base_opts, 'landscape': True}, out)
    width, height = media_box_mm(out)
    assert width > height


def test_the_docx_carries_the_sheet(tmp_path, base_opts, one_position):
    out = tmp_path / 'a5.docx'
    diagpdf.generate_docx(one_position, {**base_opts, 'page_size': 'a5'}, out)
    with zipfile.ZipFile(out) as z:
        document = z.read('word/document.xml').decode()
    # A5 is 148 x 210 mm, which Word stores in twentieths of a point.
    assert 'w:w="8392"' in document or 'w:w="8391"' in document


def test_the_rtf_carries_the_sheet(tmp_path, base_opts, one_position):
    out = tmp_path / 'a5.rtf'
    diagpdf.generate_rtf(one_position, {**base_opts, 'page_size': 'a5'}, out)
    text = out.read_text(encoding='ascii')
    assert re.search(r'\\paperw83\d\d', text)


def test_the_rtf_marks_landscape(tmp_path, base_opts, one_position):
    out = tmp_path / 'land.rtf'
    diagpdf.generate_rtf(one_position, {**base_opts, 'landscape': True}, out)
    assert r'\landscape' in out.read_text(encoding='ascii')


def test_the_html_print_css_carries_the_sheet(tmp_path, base_opts, one_position):
    out = tmp_path / 'a5.html'
    diagpdf.generate_html(one_position, {**base_opts, 'page_size': 'a5'}, out)
    text = out.read_text(encoding='utf-8')
    assert 'size: 148mm 210mm;' in text


# ── Metadata ──────────────────────────────────────────────────────────────────

def test_metadata_reaches_the_pdf(tmp_path, base_opts, one_position):
    out = tmp_path / 'meta.pdf'
    diagpdf.generate_pdf(one_position, {
        **base_opts, 'doc_title': 'Tactics', 'doc_author': 'Someone',
        'doc_subject': 'Chess', 'doc_keywords': 'chess, puzzles', 'doc_language': 'pt',
    }, out)
    raw = out.read_bytes()
    for marker in (b'/Title', b'/Author', b'/Subject', b'/Keywords', b'/Creator'):
        assert marker in raw, marker
    assert b'DiagPDF' in raw


def test_metadata_is_omitted_when_not_given(tmp_path, base_opts, one_position):
    out = tmp_path / 'nometa.pdf'
    diagpdf.generate_pdf(one_position, base_opts, out)
    raw = out.read_bytes()
    assert b'/Author' not in raw
    assert b'/Creator' in raw          # always stamped


# ── Outline ───────────────────────────────────────────────────────────────────

def test_chapters_become_outline_entries(tmp_path, base_opts):
    out = tmp_path / 'outline.pdf'
    diagpdf.generate_pdf(diagpdf.parse_pgn(PGN_WITH_CHAPTERS), base_opts, out)
    assert b'/Outlines' in out.read_bytes()


def test_a_document_without_chapters_has_no_outline(tmp_path, base_opts, one_position):
    out = tmp_path / 'flat.pdf'
    diagpdf.generate_pdf(one_position, base_opts, out)
    raw = out.read_bytes()
    assert b'/Outlines' not in raw or raw.count(b'/Outlines') <= 1


def test_the_answers_section_is_an_outline_entry(tmp_path, base_opts, positions):
    out = tmp_path / 'ans.pdf'
    diagpdf.generate_pdf(positions, {**base_opts, 'answers_section': True}, out)
    assert b'/Outlines' in out.read_bytes()


# ── Page totals ───────────────────────────────────────────────────────────────

def test_the_total_placeholder_is_resolved(tmp_path, base_opts, positions):
    out = tmp_path / 'total.pdf'
    diagpdf.generate_pdf(positions, {
        **base_opts, 'footer': 'Page {page} of {total}', 'show_footer': True,
    }, out)
    raw = out.read_bytes()
    assert b'{nb}' not in raw, 'the page-count alias survived into the output'
    assert b'{total}' not in raw


def test_no_white_rectangles_are_painted_over_the_footer(tmp_path, base_opts, positions):
    """The old implementation blanked the area and redrew it."""
    from fpdf import FPDF
    rects: list = []
    original = FPDF.rect

    def spy(self, *args, **kwargs):
        rects.append((args, kwargs))
        return original(self, *args, **kwargs)

    FPDF.rect = spy
    try:
        diagpdf.generate_pdf(positions, {
            **base_opts, 'footer': '{page}/{total}', 'show_footer': True,
        }, tmp_path / 'clean.pdf')
    finally:
        FPDF.rect = original
    assert rects == []


# ── Cover and contents ────────────────────────────────────────────────────────

def test_the_cover_adds_one_page(tmp_path, base_opts, positions):
    plain = tmp_path / 'plain.pdf'
    covered = tmp_path / 'cover.pdf'
    diagpdf.generate_pdf(positions, base_opts, plain)
    diagpdf.generate_pdf(positions, {**base_opts, 'cover': True, 'doc_title': 'T'}, covered)
    assert page_count(covered) == page_count(plain) + 1


def test_the_contents_adds_one_page(tmp_path, base_opts):
    chaptered = diagpdf.parse_pgn(PGN_WITH_CHAPTERS)
    plain = tmp_path / 'plain.pdf'
    with_toc = tmp_path / 'toc.pdf'
    diagpdf.generate_pdf(chaptered, base_opts, plain)
    diagpdf.generate_pdf(chaptered, {**base_opts, 'contents': True}, with_toc)
    assert page_count(with_toc) == page_count(plain) + 1


def test_the_contents_is_skipped_without_chapters(tmp_path, base_opts, one_position):
    plain = tmp_path / 'plain.pdf'
    with_toc = tmp_path / 'toc.pdf'
    diagpdf.generate_pdf(one_position, base_opts, plain)
    diagpdf.generate_pdf(one_position, {**base_opts, 'contents': True}, with_toc)
    assert page_count(with_toc) == page_count(plain)


def test_the_contents_lists_the_chapters(tmp_path, base_opts):
    """Rendered back to text so the entries and their page numbers are checked."""
    pdfium = pytest.importorskip('pypdfium2')
    out = tmp_path / 'toc.pdf'
    diagpdf.generate_pdf(diagpdf.parse_pgn(PGN_WITH_CHAPTERS), {
        **base_opts, 'contents': True, 'answers_section': True, 'lang': 'en',
    }, out)
    document = pdfium.PdfDocument(out)
    text = document[0].get_textpage().get_text_range()
    assert 'Contents' in text
    assert 'Pins' in text and 'Forks' in text
    assert 'Solutions' in text


def test_the_contents_heading_follows_the_language(tmp_path, base_opts):
    pdfium = pytest.importorskip('pypdfium2')
    out = tmp_path / 'toc_pt.pdf'
    diagpdf.generate_pdf(diagpdf.parse_pgn(PGN_WITH_CHAPTERS), {
        **base_opts, 'contents': True, 'lang': 'pt',
    }, out)
    text = pdfium.PdfDocument(out)[0].get_textpage().get_text_range()
    assert 'Sumário' in text


def test_the_cover_shows_title_subtitle_and_author(tmp_path, base_opts, positions):
    pdfium = pytest.importorskip('pypdfium2')
    out = tmp_path / 'cover.pdf'
    diagpdf.generate_pdf(positions, {
        **base_opts, 'cover': True, 'doc_title': 'Tactics Book',
        'cover_subtitle': 'Selected puzzles', 'doc_author': 'A Maintainer',
    }, out)
    text = pdfium.PdfDocument(out)[0].get_textpage().get_text_range()
    assert 'Tactics Book' in text
    assert 'Selected puzzles' in text
    assert 'A Maintainer' in text


def test_the_cover_and_contents_come_first(tmp_path, base_opts):
    pdfium = pytest.importorskip('pypdfium2')
    out = tmp_path / 'both.pdf'
    diagpdf.generate_pdf(diagpdf.parse_pgn(PGN_WITH_CHAPTERS), {
        **base_opts, 'cover': True, 'contents': True, 'doc_title': 'Book', 'lang': 'en',
    }, out)
    document = pdfium.PdfDocument(out)
    assert 'Book' in document[0].get_textpage().get_text_range()
    assert 'Contents' in document[1].get_textpage().get_text_range()


def test_the_contents_page_numbers_are_right(tmp_path, base_opts):
    """Chapter one starts after the cover and the contents page."""
    pdfium = pytest.importorskip('pypdfium2')
    out = tmp_path / 'numbers.pdf'
    diagpdf.generate_pdf(diagpdf.parse_pgn(PGN_WITH_CHAPTERS), {
        **base_opts, 'cover': True, 'contents': True, 'doc_title': 'Book', 'lang': 'en',
    }, out)
    text = pdfium.PdfDocument(out)[1].get_textpage().get_text_range()
    numbers = [int(n) for n in re.findall(r'\b(\d+)\s*$', text, re.MULTILINE)]
    assert numbers == sorted(numbers)
    assert numbers[0] >= 3, 'the first chapter cannot precede the front matter'


# ── Capabilities ──────────────────────────────────────────────────────────────

def test_page_setup_is_reported_as_unsupported_by_epub(tmp_path, base_opts, one_position, capsys):
    diagpdf.generate_output(one_position, {**base_opts, 'page_size': 'a5'}, tmp_path / 'a.epub')
    assert 'page size' in capsys.readouterr().err


def test_the_cover_is_reported_as_unsupported_by_html(tmp_path, base_opts, one_position, capsys):
    diagpdf.generate_output(one_position, {**base_opts, 'cover': True}, tmp_path / 'a.html')
    assert 'cover page' in capsys.readouterr().err


def test_the_pdf_reports_nothing_for_the_new_options(tmp_path, base_opts, positions, capsys):
    diagpdf.generate_output(positions, {
        **base_opts, 'page_size': 'a5', 'landscape': True, 'cover': True,
        'contents': True, 'doc_title': 'T', 'doc_author': 'A',
    }, tmp_path / 'a.pdf')
    assert 'does not support' not in capsys.readouterr().err


# ── Through the CLI ───────────────────────────────────────────────────────────

def test_the_cli_plumbs_the_page_options(tmp_path):
    src = tmp_path / 'in.pgn'
    src.write_text(PGN_WITH_CHAPTERS, encoding='utf-8')
    out = tmp_path / 'book.pdf'
    result = subprocess.run(
        [sys.executable, 'fen2rtf.py', str(src), '-o', str(out),
         '--page-size', 'a5', '--landscape', '--margin-lr', '20',
         '--cover', '--contents', '--title', 'Book', '--author', 'Someone'],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0, result.stderr
    width, height = media_box_mm(out)
    assert width > height                        # landscape
    assert abs(width - 210.0) < 0.5              # A5 rotated
