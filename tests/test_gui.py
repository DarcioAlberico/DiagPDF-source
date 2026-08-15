"""The interface's logic, exercised without a display.

The window itself is smoke-tested at the end; everything else lives in modules
that do not import tkinter, which is what makes it testable at all.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from conftest import PGN_THREE_GAMES, PROJECT_ROOT

from diagpdf.gui import filetypes, preview
from diagpdf.gui import settings as settings_mod
from diagpdf.gui.worker import Failed, Finished, GenerationJob, Progress, Stopped
from diagpdf.i18n import LANGS, T, missing_translations, tr
from diagpdf.layouts import LAYOUTS

# ── i18n catalogue ────────────────────────────────────────────────────────────

def test_every_key_covers_every_language():
    assert missing_translations() == {}


def test_every_language_has_a_name_of_its_own():
    """--list-languages prints these; a missing one would show a bare code."""
    from diagpdf.i18n import LANG_NAMES, lang_label
    assert set(LANG_NAMES) == set(LANGS)
    for code in LANGS:
        endonym, english = LANG_NAMES[code]
        assert endonym.strip() and english.strip()
        assert english in lang_label(code)


def test_no_translation_is_blank():
    blanks = [
        (key, lang) for key, entry in T.items() for lang in LANGS
        if isinstance(entry[lang], str) and not entry[lang].strip()
    ]
    assert blanks == []


@pytest.mark.parametrize('lang', LANGS)
def test_translations_differ_from_english_where_they_should(lang):
    """A catalogue that silently fell back to English would look complete."""
    if lang == 'en':
        return
    translated = sum(1 for entry in T.values()
                     if isinstance(entry['en'], str) and entry[lang] != entry['en'])
    assert translated > len(T) * 0.5, f'{lang} looks mostly untranslated'


def test_unknown_keys_return_themselves():
    assert tr('no_such_key', 'pt') == 'no_such_key'


def test_an_unknown_language_falls_back_to_english():
    assert tr('cancel', 'de') == tr('cancel', 'en')


@pytest.mark.parametrize('lang', LANGS)
def test_every_layout_has_a_label(lang):
    for layout in LAYOUTS:
        assert layout.label(lang).strip()


def test_layout_fields_are_named_and_indexable():
    layout = LAYOUTS[2]
    assert (layout.cols, layout.rows_plain, layout.rows_lined) == (layout[3], layout[4], layout[5])
    assert layout.chess_pt == layout[6]


# ── Settings ──────────────────────────────────────────────────────────────────

def test_defaults_are_valid():
    s = settings_mod.Settings()
    assert s.font in {*__import__('diagpdf').FONT_NAMES}
    assert s.lang in LANGS
    assert 0 <= s.layout < len(LAYOUTS)


def test_a_stale_font_name_is_replaced():
    """A saved config naming a font that is no longer bundled must not stick.

    Asserted against what is actually installed rather than against a literal:
    naming a real font here only tests the fallback until someone drops that
    font into Fonts/, at which point the test quietly stops testing anything.
    """
    s = settings_mod.Settings(font='NoSuchBoardFont', figurine_font='NoSuchFigurine')
    assert s.font in settings_mod.FONT_FILES
    assert s.figurine_font in settings_mod.FIGURINE_FILES


@pytest.mark.parametrize('field, bad, low, high', [
    ('layout', 99, 0, len(LAYOUTS) - 1),
    ('layout', -5, 0, len(LAYOUTS) - 1),
    ('lines_count', 42, 0, 5),
    ('answers_cols', 7, 1, 2),
    ('font_size', -3, 0, 200),
])
def test_out_of_range_values_are_clamped(field, bad, low, high):
    value = getattr(settings_mod.Settings(**{field: bad}), field)
    assert low <= value <= high


@pytest.mark.parametrize('field, bad', [
    ('lang', 'klingon'), ('theme', 'neon'), ('orient', 'sideways'),
    ('symbol', 'hexagon'), ('border_style', 'wavy'), ('lines_mode', 'cursive'),
])
def test_unknown_enum_values_fall_back(field, bad):
    value = getattr(settings_mod.Settings(**{field: bad}), field)
    assert value != bad


def test_round_trip(tmp_path):
    path = tmp_path / 'settings.json'
    original = settings_mod.Settings(lang='pt', theme='dark', lines_count=3, answers_cols=2)
    settings_mod.save_settings(original, path)
    assert settings_mod.load_settings(path) == original


def test_the_saved_file_carries_a_version(tmp_path):
    path = tmp_path / 'settings.json'
    settings_mod.save_settings(settings_mod.Settings(), path)
    assert json.loads(path.read_text(encoding='utf-8'))['version'] == settings_mod.SETTINGS_VERSION


def test_a_missing_file_gives_defaults(tmp_path):
    assert settings_mod.load_settings(tmp_path / 'nope.json') == settings_mod.Settings()


def test_corrupt_json_gives_defaults(tmp_path, capsys):
    path = tmp_path / 'settings.json'
    path.write_text('{ not json', encoding='utf-8')
    assert settings_mod.load_settings(path) == settings_mod.Settings()
    assert 'could not read' in capsys.readouterr().err


def test_a_json_array_gives_defaults(tmp_path, capsys):
    path = tmp_path / 'settings.json'
    path.write_text('[1, 2, 3]', encoding='utf-8')
    assert settings_mod.load_settings(path) == settings_mod.Settings()
    assert 'settings object' in capsys.readouterr().err


def test_unknown_keys_are_dropped(tmp_path):
    path = tmp_path / 'settings.json'
    path.write_text(json.dumps({'version': 2, 'lang': 'ru', 'from_a_future_release': 1}),
                    encoding='utf-8')
    assert settings_mod.load_settings(path).lang == 'ru'


def test_values_of_the_wrong_type_are_coerced(tmp_path):
    path = tmp_path / 'settings.json'
    path.write_text(json.dumps({'version': 2, 'lines_count': '3', 'coords': 0}), encoding='utf-8')
    loaded = settings_mod.load_settings(path)
    assert loaded.lines_count == 3 and loaded.coords is False


def test_version_1_answers_title_is_migrated(tmp_path):
    """v1 stored the English literal, which used to beat the chosen language."""
    path = tmp_path / 'settings.json'
    path.write_text(json.dumps({'lang': 'pt', 'answers_title': 'Solutions'}), encoding='utf-8')
    assert settings_mod.load_settings(path).answers_title == ''


def test_recent_files_are_most_recent_first():
    s = settings_mod.Settings()
    for name in ('a.pgn', 'b.pgn', 'c.pgn'):
        s.remember_file(name)
    assert s.recent_files == ['c.pgn', 'b.pgn', 'a.pgn']


def test_remembering_a_file_twice_does_not_duplicate_it():
    s = settings_mod.Settings()
    s.remember_file('a.pgn')
    s.remember_file('b.pgn')
    s.remember_file('a.pgn')
    assert s.recent_files == ['a.pgn', 'b.pgn']


def test_the_recent_list_is_bounded():
    s = settings_mod.Settings()
    for index in range(settings_mod.MAX_RECENT * 2):
        s.remember_file(f'{index}.pgn')
    assert len(s.recent_files) == settings_mod.MAX_RECENT


def test_recent_files_that_vanished_are_filtered(tmp_path):
    present = tmp_path / 'here.pgn'
    present.write_text('', encoding='utf-8')
    s = settings_mod.Settings(recent_files=[str(present), str(tmp_path / 'gone.pgn')])
    assert s.existing_recent_files() == [str(present)]


def test_settings_become_renderer_options():
    s = settings_mod.Settings(orient='black', lines_count=2, lang='pt')
    opts = settings_mod.settings_to_opts(s, number_offset=4, doc_title='Book')
    assert opts.flip is True and opts.flip_auto is False
    assert opts.lines_count == 2
    assert opts.number_offset == 4
    assert opts.doc_title == 'Book'
    assert opts.lang == 'pt'


def test_auto_orientation_maps_to_flip_auto():
    opts = settings_mod.settings_to_opts(settings_mod.Settings(orient='auto'))
    assert opts.flip is False and opts.flip_auto is True


# ── Save-dialog file types ────────────────────────────────────────────────────

@pytest.mark.parametrize('lang', LANGS)
def test_every_filter_label_maps_back_to_its_extension(lang):
    """The old code searched the translated label for the word "pdf"."""
    for label, _pattern in filetypes.save_filetypes(lang)[:-1]:
        extension = filetypes.extension_for_label(label, lang)
        assert extension in filetypes.SAVE_EXTENSIONS
        assert label == tr(filetypes._LABEL_KEYS[extension], lang)


@pytest.mark.parametrize('lang', LANGS)
def test_the_filter_list_covers_every_renderer(lang):
    """Every format is offered - alternative spellings share their format's entry."""
    import diagpdf
    patterns = {pattern.lstrip('*') for _label, pattern in filetypes.save_filetypes(lang)}
    assert set(diagpdf.GENERATORS) - set(filetypes.EXTENSION_ALIASES) <= patterns


