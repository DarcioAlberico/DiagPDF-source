"""Picking a renderer from the output file name."""

from __future__ import annotations

from pathlib import Path

from .capabilities import warn_unsupported_options
from .model import PositionDict
from .options import RenderOptions
from .render.docx import generate_docx
from .render.epub import generate_epub
from .render.html import generate_html
from .render.latex import generate_latex
from .render.markdown import generate_markdown
from .render.pdf import generate_pdf
from .render.rtf import generate_rtf

GENERATORS = {
    '.pdf':  generate_pdf,
    '.html': generate_html,
    '.htm':  generate_html,
    '.epub': generate_epub,
    '.docx': generate_docx,
    '.rtf':  generate_rtf,
    '.md':   generate_markdown,
    '.markdown': generate_markdown,
    '.tex':  generate_latex,
}


def generate_output(positions: list[PositionDict], opts: RenderOptions | dict,
                    out_path, progress=None) -> None:
    """Render *positions* to *out_path*, picking the format from its suffix."""
    opts = RenderOptions.coerce(opts)
    suffix = Path(out_path).suffix.lower()
    generator = GENERATORS.get(suffix, generate_pdf)
    warn_unsupported_options(opts, out_path, positions)
    generator(positions, opts, out_path, progress=progress)
