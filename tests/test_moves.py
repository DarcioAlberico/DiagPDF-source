"""Movetext cleaning, title templates and number-prefix splitting."""

from __future__ import annotations

import pytest

# ── _clean_moves ──────────────────────────────────────────────────────────────

def test_plain_movetext_is_untouched(diagpdf):
    assert diagpdf._clean_moves('1. e4 e5 2. Nf3 Nc6') == '1. e4 e5 2. Nf3 Nc6'


def test_brace_comments_are_removed(diagpdf):
    assert diagpdf._clean_moves('1. Qxd8+ {a blow} Kxd8') == '1. Qxd8+ Kxd8'


def test_multiline_brace_comment_is_removed(diagpdf):
    assert diagpdf._clean_moves('1. e4 {first\nsecond} e5') == '1. e4 e5'


def test_line_comments_are_removed(diagpdf):
    assert diagpdf._clean_moves('1.e4 ; a note\n1...e5') == '1.e4 1...e5'


def test_escape_lines_are_removed(diagpdf):
    assert diagpdf._clean_moves('%eval junk\n1.e4 e5') == '1.e4 e5'
    assert diagpdf._clean_moves('1.e4\n%directive\ne5') == '1.e4 e5'


def test_percent_inside_a_line_is_not_an_escape(diagpdf):
    """Only a '%' in column 1 starts an escape line (PGN §6)."""
    assert diagpdf._clean_moves('1.e4 50% e5') == '1.e4 50% e5'


def test_nag_codes_are_removed(diagpdf):
    assert diagpdf._clean_moves('1. Qxd8+ $1 $18 Kxd8') == '1. Qxd8+ Kxd8'


def test_annotation_glyphs_are_removed(diagpdf):
    assert diagpdf._clean_moves('1. Ng7! Kb8?? 2. Nf5!? Kc8?!') == '1. Ng7 Kb8 2. Nf5 Kc8'


@pytest.mark.parametrize('result', ['1-0', '0-1', '1/2-1/2', '*'])
def test_trailing_result_is_removed(diagpdf, result):
    assert diagpdf._clean_moves(f'1. Ke2 Kd7 {result}') == '1. Ke2 Kd7'


def test_variations_are_preserved(diagpdf):
    text = '1. Qxd8+ Kxd8 2. Ne4+ Kc8 (2... Ke8 3. Rb8#) 3. Rd8#'
    assert diagpdf._clean_moves(text) == text


def test_padding_inside_variations_is_tightened(diagpdf):
    assert diagpdf._clean_moves('1.e4 ( 1...e5 ) 2.Nf3') == '1.e4 (1...e5) 2.Nf3'


def test_line_wrapping_collapses_to_single_spaces(diagpdf):
    """PGN wraps movetext at column 80; that break is a file artefact."""
    cleaned = diagpdf._clean_moves('1.e4 e5\n2.Nf3 Nc6\n3.Bb5 a6')
    assert cleaned == '1.e4 e5 2.Nf3 Nc6 3.Bb5 a6'
    assert '\n' not in cleaned


def test_docstring_example_still_holds(diagpdf):
    """The worked example in _clean_moves' own docstring."""
    given = '1. Qxd8+ {tactical blow} $1 Kxd8 2. Ne4+ Kc8 (2... Ke8 3. Rb8#) 3. Rd8# 1-0'
    expected = '1. Qxd8+ Kxd8 2. Ne4+ Kc8 (2... Ke8 3. Rb8#) 3. Rd8#'
    assert diagpdf._clean_moves(given) == expected


def test_empty_and_comment_only_movetext(diagpdf):
    assert diagpdf._clean_moves('') == ''
    assert diagpdf._clean_moves('   ') == ''
    assert diagpdf._clean_moves('{only a comment}') == ''
    assert diagpdf._clean_moves('*') == ''


# ── _apply_title_template ─────────────────────────────────────────────────────

@pytest.fixture
def sample_position() -> dict:
    return {
        'fen': '4k3/8/8/8/8/8/8/4K3 w - - 0 1',
        'event': 'Hastings 1895',
        'white': 'Steinitz, W.',
        'black': 'Lasker, Em.',
        'date': '1895.01.03',
        'comment': 'White to move and win',
        'moves': '1.Ke2',
    }


@pytest.mark.parametrize('template, expected', [
    ('{number}',                      '42'),
    ('{event}',                       'Hastings 1895'),
    ('{white}',                       'Steinitz, W.'),
    ('{black}',                       'Lasker, Em.'),
    ('{date}',                        '1895.01.03'),
    ('{comment}',                     'White to move and win'),
    ('{number}. {event} ({date})',    '42. Hastings 1895 (1895.01.03)'),
    ('{white} - {black}',             'Steinitz, W. - Lasker, Em.'),
])
def test_template_variables(diagpdf, sample_position, template, expected):
    assert diagpdf._apply_title_template(template, sample_position, 42) == expected


def test_empty_values_collapse_surrounding_whitespace(diagpdf):
    pos = {'fen': '', 'event': '', 'comment': 'Note'}
    assert diagpdf._apply_title_template('{number} {event} {comment}', pos, 7) == '7 Note'


def test_missing_keys_are_treated_as_empty(diagpdf):
    assert diagpdf._apply_title_template('{number} {event}', {'fen': ''}, 3) == '3'