def test_every_alias_points_at_a_format_that_is_offered():
    import diagpdf
    for alias, target in filetypes.EXTENSION_ALIASES.items():
        assert alias in diagpdf.GENERATORS, alias
        assert target in filetypes.SAVE_EXTENSIONS, target
        assert diagpdf.GENERATORS[alias] is diagpdf.GENERATORS[target]


def test_an_unknown_label_falls_back_to_pdf():
    assert filetypes.extension_for_label('completely unrelated', 'en') == '.pdf'


def test_a_label_from_another_language_still_resolves():
    assert filetypes.extension_for_label(tr('filetype_epub', 'ru'), 'ru') == '.epub'


def test_the_extension_is_appended_when_missing():
    assert filetypes.normalize_output_path('book', '.epub').suffix == '.epub'


def test_an_explicit_extension_is_respected():
    assert filetypes.normalize_output_path('book.docx', '.epub').suffix == '.docx'


def test_an_empty_name_is_left_alone():
    assert filetypes.normalize_output_path('   ', '.pdf').name == ''


def test_the_default_output_sits_beside_the_input():
    out = filetypes.default_output_path(Path('/tmp/puzzles.pgn'), '.epub')
    assert out.name == 'puzzles.epub'


# ── Background generation ─────────────────────────────────────────────────────

