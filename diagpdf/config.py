"""Legacy settings access.

Superseded by :mod:`diagpdf.gui.settings`, which validates and versions what it
reads. Kept because the old module exposed these names; they now delegate so
there is a single stored file and a single notion of where it lives.
"""

from __future__ import annotations

import json

from .gui.settings import CONFIG_PATH as _CONFIG_PATH
from .log import _warn

__all__ = ['_CONFIG_PATH', '_load_config', '_save_config']


def _load_config() -> dict:
    """Return the stored settings as a raw dict (no validation)."""
    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save_config(data: dict) -> None:
    """Write *data* verbatim to the settings file."""
    try:
        _CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding='utf-8')
    except Exception as exc:
        _warn(f'could not save settings: {exc}')
