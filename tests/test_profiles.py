"""Named profiles: storage, precedence against typed flags, and both front ends."""

from __future__ import annotations

import json
from dataclasses import fields

import pytest

from diagpdf import profiles as profiles_mod
from diagpdf.cli import OPTION_SOURCES, _build_opts, _make_parser, _typed_dests, main
from diagpdf.gui.settings import Settings, settings_from_opts, settings_to_opts
from diagpdf.options import RenderOptions
from diagpdf.profiles import ProfileError


@pytest.fixture
def store(tmp_path):
    """A profile file of this test's own, never the user's."""
    return tmp_path / 'profiles.json'


@pytest.fixture
def cli_store(tmp_path, monkeypatch):
    """Point the whole package at a throwaway profile file."""
    path = tmp_path / 'cli_profiles.json'
    monkeypatch.setattr(profiles_mod, 'PROFILES_PATH', path)
    return path


def parse(argv: list[str]):
    return _make_parser().parse_args(argv)


# ── Storage ───────────────────────────────────────────────────────────────────

def test_a_saved_profile_comes_back(store):
    profiles_mod.save('studies', {'answers_section': True, 'answers_cols': 2}, store)
    assert profiles_mod.load('studies', store) == {'answers_section': True, 'answers_cols': 2}


def test_only_the_choices_are_stored(store):
    """A profile is what was asked for, not all 48 options."""
    profiles_mod.save('small', RenderOptions(page_size='a5').to_dict(), store)
    assert profiles_mod.load('small', store) == {'page_size': 'a5'}


def test_a_profile_is_validated_as_it_is_saved(store):
    """A bad value is caught once, at save time, not on every later run."""
    from diagpdf.layouts import LAYOUTS

    profiles_mod.save('odd', {'answers_cols': 9, 'layout_idx': 999}, store)
    stored = profiles_mod.load('odd', store)
    assert stored['answers_cols'] == 2
    assert stored['layout_idx'] == len(LAYOUTS) - 1


def test_saving_twice_replaces_rather_than_duplicates(store):
    profiles_mod.save('one', {'cover': True}, store)
    profiles_mod.save('one', {'contents': True}, store)
    assert profiles_mod.load('one', store) == {'contents': True}
    assert list(profiles_mod.load_all(store)) == ['one']


def test_profiles_live_alongside_each_other(store):
    profiles_mod.save('a', {'cover': True}, store)
    profiles_mod.save('b', {'landscape': True}, store)
    assert sorted(profiles_mod.load_all(store)) == ['a', 'b']


def test_deleting_removes_only_the_one_named(store):
    profiles_mod.save('a', {'cover': True}, store)
    profiles_mod.save('b', {'landscape': True}, store)
    profiles_mod.delete('a', store)
    assert sorted(profiles_mod.load_all(store)) == ['b']


def test_an_absent_profile_says_what_is_available(store):
    profiles_mod.save('studies', {'cover': True}, store)
    with pytest.raises(ProfileError, match='studies'):
        profiles_mod.load('nope', store)
    with pytest.raises(ProfileError):
        profiles_mod.delete('nope', store)


def test_no_file_yet_is_not_an_error(store):
    assert profiles_mod.load_all(store) == {}


def test_a_damaged_file_is_reported_not_raised(store, capsys):
    store.write_text('{not json', encoding='utf-8')
    assert profiles_mod.load_all(store) == {}
    assert capsys.readouterr().err.strip()


def test_a_file_without_profiles_is_reported(store, capsys):
    store.write_text(json.dumps({'version': 1}), encoding='utf-8')
    assert profiles_mod.load_all(store) == {}
    assert capsys.readouterr().err.strip()


def test_entries_that_are_not_option_sets_are_skipped(store):
    store.write_text(json.dumps({'version': 1, 'profiles': {'ok': {'cover': True}, 'bad': 7}}),
                     encoding='utf-8')
    assert list(profiles_mod.load_all(store)) == ['ok']


def test_the_file_records_its_version(store):
    profiles_mod.save('a', {'cover': True}, store)
    assert json.loads(store.read_text(encoding='utf-8'))['version'] == profiles_mod.PROFILES_VERSION


# ── Names ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('name', ['studies', 'my book', 'a-b_c.1', 'Livro2'])
def test_ordinary_names_are_accepted(name):
    assert profiles_mod.check_name(f'  {name} ') == name


@pytest.mark.parametrize('name', ['', '   ', '../evil', 'a/b', 'a\\b', '.hidden', 'x' * 65])
def test_a_name_that_could_not_be_a_key_is_refused(name):
    """A profile name reaches the filesystem's neighbourhood; keep it plain."""
    with pytest.raises(ProfileError):
        profiles_mod.check_name(name)


# ── Which options the user actually typed ─────────────────────────────────────