def run_job(job: GenerationJob, timeout: float = 30.0) -> list:
    """Drive a job to completion the way the window's poll loop does."""
    events: list = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        events.extend(job.poll())
        if any(isinstance(e, (Finished, Failed, Stopped)) for e in events):
            break
        time.sleep(0.01)
    job.join(timeout=5)
    events.extend(job.poll())
    return events


def test_a_job_reports_progress_and_finishes(tmp_path, base_opts, positions):
    out = tmp_path / 'job.pdf'
    job = GenerationJob(positions, base_opts, out)
    job.start()
    events = run_job(job)
    assert any(isinstance(e, Progress) for e in events)
    assert isinstance(events[-1], Finished)
    assert events[-1].out_path == out
    assert out.exists()


def test_the_job_runs_off_the_calling_thread(tmp_path, base_opts, positions):
    seen: list[str] = []

    def generator(*_args, **kwargs):
        seen.append(threading.current_thread().name)
        kwargs['progress'](100)

    job = GenerationJob(positions, base_opts, tmp_path / 'x.pdf', generator=generator)
    job.start()
    run_job(job)
    assert seen and seen[0] != threading.current_thread().name


def test_a_failure_is_reported_rather_than_raised(tmp_path, base_opts, one_position):
    def generator(*_args, **_kwargs):
        raise RuntimeError('boom')

    job = GenerationJob(one_position, base_opts, tmp_path / 'x.pdf', generator=generator)
    job.start()
    events = run_job(job)
    assert isinstance(events[-1], Failed)
    assert 'boom' in str(events[-1].error)


def test_cancelling_stops_the_job_and_removes_the_part_file(tmp_path, base_opts):
    out = tmp_path / 'cancelled.pdf'
    started = threading.Event()

    def generator(_positions, _opts, path, progress=None):
        Path(path).write_bytes(b'partial')
        started.set()
        for percent in range(100):
            progress(percent)          # raises Cancelled once cancel() is called
            time.sleep(0.01)

    job = GenerationJob([], base_opts, out, generator=generator)
    job.start()
    assert started.wait(5)
    job.cancel()
    events = run_job(job)
    assert isinstance(events[-1], Stopped)
    assert not out.exists(), 'a half-written file must not be left behind'


