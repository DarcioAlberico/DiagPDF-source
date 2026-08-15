"""Paper size, orientation and margins.

The geometry used to be four module constants pinned to A4 portrait with 10 mm
side and 15 mm top margins. They now come from a :class:`PageSetup` carried in
the options, so the same document can be produced as an A5 booklet or on Letter
without touching the layout code.
"""

from __future__ import annotations

from dataclasses import dataclass

# Width x height in millimetres, portrait.
PAGE_SIZES: dict[str, tuple[float, float]] = {
    'a3': (297.0, 420.0),
    'a4': (210.0, 297.0),
    'a5': (148.0, 210.0),
    'letter': (215.9, 279.4),
    'legal': (215.9, 355.6),
}
DEFAULT_PAGE_SIZE = 'a4'
PAGE_SIZE_KEYS = tuple(PAGE_SIZES)

DEFAULT_MARGIN_LR = 10.0
DEFAULT_MARGIN_TB = 15.0
DEFAULT_HDR_FTR_Y = 10.0

# The smallest sheet that still fits a readable board with its margins.
_MIN_USABLE_MM = 40.0


@dataclass(frozen=True)
class PageSetup:
    """A sheet of paper: how big, which way round, and how wide the margins."""

    size: str = DEFAULT_PAGE_SIZE
    landscape: bool = False
    margin_lr: float = DEFAULT_MARGIN_LR
    margin_tb: float = DEFAULT_MARGIN_TB
    header_offset: float = DEFAULT_HDR_FTR_Y

    @property
    def dimensions(self) -> tuple[float, float]:
        """Return (width, height) in mm, with the orientation applied."""
        width, height = PAGE_SIZES.get(self.size, PAGE_SIZES[DEFAULT_PAGE_SIZE])
        return (height, width) if self.landscape else (width, height)

    @property
    def width(self) -> float:
        return self.dimensions[0]

    @property
    def height(self) -> float:
        return self.dimensions[1]

    @property
    def usable_width(self) -> float:
        return self.width - 2 * self.margin_lr

    @property
    def usable_height(self) -> float:
        return self.height - 2 * self.margin_tb

    def fpdf_kwargs(self) -> dict:
        """Return the FPDF constructor arguments for this sheet."""
        # Always hand fpdf2 explicit portrait dimensions and let the orientation
        # flag do the rotating, so the two never disagree.
        width, height = PAGE_SIZES.get(self.size, PAGE_SIZES[DEFAULT_PAGE_SIZE])
        return {
            'orientation': 'L' if self.landscape else 'P',
            'unit': 'mm',
            'format': (width, height),
        }

    def as_twips(self) -> dict[str, int]:
        """Return the sheet in twips, for the RTF header."""
        return {
            'paperw': int(round(self.width * 56.6929)),
            'paperh': int(round(self.height * 56.6929)),
            'margl': int(round(self.margin_lr * 56.6929)),
            'margr': int(round(self.margin_lr * 56.6929)),
            'margt': int(round(self.margin_tb * 56.6929)),
            'margb': int(round(self.margin_tb * 56.6929)),
        }


def make_page_setup(size, landscape, margin_lr, margin_tb, header_offset) -> PageSetup:
    """Build a PageSetup from plain values, clamping anything unusable.

    Takes primitives rather than the options object so that :mod:`diagpdf.options`
    can call it without this module having to import the options back.
    """
    size = str(size or DEFAULT_PAGE_SIZE).lower()
    if size not in PAGE_SIZES:
        size = DEFAULT_PAGE_SIZE
    landscape = bool(landscape)

    width, height = PAGE_SIZES[size]
    if landscape:
        width, height = height, width

    return PageSetup(
        size,
        landscape,
        _margin(margin_lr, DEFAULT_MARGIN_LR, width),
        _margin(margin_tb, DEFAULT_MARGIN_TB, height),
        _margin(header_offset, DEFAULT_HDR_FTR_Y, height),
    )


def _margin(value, fallback: float, extent: float) -> float:
    """Return a margin that leaves at least a usable strip of paper."""
    try:
        margin = float(value)
    except (TypeError, ValueError):
        return fallback
    if margin < 0:
        return 0.0
    return min(margin, max(0.0, (extent - _MIN_USABLE_MM) / 2))
