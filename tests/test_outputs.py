"""Structural invariants of every generated format."""

from __future__ import annotations

import re

import inspectors as I
import pytest
from conftest import PGN_THREE_GAMES, PGN_WITH_CHAPTERS

import fen2rtf as F

# ── Shared across all formats ─────────────────────────────────────────────────

def test_every_format_produces_a_non_empty_file(tmp_path, base_opts, positions, out_format):
    out = tmp_path / f'doc{out_format}'
    F.generate_output(positions, base_opts, out)
    assert out.stat().st_size > 0


def test_every_format_survives_the_full_option_set(tmp_path, base_opts, positions, out_format):
    base_opts.update(
        answers_section=True, lichess_link=True, lines_count=3, lines_mode='numbered',
        coords=True, border_style='double', symbol='circle', answers_cols=2,
        header='H {page}/{total}', footer='F {chapter}', show_header=True, show_footer=True,
    )
    out = tmp_path / f'full{out_format}'
    F.generate_output(positions, base_opts, out)
    assert out.stat().st_size > 0


def test_every_format_handles_a_single_position(tmp_path, base_opts, one_position, out_format):
    out = tmp_path / f'one{out_format}'
    F.generate_output(one_position, base_opts, out)
    assert out.stat().st_size > 0


def test_every_format_handles_positions_without_solutions(tmp_path, base_opts, out_format):
    base_opts['answers_section'] = True
    positions = [{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'comment': 'No answer', 'moves': ''}]
    out = tmp_path / f'nosol{out_format}'
    F.generate_output(positions, base_opts, out)
    assert out.stat().st_size > 0


def test_every_format_handles_an_empty_position_list(tmp_path, base_opts, out_format):
    out = tmp_path / f'empty{out_format}'
    F.generate_output([], base_opts, out)
    assert out.exists()


def test_unknown_extensions_fall_back_to_pdf(tmp_path, base_opts, one_position):
    out = tmp_path / 'mystery.xyz'
    F.generate_output(one_position, base_opts, out)
    assert out.read_bytes().startswith(b'%PDF-')


def test_an_unknown_font_is_rejected_by_every_format(tmp_path, base_opts, one_position, out_format):
    base_opts['font'] = 'AlphaDG'
    with pytest.raises(F.UnknownFontError):
        F.generate_output(one_position, base_opts, tmp_path / f'bad{out_format}')


def test_progress_reaches_one_hundred(tmp_path, base_opts, positions, out_format):
    seen: list[int] = []
    F.generate_output(positions, base_opts, tmp_path / f'p{out_format}', progress=seen.append)
    assert seen, 'no progress reported'
    assert max(seen) == 100
    assert seen == sorted(seen)


