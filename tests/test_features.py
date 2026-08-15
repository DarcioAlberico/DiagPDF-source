"""Diagrams from move sequences, custom grids, numbering, batch and images."""

from __future__ import annotations

import re
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest
from conftest import PROJECT_ROOT

import diagpdf
from diagpdf import moves as moves_mod
from diagpdf.geometry import _compute_geometry
from diagpdf.layouts import LAYOUTS, custom_layout, parse_grid
from diagpdf.options import RenderOptions
from diagpdf.render.common import _format_number, _position_number
from diagpdf.svg import TEXT_FONT_STACK as TEXT_STACK

chess = pytest.importorskip('chess')

IMMORTAL = '''[Event "London"]
[White "Anderssen, Adolf"]
[Black "Kieseritzky, Lionel"]

1.e4 e5 2.f4 exf4 3.Bc4 Qh4+ 4.Kf1 b5 5.Bxb5 Nf6 6.Nf3 Qh6 7.d3 Nh5 8.Nh4 Qg5
9.Nf5 c6 10.g4 Nf6 11.Rg1 cxb5 12.h4 Qg6 13.h5 Qg5 14.Qf3 Ng8 15.Bxf4 Qf6
16.Nc3 Bc5 17.Nd5 {#diagram the double sacrifice} Qxb2 18.Bd6 Bxg1 19.e5 Qxa1+
20.Ke2 Na6 21.Nxg7+ Kd8 22.Qf6+ Nxf6 23.Be7# 1-0
'''

IMMORTAL_FINAL = 'r1bk3r/p2pBpNp/n4n2/1p1NP2P/6P1/3P4/P1P1K3/q5b1 b - - 1 23'

SHORT_GAME = '''[Event "Scholar"]

1.e4 e5 2.Bc4 Nc6 3.Qh5 Nf6 4.Qxf7# 1-0
'''


# ── Move selection parsing ────────────────────────────────────────────────────

@pytest.mark.parametrize('text, expected', [
    ('20', (20,)),
    ('20,25,30', (20, 25, 30)),
    ('30,20', (20, 30)),          # sorted
    ('20, 20', (20,)),            # de-duplicated
    ('', ()),
])
def test_at_move_values(text, expected):
    assert moves_mod.parse_move_selection(text).at_moves == expected


@pytest.mark.parametrize('text', ['last', 'end', 'final', 'LAST'])
def test_last_is_recognised(text):
    assert moves_mod.parse_move_selection(text).last is True


def test_last_can_be_mixed_with_numbers():
    selection = moves_mod.parse_move_selection('10,last')
    assert selection.at_moves == (10,) and selection.last is True


@pytest.mark.parametrize('text', ['abc', '3.5', '-1', '0'])
def test_invalid_at_move_values_are_rejected(text):
    with pytest.raises(ValueError):
        moves_mod.parse_move_selection(text)


def test_an_empty_selection_is_falsy():
    assert not moves_mod.parse_move_selection('')
    assert moves_mod.parse_move_selection('', every=5)
    assert moves_mod.parse_move_selection('', marker='#d')


# ── Ply arithmetic ────────────────────────────────────────────────────────────

def test_a_move_number_maps_to_blacks_reply():
    selection = moves_mod.MoveSelection(at_moves=(10,))
    assert moves_mod.selected_plies(46, selection, set()) == [20]


def test_a_move_past_the_end_clamps_to_the_last_ply():
    selection = moves_mod.MoveSelection(at_moves=(99,))
    assert moves_mod.selected_plies(45, selection, set()) == [45]


def test_every_n_moves():
    selection = moves_mod.MoveSelection(every=5)
    assert moves_mod.selected_plies(46, selection, set()) == [10, 20, 30, 40]


def test_marked_plies_are_kept():
    assert moves_mod.selected_plies(46, moves_mod.MoveSelection(), {7, 9}) == [7, 9]


# ── Replay ────────────────────────────────────────────────────────────────────

@pytest.fixture
def immortal():
    return diagpdf.parse_pgn(IMMORTAL, require_fen=False)


def test_a_game_without_a_fen_tag_used_to_produce_nothing():
    assert diagpdf.parse_pgn(IMMORTAL) == []
    assert len(diagpdf.parse_pgn(IMMORTAL, require_fen=False)) == 1


