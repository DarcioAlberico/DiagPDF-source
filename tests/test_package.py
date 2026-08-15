"""The package layout itself: imports, the compatibility shim, and the cache."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys

import pytest
from conftest import PROJECT_ROOT

import diagpdf
import fen2rtf

CORE_MODULES = [
    'diagpdf.capabilities',
    'diagpdf.chars',
    'diagpdf.cli',
    'diagpdf.config',
    'diagpdf.errors',
    'diagpdf.fen',
    'diagpdf.fonts',
    'diagpdf.geometry',
    'diagpdf.i18n',
    'diagpdf.layouts',
    'diagpdf.log',
    'diagpdf.model',
    'diagpdf.options',
    'diagpdf.output',
    'diagpdf.profiles',
    'diagpdf.parsers',
    'diagpdf.paths',
    'diagpdf.render.common',
    'diagpdf.render.docx',
    'diagpdf.render.epub',
    'diagpdf.render.html',
    'diagpdf.render.pdf',
    'diagpdf.render.rtf',
    'diagpdf.resources',
    'diagpdf.svg',
]


# ── Imports ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('name', CORE_MODULES)
def test_every_module_imports_on_its_own(name):
    assert importlib.import_module(name)


def test_the_package_exposes_its_public_api():
    for name in diagpdf.__all__:
        assert hasattr(diagpdf, name), name


def test_the_version_is_shared_by_package_and_shim():
    assert fen2rtf.__version__ == diagpdf.__version__


def test_importing_the_package_does_not_pull_in_tkinter():
    """A library user should not pay for the desktop interface."""
    result = subprocess.run(
        [sys.executable, '-c',
         'import sys, diagpdf; print("tkinter" in sys.modules)'],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    assert result.stdout.strip() == 'False', result.stderr


# ── Compatibility shim ────────────────────────────────────────────────────────

SHIM_NAMES = [
    'ALPHA_DG', 'CHESS_MERIDA', 'DEFAULT_LAYOUT', 'DIRECT_PDF_CHESS_FONTS',
    'FIGURINE_FILES', 'FIGURINE_NAMES', 'FONT_FILES', 'FONT_NAMES', 'FenError',
    'GENERATORS', 'LAYOUTS', 'MERIDA_BORDER_SETS', 'MERIDA_COMPATIBLE_FONTS',
    'PAGE_H', 'PAGE_W', 'SYMBOL_CHARS', 'TITLE_LH_FACTOR', 'UnknownFontError',
    '_BOARD_FONT_INFO', '_WARNED_ONCE', '_apply_title_template', '_clean_moves',
    '_compute_geometry', '_default_board_font_name', '_default_figurine_font_name',
    '_figurine_segments', '_make_title', '_position_number', '_resource',
    '_split_title_number_prefix', 'apply_fen_policy', 'fen_to_diagram',
    'generate_docx', 'generate_epub', 'generate_html', 'generate_output',
    'generate_pdf', 'generate_rtf', 'main', 'parse_epd', 'parse_fen',
    'parse_fen_file', 'parse_pgn', 'read_chess_file', 'resolve_board_font',
    'run_gui', 'tr', 'validate_fen',
]


@pytest.mark.parametrize('name', SHIM_NAMES)
def test_the_shim_still_exports_the_old_names(name):
    assert hasattr(fen2rtf, name), f'fen2rtf.{name} disappeared in the package split'


def test_the_shim_and_the_package_share_one_implementation():
    assert fen2rtf.parse_pgn is diagpdf.parse_pgn
    assert fen2rtf.generate_pdf is diagpdf.generate_pdf
    assert fen2rtf.FONT_FILES is diagpdf.FONT_FILES


def test_the_old_scripts_still_import(tmp_path):
    """test_smoke.py and test_batch.py import from fen2rtf by name."""
    for script in ('test_smoke.py', 'test_batch.py'):
        result = subprocess.run(
            [sys.executable, '-c', f'import runpy, sys; sys.argv=["{script}"]; '
                                   f'compile(open("{script}", encoding="utf-8").read(), "{script}", "exec")'],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, result.stderr


# ── Font cache ────────────────────────────────────────────────────────────────

def test_the_cache_round_trips(tmp_path, monkeypatch):
    from diagpdf import fonts

    monkeypatch.setattr(fonts, '_CACHE_PATH', tmp_path / 'fontcache.json')
    scanned = fonts._discover_fonts(use_cache=False)
    assert not (tmp_path / 'fontcache.json').exists()

    first = fonts._discover_fonts()          # writes the cache
    assert (tmp_path / 'fontcache.json').exists()
    second = fonts._discover_fonts()         # reads it back
    assert first == second == scanned


def test_a_changed_font_directory_invalidates_the_cache(tmp_path, monkeypatch):
    from diagpdf import fonts

    cache = tmp_path / 'fontcache.json'
    monkeypatch.setattr(fonts, '_CACHE_PATH', cache)
    fonts._discover_fonts()

    stale = json.loads(cache.read_text(encoding='utf-8'))
    stale['fingerprint'] = [['ghost.ttf', 1, 1]]
    cache.write_text(json.dumps(stale), encoding='utf-8')

    assert fonts._read_font_cache(fonts._fonts_fingerprint(fonts._resource('Fonts'))) is None


def test_a_bumped_cache_version_invalidates_the_cache(tmp_path, monkeypatch):
    from diagpdf import fonts

    cache = tmp_path / 'fontcache.json'
    monkeypatch.setattr(fonts, '_CACHE_PATH', cache)
    fonts._discover_fonts()

    stale = json.loads(cache.read_text(encoding='utf-8'))
    stale['version'] = fonts._CACHE_VERSION + 1
    cache.write_text(json.dumps(stale), encoding='utf-8')

    assert fonts._read_font_cache(fonts._fonts_fingerprint(fonts._resource('Fonts'))) is None


def test_a_corrupt_cache_is_ignored_rather_than_fatal(tmp_path, monkeypatch):
    from diagpdf import fonts

    cache = tmp_path / 'fontcache.json'
    cache.write_text('{ not json at all', encoding='utf-8')
    monkeypatch.setattr(fonts, '_CACHE_PATH', cache)
    assert fonts._discover_fonts() == fonts._discover_fonts(use_cache=False)


def test_an_unwritable_cache_location_is_not_fatal(tmp_path, monkeypatch):
    from diagpdf import fonts

    # A directory where the file should be: writing must fail silently.
    blocked = tmp_path / 'fontcache.json'
    blocked.mkdir()
    monkeypatch.setattr(fonts, '_CACHE_PATH', blocked)
    assert fonts._discover_fonts() == fonts._discover_fonts(use_cache=False)


def test_the_cached_result_matches_a_fresh_scan():
    from diagpdf import fonts
    assert fonts._discover_fonts() == fonts._scan_fonts()


# ── Library chatter ───────────────────────────────────────────────────────────

def test_fonttools_chatter_is_silenced_by_default(tmp_path, base_opts, one_position):
    result = subprocess.run(
        [sys.executable, 'fen2rtf.py', '--list-fonts'],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    assert 'timestamp' not in result.stderr, result.stderr


def test_generating_a_document_is_quiet(tmp_path):
    src = tmp_path / 'in.pgn'
    src.write_text('[Event "E"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n',
                   encoding='utf-8')
    result = subprocess.run(
        [sys.executable, 'fen2rtf.py', str(src), '-o', str(tmp_path / 'out.pdf')],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0
    assert result.stderr.strip() == '', result.stderr


def test_quiet_suppresses_warnings(tmp_path):
    src = tmp_path / 'bad.pgn'
    src.write_text('[Event "E"]\n[FEN "not-a-position"]\n1.Ke2 *\n\n'
                   '[Event "G"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n',
                   encoding='utf-8')
    noisy = subprocess.run(
        [sys.executable, 'fen2rtf.py', str(src), '-o', str(tmp_path / 'a.pdf')],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    quiet = subprocess.run(
        [sys.executable, 'fen2rtf.py', str(src), '-o', str(tmp_path / 'b.pdf'), '--quiet'],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    assert 'skipped' in noisy.stderr
    assert quiet.stderr.strip() == ''
    assert quiet.returncode == 0


def test_verbose_shows_the_library_diagnostics(tmp_path):
    src = tmp_path / 'in.pgn'
    src.write_text('[Event "E"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n',
                   encoding='utf-8')
    result = subprocess.run(
        [sys.executable, 'fen2rtf.py', str(src), '-o', str(tmp_path / 'out.pdf'), '--verbose'],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0
    assert 'DEBUG' in result.stderr