def test_progress_reaches_one_hundred_despite_skipped_positions(
    tmp_path, base_opts, out_format
):
    """Positions without a FEN are skipped, so they must not be counted."""
    positions = [
        {'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'comment': 'a', 'moves': '1.Ke2'},
        {'fen': '', 'comment': 'skipped', 'moves': ''},
        {'fen': '8/8/8/8/8/5k2/8/5K2 w - - 0 1', 'comment': 'b', 'moves': ''},
    ]
    seen: list[int] = []
    F.generate_output(positions, base_opts, tmp_path / f'skip{out_format}', progress=seen.append)
    assert max(seen) == 100, f'{out_format} stalled at {max(seen)}%'


def test_a_blank_answers_heading_falls_back_to_the_default(tmp_path, base_opts, positions):
    """Every format must agree on the fallback, and honour the language."""
    base_opts.update(answers_section=True, answers_title='   ', lang='pt')
    html_out = tmp_path / 'blank.html'
    F.generate_html(positions, base_opts, html_out)
    assert 'Soluções' in html_out.read_text(encoding='utf-8')

    rtf_out = tmp_path / 'blank.rtf'
    F.generate_rtf(positions, base_opts, rtf_out)
    assert r'\u231' in rtf_out.read_text(encoding='ascii')   # the ç of Soluções


# ── PDF ───────────────────────────────────────────────────────────────────────

def test_pdf_is_a4_portrait(tmp_path, base_opts, positions):
    out = tmp_path / 'a.pdf'
    F.generate_pdf(positions, base_opts, out)
    width, height = I.inspect_pdf(out).media_box
    assert (round(width), round(height)) == (595, 842)


def test_pdf_page_count_follows_the_layout(tmp_path, base_opts):
    """Layout 2 fits 6 diagrams per page, so 7 positions need two pages."""
    positions = [{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'comment': f'#{i}', 'moves': ''}
                 for i in range(7)]
    base_opts['layout_idx'] = 2
    out = tmp_path / 'pages.pdf'
    F.generate_pdf(positions, base_opts, out)
    assert I.inspect_pdf(out).pages == 2


def test_pdf_always_has_at_least_one_page(tmp_path, base_opts):
    out = tmp_path / 'blank.pdf'
    F.generate_pdf([], base_opts, out)
    assert I.inspect_pdf(out).pages == 1


def test_pdf_answers_section_adds_a_page(tmp_path, base_opts, positions):
    plain = tmp_path / 'plain.pdf'
    with_answers = tmp_path / 'answers.pdf'
    F.generate_pdf(positions, base_opts, plain)
    base_opts['answers_section'] = True
    F.generate_pdf(positions, base_opts, with_answers)
    assert I.inspect_pdf(with_answers).pages == I.inspect_pdf(plain).pages + 1


def test_pdf_cross_links_are_created_in_both_directions(tmp_path, base_opts, positions):
    base_opts['answers_section'] = True
    out = tmp_path / 'links.pdf'
    F.generate_pdf(positions, base_opts, out)
    # One title -> answer and one answer -> title per position with a solution.
    assert I.inspect_pdf(out).link_annotations == 2 * len(positions)


def test_pdf_lichess_links_are_external(tmp_path, base_opts, positions):
    """Without an answers section a position carries two Lichess links: the
    title and the labelled line under the board."""
    base_opts['lichess_link'] = True
    out = tmp_path / 'lichess.pdf'
    F.generate_pdf(positions, base_opts, out)
    assert I.inspect_pdf(out).external_links == 2 * len(positions)


def test_pdf_titles_link_to_answers_rather_than_lichess(tmp_path, base_opts, positions):
    """With answers on, the title points at the solution and only the labelled
    line stays external."""
    base_opts.update(lichess_link=True, answers_section=True)
    out = tmp_path / 'both.pdf'
    F.generate_pdf(positions, base_opts, out)
    facts = I.inspect_pdf(out)
    assert facts.external_links == len(positions)
    assert facts.link_annotations == 3 * len(positions)


def test_pdf_without_links_has_no_annotations(tmp_path, base_opts, positions):
    out = tmp_path / 'nolinks.pdf'
    F.generate_pdf(positions, base_opts, out)
    facts = I.inspect_pdf(out)
    assert facts.link_annotations == 0 and facts.external_links == 0


def test_pdf_chapter_change_forces_a_page_break(tmp_path, base_opts):
    positions = F.parse_pgn(PGN_WITH_CHAPTERS)
    out = tmp_path / 'chapters.pdf'
    F.generate_pdf(positions, base_opts, out)
    assert I.inspect_pdf(out).pages == 2


def test_pdf_nothing_is_drawn_past_the_page_edge(tmp_path, base_opts):
    """Long solutions used to be painted below the paper and lost."""
    from fpdf import FPDF
    long_moves = ' '.join(f'{i}. Nf3 Nc6 Bb5 a6' for i in range(1, 150))
    lowest: dict[int, float] = {}
    original = FPDF.cell

    def spy(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        lowest[self.page] = max(lowest.get(self.page, 0.0), self.get_y() + (kwargs.get('h') or 0))
        return result

    FPDF.cell = spy
    try:
        base_opts['answers_section'] = True
        F.generate_pdf(
            [{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'comment': 'Long', 'moves': long_moves}],
            base_opts, tmp_path / 'long.pdf',
        )
    finally:
        FPDF.cell = original
    assert not {p: y for p, y in lowest.items() if y > F.PAGE_H}


# ── HTML ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def html_facts(tmp_path, base_opts, positions):
    base_opts.update(answers_section=True, lichess_link=True)
    out = tmp_path / 'doc.html'
    F.generate_html(positions, base_opts, out)
    text = out.read_text(encoding='utf-8')
    I.assert_well_formed_xml(text)
    return I.inspect_html(text)


def test_html_is_well_formed_xml(html_facts):
    I.assert_well_formed_xml(html_facts.text)


def test_html_has_one_block_per_position(html_facts, positions):
    assert len(html_facts.diagram_ids) == len(positions)
    assert len(html_facts.answer_ids) == len(positions)


def test_html_board_rows_match_the_diagrams(html_facts, positions):
    assert html_facts.board_rows == 10 * len(positions)


def test_html_anchors_all_resolve(html_facts):
    assert I.dangling_anchors(html_facts) == []


def test_html_links_both_ways(html_facts):
    assert 'answer-1' in html_facts.anchor_targets
    assert 'diagram-1' in html_facts.anchor_targets


def test_html_defines_every_css_variable_it_uses(html_facts):
    assert I.undefined_css_variables(html_facts) == []
    assert {'--card-bg', '--card-border'} <= html_facts.css_variables_used


def test_html_embeds_the_board_font(html_facts):
    # Two faces: the board font and the figurine font used by the answers.
    assert html_facts.embedded_font_mimes == ['font/ttf', 'font/ttf']
    assert '../Fonts/' not in html_facts.text


def test_html_embeds_only_the_board_font_without_answers(tmp_path, base_opts, one_position):
    out = tmp_path / 'noans.html'
    F.generate_html(one_position, base_opts, out)
    assert I.inspect_html(out.read_text(encoding='utf-8')).embedded_font_mimes == ['font/ttf']


def test_html_font_mode_link_uses_a_relative_url(tmp_path, base_opts, one_position):
    base_opts['html_font_mode'] = 'link'
    out = tmp_path / 'linked.html'
    F.generate_html(one_position, base_opts, out)
    text = out.read_text(encoding='utf-8')
    assert '../Fonts/' in text and 'base64' not in text


def test_html_font_mode_none_omits_the_face_rule(tmp_path, base_opts, one_position):
    base_opts['html_font_mode'] = 'none'
    out = tmp_path / 'nofont.html'
    F.generate_html(one_position, base_opts, out)
    assert '@font-face' not in out.read_text(encoding='utf-8')


def test_html_lichess_links_point_at_lichess(html_facts, positions):
    lichess = [u for u in html_facts.external_urls if 'lichess.org' in u]
    assert len(lichess) == len(positions)


def test_html_title_comes_from_the_document_title(tmp_path, base_opts, one_position):
    base_opts['doc_title'] = 'My Puzzles'
    out = tmp_path / 'titled.html'
    F.generate_html(one_position, base_opts, out)
    assert I.inspect_html(out.read_text(encoding='utf-8')).title == 'My Puzzles'


def test_html_escapes_markup_in_titles(tmp_path, base_opts):
    positions = [{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1',
                  'comment': '<script>alert(1)</script>', 'moves': ''}]
    out = tmp_path / 'escaped.html'
    F.generate_html(positions, base_opts, out)
    text = out.read_text(encoding='utf-8')
    I.assert_well_formed_xml(text)
    assert '<script>' not in text
    assert '&lt;script&gt;' in text


def test_html_without_answers_shows_the_moves_inline(tmp_path, base_opts, positions):
    out = tmp_path / 'inline.html'
    F.generate_html(positions, base_opts, out)
    facts = I.inspect_html(out.read_text(encoding='utf-8'))
    assert facts.answer_ids == []
    assert "class='moves'" in facts.text


# ── EPUB ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def epub_facts(tmp_path, base_opts, positions):
    base_opts.update(answers_section=True, doc_title='Livro', doc_author='Autor',
                     doc_language='pt')
    out = tmp_path / 'doc.epub'
    F.generate_epub(positions, base_opts, out)
    return I.inspect_epub(out)


def test_epub_conforms_to_epub3(epub_facts):
    assert I.epub3_problems(epub_facts) == []


def test_epub_metadata_is_carried_through(epub_facts):
    assert epub_facts.title == 'Livro'
    assert epub_facts.creator == 'Autor'
    assert epub_facts.language == 'pt'


def test_epub_identifier_is_a_uuid(epub_facts):
    assert epub_facts.identifier.startswith('urn:uuid:')
    assert len(epub_facts.identifier) == len('urn:uuid:') + 36


def test_epub_identifiers_differ_between_builds(tmp_path, base_opts, one_position):
    ids = []
    for i in range(3):
        out = tmp_path / f'u{i}.epub'
        F.generate_epub(one_position, base_opts, out)
        ids.append(I.inspect_epub(out).identifier)
    assert len(set(ids)) == 3


def test_epub_packages_the_font_and_stylesheet(epub_facts):
    assert any(n.startswith('OEBPS/Fonts/') for n in epub_facts.names)
    assert 'diagram_confg.css' in epub_facts.stylesheets


def test_epub_stylesheet_font_url_resolves_inside_the_package(epub_facts):
    """The CSS lives in OEBPS/Styles/, so ../Fonts/ must land on OEBPS/Fonts/."""
    import re
    css = epub_facts.stylesheets['diagram_confg.css']
    href = re.search(r'src: url\("([^"]+)"\)', css).group(1)
    assert href.startswith('../Fonts/')
    assert f'OEBPS/{href.removeprefix("../")}' in epub_facts.names


def test_epub_content_is_the_same_document_as_the_html_export(epub_facts, positions):
    facts = I.inspect_html(epub_facts.content)
    assert len(facts.diagram_ids) == len(positions)
    assert I.dangling_anchors(facts) == []


def test_epub_spine_references_a_manifest_item(epub_facts):
    assert epub_facts.spine_idrefs == ['content']


def test_epub_extra_stylesheet_is_bundled(tmp_path, base_opts, one_position):
    extra = tmp_path / 'custom.css'
    extra.write_text('.diagram { border-width: 3px; }', encoding='utf-8')
    base_opts['epub_css_path'] = str(extra)
    out = tmp_path / 'extra.epub'
    F.generate_epub(one_position, base_opts, out)
    facts = I.inspect_epub(out)
    assert 'custom.css' in facts.stylesheets
    assert 'border-width: 3px' in facts.stylesheets['custom.css']
    assert I.epub3_problems(facts) == []


def test_epub_extra_stylesheet_cannot_clash_with_the_builtin_one(tmp_path, base_opts, one_position):
    extra = tmp_path / 'diagram_confg.css'
    extra.write_text('.diagram { color: red; }', encoding='utf-8')
    base_opts['epub_css_path'] = str(extra)
    out = tmp_path / 'clash.epub'
    F.generate_epub(one_position, base_opts, out)
    facts = I.inspect_epub(out)
    assert 'color: red' not in facts.stylesheets['diagram_confg.css']
    assert any('color: red' in css for name, css in facts.stylesheets.items()
               if name != 'diagram_confg.css')


def test_epub_passes_epubcheck_when_it_is_available(tmp_path, base_opts, positions):
    """Run the reference validator if the machine has it.

    epub3_problems() above encodes the same rules, so the suite still guards
    conformance without it; this raises the bar when the real tool is present.
    """
    import os
    import shutil
    import subprocess

    out = tmp_path / 'validate.epub'
    F.generate_epub(positions, base_opts, out)

    command: list[str] | None = None
    if shutil.which('epubcheck'):
        command = ['epubcheck', str(out)]
    elif os.environ.get('EPUBCHECK_JAR') and shutil.which('java'):
        command = ['java', '-jar', os.environ['EPUBCHECK_JAR'], str(out)]
    if command is None:
        pytest.skip('epubcheck not installed (set EPUBCHECK_JAR to enable)')

    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_epub_omits_a_font_it_may_not_embed(tmp_path, base_opts, one_position):
    base_opts['font'] = 'Chess Cases'
    out = tmp_path / 'restricted.epub'
    F.generate_epub(one_position, base_opts, out)
    facts = I.inspect_epub(out)
    assert not any(n.startswith('OEBPS/Fonts/') for n in facts.names)
    assert '@font-face' not in facts.stylesheets['diagram_confg.css']
    assert I.epub3_problems(facts) == []


# ── DOCX ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def docx_facts(tmp_path, base_opts, positions):
    base_opts.update(answers_section=True, lichess_link=True)
    out = tmp_path / 'doc.docx'
    F.generate_docx(positions, base_opts, out)
    return I.inspect_docx(out)


def test_docx_is_a_valid_package(docx_facts):
    for required in ('[Content_Types].xml', 'word/document.xml', 'word/styles.xml'):
        assert required in docx_facts.names


def test_docx_bookmarks_cover_diagrams_and_answers(docx_facts, positions):
    assert len([b for b in docx_facts.bookmarks if b.startswith('diag_')]) == len(positions)
    assert len([b for b in docx_facts.bookmarks if b.startswith('ans_')]) == len(positions)


def test_docx_every_internal_link_has_a_bookmark(docx_facts):
    assert set(docx_facts.internal_anchors) <= set(docx_facts.bookmarks)


def test_docx_bookmark_names_are_word_safe(docx_facts):
    import re
    for name in docx_facts.bookmarks:
        assert re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name), name
        assert len(name) <= 40, name


def test_docx_lichess_links_are_external_relationships(docx_facts, positions):
    lichess = [u for u in docx_facts.external_rel_targets if 'lichess.org' in u]
    assert len(lichess) == len(positions)


def test_docx_boards_use_the_chess_font(docx_facts):
    assert F._board_font_family_name(F._default_board_font_name()) in docx_facts.fonts_used


def test_docx_embeds_the_board_font(docx_facts):
    assert docx_facts.embedded_font_parts, 'no .odttf part found'


def test_docx_skips_a_font_it_may_not_embed(tmp_path, base_opts, one_position):
    base_opts['font'] = 'Chess Adventurer'
    out = tmp_path / 'restricted.docx'
    F.generate_docx(one_position, base_opts, out)          # must not raise
    assert I.inspect_docx(out).embedded_font_parts == []


def test_docx_contains_the_titles(tmp_path, base_opts, positions):
    out = tmp_path / 'titles.docx'
    F.generate_docx(positions, base_opts, out)
    text = I.inspect_docx(out).text
    for word in ('First', 'Second', 'Third'):
        assert word in text


# ── RTF ───────────────────────────────────────────────────────────────────────

@pytest.fixture
def rtf_facts(tmp_path, base_opts, positions):
    base_opts.update(answers_section=True, lichess_link=True)
    out = tmp_path / 'doc.rtf'
    F.generate_rtf(positions, base_opts, out)
    return I.inspect_rtf(out)


def test_rtf_braces_are_balanced(rtf_facts):
    assert rtf_facts.brace_balance == 0


def test_rtf_is_pure_ascii(rtf_facts):
    assert rtf_facts.text.isascii()


def test_rtf_declares_the_board_font(rtf_facts):
    expected = F._board_font_family_name(F._default_board_font_name())
    assert expected in rtf_facts.font_table


def test_rtf_bookmarks_cover_diagrams_and_answers(rtf_facts, positions):
    assert len([b for b in rtf_facts.bookmarks if b.startswith('diag_')]) == len(positions)
    assert len([b for b in rtf_facts.bookmarks if b.startswith('ans_')]) == len(positions)


def test_rtf_every_internal_link_has_a_bookmark(rtf_facts):
    assert set(rtf_facts.internal_links) <= set(rtf_facts.bookmarks)


def test_rtf_lichess_links_are_external(rtf_facts, positions):
    lichess = [u for u in rtf_facts.external_links if 'lichess.org' in u]
    assert len(lichess) == len(positions)


def test_rtf_row_count_follows_the_layout(tmp_path, base_opts):
    """Layout 2 is two columns, so four positions occupy two table rows."""
    positions = [{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'comment': f'#{i}', 'moves': ''}
                 for i in range(4)]
    base_opts['layout_idx'] = 2
    out = tmp_path / 'rows.rtf'
    F.generate_rtf(positions, base_opts, out)
    assert I.inspect_rtf(out).rows == 2


def test_rtf_pads_a_short_final_row(tmp_path, base_opts):
    positions = [{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'comment': 'only', 'moves': ''}]
    base_opts['layout_idx'] = 2
    out = tmp_path / 'pad.rtf'
    F.generate_rtf(positions, base_opts, out)
    facts = I.inspect_rtf(out)
    assert facts.rows == 1
    assert facts.brace_balance == 0


def test_rtf_escapes_non_ascii_titles(tmp_path, base_opts):
    positions = [{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'comment': 'Peão ção', 'moves': ''}]
    out = tmp_path / 'accents.rtf'
    F.generate_rtf(positions, base_opts, out)
    facts = I.inspect_rtf(out)
    assert facts.text.isascii()
    assert r'\u227' in facts.text          # ã
    assert facts.brace_balance == 0


# ── Numbering consistency across formats ──────────────────────────────────────
#
# An anchor is not the number on the page. The two used to be the same string,
# until --number-restart-per-chapter made the number come round again in every
# chapter; anchors are now the position's place in the document. What has to
# hold is that a diagram and its solution meet, and that the number *shown*
# follows the numbering options.

@pytest.mark.parametrize('offset', [0, 1, 10])
def test_html_anchors_pair_each_diagram_with_its_answer(tmp_path, base_opts, positions, offset):
    base_opts.update(answers_section=True, number_offset=offset)
    out = tmp_path / f'n{offset}.html'
    F.generate_html(positions, base_opts, out)
    facts = I.inspect_html(out.read_text(encoding='utf-8'))
    assert facts.diagram_ids == [f'diagram-{i + 1}' for i in range(len(positions))]
    assert facts.answer_ids == [f'answer-{i + 1}' for i in range(len(positions))]
    # Every anchor written is also an anchor pointed at, and the other way round.
    assert set(facts.anchor_targets) == set(facts.diagram_ids) | set(facts.answer_ids)


@pytest.mark.parametrize('offset', [0, 1, 10])
def test_html_numbering_honours_the_offset(tmp_path, base_opts, positions, offset):
    base_opts.update(answers_section=True, number_offset=offset)
    out = tmp_path / f'o{offset}.html'
    F.generate_html(positions, base_opts, out)
    text = out.read_text(encoding='utf-8')
    # The answers section labels each entry with the number the diagram shows.
    shown = re.findall(r"<a href='#diagram-\d+'>(\d+)\.</a>", text)
    assert shown == [str(i + 1 + offset) for i in range(len(positions))]


@pytest.mark.parametrize('offset', [0, 1, 10])
def test_docx_and_rtf_anchors_agree_on_the_numbering(tmp_path, base_opts, positions, offset):
    base_opts.update(answers_section=True, number_offset=offset)
    F.generate_docx(positions, base_opts, tmp_path / 'n.docx')
    F.generate_rtf(positions, base_opts, tmp_path / 'n.rtf')
    expected = {f'diag_{i + 1}' for i in range(len(positions))}
    expected |= {f'ans_{i + 1}' for i in range(len(positions))}
    assert set(I.inspect_docx(tmp_path / 'n.docx').bookmarks) == expected
    assert set(I.inspect_rtf(tmp_path / 'n.rtf').bookmarks) == expected


def test_the_number_shown_matches_the_number_linked(tmp_path, base_opts):
    """A diagram titled "11" must be answered by an entry numbered 11."""
    positions = F.parse_pgn(PGN_THREE_GAMES)
    base_opts.update(answers_section=True, number_offset=10)
    out = tmp_path / 'match.html'
    F.generate_html(positions, base_opts, out)
    text = out.read_text(encoding='utf-8')
    # The first diagram is titled 11 and links to an answer labelled 11, and
    # that answer links back to the diagram it came from.
    anchor = re.search(r"<div class='diagram-block' id='(diagram-\d+)'>", text).group(1)
    answer = re.search(r"<div class='title'><a href='#(answer-\d+)'>11\s*</a>", text).group(1)
    assert f"id='{answer}'" in text
    assert f"<a href='#{anchor}'>11.</a>" in text