def test_the_final_position_is_correct(immortal):
    result = moves_mod.expand_positions(immortal, moves_mod.parse_move_selection('last'))
    assert len(result) == 1
    assert result[0]['fen'] == IMMORTAL_FINAL


def test_the_final_position_really_is_checkmate(immortal):
    result = moves_mod.expand_positions(immortal, moves_mod.parse_move_selection('last'))
    assert chess.Board(result[0]['fen']).is_checkmate()


def test_a_short_game_replays(immortal):
    games = diagpdf.parse_pgn(SHORT_GAME, require_fen=False)
    result = moves_mod.expand_positions(games, moves_mod.parse_move_selection('last'))
    assert chess.Board(result[0]['fen']).is_checkmate()


def test_several_points_in_one_game(immortal):
    result = moves_mod.expand_positions(immortal, moves_mod.parse_move_selection('10,20,last'))
    assert len(result) == 3
    assert [p['ply'] for p in result] == sorted(p['ply'] for p in result)


def test_every_n_produces_evenly_spaced_diagrams(immortal):
    result = moves_mod.expand_positions(immortal, moves_mod.parse_move_selection('', every=5))
    assert [p['ply'] for p in result] == [10, 20, 30, 40]


def test_a_comment_marker_selects_the_position(immortal):
    selection = moves_mod.parse_move_selection('', marker='#diagram')
    result = moves_mod.expand_positions(immortal, selection)
    assert len(result) == 1
    assert result[0]['ply'] == 33          # after 17.Nd5
    assert '#diagram' not in result[0]['comment']
    assert 'double sacrifice' in result[0]['comment']


def test_the_game_tags_are_carried_onto_each_diagram(immortal):
    result = moves_mod.expand_positions(immortal, moves_mod.parse_move_selection('last'))
    assert result[0]['white'] == 'Anderssen, Adolf'
    assert result[0]['event'] == 'London'


def test_the_default_comment_names_the_move(immortal):
    result = moves_mod.expand_positions(immortal, moves_mod.parse_move_selection('10'))
    assert result[0]['comment'] == '10...'


def test_variations_are_not_followed():
    """A move inside parentheses is an alternative, not the game."""
    pgn = '[Event "V"]\n\n1.e4 e5 2.Nf3 (2.f4 exf4 3.Bc4) Nc6 3.Bb5 *\n'
    games = diagpdf.parse_pgn(pgn, require_fen=False)
    result = moves_mod.expand_positions(games, moves_mod.parse_move_selection('last'))
    board = chess.Board(result[0]['fen'])
    assert board.piece_at(chess.B5) is not None          # 3.Bb5 was played
    assert board.piece_at(chess.F4) is None              # the 2.f4 line was not


def test_an_illegal_move_stops_that_game_with_a_warning(capsys):
    pgn = '[Event "Broken"]\n\n1.e4 e5 2.Qz9 Nc6 *\n'
    games = diagpdf.parse_pgn(pgn, require_fen=False)
    result = moves_mod.expand_positions(games, moves_mod.parse_move_selection('last'))
    assert len(result) == 1                              # what was legal is kept
    assert 'could not play' in capsys.readouterr().err


def test_a_game_with_a_fen_tag_replays_from_it():
    pgn = ('[Event "Endgame"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n\n1.Ke2 Kd7 2.Ke3 *\n')
    games = diagpdf.parse_pgn(pgn, require_fen=False)
    result = moves_mod.expand_positions(games, moves_mod.parse_move_selection('last'))
    assert chess.Board(result[0]['fen']).piece_at(chess.E3) is not None


def test_no_selection_leaves_the_positions_alone(immortal):
    assert moves_mod.expand_positions(immortal, moves_mod.MoveSelection()) is immortal


def test_a_game_with_no_moves_is_skipped():
    games = [{'fen': '', 'moves': ''}]
    assert moves_mod.expand_positions(games, moves_mod.parse_move_selection('last')) == []


# ── Custom grid ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize('text, expected', [
    ('3x4', (3, 4)), ('1x1', (1, 1)), (' 2 x 3 ', (2, 3)), ('2×3', (2, 3)), ('12x12', (12, 12)),
])
def test_grid_parsing(text, expected):
    assert parse_grid(text) == expected


