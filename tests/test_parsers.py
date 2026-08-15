"""PGN / FEN-file / EPD parsing, including malformed input."""

from __future__ import annotations

import pytest
from conftest import (
    EPD_FILE,
    FEN_FILE,
    PGN_SIMPLE,
    PGN_THREE_GAMES,
    PGN_WITH_CHAPTERS,
)

# ── PGN: tags ─────────────────────────────────────────────────────────────────

def test_seven_tag_roster_is_read(diagpdf):
    pos = diagpdf.parse_pgn(PGN_SIMPLE)[0]
    assert pos['event'] == 'Test 1'
    assert pos['white'] == 'Steinitz, W.'
    assert pos['black'] == 'Lasker, Em.'
    assert pos['date'] == '1895.01.03'
    assert pos['fen'] == '4k3/8/8/8/8/8/8/4K3 w - - 0 1'


def test_movetext_and_first_comment_are_separated(diagpdf):
    pos = diagpdf.parse_pgn(PGN_SIMPLE)[0]
    assert pos['comment'] == 'White to move and win'
    assert diagpdf._clean_moves(pos['moves']) == '1. Ke2 Kd7'


def test_result_token_is_stripped_from_movetext(diagpdf):
    for result in ('1-0', '0-1', '1/2-1/2', '*'):
        pgn = f'[Event "R"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 {result}\n'
        assert diagpdf.parse_pgn(pgn)[0]['moves'] == '1.Ke2'


def test_games_without_a_fen_tag_are_skipped(diagpdf):
    pgn = (
        '[Event "No FEN"]\n[White "A"]\n\n1.e4 e5 *\n\n'
        '[Event "Has FEN"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n'
    )
    parsed = diagpdf.parse_pgn(pgn)
    assert len(parsed) == 1
    assert parsed[0]['event'] == 'Has FEN'


def test_escaped_quotes_in_tag_values(diagpdf):
    pgn = (
        '[Event "The \\"Immortal\\" Game"]\n'
        '[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n'
    )
    assert diagpdf.parse_pgn(pgn)[0]['event'] == 'The "Immortal" Game'


def test_chapter_tag_is_carried_on_each_position(diagpdf):
    parsed = diagpdf.parse_pgn(PGN_WITH_CHAPTERS)
    assert [p['chapter'] for p in parsed] == ['Pins', 'Forks']


def test_missing_optional_tags_become_empty_strings(diagpdf):
    pos = diagpdf.parse_pgn('[Event "E"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n*\n')[0]
    for key in ('white', 'black', 'date', 'chapter'):
        assert pos[key] == ''


# ── PGN: game splitting ───────────────────────────────────────────────────────

def test_three_games_are_parsed_in_order(diagpdf):
    parsed = diagpdf.parse_pgn(PGN_THREE_GAMES)
    assert [p['event'] for p in parsed] == ['One', 'Two', 'Three']


def test_game_whose_first_tag_is_not_event(diagpdf):
    """Regression: the earlier splitter merged such a game into the previous one
    and the previous position was silently overwritten."""
    pgn = (
        '[Event "One"]\n[FEN "POSITION-ONE w - - 0 1"]\n1.Ke2 *\n\n'
        '[White "Nobody"]\n[FEN "POSITION-TWO w - - 0 1"]\n1.Kf2 *\n'
    )
    parsed = diagpdf.parse_pgn(pgn)
    assert [p['fen'] for p in parsed] == ['POSITION-ONE w - - 0 1', 'POSITION-TWO w - - 0 1']


def test_tag_like_line_inside_a_comment_does_not_split(diagpdf):
    pgn = (
        '[Event "Real"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n'
        '{see\n[Event "fake"] in comment}\n1.Ke2 Kd7 *\n'
    )
    parsed = diagpdf.parse_pgn(pgn)
    assert len(parsed) == 1
    assert diagpdf._clean_moves(parsed[0]['moves']) == '1.Ke2 Kd7'


