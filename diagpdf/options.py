"""The options every renderer takes, as one validated object.

The options used to travel as a plain ``dict`` between the CLI, the GUI and the
five renderers. Nothing declared which keys existed, so each renderer carried
its own fallback for every key it read -- and six of them disagreed. A document
asked for with the same options could come out with a footer in PDF and without
one in DOCX, purely because two ``.get`` calls had been written years apart.

:class:`RenderOptions` is now the single place where a key exists, has a type,
has one default, and is checked. A value that cannot be honoured is reported
and replaced by the default rather than quietly misrendering.

Renderers coerce whatever they are handed at their entry point, so the old
``dict`` still works; everything downstream reads typed attributes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from typing import Any

from .chars import BORDER_STYLE_KEYS, SYMBOL_KEYS
from .fonts import _default_board_font_name, _default_figurine_font_name
from .i18n import DEFAULT_LANG, LANGS
from .layouts import DEFAULT_LAYOUT, LAYOUTS
from .log import _warn
from .page import (
    DEFAULT_HDR_FTR_Y,
    DEFAULT_MARGIN_LR,
    DEFAULT_MARGIN_TB,
    DEFAULT_PAGE_SIZE,
    PAGE_SIZE_KEYS,
    PageSetup,
    make_page_setup,
)

HTML_FONT_MODES = ('embed', 'link', 'none')
LINES_MODES = ('plain', 'numbered')
TITLE_MODES = ('comment', 'number', 'custom')

# Old option names kept working, mapped to the name in force.
ALIASES = {'lichess': 'lichess_link'}


@dataclass
class RenderOptions:
    """Everything the renderers need to know, validated on construction."""

    # ── Board and diagram ────────────────────────────────────────────────────
    layout_idx: int = DEFAULT_LAYOUT
    grid: tuple[int, int] | None = None
    font: str = field(default_factory=_default_board_font_name)
    font_size: int = 0
    text_size: int = 0
    coords: bool = True
    flip: bool = False
    flip_auto: bool = True
    symbol: str = 'square'
    border_style: str = 'simple'

    # ── Titles and numbering ─────────────────────────────────────────────────
    title_template: str = ''
    title_mode: str = 'comment'      # superseded by title_template
    title_custom: str = ''           # superseded by title_template
    number_start: int = 1
    number_offset: int = 0
    number_format: str = ''
    number_restart_per_chapter: bool = False

    # ── Notation lines ───────────────────────────────────────────────────────
    lines_count: int = 0
    lines_mode: str = 'plain'

    # ── Running header and footer ────────────────────────────────────────────
    # Both default to shown, matching the CLI (--no-header/--no-footer opt out)
    # and the GUI. With no text set there is nothing to draw, so a bare
    # RenderOptions() still produces a clean page.
    header: str = ''
    footer: str = ''
    show_header: bool = True
    show_footer: bool = True

    # ── Answers section ──────────────────────────────────────────────────────
    answers_section: bool = False
    answers_title: str = ''
    answers_cols: int = 1
    answers_upside_down: bool = False
    answers_new_page: bool = True
    answers_after_chapter: bool = False
    figurine_font: str = field(default_factory=_default_figurine_font_name)
    lichess_link: bool = False
    lichess_label: str = ''

    # ── Document metadata ────────────────────────────────────────────────────
    doc_title: str = ''
    doc_author: str = ''
    doc_subject: str = ''
    doc_keywords: str = ''
    doc_language: str = ''
    lang: str = DEFAULT_LANG

    # ── Page setup ───────────────────────────────────────────────────────────
    page_size: str = DEFAULT_PAGE_SIZE
    landscape: bool = False
    margin_lr: float = DEFAULT_MARGIN_LR
    margin_tb: float = DEFAULT_MARGIN_TB
    header_offset: float = DEFAULT_HDR_FTR_Y

    # ── Front matter ─────────────────────────────────────────────────────────
    watermark: str = ''
    watermark_opacity: int = 10
    cover: bool = False
    cover_title: str = ''
    cover_subtitle: str = ''
    cover_author: str = ''
    contents: bool = False
    contents_title: str = ''

    # ── Format specific ──────────────────────────────────────────────────────
    html_font_mode: str = 'embed'
    epub_css_path: str = ''
    allow_restricted_fonts: bool = False

    # ── Normalisation ────────────────────────────────────────────────────────

    def __post_init__(self) -> None:
        """Coerce types, clamp what is out of range, and report what is not valid.

        Clamping silently is right where the CLI already clamped (a layout index
        past the end has always meant "the last one"). An unrecognised *name* is
        different: it means the caller asked for something that does not exist,
        so it is named in a warning before the default takes over.
        """
        self.layout_idx = _clamp_int(self.layout_idx, 0, len(LAYOUTS) - 1, DEFAULT_LAYOUT, 'layout_idx')
        self.grid = _as_grid(self.grid)
        self.font = str(self.font or '') or _default_board_font_name()
        self.font_size = _at_least(self.font_size, 0, 0, 'font_size')
        self.text_size = _at_least(self.text_size, 0, 0, 'text_size')
        self.symbol = _one_of(self.symbol, SYMBOL_KEYS, 'square', 'symbol')
        self.border_style = _one_of(self.border_style, BORDER_STYLE_KEYS, 'simple', 'border_style')

        self.title_mode = _one_of(self.title_mode, TITLE_MODES, 'comment', 'title_mode')
        self.number_start = _at_least(self.number_start, 1, 1, 'number_start')
        self.number_offset = _at_least(self.number_offset, 0, 0, 'number_offset')

        self.lines_count = _at_least(self.lines_count, 0, 0, 'lines_count')
        self.lines_mode = _one_of(self.lines_mode, LINES_MODES, 'plain', 'lines_mode')

        self.answers_cols = _clamp_int(self.answers_cols, 1, 2, 1, 'answers_cols')
        self.figurine_font = str(self.figurine_font or '') or _default_figurine_font_name()
        self.lang = _one_of(self.lang, LANGS, DEFAULT_LANG, 'lang')

        self.page_size = _one_of(str(self.page_size or '').lower(), PAGE_SIZE_KEYS,
                                 DEFAULT_PAGE_SIZE, 'page_size')
        self.margin_lr = _as_float(self.margin_lr, DEFAULT_MARGIN_LR, 'margin_lr')
        self.margin_tb = _as_float(self.margin_tb, DEFAULT_MARGIN_TB, 'margin_tb')
        self.header_offset = _as_float(self.header_offset, DEFAULT_HDR_FTR_Y, 'header_offset')

        self.html_font_mode = _one_of(self.html_font_mode, HTML_FONT_MODES, 'embed', 'html_font_mode')
        self.watermark_opacity = _clamp_int(self.watermark_opacity, 1, 100, 10, 'watermark_opacity')

        # Text fields are strings; a None from a config file must not reach a
        # renderer that will concatenate it.
        for name in _TEXT_FIELDS:
            setattr(self, name, str(getattr(self, name) or ''))
        for name in _FLAG_FIELDS:
            setattr(self, name, bool(getattr(self, name)))

    # ── Derived values ───────────────────────────────────────────────────────

    @property
    def page(self) -> PageSetup:
        """The sheet these options describe, with margins clamped to fit."""
        return make_page_setup(self.page_size, self.landscape, self.margin_lr,
                               self.margin_tb, self.header_offset)

    @property
    def header_text(self) -> str:
        """The running header actually drawn -- empty when it is switched off."""
        return self.header if self.show_header else ''

    @property
    def footer_text(self) -> str:
        """The running footer actually drawn -- empty when it is switched off."""
        return self.footer if self.show_footer else ''

    # ── Boundary with the old dict ───────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> RenderOptions:
        """Build options from the legacy dict, naming any key it does not know."""
        if not data:
            return cls()
        known = {f.name for f in fields(cls)}
        kwargs: dict[str, Any] = {}
        unknown: list[str] = []
        for key, value in data.items():
            name = ALIASES.get(key, key)
            if name in known:
                # An alias only fills in when the current name was not given.
                if name in kwargs and key in ALIASES:
                    continue
                kwargs[name] = value
            else:
                unknown.append(str(key))
        if unknown:
            _warn('unknown option(s) ignored: ' + ', '.join(sorted(unknown)))
        return cls(**kwargs)

    @classmethod
    def coerce(cls, opts: RenderOptions | Mapping[str, Any] | None) -> RenderOptions:
        """Accept either the object or the legacy dict, and return the object.

        Every renderer calls this on the way in, so passing a dict keeps working
        while everything downstream reads typed attributes.
        """
        if isinstance(opts, cls):
            return opts
        if opts is None or isinstance(opts, Mapping):
            return cls.from_dict(opts)
        raise TypeError(f'options must be a RenderOptions or a mapping, not {type(opts).__name__}')

    def to_dict(self) -> dict[str, Any]:
        """Return the options as a plain dict, for storage and for old callers."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def changed_from_defaults(self) -> dict[str, Any]:
        """Return only the options that differ from the built-in defaults.

        What a saved profile is made of: the choices, not the 48 fields. A
        default that changes in a later release then reaches profiles that never
        pinned it.
        """
        reference = RenderOptions()
        return {name: value for name, value in self.to_dict().items()
                if value != getattr(reference, name)}

    def replace(self, **changes: Any) -> RenderOptions:
        """Return a copy with *changes* applied, re-validated."""
        return RenderOptions.from_dict({**self.to_dict(), **changes})


