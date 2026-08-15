"""FEN parsing, validation and diagram rendering."""

from __future__ import annotations

import pytest
from conftest import BLACK_TO_MOVE_FEN, KINGS_FEN, START_FEN, board_from_diagram

# ── parse_fen ─────────────────────────────────────────────────────────────────

def test_start_position_placement(diagpdf):
    board, side = diagpdf.parse_fen(START_FEN)
    assert side == 'w'
    # board[rank_index][file_index] with rank_index 0 == rank 1
    assert board[0] == list('RNBQKBNR')
    assert board[1] == ['P'] * 8
    assert board[6] == ['p'] * 8
    assert board[7] == list('rnbqkbnr')
    assert all(square is None for rank in board[2:6] for square in rank)


def test_side_to_move(diagpdf):
    assert diagpdf.parse_fen(KINGS_FEN)[1] == 'w'
    assert diagpdf.parse_fen(BLACK_TO_MOVE_FEN)[1] == 'b'


def test_missing_side_field_defaults_to_white(diagpdf):
    assert diagpdf.parse_fen('4k3/8/8/8/8/8/8/4K3')[1] == 'w'


def test_unparseable_side_field_falls_back_to_white(diagpdf):
    assert diagpdf.parse_fen('4k3/8/8/8/8/8/8/4K3 x - - 0 1')[1] == 'w'


def test_empty_fen_raises(diagpdf):
    with pytest.raises(diagpdf.FenError):
        diagpdf.parse_fen('')
    with pytest.raises(diagpdf.FenError):
        diagpdf.parse_fen('   ')


# ── validate_fen ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize('fen', [
    START_FEN,
    KINGS_FEN,
    BLACK_TO_MOVE_FEN,
    '4k3/8/8/8/8/8/8/4K3 b - - 0 1',
    '4k3/8/8/8/8/8/8/4K3',                      # placement field alone
    'r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 4 4',
])
def test_valid_fens_report_no_problems(diagpdf, fen):
    assert diagpdf.validate_fen(fen) == []


@pytest.mark.parametrize('fen, expected_fragment', [
    ('',                                    'empty FEN'),
    ('   ',                                 'empty FEN'),
    ('8/8/8 w - - 0 1',                     'expected 8 ranks'),
    ('4k3/9/8/8/8/8/8/4K3 w - - 0 1',       'square(s) instead of 8'),
    ('4k3/8/8/8/8/8/8/4K4 w - - 0 1',       'square(s) instead of 8'),
    ('4k3/8/8/8/8/8/8/4K3 x - - 0 1',       'side to move'),
    ('8/8/8/8/8/8/8/8 w - - 0 1',           'king'),
    ('4k3/8/8/8/8/8/4K3/4K3 w - - 0 1',     'white has 2 king'),
    ('4kx2/8/8/8/8/8/8/4K3 w - - 0 1',      "invalid character 'x'"),
    ('4k3/08/8/8/8/8/8/4K3 w - - 0 1',      'not a valid skip count'),
])
def test_invalid_fens_are_reported(diagpdf, fen, expected_fragment):
    problems = diagpdf.validate_fen(fen)
    assert problems, f'{fen!r} should be reported as invalid'
    assert any(expected_fragment in p for p in problems), problems


def test_problem_messages_name_the_rank(diagpdf):
    problems = diagpdf.validate_fen('4k3/8/8/8/8/8/8/4K4 w - - 0 1')
    assert any('rank 1' in p for p in problems), problems


# ── fen_to_diagram: structure ─────────────────────────────────────────────────

def test_bordered_diagram_is_10x10(diagpdf):
    lines = diagpdf.fen_to_diagram(START_FEN, font_name='ChessMerida', border_style='simple')
    assert len(lines) == 10
    assert all(len(line) == 10 for line in lines)


def test_borderless_diagram_is_8x8(diagpdf):
    lines = diagpdf.fen_to_diagram(START_FEN, font_name='ChessMerida', border_style='none')
    assert len(lines) == 8
    assert all(len(line) == 8 for line in lines)


def test_legacy_dg_diagram_is_10x10(diagpdf):
    lines = diagpdf.fen_to_diagram(START_FEN, font_name='LeipzigDG', coords=True)
    assert len(lines) == 10
    assert all(len(line) == 10 for line in lines)


@pytest.mark.parametrize('font_name', ['ChessMerida', 'LeipzigDG'])
@pytest.mark.parametrize('coords', [True, False])
def test_row_lengths_are_uniform(diagpdf, font_name, coords):
    lines = diagpdf.fen_to_diagram(START_FEN, font_name=font_name, coords=coords)
    assert len({len(line) for line in lines}) == 1


