"""Persisted interface settings.

The stored file used to be an unversioned bag of whatever the last run happened
to write. A stale font name would leave the (read-only) combobox blank, and a
hand-edited value of the wrong type would surface as a Tcl error at generation
time. Everything is now validated on load and migrated forward.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from ..chars import BORDER_STYLE_KEYS, SYMBOL_KEYS
from ..fonts import FIGURINE_FILES, FONT_FILES, _default_board_font_name, _default_figurine_font_name
from ..i18n import DEFAULT_LANG, LANGS
from ..layouts import DEFAULT_LAYOUT, LAYOUTS
from ..log import _warn
from ..options import RenderOptions
from ..page import DEFAULT_PAGE_SIZE, PAGE_SIZE_KEYS

SETTINGS_VERSION = 2
CONFIG_PATH = Path.home() / '.diagpdf.json'
MAX_RECENT = 8

LINES_MODES = ('plain', 'numbered')
ORIENTATIONS = ('auto', 'white', 'black')
THEMES = ('light', 'dark')


@dataclass
class Settings:
    """Everything the interface remembers between runs."""

    lang: str = DEFAULT_LANG
    theme: str = 'light'
    layout: int = DEFAULT_LAYOUT
    font: str = ''
    font_size: int = 0
    coords: bool = True
    orient: str = 'auto'
    header: str = ''
    footer: str = '{page}'
    show_header: bool = True
    show_footer: bool = True
    symbol: str = 'square'
    border_style: str = 'simple'
    lines_count: int = 0
    lines_mode: str = 'plain'
    title_template: str = '{number} {comment}'
    lichess: bool = False
    answers_section: bool = False
    answers_title: str = ''
    answers_cols: int = 1
    answers_upside_down: bool = False
    answers_new_page: bool = True
    answers_after_chapter: bool = False
    figurine_font: str = ''
    epub_css_path: str = ''
    page_size: str = DEFAULT_PAGE_SIZE
    landscape: bool = False
    watermark: str = ''
    watermark_opacity: int = 10
    cover: bool = False
    contents: bool = False
    doc_author: str = ''
    recent_files: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.font = self.font if self.font in FONT_FILES else _default_board_font_name()
        self.figurine_font = (
            self.figurine_font if self.figurine_font in FIGURINE_FILES
            else _default_figurine_font_name()
        )
        self.lang = self.lang if self.lang in LANGS else DEFAULT_LANG
        self.theme = self.theme if self.theme in THEMES else 'light'
        self.orient = self.orient if self.orient in ORIENTATIONS else 'auto'
        self.symbol = self.symbol if self.symbol in SYMBOL_KEYS else 'square'
        self.border_style = self.border_style if self.border_style in BORDER_STYLE_KEYS else 'simple'
        self.lines_mode = self.lines_mode if self.lines_mode in LINES_MODES else 'plain'
        self.layout = _clamp(self.layout, 0, len(LAYOUTS) - 1, DEFAULT_LAYOUT)
        self.font_size = _clamp(self.font_size, 0, 200, 0)
        self.lines_count = _clamp(self.lines_count, 0, 5, 0)
        self.answers_cols = _clamp(self.answers_cols, 1, 2, 1)
        self.watermark_opacity = _clamp(self.watermark_opacity, 1, 100, 10)
        self.page_size = self.page_size.lower() if self.page_size.lower() in PAGE_SIZE_KEYS             else DEFAULT_PAGE_SIZE
        self.recent_files = [str(p) for p in self.recent_files][:MAX_RECENT]

    def remember_file(self, path: str | Path) -> None:
        """Move *path* to the front of the recent list."""
        text = str(path)
        self.recent_files = [text] + [p for p in self.recent_files if p != text]
        del self.recent_files[MAX_RECENT:]

    def existing_recent_files(self) -> list[str]:
        return [p for p in self.recent_files if Path(p).exists()]


def _clamp(value, low: int, high: int, fallback: int) -> int:
    try:
        return max(low, min(int(value), high))
    except (TypeError, ValueError):
        return fallback


def _coerce(raw: dict) -> dict:
    """Keep only known keys, with values of the declared type."""
    known = {f.name: f for f in fields(Settings)}
    clean: dict = {}
    for key, value in raw.items():
        spec = known.get(key)
        if spec is None:
            continue
        if spec.type in ('bool', bool):
            clean[key] = bool(value)
        elif spec.type in ('int', int):
            clean[key] = _clamp(value, -10 ** 6, 10 ** 6, 0)
        elif spec.type in ('str', str):
            clean[key] = str(value)
        elif isinstance(value, list):
            clean[key] = value
    return clean


def _migrate(raw: dict) -> dict:
    """Bring a settings file written by an older version up to date."""
    version = raw.get('version', 1)
    # v1 stored the answers heading as the English literal even when the
    # interface ran in another language; an empty value now means "use the
    # translated default".
    if version < 2 and raw.get('answers_title') == 'Solutions':
        raw['answers_title'] = ''
    return raw


def load_settings(path: Path | None = None) -> Settings:
    """Read the stored settings, falling back to defaults on any problem."""
    path = path or CONFIG_PATH
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return Settings()
    except Exception as exc:
        _warn(f'could not read {path.name} ({exc}) - starting from the defaults')
        return Settings()
    if not isinstance(raw, dict):
        _warn(f'{path.name} does not contain a settings object - starting from the defaults')
        return Settings()
    return Settings(**_coerce(_migrate(raw)))


def save_settings(settings: Settings, path: Path | None = None) -> None:
    """Write the settings, stamped with the current version."""
    path = path or CONFIG_PATH
    payload = {'version': SETTINGS_VERSION, **asdict(settings)}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    except Exception as exc:
        _warn(f'could not save settings: {exc}')


# A render option whose name differs from the window's name for it.
_OPTION_TO_SETTING = {
    'layout_idx': 'layout',
    'lichess_link': 'lichess',
}

# The window's own state, which a saved profile has no business changing.
_NOT_FROM_A_PROFILE = frozenset({'lang', 'theme', 'recent_files'})


def settings_from_opts(values: dict, base: Settings | None = None) -> Settings:
    """Return the window settings a saved profile describes.

    Everything the profile does not pin falls back to the window's own defaults,
    not to whatever happened to be on screen — so loading a profile gives the
    same result twice running. The interface language, the theme and the recent
    files belong to the window rather than to a document style, and survive.
    """
    base = base or Settings()
    fresh = Settings(lang=base.lang, theme=base.theme, recent_files=list(base.recent_files))
    known = {f.name for f in fields(Settings)}

    for name, value in values.items():
        target = _OPTION_TO_SETTING.get(name, name)
        if target in known and target not in _NOT_FROM_A_PROFILE:
            setattr(fresh, target, value)

    # The window has one orientation setting where the options have two flags.
    if 'flip' in values or 'flip_auto' in values:
        fresh.orient = ('black' if values.get('flip') else
                        'auto' if values.get('flip_auto', True) else 'white')

    # setattr skipped __post_init__, so rebuild once to re-validate.
    return Settings(**{f.name: getattr(fresh, f.name) for f in fields(Settings)})


def settings_to_opts(settings: Settings, *, number_offset: int = 0,
                     doc_title: str = '') -> RenderOptions:
    """Translate stored settings into the options the renderers take.

    Anything the window cannot set keeps the default declared on
    :class:`~diagpdf.options.RenderOptions`, so the GUI and the CLI agree on
    what an unset option means.
    """
    return RenderOptions(
        layout_idx=settings.layout,
        font=settings.font,
        font_size=settings.font_size,
        coords=settings.coords,
        flip=settings.orient == 'black',
        flip_auto=settings.orient == 'auto',
        header=settings.header,
        footer=settings.footer,
        show_header=settings.show_header,
        show_footer=settings.show_footer,
        symbol=settings.symbol,
        border_style=settings.border_style,
        lines_count=settings.lines_count,
        lines_mode=settings.lines_mode,
        title_template=settings.title_template,
        lichess_link=settings.lichess,
        answers_section=settings.answers_section,
        answers_title=settings.answers_title,
        answers_cols=settings.answers_cols,
        answers_upside_down=settings.answers_upside_down,
        answers_new_page=settings.answers_new_page,
        answers_after_chapter=settings.answers_after_chapter,
        figurine_font=settings.figurine_font,
        epub_css_path=settings.epub_css_path,
        number_offset=number_offset,
        lang=settings.lang,
        doc_title=doc_title,
        doc_language=settings.lang,
        doc_author=settings.doc_author,
        page_size=settings.page_size,
        landscape=settings.landscape,
        watermark=settings.watermark,
        watermark_opacity=settings.watermark_opacity,
        cover=settings.cover,
        contents=settings.contents,
    )