# Filled after the class body so the field list stays the single source.
_FLAG_FIELDS = (
    'coords', 'flip', 'flip_auto', 'show_header', 'show_footer', 'answers_section',
    'answers_upside_down', 'answers_new_page', 'answers_after_chapter',
    'number_restart_per_chapter', 'lichess_link', 'landscape',
    'cover', 'contents',
    'allow_restricted_fonts',
)
_TEXT_FIELDS = (
    'title_template', 'title_custom', 'number_format', 'header', 'footer',
    'answers_title', 'lichess_label', 'doc_title', 'doc_author', 'doc_subject',
    'doc_keywords', 'doc_language', 'cover_title', 'cover_subtitle', 'cover_author',
    'contents_title', 'epub_css_path', 'watermark',
)


# ── Small coercion helpers ───────────────────────────────────────────────────

def _as_int(value: Any, fallback: int, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        _warn(f'{name}: {value!r} is not a whole number - using {fallback}')
        return fallback


def _as_float(value: Any, fallback: float, name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        _warn(f'{name}: {value!r} is not a number - using {fallback:g}')
        return fallback


def _at_least(value: Any, low: int, fallback: int, name: str) -> int:
    """Return the value as an int, never below *low*."""
    return max(low, _as_int(value, fallback, name))


def _clamp_int(value: Any, low: int, high: int, fallback: int, name: str) -> int:
    """Return the value as an int, held inside [low, high]."""
    return max(low, min(_as_int(value, fallback, name), high))


def _one_of(value: Any, allowed, fallback: str, name: str) -> str:
    """Return *value* when it is a recognised name, else warn and fall back."""
    text = str(value or '')
    if text in allowed:
        return text
    if not text:
        return fallback
    _warn(f'{name}: {text!r} is not one of {", ".join(allowed)} - using {fallback!r}')
    return fallback


def _as_grid(value: Any) -> tuple[int, int] | None:
    """Return a (columns, rows) pair, or None when no custom grid was asked for."""
    if not value:
        return None
    try:
        cols, rows = (int(n) for n in value)
    except (TypeError, ValueError):
        _warn(f'grid: {value!r} is not a COLSxROWS pair - using the layout preset')
        return None
    if cols < 1 or rows < 1:
        _warn(f'grid: {cols}x{rows} has no cells - using the layout preset')
        return None
    return (cols, rows)
