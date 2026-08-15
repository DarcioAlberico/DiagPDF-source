"""Page geometry: every layout must fit on the page it claims to fit on."""

from __future__ import annotations

import pytest

import fen2rtf as F

ALL_LAYOUTS = list(range(len(F.LAYOUTS)))
ALL_LINE_COUNTS = list(range(6))


def geometry(**over):
    opts = {
        'layout_idx': F.DEFAULT_LAYOUT,
        'font': F._default_board_font_name(),
        'font_size': 0,
        'lines_count': 0,
        'border_style': 'simple',
        'lichess_link': False,
    }
    opts.update(over)
    return F._compute_geometry(opts)


# ── Grid arithmetic ───────────────────────────────────────────────────────────

@pytest.mark.parametrize('layout_idx', ALL_LAYOUTS)
@pytest.mark.parametrize('lines_count', ALL_LINE_COUNTS)
def test_per_page_is_columns_times_rows(layout_idx, lines_count):
    g = geometry(layout_idx=layout_idx, lines_count=lines_count)
    assert g.per_page == g.cols * g.max_rows
    assert g.per_page >= 1


@pytest.mark.parametrize('layout_idx', ALL_LAYOUTS)
def test_rows_per_page_switch_between_the_plain_and_lined_presets(layout_idx):
    """Each preset carries two row counts — the label reads plain/lined.

    Most presets pack fewer rows once notation lines are added, but layout 1
    ("1 - 1/2 dg/pg") deliberately goes the other way: one large diagram alone,
    two smaller ones when they carry lines.
    """
    lay = F.LAYOUTS[layout_idx]
    plain = geometry(layout_idx=layout_idx, lines_count=0)
    lined = geometry(layout_idx=layout_idx, lines_count=3)
    assert plain.max_rows == lay[4]
    assert lined.max_rows == lay[5]
    assert lined.cols == plain.cols == lay[3]


@pytest.mark.parametrize('layout_idx', ALL_LAYOUTS)
def test_columns_match_the_preset(layout_idx):
    assert geometry(layout_idx=layout_idx).cols == F.LAYOUTS[layout_idx][3]


def test_layout_index_is_clamped_to_the_available_presets():
    assert geometry(layout_idx=-5).cols == F.LAYOUTS[0][3]
    assert geometry(layout_idx=999).cols == F.LAYOUTS[-1][3]


# ── The content has to fit the page ───────────────────────────────────────────

@pytest.mark.parametrize('layout_idx', ALL_LAYOUTS)
@pytest.mark.parametrize('lines_count', ALL_LINE_COUNTS)
@pytest.mark.parametrize('lichess_link', [False, True])
def test_a_full_page_of_rows_fits_between_the_margins(layout_idx, lines_count, lichess_link):
    g = geometry(layout_idx=layout_idx, lines_count=lines_count, lichess_link=lichess_link)
    content_h = g.max_rows * g.row_h
    assert content_h <= g.USABLE_H + 1e-6, (
        f'layout {layout_idx} with {lines_count} lines needs {content_h:.1f}mm '
        f'but only {g.USABLE_H:.1f}mm is available'
    )


@pytest.mark.parametrize('layout_idx', ALL_LAYOUTS)
@pytest.mark.parametrize('lines_count', ALL_LINE_COUNTS)
def test_the_grid_starts_below_the_top_margin(layout_idx, lines_count):
    g = geometry(layout_idx=layout_idx, lines_count=lines_count)
    assert g.y_top >= g.MT - 1e-6


@pytest.mark.parametrize('layout_idx', ALL_LAYOUTS)
def test_the_grid_is_vertically_centred(layout_idx):
    g = geometry(layout_idx=layout_idx)
    top_gap = g.y_top - g.MT
    bottom_gap = g.USABLE_H - (g.max_rows * g.row_h) - top_gap
    assert top_gap == pytest.approx(bottom_gap, abs=1e-6)


