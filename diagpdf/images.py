"""Exporting each diagram as its own image file.

Useful for authors assembling a book elsewhere, or for a website. Two shapes of
the same picture: PNG comes from the preview renderer — it already knows the
awkward part, which is that the chess fonts carry no Unicode character map —
and SVG carries the glyph outlines themselves, so it scales and needs no font.
"""

from __future__ import annotations

import re
from pathlib import Path

from .log import _warn
from .model import PositionDict
from .options import RenderOptions
from .render.common import _make_title, _position_number

IMAGE_FORMATS = ('png', 'svg')
DEFAULT_IMAGE_FORMAT = 'png'


def _safe_stem(text: str, fallback: str) -> str:
    """Return a file-name-safe version of *text*."""
    cleaned = re.sub(r'[^\w.-]+', '_', text, flags=re.UNICODE).strip('_.')
    return cleaned[:60] or fallback


def export_images(
    positions: list[PositionDict],
    opts: RenderOptions | dict,
    out_dir,
    *,
    image_format: str = DEFAULT_IMAGE_FORMAT,
    row_px: int = 40,
    progress=None,
) -> list[Path]:
    """Write one image per position into *out_dir* and return the paths."""
    from .gui.preview import PreviewUnavailable, render_preview_png
    from .svg import SvgUnavailable, render_diagram_svg

    opts = RenderOptions.coerce(opts)
    if image_format not in IMAGE_FORMATS:
        raise ValueError(f'unsupported image format {image_format!r} '
                         f'- available: {", ".join(IMAGE_FORMATS)}')

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    valid = [p for p in positions if str(p.get('fen', '') or '').strip()]
    written: list[Path] = []

    for index, position in enumerate(valid):
        number = _position_number(index, opts)
        title = _make_title(
            position, number, opts.title_template, opts.title_mode, opts.title_custom, opts,
        )
        stem = _safe_stem(title, f'diagram_{number}')
        target = out_dir / f'{number:04d}_{stem}.{image_format}'
        try:
            if image_format == 'svg':
                target.write_text(
                    render_diagram_svg(opts, position, row_px=row_px, number=number),
                    encoding='utf-8')
            else:
                target.write_bytes(render_preview_png(
                    opts, position, row_px=row_px, max_width=10_000, number=number))
        except (PreviewUnavailable, SvgUnavailable) as exc:
            _warn(f'could not export {target.name}: {exc}')
            continue
        written.append(target)
        if progress and valid:
            progress(int((index + 1) * 100 / len(valid)))
    return written