@pytest.mark.parametrize('text', ['3', 'abc', '0x4', '4x0', '13x2', '', 'x'])
def test_invalid_grids_are_rejected(text):
    with pytest.raises(ValueError):
        parse_grid(text)


@pytest.mark.parametrize('cols, rows', [(1, 1), (2, 3), (3, 4), (4, 5), (6, 8), (12, 12)])
def test_a_custom_grid_fits_the_sheet(cols, rows):
    g = _compute_geometry({'grid': (cols, rows)})
    assert g.cols == cols
    assert g.per_page == cols * rows
    assert g.max_rows * g.row_h <= g.USABLE_H + 1e-6
    assert g.chess_pt >= 1


def test_a_custom_grid_beats_the_preset():
    g = _compute_geometry({'layout_idx': 0, 'grid': (4, 4)})
    assert g.cols == 4 and g.per_page == 16


def test_a_denser_grid_gets_a_smaller_board():
    assert _compute_geometry({'grid': (6, 8)}).chess_pt < _compute_geometry({'grid': (2, 2)}).chess_pt


def test_the_custom_layout_labels_itself():
    assert custom_layout(3, 4).label('en') == '3 - 12 dg/pg'


def test_a_custom_grid_reaches_the_html(tmp_path, base_opts, positions):
    out = tmp_path / 'grid.html'
    diagpdf.generate_html(positions, {**base_opts, 'grid': (5, 2)}, out)
    assert '--columns: 5;' in out.read_text(encoding='utf-8')


# ── Numbering ─────────────────────────────────────────────────────────────────

def test_numbering_starts_where_asked():
    assert [_position_number(i, RenderOptions(number_start=10)) for i in range(3)] == [10, 11, 12]


def test_the_start_and_the_offset_combine():
    assert _position_number(0, RenderOptions(number_start=5, number_offset=10)) == 15


@pytest.mark.parametrize('template, expected', [
    ('', '7'), ('#{n}', '#7'), ('Ex. {n}', 'Ex. 7'), ('{number})', '7)'),
])
def test_number_formats(template, expected):
    assert _format_number(7, RenderOptions(number_format=template)) == expected


def test_a_broken_number_format_falls_back():
    assert _format_number(7, RenderOptions(number_format='{bogus}')) == '7'
    assert _format_number(7, RenderOptions(number_format='{')) == '7'


def test_the_format_reaches_the_html(tmp_path, base_opts, positions):
    out = tmp_path / 'numbered.html'
    diagpdf.generate_html(positions, {
        **base_opts, 'number_format': '#{n}', 'answers_section': True,
    }, out)
    text = out.read_text(encoding='utf-8')
    assert '#1' in text


def test_a_formatted_number_still_splits_off_as_a_link(tmp_path, base_opts, positions):
    from diagpdf.render.common import _split_title_number_prefix
    opts = RenderOptions(number_format='#{n}')
    assert _split_title_number_prefix('#7 Mate', 7, opts) == ('#7 ', 'Mate')


# ── Images ────────────────────────────────────────────────────────────────────

def test_images_are_written(tmp_path, base_opts, positions):
    written = diagpdf.export_images(positions, base_opts, tmp_path / 'imgs')
    assert len(written) == len(positions)
    for path in written:
        assert path.exists() and path.read_bytes().startswith(b'\x89PNG')


def test_image_names_carry_the_number(tmp_path, base_opts, positions):
    written = diagpdf.export_images(positions, base_opts, tmp_path / 'imgs')
    assert written[0].name.startswith('0001_')


def test_an_unknown_image_format_is_rejected(tmp_path, base_opts, one_position):
    with pytest.raises(ValueError):
        diagpdf.export_images(one_position, base_opts, tmp_path, image_format='tiff')


def test_the_image_size_is_honoured(tmp_path, base_opts, one_position):
    from io import BytesIO

    from PIL import Image
    small = diagpdf.export_images(one_position, base_opts, tmp_path / 'a', row_px=20)[0]
    large = diagpdf.export_images(one_position, base_opts, tmp_path / 'b', row_px=60)[0]
    assert Image.open(BytesIO(large.read_bytes())).width > \
        Image.open(BytesIO(small.read_bytes())).width