# ── fen_to_diagram: placement round-trip ──────────────────────────────────────

@pytest.mark.parametrize('font_name, border', [
    ('ChessMerida', 'simple'),
    ('ChessMerida', 'double'),
    ('LeipzigDG', 'simple'),
])
def test_placement_round_trips_through_the_diagram(diagpdf, font_name, border):
    """FEN -> diagram -> board must reproduce the original placement."""
    board, _ = diagpdf.parse_fen(START_FEN)
    lines = diagpdf.fen_to_diagram(
        START_FEN, coords=True, font_name=font_name, border_style=border
    )
    decoded = board_from_diagram(lines, font_name, has_border=True)
    # Diagram rows run rank 8 down to rank 1; board[] runs rank 1 up to rank 8.
    assert decoded == list(reversed(board))


def test_placement_round_trips_without_border(diagpdf):
    board, _ = diagpdf.parse_fen(START_FEN)
    lines = diagpdf.fen_to_diagram(START_FEN, font_name='ChessMerida', border_style='none')
    decoded = board_from_diagram(lines, 'ChessMerida', has_border=False)
    assert decoded == list(reversed(board))


# ── fen_to_diagram: square colours ────────────────────────────────────────────

def test_square_colours_follow_the_board(diagpdf):
    """a1 is dark, h1 light, a8 light, h8 dark — the classic orientation check."""
    lines = diagpdf.fen_to_diagram(
        '8/8/8/8/8/8/8/8 w - - 0 1', font_name='ChessMerida', border_style='none'
    )
    dark, light = '+', ' '
    rank8, rank1 = lines[0], lines[7]
    assert rank1[0] == dark,  'a1 must be a dark square'
    assert rank1[7] == light, 'h1 must be a light square'
    assert rank8[0] == light, 'a8 must be a light square'
    assert rank8[7] == dark,  'h8 must be a dark square'


def test_square_colours_survive_flipping(diagpdf):
    lines = diagpdf.fen_to_diagram(
        '8/8/8/8/8/8/8/8 w - - 0 1', font_name='ChessMerida',
        border_style='none', flip=True,
    )
    # Flipped: top-left is h1 (light), bottom-right is a8 (light).
    assert lines[0][0] == ' '
    assert lines[7][7] == ' '


# ── fen_to_diagram: orientation ───────────────────────────────────────────────

def test_flip_reverses_the_board(diagpdf):
    normal = diagpdf.fen_to_diagram(START_FEN, font_name='ChessMerida', border_style='none')
    flipped = diagpdf.fen_to_diagram(
        START_FEN, font_name='ChessMerida', border_style='none', flip=True
    )
    assert flipped == [row[::-1] for row in reversed(normal)]


def test_auto_flip_triggers_only_for_black_to_move(diagpdf):
    kwargs = dict(font_name='ChessMerida', border_style='none', flip_auto=True)
    white_auto = diagpdf.fen_to_diagram(KINGS_FEN, **kwargs)
    white_plain = diagpdf.fen_to_diagram(KINGS_FEN, font_name='ChessMerida', border_style='none')
    assert white_auto == white_plain

    black_auto = diagpdf.fen_to_diagram(BLACK_TO_MOVE_FEN, **kwargs)
    black_plain = diagpdf.fen_to_diagram(
        BLACK_TO_MOVE_FEN, font_name='ChessMerida', border_style='none'
    )
    assert black_auto != black_plain


def test_auto_flip_and_explicit_flip_cancel_out(diagpdf):
    both = diagpdf.fen_to_diagram(
        BLACK_TO_MOVE_FEN, font_name='ChessMerida', border_style='none',
        flip=True, flip_auto=True,
    )
    neither = diagpdf.fen_to_diagram(
        BLACK_TO_MOVE_FEN, font_name='ChessMerida', border_style='none'
    )
    assert both == neither


# ── fen_to_diagram: coordinates and borders ───────────────────────────────────

def test_coordinates_change_the_border_glyphs(diagpdf):
    with_coords = diagpdf.fen_to_diagram(START_FEN, coords=True, font_name='ChessMerida')
    without = diagpdf.fen_to_diagram(START_FEN, coords=False, font_name='ChessMerida')
    assert with_coords != without
    assert [row[1:-1] for row in with_coords[1:-1]] == [row[1:-1] for row in without[1:-1]]