def test_blank_lines_between_tags_do_not_split(diagpdf):
    pgn = '[Event "E"]\n\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n\n1.Ke2 *\n'
    parsed = diagpdf.parse_pgn(pgn)
    assert len(parsed) == 1
    assert parsed[0]['event'] == 'E'


def test_crlf_line_endings(diagpdf):
    assert len(diagpdf.parse_pgn(PGN_THREE_GAMES.replace('\n', '\r\n'))) == 3


def test_missing_trailing_newline(diagpdf):
    assert len(diagpdf.parse_pgn(PGN_THREE_GAMES.rstrip('\n'))) == 3


def test_empty_and_whitespace_input(diagpdf):
    assert diagpdf.parse_pgn('') == []
    assert diagpdf.parse_pgn('\n\n   \n') == []


def test_input_without_any_tags(diagpdf):
    assert diagpdf.parse_pgn('1.e4 e5 2.Nf3 Nc6 *') == []


def test_multiple_tags_on_one_line(diagpdf):
    pgn = '[Event "E"] [Site "S"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n'
    parsed = diagpdf.parse_pgn(pgn)
    assert len(parsed) == 1
    assert parsed[0]['event'] == 'E'


def test_movetext_spanning_several_lines_is_joined(diagpdf):
    pgn = (
        '[Event "E"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n'
        '1.Ke2 Kd7\n2.Kd3 Kc6\n3.Kc4 *\n'
    )
    moves = diagpdf._clean_moves(diagpdf.parse_pgn(pgn)[0]['moves'])
    assert moves == '1.Ke2 Kd7 2.Kd3 Kc6 3.Kc4'
    assert '\n' not in moves


# ── PGN: comment handling ─────────────────────────────────────────────────────

def test_first_text_comment_skips_markup_only_comments(diagpdf):
    assert diagpdf._first_text_comment('{[%clk 0:05:00]} {Real note} 1.e4') == 'Real note'


def test_first_text_comment_when_there_is_none(diagpdf):
    assert diagpdf._first_text_comment('1.e4 e5') == ''
    assert diagpdf._first_text_comment('{[%eval 0.2]}') == ''


def test_multiline_comment_is_captured(diagpdf):
    assert diagpdf._first_text_comment('{line one\nline two} 1.e4') == 'line one\nline two'


# ── FEN files ─────────────────────────────────────────────────────────────────

def test_fen_file_positions(diagpdf):
    parsed = diagpdf.parse_fen_file(FEN_FILE)
    assert len(parsed) == 2
    assert parsed[0]['fen'].startswith('4k3')
    assert parsed[1]['fen'].startswith('8/8/8/8/8/5k2')
    assert all(p['moves'] == '' for p in parsed)


def test_fen_file_ignores_other_text(diagpdf):
    content = 'A heading\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\nsome trailing prose\n'
    assert len(diagpdf.parse_fen_file(content)) == 1


def test_empty_fen_file(diagpdf):
    assert diagpdf.parse_fen_file('') == []


def test_every_fen_file_position_has_the_shared_keys(diagpdf):
    for pos in diagpdf.parse_fen_file(FEN_FILE):
        assert set(pos) >= {'fen', 'white', 'black', 'event', 'date', 'chapter', 'comment', 'moves'}


# ── EPD ───────────────────────────────────────────────────────────────────────

def test_epd_positions_and_operands(diagpdf):
    parsed = diagpdf.parse_epd(EPD_FILE)
    assert len(parsed) == 2
    assert parsed[0]['fen'] == '4k3/8/8/8/8/8/8/4K3 w - - 0 1'
    assert parsed[0]['white'] == 'position one'   # the `id` operand
    assert parsed[0]['black'] == 'Ke2'            # the `bm` operand