def test_unknown_placeholders_are_left_alone(diagpdf, sample_position):
    assert diagpdf._apply_title_template('{number} {bogus}', sample_position, 1) == '1 {bogus}'


def test_template_without_variables(diagpdf, sample_position):
    assert diagpdf._apply_title_template('Diagram', sample_position, 1) == 'Diagram'


def test_comment_is_stripped(diagpdf):
    pos = {'fen': '', 'comment': '  padded  '}
    assert diagpdf._apply_title_template('{comment}', pos, 1) == 'padded'


# ── _make_title ───────────────────────────────────────────────────────────────

def test_template_takes_precedence_over_legacy_modes(diagpdf, sample_position):
    title = diagpdf._make_title(sample_position, 5, '{number}. {event}', 'number', '')
    assert title == '5. Hastings 1895'


def test_legacy_number_mode(diagpdf, sample_position):
    assert diagpdf._make_title(sample_position, 5, '', 'number', '') == '5'


def test_legacy_comment_mode(diagpdf, sample_position):
    assert diagpdf._make_title(sample_position, 5, '', 'comment', '') == '5 White to move and win'


def test_legacy_comment_mode_without_a_comment(diagpdf):
    assert diagpdf._make_title({'fen': ''}, 5, '', 'comment', '') == '5'


def test_legacy_custom_mode(diagpdf, sample_position):
    assert diagpdf._make_title(sample_position, 5, '', 'custom', 'Puzzle') == '5 Puzzle'
    assert diagpdf._make_title(sample_position, 5, '', 'custom', '') == '5'


# ── _split_title_number_prefix ────────────────────────────────────────────────

@pytest.mark.parametrize('title, num, expected', [
    ('1 Some text',    1,  ('1 ', 'Some text')),
    ('1. Some text',   1,  ('1. ', 'Some text')),
    ('7) title',       7,  ('7) ', 'title')),
    ('10. Mate in 2',  10, ('10. ', 'Mate in 2')),
    ('1',              1,  ('1', '')),
    ('42   spaced',    42, ('42   ', 'spaced')),
])
def test_number_prefix_is_split_when_present(diagpdf, title, num, expected):
    assert diagpdf._split_title_number_prefix(title, num) == expected


@pytest.mark.parametrize('title, num', [
    ('12 Some text', 1),     # 1 is a prefix of 12
    ('1st example',  1),     # digit glued to a word
    ('100 x',        10),
    ('Mate in 2',    1),     # no leading number at all
    ('2 other',      1),     # a different number
    ('',             1),
])
def test_nothing_is_split_when_the_number_does_not_stand_alone(diagpdf, title, num):
    assert diagpdf._split_title_number_prefix(title, num) == ('', title)


def test_the_split_always_reassembles_into_the_original(diagpdf):
    for num in (1, 9, 10, 99, 100):
        for title in (f'{num} text', f'{num}. text', f'{num}x', 'no number', str(num)):
            prefix, suffix = diagpdf._split_title_number_prefix(title, num)
            assert prefix + suffix == title


# ── _position_number ──────────────────────────────────────────────────────────

def test_position_numbers_are_one_based(diagpdf):
    assert diagpdf._position_number(0, diagpdf.RenderOptions()) == 1
    assert diagpdf._position_number(4, diagpdf.RenderOptions()) == 5


def test_position_numbers_honour_the_offset(diagpdf):
    opts = diagpdf.RenderOptions(number_offset=10)
    assert diagpdf._position_number(0, opts) == 11
    assert diagpdf._position_number(4, opts) == 15


# ── figurine segmentation ─────────────────────────────────────────────────────

def test_piece_letters_are_split_onto_the_figurine_font(diagpdf):
    segments = diagpdf._figurine_segments('1. Nf3 e5', 'Text', 'Fig')
    assert segments == [('Text', '1. '), ('Fig', 'N'), ('Text', 'f3 e5')]


def test_text_without_piece_letters_stays_in_one_segment(diagpdf):
    assert diagpdf._figurine_segments('1. e4 e5', 'Text', 'Fig') == [('Text', '1. e4 e5')]


def test_consecutive_piece_letters_share_a_segment(diagpdf):
    assert diagpdf._figurine_segments('KQ', 'Text', 'Fig') == [('Fig', 'KQ')]


def test_castling_is_not_mistaken_for_a_piece(diagpdf):
    """O-O uses the letter O, which is not a figurine piece initial."""
    assert diagpdf._figurine_segments('O-O', 'Text', 'Fig') == [('Text', 'O-O')]


def test_segmentation_preserves_the_text(diagpdf):
    text = '1. Nf3 Nc6 2. Bb5 a6 3. Ba4 (3. Bxc6 dxc6) Nf6 4. O-O Be7'
    assert ''.join(part for _, part in diagpdf._figurine_segments(text, 'T', 'F')) == text


def test_empty_text_produces_no_segments(diagpdf):
    assert diagpdf._figurine_segments('', 'Text', 'Fig') == []


def test_identical_fonts_collapse_into_one_segment(diagpdf):
    assert diagpdf._figurine_segments('1. Nf3', 'Same', 'Same') == [('Same', '1. Nf3')]
