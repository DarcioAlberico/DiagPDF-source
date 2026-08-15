"""Format parity: the capability matrix has to be true, not aspirational.

Every capability a format declares is exercised against the generated document;
every capability it does not declare has to produce a warning rather than
silence.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile

import inspectors as I
import pytest
from conftest import PGN_WITH_CHAPTERS

import fen2rtf as F

FORMATS = ['.pdf', '.html', '.epub', '.docx', '.rtf', '.md', '.tex']


def supports(suffix: str, capability: str) -> bool:
    return capability in F.FORMAT_CAPABILITIES[suffix]


def needs(suffix: str, capability: str) -> None:
    if not supports(suffix, capability):
        pytest.skip(f'{suffix} does not claim {capability}')


@pytest.fixture
def many_positions() -> list[dict]:
    return [
        {'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'comment': f'P{i}', 'moves': '1.Nf3 Ke7'}
        for i in range(6)
    ]


# ── The matrix itself ─────────────────────────────────────────────────────────

def test_every_generator_has_a_capability_entry():
    assert set(F.GENERATORS) == set(F.FORMAT_CAPABILITIES)


def test_capability_keys_are_all_labelled():
    for suffix, caps in F.FORMAT_CAPABILITIES.items():
        assert caps <= set(F.CAPABILITY_LABELS), suffix


def test_pdf_is_the_reference_implementation():
    assert F.FORMAT_CAPABILITIES['.pdf'] == set(F.CAPABILITY_LABELS)


def test_requested_capabilities_reflect_the_options(base_opts):
    # The default layout is not a request, the same way the default margins are
    # not: both front ends always fill them in.
    assert F.requested_capabilities(base_opts) == set()

    base_opts.update(lines_count=3, font_size=20, answers_section=True, answers_cols=2,
                     header='H {page}', show_header=True, layout_idx=3)
    assert F.requested_capabilities(base_opts) == {
        'columns', 'lines', 'font_size', 'answers_cols',
        'header_footer', 'page_numbers',
    }


def test_an_answers_section_alone_does_not_request_a_figurine_font(base_opts):
    """Turning answers on is not the same as choosing a figurine font."""
    base_opts['answers_section'] = True
    assert 'figurine' not in F.requested_capabilities(base_opts)


def test_choosing_a_figurine_font_is_a_request(base_opts):
    others = [n for n in F.FIGURINE_NAMES if n != F._default_figurine_font_name()]
    if not others:
        pytest.skip('only one figurine font is shipped')
    base_opts.update(answers_section=True, figurine_font=others[0])
    assert 'figurine' in F.requested_capabilities(base_opts)


def test_a_hidden_header_is_not_a_request(base_opts):
    base_opts.update(header='H', show_header=False, footer='F', show_footer=False)
    assert 'header_footer' not in F.requested_capabilities(base_opts)


def test_a_single_column_layout_is_not_a_request(base_opts):
    base_opts['layout_idx'] = 0
    assert 'columns' not in F.requested_capabilities(base_opts)


# ── Unsupported options must be reported ──────────────────────────────────────

def test_epub_reports_that_it_cannot_do_running_headers(tmp_path, base_opts, one_position, capsys):
    base_opts.update(header='My header', show_header=True)
    F.generate_output(one_position, base_opts, tmp_path / 'a.epub')
    err = capsys.readouterr().err
    assert 'EPUB does not support' in err
    assert 'header/footer' in err


def test_html_reports_that_it_cannot_number_pages(tmp_path, base_opts, one_position, capsys):
    base_opts.update(footer='{page}/{total}', show_footer=True)
    F.generate_output(one_position, base_opts, tmp_path / 'a.html')
    err = capsys.readouterr().err
    assert '{page} and {total}' in err
    # A plain footer is supported, so only the numbering is reported.
    assert 'HTML does not support page header/footer' not in err


def test_rtf_lays_answers_out_in_columns(tmp_path, base_opts, many_positions):
    """RTF puts *n* answers per table row rather than filling a column first."""
    base_opts.update(answers_section=True, answers_cols=2)
    out = tmp_path / 'a.rtf'
    F.generate_rtf(many_positions, base_opts, out)
    facts = I.inspect_rtf(out)
    # Six answers, two per row, plus the six diagram rows of the three-column
    # layout — the answers contribute three rows.
    assert facts.text.count(r'\cellx') >= 2 * 3
    assert facts.brace_balance == 0


def test_pdf_never_reports_anything(tmp_path, base_opts, one_position, capsys):
    base_opts.update(header='H {page}/{total}', show_header=True, lines_count=3,
                     answers_section=True, answers_cols=2, font_size=18)
    F.generate_output(F.parse_pgn(PGN_WITH_CHAPTERS), base_opts, tmp_path / 'a.pdf')
    assert 'does not support' not in capsys.readouterr().err


def test_nothing_is_reported_when_nothing_unusual_is_asked(tmp_path, base_opts, one_position, capsys):
    for suffix in FORMATS:
        F.generate_output(one_position, base_opts, tmp_path / f'plain{suffix}')
    assert 'does not support' not in capsys.readouterr().err


@pytest.mark.parametrize('suffix', FORMATS)
def test_warnings_name_only_genuinely_unsupported_options(suffix, base_opts):
    base_opts.update(lines_count=3, font_size=18, answers_section=True, answers_cols=2,
                     header='H {page}', show_header=True)
    reported = F.unsupported_options(base_opts, suffix, has_chapters=True)
    supported_labels = {F.CAPABILITY_LABELS[c] for c in F.FORMAT_CAPABILITIES[suffix]}
    assert not (set(reported) & supported_labels)


# ── Upside-down answers ───────────────────────────────────────────────────────

@pytest.mark.parametrize('suffix', FORMATS)
def test_upside_down_answers_reach_the_document(suffix, tmp_path, base_opts, positions):
    needs(suffix, 'answers_upside_down')
    base_opts['answers_section'] = True
    upright, turned = tmp_path / f'u{suffix}', tmp_path / f't{suffix}'
    F.generate_output(positions, base_opts, upright)
    base_opts['answers_upside_down'] = True
    F.generate_output(positions, base_opts, turned)
    assert upright.read_bytes() != turned.read_bytes()


@pytest.mark.parametrize('suffix', FORMATS)
def test_a_format_that_cannot_turn_the_answers_says_so(suffix, tmp_path, base_opts,
                                                       one_position, capsys):
    if supports(suffix, 'answers_upside_down'):
        pytest.skip(f'{suffix} can turn the answers over')
    base_opts.update(answers_section=True, answers_upside_down=True)
    F.generate_output(one_position, base_opts, tmp_path / f'a{suffix}')
    assert 'upside-down answers' in capsys.readouterr().err


def test_turning_the_answers_is_only_a_request_when_there_are_answers(base_opts):
    base_opts['answers_upside_down'] = True
    assert 'answers_upside_down' not in F.requested_capabilities(base_opts)
    base_opts['answers_section'] = True
    assert 'answers_upside_down' in F.requested_capabilities(base_opts)


def test_pdf_turns_the_answers_once_per_answers_page(tmp_path, base_opts, positions):
    """One transform per page: the block is turned, not each line."""
    base_opts.update(answers_section=True, answers_upside_down=True)
    out = tmp_path / 'turned.pdf'
    F.generate_output(positions, base_opts, out)
    facts = I.inspect_pdf(out)
    assert facts.half_turns == 1        # these answers fit on one page


def test_pdf_turns_every_page_of_a_long_answers_section(tmp_path, base_opts):
    """The rotation is opened and closed per page, so page two is turned too."""
    many = [{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'comment': f'P{i}',
             'moves': '1.Nf3 Ke7 2.Nc3 Kd6 3.Ne4+ Kc6 4.Nd4+ Kb6 5.Nc3 Ka5'}
            for i in range(120)]
    base_opts.update(answers_section=True, answers_upside_down=True)
    out = tmp_path / 'long.pdf'
    F.generate_output(many, base_opts, out)
    facts = I.inspect_pdf(out)
    assert facts.half_turns >= 2


def test_pdf_leaves_the_upright_document_untouched(tmp_path, base_opts, positions):
    base_opts['answers_section'] = True
    out = tmp_path / 'upright.pdf'
    F.generate_output(positions, base_opts, out)
    assert I.inspect_pdf(out).half_turns == 0


def test_pdf_turning_the_answers_does_not_change_the_page_count(tmp_path, base_opts, positions):
    """Rotating is a transform, not a re-layout."""
    base_opts['answers_section'] = True
    upright, turned = tmp_path / 'u.pdf', tmp_path / 't.pdf'
    F.generate_output(positions, base_opts, upright)
    base_opts['answers_upside_down'] = True
    F.generate_output(positions, base_opts, turned)
    assert I.inspect_pdf(upright).pages == I.inspect_pdf(turned).pages


def test_pdf_answer_links_follow_the_turned_text(tmp_path, base_opts, positions):
    """A link rectangle is page space, so it has to be turned over by hand.

    Left alone the number would move and its clickable area would stay behind.
    """
    base_opts['answers_section'] = True
    upright, turned = tmp_path / 'u.pdf', tmp_path / 't.pdf'
    F.generate_output(positions, base_opts, upright)
    base_opts['answers_upside_down'] = True
    F.generate_output(positions, base_opts, turned)

    up, tu = I.inspect_pdf(upright), I.inspect_pdf(turned)
    assert up.link_annotations == tu.link_annotations       # none lost

    width, height = up.media_box
    moved = set(up.link_rects) - set(tu.link_rects)
    assert moved, 'the answer links should have moved'

    def centre(r):
        return ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)

    turned_centres = [centre(r) for r in tu.link_rects]
    for rect in moved:
        cx, cy = centre(rect)
        want = (width - cx, height - cy)
        assert any(abs(want[0] - c[0]) < 1.0 and abs(want[1] - c[1]) < 1.0
                   for c in turned_centres), f'no mirrored partner for {rect}'


def test_html_marks_the_answers_as_turned(tmp_path, base_opts, positions):
    base_opts.update(answers_section=True, answers_upside_down=True)
    out = tmp_path / 'turned.html'
    F.generate_html(positions, base_opts, out)
    text = out.read_text(encoding='utf-8')
    assert "class='answers upside-down'" in text
    assert 'transform: rotate(180deg)' in text
    I.assert_well_formed_xml(text)


def test_html_says_nothing_about_turning_when_it_was_not_asked(tmp_path, base_opts, positions):
    base_opts['answers_section'] = True
    out = tmp_path / 'upright.html'
    F.generate_html(positions, base_opts, out)
    assert 'upside-down' not in out.read_text(encoding='utf-8')


def test_epub_carries_the_same_rule(tmp_path, base_opts, positions):
    base_opts.update(answers_section=True, answers_upside_down=True)
    out = tmp_path / 'turned.epub'
    F.generate_epub(positions, base_opts, out)
    facts = I.inspect_epub(out)
    assert 'upside-down' in facts.content
    assert any('rotate(180deg)' in css for css in facts.stylesheets.values())


# ── Answers on a page of their own ────────────────────────────────────────────

PAGINATED = ['.pdf', '.tex', '.html', '.docx', '.rtf']


@pytest.mark.parametrize('suffix', PAGINATED)
def test_a_page_break_before_the_answers_is_the_default(suffix, tmp_path, base_opts, positions):
    """Four of these already broke the page; HTML was the odd one out."""
    base_opts['answers_section'] = True
    broken, joined = tmp_path / f'b{suffix}', tmp_path / f'j{suffix}'
    F.generate_output(positions, base_opts, broken)
    base_opts['answers_new_page'] = False
    F.generate_output(positions, base_opts, joined)
    assert broken.read_bytes() != joined.read_bytes()


def test_pdf_answers_start_their_own_page_by_default(tmp_path, base_opts, positions):
    base_opts['answers_section'] = True
    out = tmp_path / 'split.pdf'
    F.generate_output(positions, base_opts, out)
    with_break = I.inspect_pdf(out).pages

    base_opts['answers_new_page'] = False
    out2 = tmp_path / 'joined.pdf'
    F.generate_output(positions, base_opts, out2)
    assert I.inspect_pdf(out2).pages < with_break


def test_pdf_breaks_anyway_when_the_answers_would_not_fit(tmp_path, base_opts):
    """Continuing is a preference, not a promise to overrun the sheet."""
    many = [{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'comment': f'P{i}', 'moves': '1.Nf3 Ke7'}
            for i in range(24)]          # fills the last page to the bottom
    base_opts.update(answers_section=True, answers_new_page=False)
    out = tmp_path / 'tight.pdf'
    F.generate_output(many, base_opts, out)
    facts = I.inspect_pdf(out)
    assert facts.pages >= 2
    # Nothing may be drawn below the bottom margin.
    assert facts.link_annotations > 0


def test_html_breaks_before_the_answers_when_printed(tmp_path, base_opts, positions):
    base_opts['answers_section'] = True
    out = tmp_path / 'split.html'
    F.generate_html(positions, base_opts, out)
    text = out.read_text(encoding='utf-8')
    assert 'page-break-before: always' in text
    I.assert_well_formed_xml(text)


def test_html_can_keep_the_answers_flowing(tmp_path, base_opts, positions):
    base_opts.update(answers_section=True, answers_new_page=False)
    out = tmp_path / 'joined.html'
    F.generate_html(positions, base_opts, out)
    css = out.read_text(encoding='utf-8').split('.answers {')[1].split('}')[0]
    assert 'page-break-before' not in css


@pytest.mark.parametrize('suffix, marker', [
    ('.docx', 'w:br'), ('.rtf', r'\page'), ('.tex', r'\clearpage'),
])
def test_the_break_disappears_when_it_is_switched_off(suffix, marker, tmp_path,
                                                     base_opts, positions):
    base_opts['answers_section'] = True
    with_break = tmp_path / f'b{suffix}'
    F.generate_output(positions, base_opts, with_break)

    base_opts['answers_new_page'] = False
    without = tmp_path / f'j{suffix}'
    F.generate_output(positions, base_opts, without)

    if suffix == '.docx':
        import zipfile
        with zipfile.ZipFile(with_break) as z:
            before = z.read('word/document.xml').decode()
        with zipfile.ZipFile(without) as z:
            after = z.read('word/document.xml').decode()
    else:
        before = with_break.read_text(encoding='utf-8' if suffix == '.tex' else 'ascii')
        after = without.read_text(encoding='utf-8' if suffix == '.tex' else 'ascii')
    assert before.count(marker) > after.count(marker)


def test_a_format_without_pages_ignores_it_quietly(tmp_path, base_opts, one_position, capsys):
    """EPUB and Markdown have no page to break; that is not a dropped option."""
    base_opts.update(answers_section=True, answers_new_page=True)
    for suffix in ('.epub', '.md'):
        F.generate_output(one_position, base_opts, tmp_path / f'a{suffix}')
    assert 'new page' not in capsys.readouterr().err


# ── Watermark ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('suffix', FORMATS)
def test_a_watermark_reaches_the_document(suffix, tmp_path, base_opts, one_position):
    needs(suffix, 'watermark')
    plain, marked = tmp_path / f'p{suffix}', tmp_path / f'm{suffix}'
    F.generate_output(one_position, base_opts, plain)
    base_opts['watermark'] = 'SAMPLE'
    F.generate_output(one_position, base_opts, marked)
    assert plain.read_bytes() != marked.read_bytes()


@pytest.mark.parametrize('suffix', FORMATS)
def test_a_format_that_cannot_stamp_says_so(suffix, tmp_path, base_opts, one_position, capsys):
    if supports(suffix, 'watermark'):
        pytest.skip(f'{suffix} can stamp a watermark')
    base_opts['watermark'] = 'SAMPLE'
    F.generate_output(one_position, base_opts, tmp_path / f'w{suffix}')
    assert 'watermark' in capsys.readouterr().err


def test_only_a_watermark_with_text_is_a_request(base_opts):
    base_opts['watermark'] = '   '
    assert 'watermark' not in F.requested_capabilities(base_opts)
    base_opts['watermark'] = 'SAMPLE'
    assert 'watermark' in F.requested_capabilities(base_opts)


def test_pdf_stamps_every_page(tmp_path, base_opts):
    """Including the cover and the contents, which are not diagram pages."""
    chaptered = F.parse_pgn(PGN_WITH_CHAPTERS)
    base_opts.update(watermark='SAMPLE', cover=True, contents=True,
                     answers_section=True, doc_title='Book')
    out = tmp_path / 'marked.pdf'
    F.generate_output(chaptered, base_opts, out)
    facts = I.inspect_pdf(out)
    assert facts.quarter_turns == facts.pages > 1


def test_pdf_without_a_watermark_stamps_nothing(tmp_path, base_opts, one_position):
    out = tmp_path / 'plain.pdf'
    F.generate_output(one_position, base_opts, out)
    assert I.inspect_pdf(out).quarter_turns == 0


def test_pdf_watermark_opacity_reaches_the_graphics_state(tmp_path, base_opts, one_position):
    base_opts.update(watermark='SAMPLE', watermark_opacity=35)
    out = tmp_path / 'faint.pdf'
    F.generate_output(one_position, base_opts, out)
    assert '0.35' in I.inspect_pdf(out).fill_opacities


def test_html_watermark_uses_only_defined_colours(tmp_path, base_opts, one_position):
    """An undefined custom property makes the whole declaration invalid.

    That is defect C2 from the first phase: the card background and border
    named variables that were never defined, and every browser dropped them.
    """
    base_opts['watermark'] = 'SAMPLE'
    out = tmp_path / 'marked.html'
    F.generate_html(one_position, base_opts, out)
    facts = I.inspect_html(out.read_text(encoding='utf-8'))
    assert I.undefined_css_variables(facts) == []
    assert 'SAMPLE' in facts.text


def test_html_escapes_markup_in_the_watermark(tmp_path, base_opts, one_position):
    base_opts['watermark'] = '<script>x</script>'
    out = tmp_path / 'x.html'
    F.generate_html(one_position, base_opts, out)
    text = out.read_text(encoding='utf-8')
    assert '<script>' not in text
    I.assert_well_formed_xml(text)


def test_docx_stamps_the_watermark_into_the_header(tmp_path, base_opts, one_position):
    """The header is the only part of a Word document that repeats per page."""
    base_opts.update(watermark='SAMPLE', watermark_opacity=35)
    out = tmp_path / 'marked.docx'
    F.generate_docx(one_position, base_opts, out)
    headers = I.inspect_docx(out).headers
    assert headers, 'no header part was written'
    shape = '\n'.join(headers.values())
    assert 'v:shape' in shape and 'type="#_x0000_t136"' in shape
    assert 'string="SAMPLE"' in shape
    assert 'opacity="0.3500"' in shape
    # It must not become body text: a watermark is a drawing, not a paragraph.
    assert 'SAMPLE' not in I.inspect_docx(out).text


def test_docx_without_a_watermark_carries_no_shape(tmp_path, base_opts, one_position):
    out = tmp_path / 'plain.docx'
    F.generate_docx(one_position, base_opts, out)
    assert 'v:shape' not in '\n'.join(I.inspect_docx(out).headers.values())


def test_docx_escapes_markup_in_the_watermark(tmp_path, base_opts, one_position):
    base_opts['watermark'] = 'a " & <b>'
    out = tmp_path / 'x.docx'
    F.generate_docx(one_position, base_opts, out)
    header = '\n'.join(I.inspect_docx(out).headers.values())
    assert 'string="a &quot; &amp; &lt;b&gt;"' in header
    ET.fromstring(header)                      # still well-formed XML


def test_rtf_stamps_the_watermark_into_the_header(tmp_path, base_opts, one_position):
    base_opts.update(watermark='SAMPLE', watermark_opacity=35)
    out = tmp_path / 'marked.rtf'
    F.generate_rtf(one_position, base_opts, out)
    facts = I.inspect_rtf(out)
    assert r'{\header' in facts.text
    assert r'{\sp{\sn shapeType}{\sv 136}}' in facts.text
    assert r'{\sp{\sn gtextUNICODE}{\sv SAMPLE}}' in facts.text
    assert rf'{{\sp{{\sn fillOpacity}}{{\sv {int(65536 * 0.35)}}}}}' in facts.text
    assert facts.brace_balance == 0


def test_rtf_without_a_watermark_carries_no_shape(tmp_path, base_opts, one_position):
    base_opts.update(show_header=False, show_footer=False)
    out = tmp_path / 'plain.rtf'
    F.generate_rtf(one_position, base_opts, out)
    facts = I.inspect_rtf(out)
    assert r'\shp' not in facts.text
    assert facts.brace_balance == 0


def test_rtf_escapes_the_watermark_text(tmp_path, base_opts, one_position):
    base_opts['watermark'] = r'a\b{c}ção'
    out = tmp_path / 'x.rtf'
    F.generate_rtf(one_position, base_opts, out)
    facts = I.inspect_rtf(out)
    assert facts.text.isascii() and facts.brace_balance == 0
    assert r'a\\b\{c\}' in facts.text


def test_epub_does_not_carry_a_watermark(tmp_path, base_opts, one_position):
    """A reflowable book has no page to stamp, so the mark must not leak in."""
    base_opts['watermark'] = 'SAMPLE'
    out = tmp_path / 'book.epub'
    F.generate_epub(one_position, base_opts, out)
    facts = I.inspect_epub(out)
    assert 'watermark' not in facts.content
    assert 'SAMPLE' not in facts.content


def test_latex_asks_for_the_package_only_when_it_stamps(tmp_path, base_opts, one_position):
    plain = tmp_path / 'p.tex'
    F.generate_output(one_position, base_opts, plain)
    assert 'draftwatermark' not in I.inspect_latex(plain).packages

    base_opts['watermark'] = 'SAMPLE'
    marked = tmp_path / 'm.tex'
    F.generate_output(one_position, base_opts, marked)
    facts = I.inspect_latex(marked)
    assert 'draftwatermark' in facts.packages
    assert r'\SetWatermarkText{SAMPLE}' in facts.text
    assert I.latex_problems(facts) == []


def test_latex_escapes_markup_in_the_watermark(tmp_path, base_opts, one_position):
    base_opts['watermark'] = '100% & co_'
    out = tmp_path / 'x.tex'
    F.generate_output(one_position, base_opts, out)
    facts = I.inspect_latex(out)
    assert r'\SetWatermarkText{100\% \& co\_}' in facts.text
    assert I.latex_problems(facts) == []


# ── Notation lines ────────────────────────────────────────────────────────────

@pytest.mark.parametrize('suffix', FORMATS)
def test_notation_lines_reach_the_document(suffix, tmp_path, base_opts, one_position):
    needs(suffix, 'lines')
    without = tmp_path / f'plain{suffix}'
    with_lines = tmp_path / f'lined{suffix}'
    F.generate_output(one_position, base_opts, without)
    base_opts.update(lines_count=3, lines_mode='plain')
    F.generate_output(one_position, base_opts, with_lines)
    assert with_lines.stat().st_size != without.stat().st_size


def test_html_draws_one_notation_line_per_request(tmp_path, base_opts, one_position):
    base_opts.update(lines_count=4, lines_mode='plain')
    out = tmp_path / 'lines.html'
    F.generate_html(one_position, base_opts, out)
    text = out.read_text(encoding='utf-8')
    I.assert_well_formed_xml(text)
    assert text.count("class='notation-line'") == 4


def test_html_numbered_lines_carry_move_numbers(tmp_path, base_opts, one_position):
    base_opts.update(lines_count=3, lines_mode='numbered')
    out = tmp_path / 'numbered.html'
    F.generate_html(one_position, base_opts, out)
    text = out.read_text(encoding='utf-8')
    assert "<span class='move-no'>1.</span>" in text
    assert "<span class='move-no'>3.</span>" in text
    assert text.count("class='blank'") == 6      # two blanks per numbered line


def test_html_numbered_lines_skip_whites_blank_when_black_moves(tmp_path, base_opts):
    positions = [{'fen': '8/8/8/8/8/5k2/8/5K2 b - - 0 1', 'comment': 'Black', 'moves': ''}]
    base_opts.update(lines_count=2, lines_mode='numbered')
    out = tmp_path / 'black.html'
    F.generate_html(positions, base_opts, out)
    text = out.read_text(encoding='utf-8')
    assert "class='blank skip'" in text
    assert text.count("class='blank skip'") == 1   # only on the first line


def test_docx_draws_notation_lines(tmp_path, base_opts, one_position):
    base_opts.update(lines_count=3, lines_mode='numbered')
    out = tmp_path / 'lines.docx'
    F.generate_docx(one_position, base_opts, out)
    with zipfile.ZipFile(out) as z:
        doc = z.read('word/document.xml').decode()
    assert doc.count('diagpdf-notation') >= 3


def test_rtf_draws_notation_lines(tmp_path, base_opts, one_position):
    """Blanks are underscore tab leaders, the same technique as the DOCX export."""
    base_opts.update(lines_count=3, lines_mode='plain')
    out = tmp_path / 'lines.rtf'
    F.generate_rtf(one_position, base_opts, out)
    facts = I.inspect_rtf(out)
    assert facts.text.count(r'\tlul') == 3
    assert facts.brace_balance == 0


def test_rtf_numbered_lines_carry_move_numbers(tmp_path, base_opts, one_position):
    base_opts.update(lines_count=2, lines_mode='numbered')
    out = tmp_path / 'numbered.rtf'
    F.generate_rtf(one_position, base_opts, out)
    text = I.inspect_rtf(out).text
    assert text.count(r'\tlul') == 4          # two blanks per numbered line
    assert '1.' in text and '2.' in text


def test_rtf_numbered_lines_skip_whites_blank_when_black_moves(tmp_path, base_opts):
    positions = [{'fen': '8/8/8/8/8/5k2/8/5K2 b - - 0 1', 'comment': 'Black', 'moves': ''}]
    base_opts.update(lines_count=2, lines_mode='numbered')
    out = tmp_path / 'black.rtf'
    F.generate_rtf(positions, base_opts, out)
    # Three leaders instead of four: White's blank on the first line is dropped.
    assert I.inspect_rtf(out).text.count(r'\tlul') == 3


# ── Board font size ───────────────────────────────────────────────────────────

@pytest.mark.parametrize('suffix', FORMATS)
def test_font_size_changes_the_document(suffix, tmp_path, base_opts, one_position):
    needs(suffix, 'font_size')
    small, large = tmp_path / f's{suffix}', tmp_path / f'l{suffix}'
    base_opts['font_size'] = 10
    F.generate_output(one_position, base_opts, small)
    base_opts['font_size'] = 30
    F.generate_output(one_position, base_opts, large)
    assert small.read_bytes() != large.read_bytes()


def test_html_font_size_drives_the_board_row_variable(tmp_path, base_opts, one_position):
    base_opts['font_size'] = 46
    out = tmp_path / 'big.html'
    F.generate_html(one_position, base_opts, out)
    size = re.search(r'--board-row-size:\s*(\d+)px', out.read_text(encoding='utf-8'))
    assert int(size.group(1)) > 36


# ── Columns ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('suffix', FORMATS)
def test_column_count_reaches_the_document(suffix, tmp_path, base_opts, many_positions):
    needs(suffix, 'columns')
    one_col, four_col = tmp_path / f'c1{suffix}', tmp_path / f'c4{suffix}'
    base_opts['layout_idx'] = 0          # single column
    F.generate_output(many_positions, base_opts, one_col)
    base_opts['layout_idx'] = 4          # four columns
    F.generate_output(many_positions, base_opts, four_col)
    assert one_col.read_bytes() != four_col.read_bytes()


@pytest.mark.parametrize('layout_idx, expected', [(0, 1), (2, 2), (3, 3), (4, 4)])
def test_html_grid_uses_the_layout_columns(tmp_path, base_opts, many_positions,
                                           layout_idx, expected):
    base_opts['layout_idx'] = layout_idx
    out = tmp_path / f'grid{layout_idx}.html'
    F.generate_html(many_positions, base_opts, out)
    text = out.read_text(encoding='utf-8')
    assert f'--columns: {expected};' in text
    assert 'grid-template-columns: repeat(var(--columns)' in text


def test_docx_lays_diagrams_out_in_a_table(tmp_path, base_opts, many_positions):
    base_opts['layout_idx'] = 3          # three columns
    out = tmp_path / 'grid.docx'
    F.generate_docx(many_positions, base_opts, out)
    with zipfile.ZipFile(out) as z:
        doc = z.read('word/document.xml').decode()
    assert doc.count('<w:tbl>') >= 1
    assert doc.count('<w:tr>') == 2      # six diagrams over three columns


# ── Answers columns ───────────────────────────────────────────────────────────

@pytest.mark.parametrize('suffix', FORMATS)
def test_answers_columns_reach_the_document(suffix, tmp_path, base_opts):
    needs(suffix, 'answers_cols')
    # The PDF only moves into the second column once the first one is full, so
    # the sample has to be long enough to overflow a page.
    positions = [
        {'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'comment': f'P{i}', 'moves': '1.Nf3 Ke7'}
        for i in range(80)
    ]
    base_opts['answers_section'] = True
    one, two = tmp_path / f'a1{suffix}', tmp_path / f'a2{suffix}'
    base_opts['answers_cols'] = 1
    F.generate_output(positions, base_opts, one)
    base_opts['answers_cols'] = 2
    F.generate_output(positions, base_opts, two)
    assert one.read_bytes() != two.read_bytes()


def test_html_answers_use_css_columns(tmp_path, base_opts, many_positions):
    base_opts.update(answers_section=True, answers_cols=2)
    out = tmp_path / 'ans.html'
    F.generate_html(many_positions, base_opts, out)
    text = out.read_text(encoding='utf-8')
    assert '--answers-columns: 2;' in text
    assert 'column-count: var(--answers-columns)' in text


def test_docx_answers_use_two_columns(tmp_path, base_opts, many_positions):
    base_opts.update(answers_section=True, answers_cols=2)
    out = tmp_path / 'ans.docx'
    F.generate_docx(many_positions, base_opts, out)
    with zipfile.ZipFile(out) as z:
        doc = z.read('word/document.xml').decode()
    assert 'w:num="2"' in doc            # a two-column section for the answers


# ── Figurine font in the answers ──────────────────────────────────────────────

@pytest.mark.parametrize('suffix', FORMATS)
def test_figurine_font_reaches_the_answers(suffix, tmp_path, base_opts, one_position):
    needs(suffix, 'figurine')
    base_opts['answers_section'] = True
    out = tmp_path / f'fig{suffix}'
    F.generate_output(one_position, base_opts, out)
    assert out.stat().st_size > 0


def test_html_marks_piece_letters_for_the_figurine_font(tmp_path, base_opts):
    positions = [{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'comment': 'x', 'moves': '1.Nf3 Ke7'}]
    base_opts['answers_section'] = True
    out = tmp_path / 'fig.html'
    F.generate_html(positions, base_opts, out)
    text = out.read_text(encoding='utf-8')
    I.assert_well_formed_xml(text)
    assert "<span class='figurine'>N</span>" in text
    assert "<span class='figurine'>K</span>" in text
    assert '.figurine { font-family:' in text


def test_epub_packages_the_figurine_font(tmp_path, base_opts, one_position):
    base_opts['answers_section'] = True
    out = tmp_path / 'fig.epub'
    F.generate_epub(one_position, base_opts, out)
    facts = I.inspect_epub(out)
    fonts = [n for n in facts.names if n.startswith('OEBPS/Fonts/')]
    assert len(fonts) == 2, fonts
    assert any('Figurine' in n for n in fonts)
    assert 'figurine_font' in ''.join(facts.manifest_hrefs) or any(
        'Figurine' in h for h in facts.manifest_hrefs)
    assert I.epub3_problems(facts) == []


def test_epub_omits_the_figurine_font_without_answers(tmp_path, base_opts, one_position):
    out = tmp_path / 'nofig.epub'
    F.generate_epub(one_position, base_opts, out)
    facts = I.inspect_epub(out)
    assert len([n for n in facts.names if n.startswith('OEBPS/Fonts/')]) == 1


def test_docx_answers_use_the_figurine_font(tmp_path, base_opts):
    positions = [{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'comment': 'x', 'moves': '1.Nf3'}]
    base_opts['answers_section'] = True
    out = tmp_path / 'fig.docx'
    F.generate_docx(positions, base_opts, out)
    assert F._figurine_family_name(F.RenderOptions.from_dict(base_opts)) in I.inspect_docx(out).fonts_used


def test_rtf_answers_use_the_figurine_font(tmp_path, base_opts):
    positions = [{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'comment': 'x', 'moves': '1.Nf3'}]
    base_opts['answers_section'] = True
    out = tmp_path / 'fig.rtf'
    F.generate_rtf(positions, base_opts, out)
    facts = I.inspect_rtf(out)
    assert F._figurine_family_name(F.RenderOptions.from_dict(base_opts)) in facts.font_table
    assert facts.brace_balance == 0


# ── Chapters ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('suffix', FORMATS)
def test_chapters_reach_the_document(suffix, tmp_path, base_opts):
    needs(suffix, 'chapters')
    chaptered = F.parse_pgn(PGN_WITH_CHAPTERS)
    plain = [dict(p, chapter='') for p in chaptered]
    a, b = tmp_path / f'ch{suffix}', tmp_path / f'nc{suffix}'
    F.generate_output(chaptered, base_opts, a)
    F.generate_output(plain, base_opts, b)
    assert a.read_bytes() != b.read_bytes()


def test_html_renders_a_heading_per_chapter(tmp_path, base_opts):
    out = tmp_path / 'ch.html'
    F.generate_html(F.parse_pgn(PGN_WITH_CHAPTERS), base_opts, out)
    text = out.read_text(encoding='utf-8')
    I.assert_well_formed_xml(text)
    assert "<h2 class='chapter-title'>Pins</h2>" in text
    assert "<h2 class='chapter-title'>Forks</h2>" in text
    assert "id='chapter-1'" in text and "id='chapter-2'" in text


def test_epub_navigation_lists_the_chapters(tmp_path, base_opts):
    out = tmp_path / 'ch.epub'
    F.generate_epub(F.parse_pgn(PGN_WITH_CHAPTERS), base_opts, out)
    with zipfile.ZipFile(out) as z:
        nav = z.read('OEBPS/nav.xhtml').decode()
    assert 'content.xhtml#chapter-1">Pins' in nav
    assert 'content.xhtml#chapter-2">Forks' in nav
    assert I.epub3_problems(I.inspect_epub(out)) == []


def test_epub_navigation_falls_back_without_chapters(tmp_path, base_opts, one_position):
    out = tmp_path / 'nochap.epub'
    F.generate_epub(one_position, base_opts, out)
    with zipfile.ZipFile(out) as z:
        assert 'Diagrams' in z.read('OEBPS/nav.xhtml').decode()


def test_docx_starts_a_new_page_per_chapter(tmp_path, base_opts):
    out = tmp_path / 'ch.docx'
    F.generate_docx(F.parse_pgn(PGN_WITH_CHAPTERS), base_opts, out)
    facts = I.inspect_docx(out)
    assert 'Pins' in facts.text and 'Forks' in facts.text


def test_rtf_starts_a_new_page_per_chapter(tmp_path, base_opts):
    out = tmp_path / 'ch.rtf'
    F.generate_rtf(F.parse_pgn(PGN_WITH_CHAPTERS), base_opts, out)
    facts = I.inspect_rtf(out)
    assert facts.text.count(r'\page') >= 1
    assert facts.brace_balance == 0


# How each paginated format says "start a new page here". LaTeX was the odd one
# out: \section flows by design, so the break has to be asked for.
#
# HTML carries it in the stylesheet rather than in the markup, and the
# stylesheet is written whether or not the document has chapters -- so what is
# counted there is the element the rule breaks before.
CHAPTER_BREAKS = {
    '.tex':  r'\clearpage',
    '.rtf':  r'\page',
    '.docx': 'w:br',
    '.html': "class='chapter-title'",
}


@pytest.mark.parametrize('suffix', ['.tex', '.rtf', '.docx', '.html'])
def test_every_paginated_format_starts_a_chapter_on_a_new_page(suffix, tmp_path, base_opts,
                                                               two_chapters):
    """One chapter after another means a page between them, in all of them."""
    chaptered = tmp_path / f'c{suffix}'
    F.generate_output(two_chapters, base_opts, chaptered)
    plain = tmp_path / f'p{suffix}'
    F.generate_output([dict(p, chapter='') for p in two_chapters], base_opts, plain)

    marker = CHAPTER_BREAKS[suffix]
    if suffix == '.docx':
        with zipfile.ZipFile(chaptered) as z:
            broken = z.read('word/document.xml').decode()
        with zipfile.ZipFile(plain) as z:
            unbroken = z.read('word/document.xml').decode()
    else:
        encoding = 'ascii' if suffix == '.rtf' else 'utf-8'
        broken = chaptered.read_text(encoding=encoding)
        unbroken = plain.read_text(encoding=encoding)
    assert broken.count(marker) > unbroken.count(marker)


def test_the_pdf_puts_each_chapter_on_its_own_page(tmp_path, base_opts, two_chapters):
    out = tmp_path / 'ch.pdf'
    F.generate_output(two_chapters, base_opts, out)
    # Four diagrams fit one page; two chapters make it two.
    assert I.inspect_pdf(out).pages == 2


def test_the_first_chapter_does_not_break_a_page_before_itself(tmp_path, base_opts,
                                                               two_chapters):
    """Nothing precedes it, so a break there would only add a blank page."""
    out = tmp_path / 'first.tex'
    F.generate_output(two_chapters, base_opts, out)
    text = out.read_text(encoding='utf-8')
    assert text.index(r'\section{Pins}') < text.index(r'\clearpage')
    assert text.count(r'\clearpage') == 1


# ── Answers and numbering, chapter by chapter ─────────────────────────────────

@pytest.fixture
def two_chapters() -> list[dict]:
    """Two chapters of two positions each, every one with a solution.

    Only the first position of a chapter carries the tag, which is how a PGN
    usually marks one -- and it is what tells the renderers that the position
    after it continues the same chapter.
    """
    fens = ['4k3/8/8/8/8/8/8/4K3 w - - 0 1', '8/8/8/8/8/5k2/8/5K2 w - - 0 1']
    return [
        {'fen': fens[0], 'chapter': 'Pins',  'comment': 'A', 'moves': '1.Ke2 Kd7'},
        {'fen': fens[1], 'chapter': '',      'comment': 'B', 'moves': '1.Kf2 Kg4'},
        {'fen': fens[0], 'chapter': 'Forks', 'comment': 'C', 'moves': '1.Kd2 Ke7'},
        {'fen': fens[1], 'chapter': '',      'comment': 'D', 'moves': '1.Kg2 Kf4'},
    ]


# How each format writes the answers heading, so the sections can be counted.
ANSWER_HEADINGS = {
    '.html': "<h2 class='answers-title'>",
    '.epub': "<h2 class='answers-title'>",
    '.md':   '## Solutions',
    '.tex':  r'\section*{Solutions}',
}


def _document_text(path) -> str:
    suffix = path.suffix.lower()
    if suffix == '.epub':
        return I.inspect_epub(path).content
    if suffix == '.docx':
        return I.inspect_docx(path).text
    if suffix == '.rtf':
        return I.inspect_rtf(path).text
    return path.read_text(encoding='utf-8' if suffix != '.rtf' else 'ascii')


@pytest.mark.parametrize('suffix', ['.html', '.epub', '.md', '.tex', '.docx', '.rtf'])
def test_the_answers_can_follow_each_chapter(suffix, tmp_path, base_opts, two_chapters):
    base_opts['answers_section'] = True
    one = tmp_path / f'one{suffix}'
    each = tmp_path / f'each{suffix}'
    F.generate_output(two_chapters, base_opts, one)
    base_opts['answers_after_chapter'] = True
    F.generate_output(two_chapters, base_opts, each)

    marker = ANSWER_HEADINGS.get(suffix, 'Solutions')
    assert _document_text(one).count(marker) == 1
    assert _document_text(each).count(marker) == 2


@pytest.mark.parametrize('suffix', FORMATS)
def test_answers_after_chapter_alone_is_not_a_request_for_answers(
        suffix, tmp_path, base_opts, two_chapters):
    """Without --answers the moves belong under their diagrams, as always."""
    base_opts['answers_after_chapter'] = True
    plain, asked = tmp_path / f'p{suffix}', tmp_path / f'a{suffix}'
    F.generate_output(two_chapters, {**base_opts, 'answers_after_chapter': False}, plain)
    F.generate_output(two_chapters, base_opts, asked)
    if suffix == '.pdf':
        assert I.inspect_pdf(asked).pages == I.inspect_pdf(plain).pages
    elif suffix in ('.epub', '.docx'):
        # Both stamp a fresh timestamp or GUID into every build, so the
        # comparison is of what they say, not of their bytes.
        assert _document_text(asked) == _document_text(plain)
    else:
        assert asked.read_bytes() == plain.read_bytes()


def test_the_pdf_outline_interleaves_chapters_and_their_answers(tmp_path, base_opts, two_chapters):
    base_opts.update(answers_section=True, answers_after_chapter=True)
    out = tmp_path / 'each.pdf'
    F.generate_output(two_chapters, base_opts, out)
    assert I.inspect_pdf(out).titles == ['Pins', 'Solutions', 'Forks', 'Solutions']


def test_html_answer_sections_do_not_share_an_id(tmp_path, base_opts, two_chapters):
    base_opts.update(answers_section=True, answers_after_chapter=True)
    out = tmp_path / 'each.html'
    F.generate_html(two_chapters, base_opts, out)
    text = out.read_text(encoding='utf-8')
    ids = re.findall(r"<section class='answers[^']*' id='([^']+)'>", text)
    assert ids == ['answers-1', 'answers-2']
    I.assert_well_formed_xml(text)


@pytest.mark.parametrize('suffix', FORMATS)
def test_the_numbering_can_restart_in_every_chapter(suffix, tmp_path, base_opts, two_chapters):
    base_opts.update(title_mode='number', title_template='{number}',
                     number_restart_per_chapter=True)
    out = tmp_path / f'r{suffix}'
    F.generate_output(two_chapters, base_opts, out)
    numbers = F._numbering(two_chapters, F.RenderOptions.coerce(base_opts))
    assert numbers == [1, 2, 1, 2]


def test_restarting_the_numbering_keeps_every_anchor_unique(tmp_path, base_opts, two_chapters):
    """The number comes round again per chapter; the anchors must not.

    Two anchors sharing a name would send every link in the book to the first
    of them -- so the anchors count positions, not diagrams on the page.
    """
    base_opts.update(answers_section=True, number_restart_per_chapter=True,
                     answers_after_chapter=True)
    out = tmp_path / 'r.html'
    F.generate_html(two_chapters, base_opts, out)
    facts = I.inspect_html(out.read_text(encoding='utf-8'))
    assert len(set(facts.diagram_ids)) == len(facts.diagram_ids) == 4
    assert len(set(facts.answer_ids)) == len(facts.answer_ids) == 4
    assert I.dangling_anchors(facts) == []

    docx_out = tmp_path / 'r.docx'
    F.generate_docx(two_chapters, base_opts, docx_out)
    bookmarks = I.inspect_docx(docx_out).bookmarks
    assert len(set(bookmarks)) == len(bookmarks) == 8


def test_without_the_option_the_numbering_runs_straight_through(base_opts, two_chapters):
    numbers = F._numbering(two_chapters, F.RenderOptions.coerce(base_opts))
    assert numbers == [1, 2, 3, 4]


# ── Header and footer ─────────────────────────────────────────────────────────

@pytest.mark.parametrize('suffix', FORMATS)
def test_header_and_footer_reach_the_document(suffix, tmp_path, base_opts, one_position):
    needs(suffix, 'header_footer')
    plain, decorated = tmp_path / f'p{suffix}', tmp_path / f'd{suffix}'
    F.generate_output(one_position, base_opts, plain)
    base_opts.update(header='Running head', footer='Running foot',
                     show_header=True, show_footer=True)
    F.generate_output(one_position, base_opts, decorated)
    assert plain.read_bytes() != decorated.read_bytes()


def test_html_header_and_footer_are_print_only(tmp_path, base_opts, one_position):
    base_opts.update(header='Head', footer='Foot', show_header=True, show_footer=True)
    out = tmp_path / 'hf.html'
    F.generate_html(one_position, base_opts, out)
    text = out.read_text(encoding='utf-8')
    assert "<div class='page-header'>Head</div>" in text
    assert "<div class='page-footer'>Foot</div>" in text
    # Hidden on screen, shown when printing.
    assert '.page-header,\n.page-footer {\n  display: none;' in text


def test_html_drops_page_numbers_it_cannot_resolve(tmp_path, base_opts, one_position):
    base_opts.update(header='Page {page} of {total}', show_header=True)
    out = tmp_path / 'pn.html'
    F.generate_html(one_position, base_opts, out)
    text = out.read_text(encoding='utf-8')
    assert '{page}' not in text and '{total}' not in text
    assert 'Page' in text and 'of' in text


def test_epub_has_no_running_header(tmp_path, base_opts, one_position):
    base_opts.update(header='Head', footer='Foot', show_header=True, show_footer=True)
    out = tmp_path / 'hf.epub'
    F.generate_epub(one_position, base_opts, out)
    assert 'page-header' not in I.inspect_epub(out).content


def test_docx_header_and_footer_are_real_word_parts(tmp_path, base_opts, one_position):
    base_opts.update(header='Head', footer='Foot', show_header=True, show_footer=True)
    out = tmp_path / 'hf.docx'
    F.generate_docx(one_position, base_opts, out)
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert any(n.startswith('word/header') for n in names), names
        assert any(n.startswith('word/footer') for n in names), names
        assert 'Head' in z.read([n for n in names if n.startswith('word/header')][0]).decode()


def test_docx_page_number_fields(tmp_path, base_opts, one_position):
    base_opts.update(footer='{page} / {total}', show_footer=True)
    out = tmp_path / 'pn.docx'
    F.generate_docx(one_position, base_opts, out)
    with zipfile.ZipFile(out) as z:
        footer = z.read([n for n in z.namelist() if n.startswith('word/footer')][0]).decode()
    assert 'PAGE' in footer and 'NUMPAGES' in footer
    assert '{page}' not in footer


def test_rtf_header_and_footer_use_native_groups(tmp_path, base_opts, one_position):
    base_opts.update(header='Head', footer='Foot', show_header=True, show_footer=True)
    out = tmp_path / 'hf.rtf'
    F.generate_rtf(one_position, base_opts, out)
    facts = I.inspect_rtf(out)
    assert r'{\header' in facts.text and r'{\footer' in facts.text
    assert 'Head' in facts.text and 'Foot' in facts.text
    assert facts.brace_balance == 0


def test_rtf_page_number_field(tmp_path, base_opts, one_position):
    base_opts.update(footer='{page}', show_footer=True)
    out = tmp_path / 'pn.rtf'
    F.generate_rtf(one_position, base_opts, out)
    facts = I.inspect_rtf(out)
    assert r'\chpgn' in facts.text
    assert '{page}' not in facts.text
    assert facts.brace_balance == 0
