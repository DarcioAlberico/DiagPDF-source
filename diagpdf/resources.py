"""Locating bundled resources, from source and from a frozen build."""

from __future__ import annotations

import sys
from pathlib import Path


def _resource(rel: str) -> Path:
    """Return the absolute path to a bundled resource.

    Resources such as ``Fonts/`` and ``icon.ico`` sit beside the package, not
    inside it, so the search starts one level above this module. When frozen by
    PyInstaller they are unpacked into ``sys._MEIPASS`` instead.
    """
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    return base / rel