def test_epd_reconstructs_the_move_counters(diagpdf):
    parsed = diagpdf.parse_epd('4k3/8/8/8/8/8/8/4K3 w - - bm Ke2;\n')
    assert parsed[0]['fen'].endswith(' 0 1')
    assert diagpdf.validate_fen(parsed[0]['fen']) == []


def test_epd_without_operands(diagpdf):
    parsed = diagpdf.parse_epd('4k3/8/8/8/8/8/8/4K3 w - -\n')
    assert len(parsed) == 1
    assert parsed[0]['white'] == '' and parsed[0]['black'] == ''


def test_epd_skips_blank_and_comment_lines(diagpdf):
    content = '\n; a comment\n4k3/8/8/8/8/8/8/4K3 w - - bm Ke2;\n\n'
    assert len(diagpdf.parse_epd(content)) == 1


def test_epd_skips_lines_with_too_few_fields(diagpdf):
    assert diagpdf.parse_epd('4k3/8/8/8/8/8/8/4K3 w\n') == []


def test_empty_epd(diagpdf):
    assert diagpdf.parse_epd('') == []


# ── Encoding detection ────────────────────────────────────────────────────────

def test_utf8_input(diagpdf, tmp_path):
    src = tmp_path / 'utf8.pgn'
    src.write_text('[Event "Peão"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n',
                   encoding='utf-8')
    assert diagpdf.parse_pgn(diagpdf.read_chess_file(src))[0]['event'] == 'Peão'


def test_utf8_bom_is_stripped(diagpdf, tmp_path):
    src = tmp_path / 'bom.pgn'
    src.write_text('[Event "E"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n',
                   encoding='utf-8-sig')
    parsed = diagpdf.parse_pgn(diagpdf.read_chess_file(src))
    assert len(parsed) == 1 and parsed[0]['event'] == 'E'


def test_cp1252_input_is_detected(diagpdf, tmp_path, capsys):
    src = tmp_path / 'latin.pgn'
    src.write_bytes(
        '[Event "Peão"]\n[FEN "4k3/8/8/8/8/8/8/4K3 w - - 0 1"]\n1.Ke2 *\n'.encode('cp1252')
    )
    assert diagpdf.parse_pgn(diagpdf.read_chess_file(src))[0]['event'] == 'Peão'
    assert 'cp1252' in capsys.readouterr().err


def test_explicit_encoding_is_honoured(diagpdf, tmp_path):
    src = tmp_path / 'explicit.pgn'
    src.write_bytes('[Event "Peão"]\n'.encode('cp1252'))
    assert 'Peão' in diagpdf.read_chess_file(src, 'cp1252')


def test_unknown_encoding_name_raises(diagpdf, tmp_path):
    src = tmp_path / 'x.pgn'
    src.write_text('[Event "E"]\n', encoding='utf-8')
    with pytest.raises(LookupError):
        diagpdf.read_chess_file(src, 'not-a-codec')


# ── Invalid-FEN policy ────────────────────────────────────────────────────────

def test_skip_policy_drops_invalid_positions(diagpdf, capsys):
    positions = [
        {'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1'},
        {'fen': 'garbage'},
        {'fen': '8/8/8/8/8/5k2/8/5K2 b - - 0 1'},
    ]
    kept = diagpdf.apply_fen_policy(positions, 'skip')
    assert len(kept) == 2
    err = capsys.readouterr().err
    assert 'position 2 skipped' in err
    assert '1 position(s) skipped' in err


def test_fail_policy_names_the_offending_position(diagpdf):
    positions = [{'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1'}, {'fen': 'garbage'}]
    with pytest.raises(diagpdf.FenError, match='position 2'):
        diagpdf.apply_fen_policy(positions, 'fail')


def test_policy_is_a_no_op_when_everything_is_valid(diagpdf, capsys):
    positions = diagpdf.parse_pgn(PGN_THREE_GAMES)
    assert diagpdf.apply_fen_policy(positions, 'skip') == positions
    assert capsys.readouterr().err == ''
