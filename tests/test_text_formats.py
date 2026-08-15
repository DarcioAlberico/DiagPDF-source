"""The two text formats: Markdown and LaTeX.

Neither can be checked by opening it in a reader, so the assertions are on
structure: the board decoded back into a position, links that resolve, and
markup that is escaped rather than executed.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import inspectors as I
import pytest
from conftest import BLACK_TO_MOVE_FEN, KINGS_FEN, PGN_WITH_CHAPTERS, START_FEN

import fen2rtf as F
from diagpdf.fen import parse_fen

MARKUP_COMMENT = 'Star * under_score [bracket] `tick` <tag> pipe| back\\slash'
TEX_COMMENT = r'50% of #1 & $5 ~ x^2 _under_ {brace} \command'


@pytest.fixture
def start_position():
    return [{'fen': START_FEN, 'comment': 'Opening', 'moves': '1.e4 e5'}]


def md(tmp_path, base_opts, positions, name='out.md'):
    out = tmp_path / name
    F.generate_output(positions, base_opts, out)
    return I.inspect_markdown(out)


def tex(tmp_path, base_opts, positions, name='out.tex'):
    out = tmp_path / name
    F.generate_output(positions, base_opts, out)
    return I.inspect_latex(out)


# ══ Markdown ══════════════════════════════════════════════════════════════════

def test_the_board_decodes_back_to_the_position(tmp_path, base_opts, start_position):
    """FEN -> Unicode board -> position must round-trip, square for square."""
    facts = md(tmp_path, base_opts, start_position)
    assert len(facts.boards) == 1
    decoded = I.board_from_markdown(facts.boards[0], has_coords=True)
    expected, _ = parse_fen(START_FEN)
    assert decoded == list(reversed(expected))     # rank 8 is written first


def test_the_board_is_mirrored_when_black_is_to_move(tmp_path, base_opts):
    """flip_auto is on by default, so a black-to-move board is seen from Black."""
    positions = [{'fen': BLACK_TO_MOVE_FEN, 'comment': 'B', 'moves': ''}]
    base_opts['flip_auto'] = True
    facts = md(tmp_path, base_opts, positions)
    rows = facts.boards[0]
    assert rows[0].startswith('1 ')            # rank 1 at the top
    assert rows[-2].strip() == 'h g f e d c b a'


def test_the_board_is_not_mirrored_when_white_is_to_move(tmp_path, base_opts, start_position):
    facts = md(tmp_path, base_opts, start_position)
    rows = facts.boards[0]
    assert rows[0].startswith('8 ')
    assert rows[-2].strip() == 'a b c d e f g h'


def test_coordinates_can_be_switched_off(tmp_path, base_opts, start_position):
    base_opts['coords'] = False
    facts = md(tmp_path, base_opts, start_position)
    rows = facts.boards[0]
    assert not any(row.strip().startswith(('8 ', '1 ')) for row in rows[:1] if row[0].isdigit())
    assert 'a b c d e f g h' not in '\n'.join(rows)


def test_the_side_to_move_is_named_in_the_chosen_language(tmp_path, base_opts, start_position):
    base_opts['lang'] = 'pt'
    facts = md(tmp_path, base_opts, start_position)
    assert 'Brancas jogam' in '\n'.join(facts.boards[0])


def test_markup_in_a_comment_is_escaped_not_executed(tmp_path, base_opts):
    positions = [{'fen': KINGS_FEN, 'comment': MARKUP_COMMENT, 'moves': ''}]
    facts = md(tmp_path, base_opts, positions)
    heading = next(text for level, text in facts.headings if level == 3)
    for char in '*_[]<>|\\`':
        assert f'\\{char}' in heading, char


def test_ordinary_punctuation_is_left_alone(tmp_path, base_opts):
    """Escaping the whole CommonMark set turns prose into backslash soup."""
    positions = [{'fen': KINGS_FEN, 'comment': 'Mate in 2 - and it is quick.', 'moves': ''}]
    facts = md(tmp_path, base_opts, positions)
    heading = next(text for level, text in facts.headings if level == 3)
    assert 'Mate in 2 - and it is quick.' in heading


def test_every_fence_is_closed(tmp_path, base_opts, positions):
    facts = md(tmp_path, base_opts, positions)
    assert facts.fence_count == 2 * len(facts.boards)


def test_one_board_per_position(tmp_path, base_opts, positions):
    facts = md(tmp_path, base_opts, positions)
    assert len(facts.boards) == len(positions)
    assert len(facts.diagram_ids) == len(positions)


def test_answers_link_both_ways(tmp_path, base_opts, positions):
    base_opts['answers_section'] = True
    facts = md(tmp_path, base_opts, positions)
    assert facts.answer_ids
    known = set(facts.diagram_ids) | set(facts.answer_ids)
    assert not [t for t in facts.anchor_targets if t not in known]


def test_without_an_answers_section_the_moves_are_inline(tmp_path, base_opts, positions):
    base_opts['answers_section'] = False
    facts = md(tmp_path, base_opts, positions)
    assert not facts.answer_ids
    assert '1.' in facts.text


def test_piece_letters_become_symbols_in_the_answers(tmp_path, base_opts):
    positions = [{'fen': KINGS_FEN, 'comment': 'x', 'moves': '1.Nf3 Ke7'}]
    base_opts['answers_section'] = True
    facts = md(tmp_path, base_opts, positions)
    answers = facts.text.split('##')[-1]
    assert '♘f3' in answers and '♔e7' in answers


def test_metadata_becomes_front_matter(tmp_path, base_opts, start_position):
    base_opts.update(doc_title='My Book', doc_author='Me', doc_keywords='chess')
    facts = md(tmp_path, base_opts, start_position)
    assert facts.front_matter['title'] == 'My Book'
    assert facts.front_matter['author'] == 'Me'
    assert facts.front_matter['keywords'] == 'chess'


def test_a_title_with_a_colon_does_not_break_the_front_matter(tmp_path, base_opts, start_position):
    base_opts['doc_title'] = 'Endgames: volume 2'
    facts = md(tmp_path, base_opts, start_position)
    assert facts.front_matter['title'] == 'Endgames: volume 2'


def test_chapters_become_headings(tmp_path, base_opts):
    facts = md(tmp_path, base_opts, F.parse_pgn(PGN_WITH_CHAPTERS))
    level_two = [text for level, text in facts.headings if level == 2]
    assert 'Pins' in level_two and 'Forks' in level_two


def test_notation_lines_are_written(tmp_path, base_opts, start_position):
    base_opts.update(lines_count=3, lines_mode='numbered')
    facts = md(tmp_path, base_opts, start_position)
    assert facts.text.count('> 1.') == 1
    assert facts.text.count('> 3.') == 1


def test_lichess_links_are_external(tmp_path, base_opts, start_position):
    base_opts['lichess_link'] = True
    facts = md(tmp_path, base_opts, start_position)
    assert facts.external_urls and all('lichess.org' in u for u in facts.external_urls)


# ══ LaTeX ═════════════════════════════════════════════════════════════════════

def test_the_document_is_structurally_sound(tmp_path, base_opts, positions):
    base_opts.update(answers_section=True, answers_cols=2, lines_count=2,
                     lichess_link=True, cover=True, contents=True,
                     header='H {page}/{total}', show_header=True,
                     doc_title='Book', doc_author='Me')
    assert I.latex_problems(tex(tmp_path, base_opts, positions)) == []


def test_tex_markup_in_a_comment_is_escaped(tmp_path, base_opts):
    positions = [{'fen': KINGS_FEN, 'comment': TEX_COMMENT, 'moves': ''}]
    facts = tex(tmp_path, base_opts, positions)
    for escaped in (r'\%', r'\#', r'\&', r'\$', r'\_', r'\{', r'\}',
                    r'\textasciitilde{}', r'\textasciicircum{}', r'\textbackslash{}'):
        assert escaped in facts.text, escaped
    assert I.latex_problems(facts) == []


def test_a_comment_full_of_markup_keeps_the_braces_balanced(tmp_path, base_opts):
    positions = [{'fen': KINGS_FEN, 'comment': '{{{ unbalanced }', 'moves': ''}]
    assert tex(tmp_path, base_opts, positions).brace_balance == 0


def test_one_board_per_position_with_its_fen(tmp_path, base_opts, positions):
    facts = tex(tmp_path, base_opts, positions)
    assert len(facts.fens) == len(positions)
    assert facts.fens[0].startswith(positions[0]['fen'].split()[0])


def test_the_board_is_inverted_only_when_it_should_be(tmp_path, base_opts):
    white = [{'fen': START_FEN, 'comment': 'w', 'moves': ''}]
    black = [{'fen': BLACK_TO_MOVE_FEN, 'comment': 'b', 'moves': ''}]
    assert tex(tmp_path, base_opts, white, 'w.tex').inverse_count == 0
    assert tex(tmp_path, base_opts, black, 'b.tex').inverse_count == 1


def test_the_chess_package_is_requested(tmp_path, base_opts, start_position):
    assert 'chessboard' in tex(tmp_path, base_opts, start_position).packages


def test_the_document_language_reaches_babel(tmp_path, base_opts, start_position):
    base_opts['lang'] = 'ru'
    facts = tex(tmp_path, base_opts, start_position)
    assert r'\usepackage[russian]{babel}' in facts.text
    # T1 alone cannot set Cyrillic; T2A has to be loaded for the sample games.
    assert 'T2A' in facts.text


def test_the_paper_size_reaches_geometry(tmp_path, base_opts, start_position):
    base_opts.update(page_size='a5', landscape=True)
    facts = tex(tmp_path, base_opts, start_position)
    assert 'a5paper' in facts.text and 'landscape' in facts.text


def test_metadata_reaches_hypersetup(tmp_path, base_opts, start_position):
    base_opts.update(doc_title='Book', doc_author='Me', doc_subject='Chess')
    facts = tex(tmp_path, base_opts, start_position)
    assert 'pdftitle={Book}' in facts.text
    assert 'pdfauthor={Me}' in facts.text
    assert 'pdfsubject={Chess}' in facts.text


def test_page_placeholders_become_latex_counters(tmp_path, base_opts, start_position):
    base_opts.update(header='p {page} of {total}', show_header=True)
    facts = tex(tmp_path, base_opts, start_position)
    assert r'\thepage' in facts.text
    assert r'\pageref{LastPage}' in facts.text
    assert '{page}' not in facts.text.replace(r'\pageref{LastPage}', '')


def test_chapters_become_sections(tmp_path, base_opts):
    facts = tex(tmp_path, base_opts, F.parse_pgn(PGN_WITH_CHAPTERS))
    assert 'Pins' in facts.sections and 'Forks' in facts.sections


def test_a_single_answer_column_avoids_multicol(tmp_path, base_opts, positions):
    """multicol refuses one column, so asking for one must not start it."""
    base_opts.update(answers_section=True, answers_cols=1)
    facts = tex(tmp_path, base_opts, positions)
    assert 'multicols' not in facts.text
    assert I.latex_problems(facts) == []


def test_two_answer_columns_use_multicol(tmp_path, base_opts, positions):
    base_opts.update(answers_section=True, answers_cols=2)
    facts = tex(tmp_path, base_opts, positions)
    assert r'\begin{multicols}{2}' in facts.text
    assert I.latex_problems(facts) == []


def test_a_cover_and_contents_are_produced(tmp_path, base_opts, positions):
    base_opts.update(cover=True, contents=True, doc_title='Book')
    facts = tex(tmp_path, base_opts, positions)
    assert r'\begin{titlepage}' in facts.text
    assert r'\tableofcontents' in facts.text


def test_the_board_size_is_set_once(tmp_path, base_opts, start_position):
    """Everything stylistic sits on one line, so a package change is one edit."""
    base_opts['font_size'] = 31
    facts = tex(tmp_path, base_opts, start_position)
    assert facts.text.count(r'\setchessboard') == 1
    assert 'boardfontsize=31pt' in facts.text


def test_only_setfen_varies_per_diagram(tmp_path, base_opts, positions):
    """The per-diagram surface is kept to the one package key it must use."""
    facts = tex(tmp_path, base_opts, positions)
    for call in facts.text.split(r'\chessboard[')[1:]:
        keys = call.split(']')[0]
        assert set(k.split('=')[0] for k in keys.split(',') if '=' in k) <= {'setfen', 'inverse'}


def test_lichess_links_use_href(tmp_path, base_opts, start_position):
    base_opts['lichess_link'] = True
    facts = tex(tmp_path, base_opts, start_position)
    assert facts.external_urls and 'lichess.org' in facts.external_urls[0]


# ── Compiling it for real ─────────────────────────────────────────────────────
#
# Everything above reads the .tex as text. Structure is all that can be checked
# without TeX, and it is not enough: the first real compile stopped on
# "Command \CYRR unavailable in encoding T1" — a document that inspected
# perfectly and produced no PDF at all.

def _pdflatex() -> str | None:
    """Return the pdflatex to use, or None when there is no TeX here."""
    found = shutil.which('pdflatex')
    if found:
        return found
    # MiKTeX installs per user and does not always reach PATH.
    candidate = Path.home() / 'AppData/Local/Programs/MiKTeX/miktex/bin/x64/pdflatex.exe'
    return str(candidate) if candidate.exists() else None


def compile_tex(path: Path, passes: int = 1) -> subprocess.CompletedProcess:
    """Run pdflatex on *path*, returning the last run."""
    result = None
    for _ in range(passes):
        result = subprocess.run(
            [_pdflatex(), '-interaction=nonstopmode', '-halt-on-error', path.name],
            cwd=str(path.parent), capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=600,
        )
    return result


@pytest.fixture
def latex_compiler():
    compiler = _pdflatex()
    if not compiler:
        pytest.skip('no pdflatex installed')
    return compiler


@pytest.mark.slow
def test_the_generated_latex_compiles(tmp_path, base_opts, positions, latex_compiler):
    out = tmp_path / 'doc.tex'
    F.generate_output(positions, base_opts, out)
    result = compile_tex(out)
    assert result.returncode == 0, result.stdout[-3000:]
    assert (tmp_path / 'doc.pdf').exists()


@pytest.mark.slow
def test_cyrillic_compiles(tmp_path, base_opts, latex_compiler):
    """The defect the first compile found: T1 has no Cyrillic at all."""
    russian = [{'fen': START_FEN, 'comment': 'Расположение белого ферзя', 'moves': '1.e4'}]
    out = tmp_path / 'ru.tex'
    F.generate_output(russian, base_opts, out)
    assert r'\usepackage[T1,T2A]{fontenc}' in out.read_text(encoding='utf-8')
    assert compile_tex(out).returncode == 0


@pytest.mark.slow
def test_accented_latin_still_compiles(tmp_path, base_opts, latex_compiler):
    """And the other half: T2A must not become the default without reason."""
    portuguese = [{'fen': START_FEN, 'comment': 'Peão em ação — mate', 'moves': '1.e4'}]
    out = tmp_path / 'pt.tex'
    F.generate_output(portuguese, base_opts, out)
    assert r'\usepackage[T2A,T1]{fontenc}' in out.read_text(encoding='utf-8')
    assert compile_tex(out).returncode == 0


@pytest.mark.slow
def test_every_option_group_compiles(tmp_path, base_opts, positions, latex_compiler):
    """The options that reach the preamble: packages, and how they combine."""
    base_opts.update(
        answers_section=True, answers_cols=2, answers_after_chapter=True,
        number_restart_per_chapter=True, cover=True, contents=True,
        watermark='RASCUNHO', lines_count=2, lines_mode='numbered',
        lichess_link=True, doc_title='Tactics', doc_author='DiagPDF',
        page_size='a5', landscape=True, header='H', footer='{page}/{total}',
    )
    chaptered = F.parse_pgn(PGN_WITH_CHAPTERS)
    out = tmp_path / 'everything.tex'
    F.generate_output(chaptered, base_opts, out)
    result = compile_tex(out, passes=2)      # contents and {total} need two
    assert result.returncode == 0, result.stdout[-3000:]
    assert (tmp_path / 'everything.pdf').exists()
