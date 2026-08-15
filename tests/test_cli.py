"""End-to-end CLI behaviour: exit codes, messages and option plumbing."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import inspectors as I
import pytest
from conftest import MISSING_FONT, PGN_THREE_GAMES, PROJECT_ROOT

import fen2rtf as F

SCRIPT = PROJECT_ROOT / 'fen2rtf.py'


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        cwd=str(PROJECT_ROOT),
    )


@pytest.fixture
def pgn(tmp_path) -> Path:
    path = tmp_path / 'input.pgn'
    path.write_text(PGN_THREE_GAMES, encoding='utf-8')
    return path


# ── Basics ────────────────────────────────────────────────────────────────────

def test_version_is_reported():
    result = run_cli('--version')
    assert result.returncode == 0
    assert F.__version__ in result.stdout


def test_list_fonts_names_the_default():
    result = run_cli('--list-fonts')
    assert result.returncode == 0
    assert 'Board fonts:' in result.stdout
    assert f'{F._default_board_font_name()} (default)' in result.stdout
    assert 'Figurine fonts:' in result.stdout


def test_list_languages_names_every_language():
    result = run_cli('--list-languages')
    assert result.returncode == 0
    for code in F.LANGS:
        assert f'  {code}  ' in result.stdout
    assert '(default)' in result.stdout


def test_listing_survives_a_console_that_cannot_spell_the_names():
    """Cyrillic through a cp1252 console used to end the run in a traceback."""
    import os
    env = {**os.environ, 'PYTHONIOENCODING': 'cp1252'}
    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--list-languages'],
        capture_output=True, text=True, encoding='cp1252', errors='replace',
        cwd=str(PROJECT_ROOT), env=env,
    )
    assert result.returncode == 0, result.stderr
    assert 'Russian' in result.stdout       # the English name always survives


def test_help_mentions_every_output_format():
    result = run_cli('--help')
    for word in ('PDF', 'HTML', 'EPUB', 'DOCX', 'RTF'):
        assert word in result.stdout


# ── Conversion ────────────────────────────────────────────────────────────────

def test_default_output_is_a_pdf_beside_the_input(pgn):
    result = run_cli(str(pgn))
    assert result.returncode == 0, result.stderr
    assert pgn.with_suffix('.pdf').exists()
    assert 'Converted 3 position(s)' in result.stdout


@pytest.mark.parametrize('ext', ['.pdf', '.html', '.epub', '.docx', '.rtf'])
def test_the_extension_picks_the_format(pgn, tmp_path, ext):
    out = tmp_path / f'book{ext}'
    result = run_cli(str(pgn), '-o', str(out))
    assert result.returncode == 0, result.stderr
    assert out.stat().st_size > 0


def test_font_size_changes_the_output(pgn, tmp_path):
    small, large = tmp_path / 'small.pdf', tmp_path / 'large.pdf'
    run_cli(str(pgn), '-o', str(small), '--font-size', '10')
    run_cli(str(pgn), '-o', str(large), '--font-size', '30')
    assert small.read_bytes() != large.read_bytes()


def test_range_selection_limits_the_positions(pgn, tmp_path):
    out = tmp_path / 'range.pdf'
    result = run_cli(str(pgn), '-o', str(out), '--from', '2', '--to', '3')
    assert 'Converted 2 position(s)' in result.stdout


def test_keep_numbers_and_its_documented_alias_agree(pgn, tmp_path):
    a, b = tmp_path / 'a.html', tmp_path / 'b.html'
    run_cli(str(pgn), '-o', str(a), '--from', '2', '--keep-numbers')
    run_cli(str(pgn), '-o', str(b), '--from', '2', '--no-renumber')
    assert a.read_text(encoding='utf-8') == b.read_text(encoding='utf-8')
    assert "id='diagram-2'" in a.read_text(encoding='utf-8')


def test_renumbering_is_the_default(pgn, tmp_path):
    out = tmp_path / 'renum.html'
    run_cli(str(pgn), '-o', str(out), '--from', '2')
    assert "id='diagram-1'" in out.read_text(encoding='utf-8')


def test_language_selects_the_generated_labels(pgn, tmp_path):
    out = tmp_path / 'ru.html'
    run_cli(str(pgn), '-o', str(out), '--lichess-link', '--lang', 'ru')
    assert 'Анализ на Lichess' in out.read_text(encoding='utf-8')


def test_epub_metadata_options(pgn, tmp_path):
    out = tmp_path / 'meta.epub'
    run_cli(str(pgn), '-o', str(out), '--title', 'Livro', '--author', 'Autor',
            '--language', 'pt')
    facts = I.inspect_epub(out)
    assert (facts.title, facts.creator, facts.language) == ('Livro', 'Autor', 'pt')
    assert I.epub3_problems(facts) == []


def test_html_font_mode_is_plumbed_through(pgn, tmp_path):
    out = tmp_path / 'linked.html'
    run_cli(str(pgn), '-o', str(out), '--html-font-mode', 'link')
    assert 'base64' not in out.read_text(encoding='utf-8')


# ── Errors ────────────────────────────────────────────────────────────────────

def test_missing_input_file_fails_with_a_message(tmp_path):
    result = run_cli(str(tmp_path / 'nope.pgn'))
    assert result.returncode == 1
    assert 'file not found' in result.stderr


def test_unknown_extension_is_rejected(tmp_path):
    src = tmp_path / 'data.txt'
    src.write_text('nothing', encoding='utf-8')
    result = run_cli(str(src))
    assert result.returncode == 1
    assert 'unknown extension' in result.stderr


def test_unknown_font_lists_the_available_ones(pgn, tmp_path):
    result = run_cli(str(pgn), '-o', str(tmp_path / 'x.pdf'), '-f', MISSING_FONT)
    assert result.returncode != 0
    assert 'invalid choice' in result.stderr
    assert F._default_board_font_name() in result.stderr


def test_empty_range_fails_rather_than_writing_nothing(pgn, tmp_path):
    result = run_cli(str(pgn), '-o', str(tmp_path / 'x.pdf'), '--from', '99')
    assert result.returncode == 1
    assert 'no positions in selected range' in result.stderr


# ── Invalid FEN policy ────────────────────────────────────────────────────────

@pytest.fixture
def pgn_with_a_bad_fen(tmp_path) -> Path:
    path = tmp_path / 'mixed.pgn'
    path.write_text(
        '[Event "Good"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n\n'
        '[Event "Bad"]\n[FEN "not-a-position"]\n1.Ke2 *\n',
        encoding='utf-8',
    )
    return path


def test_invalid_positions_are_skipped_with_a_warning(pgn_with_a_bad_fen, tmp_path):
    result = run_cli(str(pgn_with_a_bad_fen), '-o', str(tmp_path / 'skip.pdf'))
    assert result.returncode == 0
    assert 'position 2 skipped' in result.stderr
    assert 'Converted 1 position(s)' in result.stdout


def test_on_invalid_fail_stops_the_run(pgn_with_a_bad_fen, tmp_path):
    out = tmp_path / 'fail.pdf'
    result = run_cli(str(pgn_with_a_bad_fen), '-o', str(out), '--on-invalid', 'fail')
    assert result.returncode == 1
    assert 'invalid FEN' in result.stderr
    assert not out.exists()


# ── Encoding ──────────────────────────────────────────────────────────────────

def test_cp1252_input_is_detected_and_reported(tmp_path):
    src = tmp_path / 'latin.pgn'
    src.write_bytes(
        '[Event "Partida do Peão"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n'
        .encode('cp1252')
    )
    out = tmp_path / 'latin.html'
    result = run_cli(str(src), '-o', str(out), '--title-template', '{event}')
    assert result.returncode == 0
    assert 'cp1252' in result.stderr
    assert 'Partida do Peão' in out.read_text(encoding='utf-8')


def test_an_unknown_encoding_name_is_reported(tmp_path, pgn):
    result = run_cli(str(pgn), '-o', str(tmp_path / 'x.pdf'), '--encoding', 'not-a-codec')
    assert result.returncode == 1
    assert 'Error' in result.stderr


# ── Font licence ──────────────────────────────────────────────────────────────

def test_restricted_font_warns_but_succeeds(pgn, tmp_path):
    out = tmp_path / 'restricted.docx'
    result = run_cli(str(pgn), '-o', str(out), '-f', 'Chess Cases')
    assert result.returncode == 0, result.stderr
    assert 'non-embeddable' in result.stderr
    assert out.stat().st_size > 0


def test_the_licence_override_embeds_anyway(pgn, tmp_path):
    out = tmp_path / 'override.docx'
    result = run_cli(str(pgn), '-o', str(out), '-f', 'Chess Cases',
                     '--allow-restricted-fonts')
    assert result.returncode == 0, result.stderr
    assert 'anyway' in result.stderr
    assert I.inspect_docx(out).embedded_font_parts
