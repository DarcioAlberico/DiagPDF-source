"""Save-dialog file types.

Tk reports the chosen filter through ``typevariable`` as the *displayed* text,
which is translated. Deriving the extension by looking for "pdf" inside
"Arquivos PDF" happened to work, but it tied the output format to the wording of
the interface. The dialog is built from this table instead, so the label and the
extension travel together.
"""

from __future__ import annotations

from pathlib import Path

from ..i18n import tr

# Order matters: the first entry is the default filter shown by the dialog.
SAVE_EXTENSIONS: tuple[str, ...] = ('.pdf', '.html', '.epub', '.docx', '.rtf', '.md', '.tex')

# Spellings the renderers also answer to, which the dialog does not need a
# second entry for: one filter per format, not per extension.
EXTENSION_ALIASES: dict[str, str] = {'.htm': '.html', '.markdown': '.md'}

_LABEL_KEYS = {
    '.pdf': 'filetype_pdf',
    '.html': 'filetype_html',
    '.epub': 'filetype_epub',
    '.docx': 'filetype_docx',
    '.rtf': 'filetype_rtf',
    '.md': 'filetype_md',
    '.tex': 'filetype_tex',
}


def save_filetypes(lang: str) -> list[tuple[str, str]]:
    """Return the ``filetypes`` list for a save dialog, in *lang*."""
    entries = [(tr(_LABEL_KEYS[ext], lang), f'*{ext}') for ext in SAVE_EXTENSIONS]
    entries.append((tr('filetype_all', lang), '*.*'))
    return entries


def open_filetypes(lang: str) -> list[tuple[str, str]]:
    """Return the ``filetypes`` list for the input-file dialog."""
    return [
        (tr('filetype_chess', lang), '*.pgn *.fen *.epd'),
        (tr('filetype_all', lang), '*.*'),
    ]


def extension_for_label(label: str, lang: str) -> str:
    """Return the extension whose dialog label is *label*.

    Falls back to matching the pattern, then to PDF, so a filter string from an
    older settings file or another language cannot select the wrong renderer.
    """
    for ext, key in _LABEL_KEYS.items():
        if label == tr(key, lang):
            return ext
    for ext in SAVE_EXTENSIONS:
        if ext.lstrip('.') in (label or '').lower():
            return ext
    return SAVE_EXTENSIONS[0]


def default_output_path(input_path: Path, extension: str) -> Path:
    """Return the output path suggested for *input_path*."""
    return input_path.with_suffix(extension)


def normalize_output_path(text: str, extension: str) -> Path:
    """Append *extension* when the user saved without typing one."""
    path = Path(text.strip())
    if not path.name or path.suffix:
        return path
    return path.with_suffix(extension)
