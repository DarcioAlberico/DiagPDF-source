"""Exception types raised across the package."""

from __future__ import annotations


class FenError(ValueError):
    """Raised when a FEN string cannot be parsed into a position."""

class UnknownFontError(ValueError):
    """Raised when a requested font name is not available."""