def test_an_exported_image_is_titled_with_its_own_number(tmp_path, base_opts, positions):
    """Every picture used to carry the title of the first diagram."""
    from diagpdf.svg import render_diagram_svg
    marked = [render_diagram_svg(base_opts, position, number=index + 1)
              for index, position in enumerate(positions)]
    titles = [re.search(r'<title>(.*?)</title>', text).group(1) for text in marked]
    assert [title.split()[0] for title in titles] == [str(i + 1) for i in range(len(positions))]


# ── SVG export ────────────────────────────────────────────────────────────────

def test_svg_images_are_written(tmp_path, base_opts, positions):
    written = diagpdf.export_images(positions, base_opts, tmp_path / 'svgs', image_format='svg')
    assert len(written) == len(positions)
    for path in written:
        assert path.suffix == '.svg'
        ET.fromstring(path.read_text(encoding='utf-8'))       # well-formed XML


def test_the_svg_carries_outlines_not_text(tmp_path, base_opts, one_position):
    """The point of the vector export: no chess font needed to read it."""
    written = diagpdf.export_images(one_position, base_opts, tmp_path, image_format='svg')[0]
    text = written.read_text(encoding='utf-8')
    assert '<path id=' in text and '<use ' in text
    # The title is the only text element, and the only place a font is named.
    assert text.count('<text ') == 1
    assert text.count('font-family') == text.count(TEXT_STACK) == 1


@pytest.mark.parametrize('font', ['ChessMerida', 'chess-alpha'])
def test_the_svg_board_is_the_position_it_was_given(tmp_path, base_opts, font):
    """Decode the drawn squares back and compare them with the FEN.

    A wrong character map draws a legal-looking board of the wrong pieces, so
    the check has to run through the glyphs rather than stop at "a file exists".
    """
    from diagpdf.fen import fen_to_diagram
    from diagpdf.fonts import FONT_NAMES, get_chess_font_path
    from diagpdf.resources import _resource
    from diagpdf.svg import _Outlines, render_diagram_svg
    if font not in FONT_NAMES:
        pytest.skip(f'{font} is not installed')

    fen = 'r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4'
    base_opts.update(font=font, title_template=' ')
    svg = render_diagram_svg(base_opts, {'fen': fen})

    rows = fen_to_diagram(fen, coords=base_opts['coords'], font_name=font,
                          border_style=base_opts['border_style'])
    outlines = _Outlines(get_chess_font_path(font, _resource('Fonts')))
    try:
        expected = [outlines.reference(ch) for row in rows for ch in row]
    finally:
        outlines.close()
    drawn = re.findall(r'<use href="#(g\d+)"', svg)
    assert drawn == [ident for ident in expected if ident is not None]


def test_the_svg_only_asks_for_glyphs_the_font_has(tmp_path, base_opts, one_position, capsys):
    diagpdf.export_images(one_position, base_opts, tmp_path, image_format='svg')
    assert 'no glyph' not in capsys.readouterr().err


def test_the_cli_exports_svg(immortal_file, tmp_path):
    images = tmp_path / 'svgs'
    result = run_cli(str(immortal_file), '-o', str(tmp_path / 'b.pdf'), '--at-move', 'last',
                     '--export-images', str(images), '--image-format', 'svg')
    assert result.returncode == 0, result.stderr
    assert list(images.glob('*.svg'))


# ── Through the CLI ───────────────────────────────────────────────────────────

def run_cli(*args, cwd=None):
    return subprocess.run(
        [sys.executable, 'fen2rtf.py', *args],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        cwd=str(cwd or PROJECT_ROOT),
    )


@pytest.fixture
def immortal_file(tmp_path):
    path = tmp_path / 'immortal.pgn'
    path.write_text(IMMORTAL, encoding='utf-8')
    return path


def test_list_layouts(tmp_path):
    result = run_cli('--list-layouts')
    assert result.returncode == 0
    assert 'Layout presets' in result.stdout
    for layout in LAYOUTS:
        assert layout.label_en in result.stdout


def test_the_cli_takes_diagrams_from_moves(immortal_file, tmp_path):
    out = tmp_path / 'book.pdf'
    result = run_cli(str(immortal_file), '-o', str(out), '--at-move', '10,20,last')
    assert result.returncode == 0, result.stderr
    assert 'Converted 3 position(s)' in result.stdout
    assert out.exists()


