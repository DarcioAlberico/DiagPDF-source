"""Font discovery, resolution, licence policy and VDMX patching."""

from __future__ import annotations

import pytest
from conftest import MISSING_FONT, START_FEN, board_from_diagram

import fen2rtf as F

FONTS_DIR = F._resource('Fonts')


# ── Discovery ─────────────────────────────────────────────────────────────────

def test_some_board_fonts_were_discovered():
    assert F.FONT_NAMES, 'no board fonts found in Fonts/'
    assert F.FONT_FILES.keys() == set(F.FONT_NAMES)


def test_every_discovered_font_file_exists():
    for name, file_name in F.FONT_FILES.items():
        assert (FONTS_DIR / file_name).is_file(), f'{name} -> {file_name}'


def test_figurine_fonts_are_kept_separate_from_board_fonts():
    assert F.FIGURINE_NAMES
    assert not set(F.FIGURINE_NAMES) & set(F.FONT_NAMES)
    for file_name in F.FIGURINE_FILES.values():
        assert 'figurine' in file_name.lower()


def test_the_defaults_are_actually_available():
    assert F._default_board_font_name() in F.FONT_FILES
    assert F._default_figurine_font_name() in F.FIGURINE_FILES


def test_preferred_fonts_are_listed_first():
    """ChessMerida heads the list so the GUI opens on the recommended font."""
    assert F.FONT_NAMES[0] == 'ChessMerida'


def test_each_font_is_classified_into_exactly_one_character_map():
    for name in F.FONT_NAMES:
        info = F._BOARD_FONT_INFO[name]
        assert info.legacy_dg != (name in F.MERIDA_COMPATIBLE_FONTS)


def test_the_bundled_dg_fonts_address_glyphs_through_the_private_use_area():
    """The shipped *DG* files are symbol-encoded, so their glyphs sit at U+F0xx.

    Which piece map a font needs and how its glyphs are addressed are two
    separate things: an Alpha-layout font with an ordinary Unicode cmap is
    perfectly possible, and is addressed directly. The claim is therefore made
    about the files that actually have that encoding, not about the layout.
    """
    for name in F.FONT_NAMES:
        if not name.endswith('DG'):
            continue
        assert name not in F.DIRECT_PDF_CHESS_FONTS, f'{name} should be reached through the PUA'


@pytest.mark.parametrize('name', F.FONT_NAMES)
def test_every_font_draws_the_position_it_was_given(name):
    """Decode the diagram back and compare it square by square with the FEN.

    The per-font tests used to check only that a non-empty file came out, which
    a font given the wrong character map passes happily — it just draws the
    wrong pieces, or none. Reading the board back is what catches that.
    """
    lines = F.fen_to_diagram(START_FEN, coords=True, font_name=name, border_style='simple')
    decoded = board_from_diagram(lines, name, has_border=True)
    expected, _ = F.parse_fen(START_FEN)
    assert decoded == list(reversed(expected)), f'{name} did not draw the starting position'


@pytest.mark.parametrize('name', F.FONT_NAMES)
def test_every_font_can_draw_every_character_it_is_handed(name):
    """A font missing a glyph renders a hole; the renderers cannot report it."""
    lines = F.fen_to_diagram(START_FEN, coords=True, font_name=name, border_style='simple')
    from diagpdf.fonts import _font_codepoints

    codepoints = _font_codepoints(FONTS_DIR / F.FONT_FILES[name])
    missing = sorted({
        ch for ch in ''.join(lines)
        if ch != ' ' and ord(ch) not in codepoints and (0xF000 + ord(ch)) not in codepoints
    })
    assert not missing, f'{name} has no glyph for {missing}'


def test_a_font_is_classified_by_its_glyphs_not_its_file_name():
    """AlphaDG earned its map by ending in "DG"; that was never the real rule."""
    for name, info in F._BOARD_FONT_INFO.items():
        if info.legacy_dg and not name.endswith('DG'):
            break
    else:
        pytest.skip('no Alpha-layout font with a non-DG name is installed')
    assert name not in F.MERIDA_COMPATIBLE_FONTS


def test_the_piece_map_and_the_encoding_are_independent():
    """Every font must be classified on both axes without one implying the other."""
    for name in F.FONT_NAMES:
        info = F._BOARD_FONT_INFO[name]
        assert isinstance(info.legacy_dg, bool)
        assert (name in F.DIRECT_PDF_CHESS_FONTS) == info.direct_pdf


# ── Resolution ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('name', F.FONT_NAMES)
def test_known_fonts_resolve_to_a_real_file(name):
    assert (FONTS_DIR / F.resolve_board_font(name)).is_file()


@pytest.mark.parametrize('name', [MISSING_FONT, 'ZurichFigurine', '', 'Comic Sans'])
def test_unknown_fonts_raise_with_a_usable_message(name):
    with pytest.raises(F.UnknownFontError) as excinfo:
        F.resolve_board_font(name)
    message = str(excinfo.value)
    assert repr(name) in message
    assert 'Available' in message
    assert F.FONT_NAMES[0] in message


def test_coerce_falls_back_and_says_so(capsys):
    assert F.coerce_board_font(MISSING_FONT) == F._default_board_font_name()
    err = capsys.readouterr().err
    assert 'unknown board font' in err and MISSING_FONT in err


def test_coerce_leaves_a_known_font_alone(capsys):
    name = F.FONT_NAMES[0]
    assert F.coerce_board_font(name) == name
    assert capsys.readouterr().err == ''