def test_nothing_typed_is_nothing_reported():
    assert _typed_dests([]) == set()


def test_a_flag_set_to_its_own_default_still_counts_as_typed():
    """--layout 2 must beat a profile even though 2 is the default."""
    default_layout = parse([]).layout
    assert 'layout' in _typed_dests(['a.pgn', '--layout', str(default_layout)])


def test_only_what_was_typed_is_reported():
    typed = _typed_dests(['a.pgn', '--answers', '--page-size', 'a5'])
    assert {'answers', 'page_size'} <= typed
    assert 'layout' not in typed and 'font' not in typed


# ── Precedence ────────────────────────────────────────────────────────────────

def test_a_profile_supplies_what_was_not_typed():
    opts = _build_opts(parse(['a.pgn']), 'a', 0, None,
                       profile={'answers_section': True, 'page_size': 'a5'},
                       typed=_typed_dests(['a.pgn']))
    assert opts.answers_section is True
    assert opts.page_size == 'a5'


def test_a_typed_flag_beats_the_profile():
    argv = ['a.pgn', '--page-size', 'letter']
    opts = _build_opts(parse(argv), 'a', 0, None,
                       profile={'answers_section': True, 'page_size': 'a5'},
                       typed=_typed_dests(argv))
    assert opts.page_size == 'letter'      # typed
    assert opts.answers_section is True    # still from the profile


def test_a_typed_flag_beats_the_profile_even_at_its_default_value():
    argv = ['a.pgn', '--answers-cols', '1']
    opts = _build_opts(parse(argv), 'a', 0, None,
                       profile={'answers_cols': 2}, typed=_typed_dests(argv))
    assert opts.answers_cols == 1


def test_a_negative_flag_overrides_a_profile():
    """--no-header must switch off a header the profile switched on."""
    argv = ['a.pgn', '--no-header']
    opts = _build_opts(parse(argv), 'a', 0, None,
                       profile={'show_header': True}, typed=_typed_dests(argv))
    assert opts.show_header is False


def test_without_a_profile_everything_comes_from_the_command_line():
    """typed=None is the no-profile path, and must behave as it always did."""
    plain = _build_opts(parse(['a.pgn', '--answers']), 'a', 0, None)
    assert plain.answers_section is True
    assert plain.page_size == 'a4'
    assert plain.header == 'a' and plain.footer == '{page}'


def test_the_input_name_still_fills_an_unset_header_and_title():
    opts = _build_opts(parse(['a.pgn']), 'mybook', 0, None,
                       profile={}, typed=_typed_dests(['a.pgn']))
    assert opts.header == 'mybook' and opts.doc_title == 'mybook'


def test_a_profile_header_is_not_replaced_by_the_input_name():
    opts = _build_opts(parse(['a.pgn']), 'mybook', 0, None,
                       profile={'header': 'My Series'}, typed=_typed_dests(['a.pgn']))
    assert opts.header == 'My Series'


# ── The option table ──────────────────────────────────────────────────────────

def test_every_mapped_option_exists_on_both_sides():
    namespace = vars(parse([]))
    option_fields = {f.name for f in fields(RenderOptions)}
    for dest, field_name, _ in OPTION_SOURCES:
        assert dest in namespace, f'{dest} is not a command-line option'
        assert field_name in option_fields, f'{field_name} is not a render option'


def test_no_render_option_is_fed_by_two_command_line_options():
    mapped = [field_name for _, field_name, _ in OPTION_SOURCES]
    assert sorted(mapped) == sorted(set(mapped))


@pytest.mark.parametrize('argv, field_name, expected', [
    (['--no-coords'], 'coords', False),
    (['--no-auto-flip'], 'flip_auto', False),
    (['--no-footer'], 'show_footer', False),
    (['--lines-numbered'], 'lines_mode', 'numbered'),
    (['--answers'], 'answers_section', True),
    (['--border', 'none'], 'border_style', 'none'),
    (['--layout', '4'], 'layout_idx', 4),
    (['--epub-css', 'x.css'], 'epub_css_path', 'x.css'),
])
def test_the_options_that_are_not_named_alike_still_arrive(argv, field_name, expected):
    """The table is the only place these renamings live; a stale row would be silent."""
    full = ['a.pgn', *argv]
    opts = _build_opts(parse(full), 'a', 0, None, profile={}, typed=_typed_dests(full))
    assert getattr(opts, field_name) == expected


# ── The window ────────────────────────────────────────────────────────────────

def test_a_profile_becomes_window_settings():
    got = settings_from_opts({'answers_section': True, 'page_size': 'a5', 'layout_idx': 4})
    assert got.answers_section is True
    assert got.page_size == 'a5'
    assert got.layout == 4