def test_without_a_move_selection_a_plain_pgn_yields_nothing(immortal_file, tmp_path):
    result = run_cli(str(immortal_file), '-o', str(tmp_path / 'empty.pdf'))
    assert 'no positions found' in result.stderr


def test_an_invalid_at_move_is_reported(immortal_file, tmp_path):
    result = run_cli(str(immortal_file), '-o', str(tmp_path / 'x.pdf'), '--at-move', 'abc')
    assert result.returncode == 1
    assert 'invalid --at-move' in result.stderr


def test_an_invalid_grid_is_reported(immortal_file, tmp_path):
    result = run_cli(str(immortal_file), '-o', str(tmp_path / 'x.pdf'), '--grid', '99x1')
    assert result.returncode == 1
    assert 'out of range' in result.stderr


def test_dry_run_writes_nothing(immortal_file, tmp_path):
    out = tmp_path / 'nope.pdf'
    result = run_cli(str(immortal_file), '-o', str(out), '--at-move', 'last', '--dry-run')
    assert result.returncode == 0
    assert 'Would convert' in result.stdout
    assert not out.exists()


def test_batch_produces_one_document_per_input(tmp_path):
    first = tmp_path / 'a.pgn'
    second = tmp_path / 'b.pgn'
    for path in (first, second):
        path.write_text('[Event "E"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n',
                        encoding='utf-8')
    result = run_cli(str(first), str(second))
    assert result.returncode == 0, result.stderr
    assert first.with_suffix('.pdf').exists()
    assert second.with_suffix('.pdf').exists()


def test_merge_combines_the_inputs(tmp_path):
    first = tmp_path / 'a.pgn'
    second = tmp_path / 'b.pgn'
    first.write_text('[Event "A"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n', encoding='utf-8')
    second.write_text('[Event "B"]\n[FEN "8/8/8/8/8/5k2/8/5K2 w - - 0 1"]\n1.Kf2 *\n', encoding='utf-8')
    out = tmp_path / 'both.pdf'
    result = run_cli(str(first), str(second), '-o', str(out), '--merge')
    assert result.returncode == 0, result.stderr
    assert 'Converted 2 position(s)' in result.stdout
    assert out.exists()


def test_several_inputs_with_one_output_needs_merge(tmp_path):
    first = tmp_path / 'a.pgn'
    second = tmp_path / 'b.pgn'
    for path in (first, second):
        path.write_text('[Event "E"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n',
                        encoding='utf-8')
    result = run_cli(str(first), str(second), '-o', str(tmp_path / 'one.pdf'))
    assert result.returncode == 1
    assert '--merge' in result.stderr


def test_the_cli_exports_images(immortal_file, tmp_path):
    images = tmp_path / 'imgs'
    result = run_cli(str(immortal_file), '-o', str(tmp_path / 'b.pdf'),
                     '--at-move', 'last', '--export-images', str(images))
    assert result.returncode == 0, result.stderr
    assert 'image(s)' in result.stdout
    assert list(images.glob('*.png'))


def test_the_report_counts_skipped_positions(tmp_path):
    src = tmp_path / 'mixed.pgn'
    src.write_text(
        '[Event "Good"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n\n'
        '[Event "Bad"]\n[FEN "not-a-position"]\n1.Ke2 *\n',
        encoding='utf-8')
    result = run_cli(str(src), '-o', str(tmp_path / 'out.pdf'))
    assert '1 position(s) skipped as invalid' in result.stderr


def test_the_report_names_ignored_options(tmp_path):
    src = tmp_path / 'in.pgn'
    src.write_text('[Event "E"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n', encoding='utf-8')
    result = run_cli(str(src), '-o', str(tmp_path / 'out.epub'), '--page-size', 'a5')
    assert 'ignored by the target format' in result.stderr


def test_numbering_options_reach_the_cli(tmp_path):
    src = tmp_path / 'in.pgn'
    src.write_text('[Event "E"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n', encoding='utf-8')
    out = tmp_path / 'out.html'
    result = run_cli(str(src), '-o', str(out), '--number-start', '42', '--number-format', 'Ex. {n}')
    assert result.returncode == 0, result.stderr
    assert 'Ex. 42' in out.read_text(encoding='utf-8')
