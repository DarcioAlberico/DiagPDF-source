"""The options object: defaults, normalisation, validation, and the dict boundary."""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest
from conftest import PROJECT_ROOT

import diagpdf
from diagpdf.i18n import DEFAULT_LANG
from diagpdf.layouts import DEFAULT_LAYOUT, LAYOUTS
from diagpdf.options import ALIASES, RenderOptions
from diagpdf.page import DEFAULT_MARGIN_LR, DEFAULT_MARGIN_TB, DEFAULT_PAGE_SIZE

FIELD_NAMES = {f.name for f in fields(RenderOptions)}


# ── Defaults ──────────────────────────────────────────────────────────────────

def test_every_option_has_a_default():
    """RenderOptions() must be constructible — it is the reference document."""
    opts = RenderOptions()
    assert opts.layout_idx == DEFAULT_LAYOUT
    assert opts.lang == DEFAULT_LANG
    assert opts.page_size == DEFAULT_PAGE_SIZE
    assert opts.font and opts.figurine_font       # resolved from the shipped fonts


def test_the_defaults_render_in_every_format(tmp_path, one_position, out_format):
    """A bare options object is a valid document in all five formats."""
    out = tmp_path / f'default{out_format}'
    diagpdf.generate_output(one_position, RenderOptions(), out)
    assert out.exists() and out.stat().st_size > 0


# ── The six defaults that used to disagree ────────────────────────────────────
#
# Each renderer carried its own fallback for these, and the fallbacks differed:
# a partial options dict produced a footer in PDF and none in DOCX. There is now
# one default per option, so the formats cannot drift apart again.

@pytest.mark.parametrize('name, expected', [
    ('answers_section', False),
    ('show_header', True),      # the CLI (--no-header) and the GUI both default to shown
    ('show_footer', True),
    ('lang', DEFAULT_LANG),
])
def test_the_previously_disagreeing_defaults_are_pinned(name, expected):
    assert getattr(RenderOptions(), name) == expected


def test_the_font_defaults_resolve_to_a_real_file():
    """'' used to reach the CSS family name while the file came from the default."""
    from diagpdf.fonts import _default_board_font_name, _default_figurine_font_name

    opts = RenderOptions()
    assert opts.font == _default_board_font_name()
    assert opts.figurine_font == _default_figurine_font_name()


def test_a_shown_but_empty_header_draws_nothing():
    """show_header defaults to True, so blank text must be what silences it."""
    assert RenderOptions().header_text == ''
    assert RenderOptions().footer_text == ''
    assert RenderOptions(header='H').header_text == 'H'
    assert RenderOptions(header='H', show_header=False).header_text == ''
    assert RenderOptions(footer='F', show_footer=False).footer_text == ''


def test_no_renderer_keeps_its_own_option_fallbacks():
    """The structural guarantee: stringly-typed access is gone from the renderers.

    A single ``opts.get('x', <default>)`` creeping back into one renderer is how
    the formats drifted apart in the first place.
    """
    offenders = []
    for path in sorted((PROJECT_ROOT / 'diagpdf').rglob('*.py')):
        if path.name == 'options.py':
            continue          # the boundary itself reads the incoming dict
        text = path.read_text(encoding='utf-8')
        if re.search(r"""\bopts(\.get\(|\[)\s*['"]""", text):
            offenders.append(str(path.relative_to(PROJECT_ROOT)))
    assert offenders == []


# ── Normalisation ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize('given, expected', [
    (-1, 0), (0, 0), (len(LAYOUTS) - 1, len(LAYOUTS) - 1), (len(LAYOUTS), len(LAYOUTS) - 1), (999, len(LAYOUTS) - 1),
])
def test_the_layout_index_is_clamped(given, expected):
    assert RenderOptions(layout_idx=given).layout_idx == expected


@pytest.mark.parametrize('given, expected', [(0, 1), (1, 1), (2, 2), (5, 2)])
def test_the_answer_columns_are_clamped(given, expected):
    assert RenderOptions(answers_cols=given).answers_cols == expected


@pytest.mark.parametrize('name, given, expected', [
    ('font_size', -5, 0),
    ('text_size', -5, 0),
    ('lines_count', -1, 0),
    ('number_start', 0, 1),
    ('number_start', -3, 1),
    ('number_offset', -2, 0),
])
def test_sizes_and_counts_never_go_negative(name, given, expected):
    assert getattr(RenderOptions(**{name: given}), name) == expected


def test_the_page_size_is_case_insensitive():
    assert RenderOptions(page_size='A4').page_size == 'a4'
    assert RenderOptions(page_size='LETTER').page_size == 'letter'


def test_text_options_survive_a_none_from_a_config_file():
    opts = RenderOptions(header=None, doc_title=None, number_format=None)
    assert opts.header == '' and opts.doc_title == '' and opts.number_format == ''


