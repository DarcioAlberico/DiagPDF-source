#!/usr/bin/env python3
"""Regression tests for the defects fixed in 0.2.4 (ROADMAP phase 0).

Every test here fails on 0.2.3. They stay separate from the topic-based
modules so the link between a fixed defect and its guard remains obvious.
"""

from __future__ import annotations

import base64
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import fen2rtf as F

PGN_TWO_GAMES = '''[Event "G1"]
[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]
{First} 1.Ke2 *

[White "Nobody"]
[FEN "8/8/8/8/8/5k2/8/5K2 b - - 0 1"]
{Second} 1...Kg3 *
'''

PGN_EVENT_IN_COMMENT = '''[Event "Real"]
[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]
{see
[Event "fake"] in comment}
1.Ke2 Kd7 *
'''

BASE_OPTS = {
    'layout_idx': F.DEFAULT_LAYOUT,
    'font': F._default_board_font_name(),
    'font_size': 0,
    'text_size': 0,
    'coords': True,
    'flip': False,
    'flip_auto': True,
    'symbol': 'square',
    'border_style': 'simple',
    'lines_count': 0,
    'lines_mode': 'plain',
    'title_template': '{number} {comment}',
    'header': '',
    'footer': '',
    'show_header': False,
    'show_footer': False,
    'lichess_link': False,
    'answers_section': False,
    'answers_title': 'Solutions',
    'answers_cols': 1,
    'figurine_font': F._default_figurine_font_name(),
}


def opts(**over) -> dict:
    merged = dict(BASE_OPTS)
    merged.update(over)
    return merged


# ── C5 · title number prefix ──────────────────────────────────────────────────

def test_c5_multi_digit_title_is_not_split():
    assert F._split_title_number_prefix('1 Some text', 1) == ('1 ', 'Some text')
    assert F._split_title_number_prefix('10. Mate in 2', 10) == ('10. ', 'Mate in 2')
    assert F._split_title_number_prefix('7) title', 7) == ('7) ', 'title')
    # 0.2.3 returned ('1', '2 Some text') / ('1', 'st example') / ('10', '0 x')
    assert F._split_title_number_prefix('12 Some text', 1) == ('', '12 Some text')
    assert F._split_title_number_prefix('1st example', 1) == ('', '1st example')
    assert F._split_title_number_prefix('100 x', 10) == ('', '100 x')


# ── C7 · FEN validation ───────────────────────────────────────────────────────

def test_c7_validate_fen():
    assert F.validate_fen('4k3/8/8/8/8/8/8/4K3 w - - 0 1') == []
    assert F.validate_fen('') == ['empty FEN']
    assert F.validate_fen('8/8/8 w - - 0 1')            # too few ranks
    assert F.validate_fen('8/8/8/8/8/8/8/8 w - - 0 1')  # no kings
    assert F.validate_fen('4k3/9/8/8/8/8/8/4K3 w - - 0 1')  # rank overflows
    assert F.validate_fen('4k3/8/8/8/8/8/8/4K3 x - - 0 1')  # bad side to move


def test_c7_parse_fen_rejects_empty():
    try:
        F.parse_fen('')
    except F.FenError:
        return
    raise AssertionError('parse_fen("") must raise FenError, not IndexError')


def test_c7_policy_skips_and_fails():
    positions = [
        {'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1'},
        {'fen': 'garbage'},
    ]
    assert len(F.apply_fen_policy(positions, 'skip')) == 1
    try:
        F.apply_fen_policy(positions, 'fail')
    except F.FenError:
        return
    raise AssertionError('--on-invalid fail must raise')


# ── C10 / C11 · PGN splitting ─────────────────────────────────────────────────

def test_c10_game_without_event_tag_is_not_swallowed():
    parsed = F.parse_pgn(PGN_TWO_GAMES)
    # 0.2.3 returned a single game whose FEN was the *second* one.
    assert len(parsed) == 2
    assert parsed[0]['fen'].startswith('4k3')
    assert parsed[1]['fen'].startswith('8/8/8/8/8/5k2')


def test_c11_event_inside_comment_keeps_movetext():
    parsed = F.parse_pgn(PGN_EVENT_IN_COMMENT)
    assert len(parsed) == 1
    # 0.2.3 truncated the movetext to '{see'
    assert F._clean_moves(parsed[0]['moves']) == '1.Ke2 Kd7'


def test_r3_line_comments_and_escape_lines_are_stripped():
    assert F._clean_moves('1.e4 ; a note\n1...e5') == '1.e4 1...e5'
    assert F._clean_moves('%eval junk\n1.e4 e5') == '1.e4 e5'