@pytest.mark.parametrize('layout_idx', ALL_LAYOUTS)
def test_columns_divide_the_usable_width(layout_idx):
    g = geometry(layout_idx=layout_idx)
    assert g.cols * g.col_w == pytest.approx(g.USABLE_W)


def test_page_constants_are_a4():
    g = geometry()
    assert (g.PW, g.PH) == (210.0, 297.0)
    assert g.USABLE_W == g.PW - g.ML - g.MR
    assert g.USABLE_H == g.PH - 2 * g.MT


# ── Font sizing ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize('layout_idx', ALL_LAYOUTS)
@pytest.mark.parametrize('lines_count', ALL_LINE_COUNTS)
def test_the_chess_size_stays_positive(layout_idx, lines_count):
    assert geometry(layout_idx=layout_idx, lines_count=lines_count).chess_pt >= 1


@pytest.mark.parametrize('layout_idx', ALL_LAYOUTS)
def test_a_requested_size_is_capped_by_what_fits(layout_idx):
    """A caller may ask for 200pt; the page still wins."""
    auto = geometry(layout_idx=layout_idx, font_size=0).chess_pt
    huge = geometry(layout_idx=layout_idx, font_size=200).chess_pt
    assert huge <= max(auto, huge)
    g = geometry(layout_idx=layout_idx, font_size=200)
    assert g.max_rows * g.row_h <= g.USABLE_H + 1e-6


@pytest.mark.parametrize('layout_idx', ALL_LAYOUTS)
def test_a_small_requested_size_is_honoured(layout_idx):
    assert geometry(layout_idx=layout_idx, font_size=6).chess_pt == 6


def test_denser_layouts_get_smaller_boards():
    one_per_page = geometry(layout_idx=0).chess_pt
    four_columns = geometry(layout_idx=4).chess_pt
    assert one_per_page > four_columns


def test_more_notation_lines_shrink_the_board():
    assert geometry(lines_count=5).chess_pt <= geometry(lines_count=0).chess_pt


def test_chess_millimetres_track_the_point_size():
    g = geometry()
    assert g.chess_mm == pytest.approx(g.chess_pt * 25.4 / 72)


# ── Borderless Merida boards reserve room for the title ───────────────────────

def test_a_borderless_board_moves_the_title_above_it():
    bordered = geometry(border_style='simple', font='ChessMerida')
    borderless = geometry(border_style='none', font='ChessMerida')
    # 8 rows instead of 10, plus a title band on top.
    assert borderless.row_h < bordered.row_h + borderless.title_lh


def test_lichess_links_reserve_vertical_room():
    without = geometry(lichess_link=False)
    with_link = geometry(lichess_link=True)
    assert with_link.row_h - without.row_h == pytest.approx(
        5.0 + (with_link.chess_mm - without.chess_mm) * 10, abs=5.0
    )
    assert with_link.max_rows * with_link.row_h <= with_link.USABLE_H + 1e-6


# ── Text sizing ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize('layout_idx', ALL_LAYOUTS)
def test_title_size_defaults_to_the_preset(layout_idx):
    assert geometry(layout_idx=layout_idx).txt_size == F.LAYOUTS[layout_idx][7]


def test_an_explicit_text_size_overrides_the_preset():
    assert geometry(text_size=13).txt_size == 13


def test_title_line_height_follows_the_text_size():
    g = geometry(text_size=10)
    assert g.title_lh == pytest.approx(10 * (25.4 / 72) * F.TITLE_LH_FACTOR)


# ── Purity ────────────────────────────────────────────────────────────────────

def test_compute_geometry_does_not_mutate_its_input():
    opts = {'layout_idx': 3, 'font_size': 0, 'lines_count': 2}
    snapshot = dict(opts)
    F._compute_geometry(opts)
    assert opts == snapshot


def test_compute_geometry_is_deterministic():
    assert geometry(layout_idx=4, lines_count=2) == geometry(layout_idx=4, lines_count=2)


def test_compute_geometry_accepts_an_empty_options_dict():
    g = F._compute_geometry({})
    assert g.cols == F.LAYOUTS[F.DEFAULT_LAYOUT][3]