def test_coordinate_glyphs_run_in_board_order(diagpdf):
    lines = diagpdf.fen_to_diagram(START_FEN, coords=True, font_name='ChessMerida')
    ranks = [row[0] for row in lines[1:-1]]
    assert ranks == list(reversed(diagpdf.MERIDA_SIMPLE_RANK_CHARS))
    assert lines[-1][1:-1] == ''.join(diagpdf.MERIDA_SIMPLE_FILE_CHARS)


def test_flipping_reverses_the_coordinate_glyphs(diagpdf):
    lines = diagpdf.fen_to_diagram(START_FEN, coords=True, font_name='ChessMerida', flip=True)
    assert [row[0] for row in lines[1:-1]] == list(diagpdf.MERIDA_SIMPLE_RANK_CHARS)
    assert lines[-1][1:-1] == ''.join(reversed(diagpdf.MERIDA_SIMPLE_FILE_CHARS))


@pytest.mark.parametrize('border', ['simple', 'double'])
def test_border_styles_use_their_own_glyph_set(diagpdf, border):
    lines = diagpdf.fen_to_diagram(START_FEN, font_name='ChessMerida', border_style=border)
    style = diagpdf.MERIDA_BORDER_SETS[border]
    assert lines[0][0] == style['top_left']
    assert lines[0][-1] == style['top_right']
    assert lines[-1][0] == style['bottom_left']
    assert lines[-1][-1] == style['bottom_right']


def test_unknown_border_style_falls_back_to_simple(diagpdf):
    fallback = diagpdf.fen_to_diagram(START_FEN, font_name='ChessMerida', border_style='bogus')
    simple = diagpdf.fen_to_diagram(START_FEN, font_name='ChessMerida', border_style='simple')
    assert fallback == simple


# ── to-move indicator ─────────────────────────────────────────────────────────

def test_legacy_fonts_draw_the_indicator_inside_the_frame(diagpdf):
    """Alpha-style fonts replace the right border glyph on the bottom rank."""
    assert diagpdf._has_embedded_side_indicator('LeipzigDG')
    white = diagpdf.fen_to_diagram(KINGS_FEN, font_name='LeipzigDG', symbol='square')
    black = diagpdf.fen_to_diagram(BLACK_TO_MOVE_FEN, font_name='LeipzigDG',
                                   symbol='square', flip_auto=False)
    sym_w, sym_b = diagpdf.SYMBOL_CHARS['square']
    assert white[8][-1] == sym_w
    assert black[8][-1] == sym_b


@pytest.mark.parametrize('symbol', ['square', 'circle', 'triangle'])
def test_each_symbol_has_its_own_glyph_pair(diagpdf, symbol):
    sym_w, sym_b = diagpdf.SYMBOL_CHARS[symbol]
    assert sym_w != sym_b
    lines = diagpdf.fen_to_diagram(KINGS_FEN, font_name='LeipzigDG', symbol=symbol)
    assert lines[8][-1] == sym_w


def test_merida_fonts_need_a_separate_indicator(diagpdf):
    assert not diagpdf._has_embedded_side_indicator('ChessMerida')
    assert diagpdf._side_indicator_text('w', 'square') == '□'
    assert diagpdf._side_indicator_text('b', 'square') == '■'
    assert diagpdf._side_indicator_text('b', 'circle') == '●'
    assert diagpdf._side_indicator_text('b', 'bogus') == '■'


def test_borderless_boards_warn_that_coordinates_are_unavailable(diagpdf, capsys):
    diagpdf._WARNED_ONCE.clear()
    diagpdf.fen_to_diagram(START_FEN, coords=True, font_name='ChessMerida', border_style='none')
    assert 'coordinates are not available' in capsys.readouterr().err


def test_that_warning_is_emitted_only_once(diagpdf, capsys):
    diagpdf._WARNED_ONCE.clear()
    for _ in range(5):
        diagpdf.fen_to_diagram(START_FEN, coords=True, font_name='ChessMerida', border_style='none')
    assert capsys.readouterr().err.count('coordinates are not available') == 1


# ── Lichess URLs ──────────────────────────────────────────────────────────────

def test_lichess_url_encodes_the_fen_and_orientation(diagpdf):
    url = diagpdf._lichess_analysis_url(KINGS_FEN)
    assert url.startswith('https://lichess.org/analysis/')
    assert ' ' not in url
    assert url.endswith('?color=white')
    assert diagpdf._lichess_analysis_url(BLACK_TO_MOVE_FEN).endswith('?color=black')


def test_lichess_url_is_empty_for_an_empty_fen(diagpdf):
    assert diagpdf._lichess_analysis_url('') == ''
    assert diagpdf._lichess_analysis_url('   ') == ''