def test_cancelling_before_the_first_report_still_stops(tmp_path, base_opts, one_position):
    job = GenerationJob(one_position, base_opts, tmp_path / 'x.pdf')
    job.cancel()
    job.start()
    events = run_job(job)
    assert isinstance(events[-1], Stopped)


def test_polling_never_blocks(tmp_path, base_opts, one_position):
    job = GenerationJob(one_position, base_opts, tmp_path / 'x.pdf')
    assert job.poll() == []          # before it even starts


def test_progress_is_monotonic(tmp_path, base_opts, positions):
    job = GenerationJob(positions, base_opts, tmp_path / 'p.pdf')
    job.start()
    percents = [e.percent for e in run_job(job) if isinstance(e, Progress)]
    assert percents == sorted(percents)
    assert percents[-1] == 100


# ── Preview ───────────────────────────────────────────────────────────────────

def test_the_preview_renders_a_png(base_opts):
    png = preview.render_preview_png(base_opts)
    assert png.startswith(b'\x89PNG\r\n\x1a\n')


def test_the_preview_reacts_to_the_settings(base_opts):
    plain = preview.render_preview_png(dict(base_opts))
    lined = preview.render_preview_png({**base_opts, 'lines_count': 4, 'lines_mode': 'numbered'})
    flipped = preview.render_preview_png({**base_opts, 'flip': True, 'flip_auto': False})
    assert len({plain, lined, flipped}) == 3


def test_the_preview_grows_with_the_notation_lines(base_opts):
    from io import BytesIO

    from PIL import Image
    short = Image.open(BytesIO(preview.render_preview_png(base_opts))).height
    tall = Image.open(BytesIO(preview.render_preview_png({**base_opts, 'lines_count': 5}))).height
    assert tall > short


@pytest.mark.parametrize('border', ['simple', 'double', 'none'])
def test_the_preview_handles_every_border(base_opts, border):
    assert preview.render_preview_png({**base_opts, 'border_style': border, 'coords': False})


def test_the_preview_uses_the_given_position(base_opts):
    a = preview.render_preview_png(base_opts, {'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1', 'moves': ''})
    b = preview.render_preview_png(base_opts)
    assert a != b


def test_an_unknown_font_gives_a_message_not_a_crash(base_opts):
    with pytest.raises(preview.PreviewUnavailable):
        preview.render_preview_png({**base_opts, 'font': 'AlphaDG'})


def test_the_preview_fits_the_panel(base_opts):
    from io import BytesIO

    from PIL import Image
    image = Image.open(BytesIO(preview.render_preview_png(base_opts, max_width=200)))
    assert image.width <= 260      # board plus margins and the side indicator


# ── The window ────────────────────────────────────────────────────────────────

BUILD_AND_CLOSE = '''
import tkinter as tk
import fen2rtf
_real = tk.Misc.mainloop
tk.Misc.mainloop = lambda self, *a, **k: (self.after(1200, self.quit), _real(self, *a, **k))[1]
fen2rtf.run_gui()
print("OK")
'''


@pytest.mark.slow
def test_the_window_builds_cycles_languages_and_closes(tmp_path, monkeypatch):
    """Startup measures the window in all four languages, so this covers them."""
    env = {**dict(__import__('os').environ), 'HOME': str(tmp_path), 'USERPROFILE': str(tmp_path)}
    result = subprocess.run(
        [sys.executable, '-c', BUILD_AND_CLOSE],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), env=env, timeout=180,
    )
    assert 'OK' in result.stdout, result.stderr


@pytest.mark.slow
def test_the_window_starts_from_a_corrupt_settings_file(tmp_path):
    (tmp_path / '.diagpdf.json').write_text('{ broken', encoding='utf-8')
    env = {**dict(__import__('os').environ), 'HOME': str(tmp_path), 'USERPROFILE': str(tmp_path)}
    result = subprocess.run(
        [sys.executable, '-c', BUILD_AND_CLOSE],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT), env=env, timeout=180,
    )
    assert 'OK' in result.stdout, result.stderr