def test_loading_a_profile_does_not_depend_on_what_was_on_screen():
    """Twice from different states must give the same result."""
    busy = Settings(cover=True, landscape=True, lines_count=4, answers_cols=2)
    values = {'page_size': 'a5'}
    assert settings_from_opts(values, busy) == settings_from_opts(values, Settings())


def test_the_window_keeps_its_own_state_when_a_profile_loads():
    base = Settings(lang='pt', theme='dark', recent_files=['a.pgn'])
    got = settings_from_opts({'page_size': 'a5', 'lang': 'ru'}, base)
    assert got.lang == 'pt'          # the interface language is not a document style
    assert got.theme == 'dark'
    assert got.recent_files == ['a.pgn']


@pytest.mark.parametrize('values, expected', [
    ({'flip': True}, 'black'),
    ({'flip_auto': False}, 'white'),
    ({'flip_auto': True}, 'auto'),
    ({}, 'auto'),
])
def test_the_two_flip_flags_become_one_orientation(values, expected):
    assert settings_from_opts(values).orient == expected


@pytest.mark.parametrize('orient', ['auto', 'white', 'black'])
def test_settings_survive_a_round_trip_through_a_profile(orient):
    original = Settings(orient=orient, answers_section=True, answers_cols=2,
                        page_size='a5', cover=True, lines_count=3, layout=4)
    stored = settings_to_opts(original).changed_from_defaults()
    assert settings_from_opts(stored, original) == original


# ── The command line, end to end ──────────────────────────────────────────────

def test_save_then_list_then_delete(cli_store, capsys):
    main(['--save-profile', 'studies', '--answers', '--page-size', 'a5'])
    assert 'studies' in capsys.readouterr().out

    main(['--list-profiles'])
    listed = capsys.readouterr().out
    assert 'studies' in listed and 'a5' in listed

    main(['--delete-profile', 'studies'])
    assert 'studies' in capsys.readouterr().out

    main(['--list-profiles'])
    assert 'No profiles saved yet' in capsys.readouterr().out


def test_listing_nothing_suggests_how_to_make_one(cli_store, capsys):
    main(['--list-profiles'])
    assert '--save-profile' in capsys.readouterr().out


def test_an_unusable_profile_name_stops_the_run(cli_store, capsys):
    with pytest.raises(SystemExit) as exc:
        main(['--save-profile', '../evil', '--answers'])
    assert exc.value.code == 1
    assert 'not a usable profile name' in capsys.readouterr().err


def test_asking_for_a_profile_that_is_not_there_stops_the_run(cli_store, capsys, tmp_path):
    source = tmp_path / 'in.fen'
    source.write_text('[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]', encoding='utf-8')
    with pytest.raises(SystemExit) as exc:
        main([str(source), '-o', str(tmp_path / 'out.pdf'), '--profile', 'nope'])
    assert exc.value.code == 1
    assert 'no profile called' in capsys.readouterr().err


def test_a_profile_reaches_the_document(cli_store, tmp_path, capsys):
    """The end the user cares about: the saved options change the PDF."""
    import re

    source = tmp_path / 'in.fen'
    source.write_text('[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]', encoding='utf-8')
    main(['--save-profile', 'small', '--page-size', 'a5'])

    out = tmp_path / 'out.pdf'
    main([str(source), '-o', str(out), '--profile', 'small', '-q'])
    width, height = re.search(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)',
                              out.read_bytes()).groups()
    assert round(float(width) * 25.4 / 72) == 148        # A5, not the default A4
    assert round(float(height) * 25.4 / 72) == 210


def test_a_flag_still_wins_over_the_profile_in_a_real_run(cli_store, tmp_path):
    import re

    source = tmp_path / 'in.fen'
    source.write_text('[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]', encoding='utf-8')
    main(['--save-profile', 'small', '--page-size', 'a5'])

    out = tmp_path / 'out.pdf'
    main([str(source), '-o', str(out), '--profile', 'small', '--page-size', 'a4', '-q'])
    width, _ = re.search(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)',
                         out.read_bytes()).groups()
    assert round(float(width) * 25.4 / 72) == 210


def test_a_profile_can_be_derived_from_another(cli_store, capsys):
    main(['--save-profile', 'base', '--answers'])
    main(['--profile', 'base', '--lines', '3', '--save-profile', 'derived'])
    derived = profiles_mod.load('derived', cli_store)
    assert derived['answers_section'] is True and derived['lines_count'] == 3


def test_saving_a_profile_does_not_store_the_input_name(cli_store, tmp_path):
    """header defaults to the input's stem, which must not be baked into a profile."""
    source = tmp_path / 'chapter1.fen'
    source.write_text('[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]', encoding='utf-8')
    main([str(source), '-o', str(tmp_path / 'o.pdf'), '--save-profile', 'plain', '-q'])
    assert 'header' not in profiles_mod.load('plain', cli_store)
    assert 'doc_title' not in profiles_mod.load('plain', cli_store)