@pytest.mark.parametrize('given, expected', [
    (None, None), ((), None), ((3, 4), (3, 4)), (['3', '4'], (3, 4)),
    ((0, 3), None), ((3, 0), None), ('nonsense', None),
])
def test_the_grid_becomes_a_pair_or_nothing(given, expected):
    assert RenderOptions(grid=given).grid == expected


# ── Validation ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('name, bad, fallback', [
    ('symbol', 'hexagon', 'square'),
    ('border_style', 'dotted', 'simple'),
    ('lang', 'xx', DEFAULT_LANG),
    ('page_size', 'a9', DEFAULT_PAGE_SIZE),
    ('html_font_mode', 'inline', 'embed'),
    ('lines_mode', 'roman', 'plain'),
    ('title_mode', 'poetic', 'comment'),
])
def test_an_unknown_name_is_reported_and_replaced(name, bad, fallback, capsys):
    """Silently misrendering is the failure mode this whole phase exists to stop."""
    assert getattr(RenderOptions(**{name: bad}), name) == fallback
    assert bad in capsys.readouterr().err


@pytest.mark.parametrize('name, bad, fallback', [
    ('font_size', 'huge', 0),
    ('margin_lr', 'wide', DEFAULT_MARGIN_LR),
    ('margin_tb', None, DEFAULT_MARGIN_TB),
])
def test_a_value_that_is_not_a_number_is_reported_and_replaced(name, bad, fallback, capsys):
    assert getattr(RenderOptions(**{name: bad}), name) == fallback
    assert capsys.readouterr().err.strip()


def test_an_unknown_option_name_is_reported(capsys):
    opts = RenderOptions.from_dict({'font_size': 12, 'colour_scheme': 'dark'})
    assert opts.font_size == 12
    assert 'colour_scheme' in capsys.readouterr().err


# ── The boundary with the legacy dict ─────────────────────────────────────────

def test_a_dict_round_trips_through_the_object():
    opts = RenderOptions(font_size=14, answers_section=True, header='H')
    assert RenderOptions.from_dict(opts.to_dict()) == opts


def test_to_dict_covers_every_field():
    assert set(RenderOptions().to_dict()) == FIELD_NAMES


@pytest.mark.parametrize('old, current', sorted(ALIASES.items()))
def test_the_old_option_names_still_work(old, current):
    assert getattr(RenderOptions.from_dict({old: True}), current) is True


def test_the_current_name_wins_over_its_alias():
    opts = RenderOptions.from_dict({'lichess_link': True, 'lichess': False})
    assert opts.lichess_link is True


def test_coerce_accepts_what_the_renderers_are_handed():
    opts = RenderOptions(font_size=9)
    assert RenderOptions.coerce(opts) is opts               # already converted
    assert RenderOptions.coerce({'font_size': 9}) == opts
    assert RenderOptions.coerce(None) == RenderOptions()
    with pytest.raises(TypeError):
        RenderOptions.coerce(['font_size', 9])


def test_replace_revalidates():
    assert RenderOptions().replace(answers_cols=9).answers_cols == 2


# ── The front ends ────────────────────────────────────────────────────────────

def _cli_opts(argv: list[str] = ('book.pgn',)) -> RenderOptions:
    """Build the options the CLI would use for *argv*, without converting anything."""
    from diagpdf.cli import _build_opts, _make_parser

    return _build_opts(_make_parser().parse_args(list(argv)), 'book', 0, None)


def test_the_cli_builds_the_options_object():
    opts = _cli_opts()
    assert isinstance(opts, RenderOptions)
    assert opts.header == 'book' and opts.doc_title == 'book'


def test_the_gui_builds_the_options_object():
    from diagpdf.gui.settings import Settings, settings_to_opts

    assert isinstance(settings_to_opts(Settings()), RenderOptions)


def test_the_cli_clamps_through_the_options_object():
    """The clamping moved out of _build_opts; it must still happen."""
    assert _cli_opts(['book.pgn', '--layout', '99']).layout_idx == len(LAYOUTS) - 1
    assert _cli_opts(['book.pgn', '--number-start', '0']).number_start == 1


def test_the_two_front_ends_agree_on_every_shared_option():
    """Whatever the CLI and the GUI both leave alone must mean the same thing."""
    from diagpdf.gui.settings import Settings, settings_to_opts

    cli = _cli_opts()
    gui = settings_to_opts(Settings(), doc_title='book')
    differing = {name for name in FIELD_NAMES if getattr(cli, name) != getattr(gui, name)}
    # The CLI stamps the input name into the running header and footer and
    # supplies a title template; the window has its own fields for those.
    # doc_language is stored differently but resolves the same — checked below.
    assert differing <= {'header', 'footer', 'title_template', 'doc_language'}


def test_the_two_front_ends_resolve_the_same_document_language():
    """The GUI stores the language explicitly, the CLI falls back to --lang."""
    from diagpdf.gui.settings import Settings, settings_to_opts

    def effective(opts):
        return opts.doc_language.strip() or opts.lang

    assert effective(_cli_opts()) == effective(settings_to_opts(Settings()))