# ── C8 · font resolution ──────────────────────────────────────────────────────

def test_c8_unknown_font_raises_instead_of_serving_the_wrong_file():
    try:
        F.resolve_board_font('AlphaDG')
    except F.UnknownFontError as exc:
        assert 'Available' in str(exc)
        return
    raise AssertionError('unknown font must raise UnknownFontError')


def test_c8_known_fonts_all_resolve():
    for name in F.FONT_NAMES:
        assert (F._resource('Fonts') / F.resolve_board_font(name)).exists()


# ── C1 / C2 · standalone HTML ─────────────────────────────────────────────────

def test_c1_html_embeds_the_board_font(tmp_path: Path):
    out = tmp_path / 'a.html'
    F.generate_html([{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'moves': ''}], opts(), out)
    text = out.read_text(encoding='utf-8')
    m = re.search(r'src: url\("data:font/(?:ttf|otf);base64,([A-Za-z0-9+/=]+)"\)', text)
    assert m, 'board font must be inlined, not linked relatively'
    assert '../Fonts/' not in text
    payload = base64.b64decode(m.group(1))
    assert payload[:4] in (b'\x00\x01\x00\x00', b'true', b'OTTO')


def test_c2_every_css_variable_is_defined(tmp_path: Path):
    out = tmp_path / 'b.html'
    F.generate_html([{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'moves': ''}], opts(), out)
    text = out.read_text(encoding='utf-8')
    used = set(re.findall(r'var\((--[a-z-]+)\)', text))
    defined = set(re.findall(r'(--[a-z-]+)\s*:', text))
    assert used <= defined, f'undefined CSS variables: {sorted(used - defined)}'
    assert '--card-bg' in used and '--card-border' in used


# ── C6 · EPUB 3 conformance ───────────────────────────────────────────────────

def test_c6_epub_is_epub3_conformant(tmp_path: Path):
    out = tmp_path / 'c.epub'
    F.generate_epub(
        [{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'moves': '1.Ke2'}],
        opts(doc_title='T', doc_author='A', doc_language='pt'),
        out,
    )
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert names[0] == 'mimetype'
        assert z.infolist()[0].compress_type == zipfile.ZIP_STORED
        assert 'OEBPS/nav.xhtml' in names
        opf = z.read('OEBPS/content.opf').decode()
        for part in names:
            if part.endswith(('.xhtml', '.opf', '.ncx', '.xml')):
                ET.fromstring(z.read(part))
    assert 'dcterms:modified' in opf
    assert 'properties="nav"' in opf
    assert 'urn:uuid:12345' not in opf, 'identifier must be unique per publication'
    assert '<dc:title>T</dc:title>' in opf
    assert '<dc:creator>A</dc:creator>' in opf
    assert '<dc:language>pt</dc:language>' in opf


def test_c6_epub_identifiers_are_unique(tmp_path: Path):
    ids = []
    for i in range(2):
        out = tmp_path / f'u{i}.epub'
        F.generate_epub([{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'moves': ''}], opts(), out)
        with zipfile.ZipFile(out) as z:
            ids.append(re.search(r'<dc:identifier[^>]*>([^<]+)', z.read('OEBPS/content.opf').decode()).group(1))
    assert ids[0] != ids[1]


# ── C4 / C13 · answers numbering and links ────────────────────────────────────

def _pdf_text_calls(positions, options, out_path) -> list[tuple[str, object]]:
    """Render a PDF, capturing the text and link of every cell drawn."""
    from fpdf import FPDF
    captured: list[tuple[str, object]] = []
    original = FPDF.cell

    def spy(self, *args, **kwargs):
        text = kwargs.get('text', '')
        if text:
            captured.append((text, kwargs.get('link')))
        return original(self, *args, **kwargs)

    FPDF.cell = spy
    try:
        F.generate_pdf(positions, options, out_path)
    finally:
        FPDF.cell = original
    return captured


def test_c4_answer_numbers_match_diagram_numbers(tmp_path: Path):
    positions = F.parse_pgn(PGN_TWO_GAMES)
    calls = _pdf_text_calls(
        positions,
        opts(answers_section=True, number_offset=1),
        tmp_path / 'd.pdf',
    )
    drawn = [text for text, _ in calls]
    # Diagrams are numbered 2 and 3; 0.2.3 numbered the answers 1 and 2.
    assert '2 ' in drawn and '3 ' in drawn
    assert '2. ' in drawn and '3. ' in drawn
    assert '1. ' not in drawn