def test_resolution_is_case_sensitive():
    """Font names come from file stems, so casing has to match exactly."""
    with pytest.raises(F.UnknownFontError):
        F.resolve_board_font(F.FONT_NAMES[0].lower())


# ── Family names ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize('name', F.FONT_NAMES)
def test_every_font_reports_a_family_name(name):
    family = F._board_font_family_name(name)
    assert family and not family.isspace()


def test_family_names_are_read_from_the_font_not_the_filename():
    assert F._board_font_family_name('ChessMerida') == 'Chess Merida'


def test_css_family_names_are_lowercase_and_stable():
    assert F._css_font_family('ChessMerida') == 'merida'
    assert F._css_font_family('LeipzigDG') == 'leipzigdg'


# ── Licence policy ────────────────────────────────────────────────────────────

@pytest.mark.parametrize('name', F.FONT_NAMES)
def test_embedding_policy_returns_two_booleans(name):
    can_embed, can_subset = F.font_embedding_allowed(FONTS_DIR / F.FONT_FILES[name])
    assert isinstance(can_embed, bool) and isinstance(can_subset, bool)


def test_the_known_restricted_fonts_are_flagged():
    """Two bundled fonts carry a non-embeddable fsType; the rest do not."""
    restricted = {
        name for name in F.FONT_NAMES
        if not F.font_embedding_allowed(FONTS_DIR / F.FONT_FILES[name])[0]
    }
    assert restricted == {'Chess Adventurer', 'Chess Cases'}


def test_a_missing_font_file_is_treated_permissively():
    assert F.font_embedding_allowed(FONTS_DIR / 'does-not-exist.ttf') == (True, True)


def test_permitted_fonts_pass_the_check(capsys):
    path = FONTS_DIR / F.FONT_FILES['ChessMerida']
    assert F.check_embedding_permitted(path, 'EPUB', allow_restricted=False)
    assert capsys.readouterr().err == ''


def test_restricted_fonts_are_refused_with_an_explanation(capsys):
    path = FONTS_DIR / F.FONT_FILES['Chess Cases']
    assert not F.check_embedding_permitted(path, 'EPUB', allow_restricted=False)
    err = capsys.readouterr().err
    assert 'non-embeddable' in err and 'EPUB' in err
    assert '--allow-restricted-fonts' in err


def test_the_override_is_honoured_and_still_warns(capsys):
    path = FONTS_DIR / F.FONT_FILES['Chess Cases']
    assert F.check_embedding_permitted(path, 'DOCX', allow_restricted=True)
    assert 'anyway' in capsys.readouterr().err


# ── Patching and loading ──────────────────────────────────────────────────────

@pytest.mark.parametrize('name', F.FONT_NAMES)
def test_every_board_font_resolves_to_a_loadable_path(name):
    from pathlib import Path
    path = Path(F.get_chess_font_path(name, FONTS_DIR))
    assert path.is_file()
    assert path.suffix.lower() in ('.ttf', '.otf')


def test_patching_leaves_fonts_without_a_vdmx_table_alone(tmp_path):
    source = FONTS_DIR / F.FONT_FILES['ChessMerida']
    copy = tmp_path / source.name
    copy.write_bytes(source.read_bytes())
    patched = tmp_path / (copy.stem + '_patch.ttf')
    result = F._ensure_chess_font_patched(copy, patched)
    assert result == str(copy)
    assert not patched.exists()


def test_patching_reuses_an_existing_patched_copy(tmp_path):
    original = tmp_path / 'x.ttf'
    original.write_bytes(b'not a font')
    patched = tmp_path / 'x_patch.ttf'
    patched.write_bytes(b'already patched')
    assert F._ensure_chess_font_patched(original, patched) == str(patched)


def test_patching_a_missing_font_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        F._ensure_chess_font_patched(tmp_path / 'gone.ttf', tmp_path / 'gone_patch.ttf')


def test_a_corrupt_font_falls_back_to_the_original(tmp_path):
    original = tmp_path / 'broken.ttf'
    original.write_bytes(b'definitely not a font')
    patched = tmp_path / 'broken_patch.ttf'
    assert F._ensure_chess_font_patched(original, patched) == str(original)
    assert not patched.exists(), 'a partial patch file must not be left behind'


# ── Every font can actually render ────────────────────────────────────────────

@pytest.mark.slow
@pytest.mark.parametrize('name', F.FONT_NAMES)
def test_every_font_renders_a_diagram(name):
    lines = F.fen_to_diagram(
        'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        font_name=name,
    )
    assert len(lines) in (8, 10)
    assert all(line.strip() for line in lines)


@pytest.mark.slow
@pytest.mark.parametrize('name', F.FONT_NAMES)
def test_every_font_produces_a_pdf(name, tmp_path, base_opts, one_position):
    base_opts['font'] = name
    out = tmp_path / f'{name}.pdf'
    F.generate_pdf(one_position, base_opts, out)
    assert out.stat().st_size > 1000


@pytest.mark.slow
@pytest.mark.parametrize('name', F.FIGURINE_NAMES)
def test_every_figurine_font_produces_an_answers_section(name, tmp_path, base_opts, one_position):
    base_opts.update(answers_section=True, figurine_font=name)
    out = tmp_path / f'fig_{name}.pdf'
    F.generate_pdf(one_position, base_opts, out)
    assert out.stat().st_size > 1000
