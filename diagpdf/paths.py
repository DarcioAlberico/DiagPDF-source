"""Output path handling shared by the CLI and the GUI."""

from __future__ import annotations

import re
from pathlib import Path


def _ext_from_save_filter(filter_value: str) -> str:
    """Extract a preferred extension from a Tk save-dialog filter value."""
    raw = filter_value or ''
    m = re.search(r'\*\.([A-Za-z0-9]+)', raw)
    if m:
        return f'.{m.group(1).lower()}'
    low = raw.lower()
    # Longest first, so 'markdown' is not matched by '.md' and 'html' wins over
    # a bare 'tex' appearing inside another word.
    for ext in ('.markdown', '.epub', '.html', '.docx', '.rtf', '.tex', '.pdf', '.md'):
        if ext[1:] in low:
            return ext
    return '.pdf'


def _normalize_output_path(out_str: str, selected_filter: str = '') -> Path:
    """Append the chosen extension when the user saves without typing it."""
    out_path = Path(out_str.strip())
    if not out_path.name:
        return out_path
    if out_path.suffix:
        return out_path
    return out_path.with_suffix(_ext_from_save_filter(selected_filter))


def _default_output_path(in_path: Path, selected_filter: str = '') -> Path:
    """Return the default output path for an input file and selected save type."""
    return in_path.with_suffix(_ext_from_save_filter(selected_filter))