def test_c13_titles_without_an_answer_are_not_styled_as_links(tmp_path: Path):
    positions = [
        {'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'comment': 'has', 'moves': '1.Ke2'},
        {'fen': '8/8/8/8/8/5k2/8/5K2 w - - 0 1', 'comment': 'none', 'moves': ''},
    ]
    calls = _pdf_text_calls(positions, opts(answers_section=True), tmp_path / 'e.pdf')
    # 0.2.3 drew '2 ' in blue with link=0 — clickable-looking but inert.
    for text, link in calls:
        if text.strip() in ('1', '2'):
            assert link != 0, f'{text!r} drawn as a link target with link=0'


# ── C12 · answers must not overflow the page ──────────────────────────────────

def test_c12_long_answer_paginates(tmp_path: Path):
    from fpdf import FPDF
    long_moves = ' '.join(f'{i}. Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7' for i in range(1, 200))
    lowest: dict[int, float] = {}
    original = FPDF.cell

    def spy(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        lowest[self.page] = max(lowest.get(self.page, 0.0), self.get_y() + (kwargs.get('h') or 0))
        return result

    FPDF.cell = spy
    try:
        F.generate_pdf(
            [{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'comment': 'Long', 'moves': long_moves}],
            opts(answers_section=True),
            tmp_path / 'f.pdf',
        )
    finally:
        FPDF.cell = original
    # 0.2.3 drew down to y=322mm on a 297mm page and lost the text.
    overflowing = {page: y for page, y in lowest.items() if y > F.PAGE_H}
    assert not overflowing, f'content drawn past the page edge: {overflowing}'
    assert len(lowest) > 2, 'a 200-move answer should span more than one answers page'


# ── C9 · Lichess label follows the language ───────────────────────────────────

def test_c9_lichess_label_is_translated(tmp_path: Path):
    seen = {}
    for lang in ('en', 'ru', 'pt', 'es'):
        out = tmp_path / f'g_{lang}.html'
        F.generate_html(
            [{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'moves': ''}],
            opts(lichess_link=True, lang=lang),
            out,
        )
        seen[lang] = re.search(
            r"class='lichess-link'><a href='[^']*'>([^<]+)", out.read_text(encoding='utf-8')
        ).group(1)
    assert len(set(seen.values())) == 4, seen
    assert seen['pt'] == 'Analisar no Lichess'
    assert seen['en'] == 'Analyse on Lichess'


def test_c9_custom_label_overrides(tmp_path: Path):
    out = tmp_path / 'h.html'
    F.generate_html(
        [{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'moves': ''}],
        opts(lichess_link=True, lichess_label='Abrir análise'),
        out,
    )
    assert 'Abrir an' in out.read_text(encoding='utf-8')


# ── C15 / C16 · font licence policy ───────────────────────────────────────────

def test_c15_restricted_font_does_not_break_docx(tmp_path: Path):
    restricted = [n for n in F.FONT_NAMES
                  if not F.font_embedding_allowed(F._resource('Fonts') / F.FONT_FILES[n])[0]]
    if not restricted:
        return
    out = tmp_path / 'i.docx'
    # 0.2.3 raised RuntimeError *after* writing the file.
    F.generate_docx([{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'moves': ''}],
                    opts(font=restricted[0]), out)
    assert out.exists() and out.stat().st_size > 0
    with zipfile.ZipFile(out) as z:
        assert not [n for n in z.namelist() if n.endswith('.odttf')]


def test_c16_restricted_font_is_not_packaged_into_epub(tmp_path: Path):
    restricted = [n for n in F.FONT_NAMES
                  if not F.font_embedding_allowed(F._resource('Fonts') / F.FONT_FILES[n])[0]]
    if not restricted:
        return
    out = tmp_path / 'j.epub'
    F.generate_epub([{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'moves': ''}],
                    opts(font=restricted[0]), out)
    with zipfile.ZipFile(out) as z:
        assert not [n for n in z.namelist() if n.startswith('OEBPS/Fonts/')]


# ── R5 · input encoding ───────────────────────────────────────────────────────

def test_r5_cp1252_input_is_decoded(tmp_path: Path):
    src = tmp_path / 'latin.pgn'
    src.write_bytes(
        '[Event "Partida do Peão"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n'
        .encode('cp1252')
    )
    assert F.parse_pgn(F.read_chess_file(src))[0]['event'] == 'Partida do Peão'


# ── all five formats still generate ───────────────────────────────────────────

def test_all_formats_generate(tmp_path: Path):
    positions = F.parse_pgn(PGN_TWO_GAMES)
    for ext in ('.pdf', '.html', '.epub', '.docx', '.rtf'):
        out = tmp_path / f'all{ext}'
        F.generate_output(positions, opts(answers_section=True, lichess_link=True), out)
        assert out.exists() and out.stat().st_size > 0, ext
