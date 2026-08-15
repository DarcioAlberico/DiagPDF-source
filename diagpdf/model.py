"""Data shared by the parsers and the renderers."""

from __future__ import annotations

from typing import TypedDict


class _PositionRequired(TypedDict):
    fen: str

class PositionDict(_PositionRequired, total=False):
    """Position data shared by all three parsers (PGN / FEN file / EPD)."""
    white:   str
    black:   str
    event:   str
    date:    str
    chapter: str
    comment: str
    moves:   str
