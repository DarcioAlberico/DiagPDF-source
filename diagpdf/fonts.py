"""Discovery, resolution, patching and licence policy of the bundled fonts."""

from __future__ import annotations

import base64
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from .chars import (
    _ALPHA_REQUIRED_CHARS,
    _MERIDA_REQUIRED_CHARS,
    ALPHA_DG,
    BDR_N,
    CHESS_MERIDA,
    SYMBOL_CHARS,
)
from .errors import UnknownFontError
from .log import _warn
from .resources import _resource

_FALLBACK_FONT_FILES: dict[str, str] = {
    'AlphaDG': 'AlphaDG.ttf',
    'LeipzigDG': 'LeipzigDG.ttf',
    'CondalDG': 'CondalDG.ttf',
    'KingdomDG': 'KingdomDG.ttf',
    'ChessMerida': 'ChessMerida.ttf',
}
_FALLBACK_FIGURINE_FILES: dict[str, str] = {
    'Hastings': 'HastingsFigurine.TTF',
    'Zurich': 'ZurichFigurine.TTF',
    'Linares': 'LinaresFigurine.TTF',
}

@dataclass(frozen=True)
class _BoardFontInfo:
    file_name: str
    legacy_dg: bool
    direct_pdf: bool
    family_name: str
    top_fill: str = BDR_N
    draws_indicator: bool = False


def _ordered_names(names: list[str], preferred: list[str]) -> list[str]:
    seen = {name for name in names}
    ordered = [name for name in preferred if name in seen]
    ordered.extend(sorted(name for name in names if name not in ordered))
    return ordered


def _font_codepoints(font_path: Path) -> set[int]:
    try:
        from fontTools import ttLib
        font = ttLib.TTFont(str(font_path))
        cps: set[int] = set()
        for table in font['cmap'].tables:
            cps.update(table.cmap.keys())
        font.close()
        return cps
    except Exception:
        return set()


def _font_family_name(font_path: Path) -> str:
    """Return the internal family name declared inside the font."""
    try:
        from fontTools import ttLib
        font = ttLib.TTFont(str(font_path))
        names = font['name'].names
        for preferred_id in (16, 1, 21, 4):
            for record in names:
                if record.nameID == preferred_id:
                    value = str(record.toUnicode()).strip()
                    if value:
                        font.close()
                        return value
        font.close()
    except Exception:
        pass
    return font_path.stem


def _supports_pua_for_chars(codepoints: set[int], chars: set[str]) -> bool:
    return bool(codepoints) and all((0xF000 + ord(ch)) in codepoints for ch in chars)


def _has_chars(codepoints: set[int], chars) -> bool:
    """True when every character can be reached, directly or through the PUA."""
    return bool(codepoints) and all(
        ord(ch) in codepoints or (0xF000 + ord(ch)) in codepoints for ch in chars
    )


def _uses_alpha_layout(codepoints: set[int], name: str) -> bool:
    """Decide which piece map a board font needs, from what it actually carries.

    The two layouts part company on the knight and the bishop: Merida draws them
    with m/M and v/V, the Alpha family with j/J and n/N. Reading that off the
    font beats trusting the file name — a font called anything at all still has
    to be drawn with the map whose glyphs it has, and guessing from the name is
    how a diagram ends up missing its knights.
    """
    if name.endswith('DG') or name == 'AlphaDG':
        return True
    alpha = _has_chars(codepoints, set(ALPHA_DG.values()))
    merida = _has_chars(codepoints, set(CHESS_MERIDA.values()))
    return alpha and not merida


def _board_top_fill(codepoints: set[int]) -> str:
    """Return the glyph that draws the top edge of an Alpha-layout board.

    AlphaDG puts it on 'z'. Plain Chess Alpha has no 'z' and uses the double
    quote instead, so the border would come out with a missing top row.
    """
    if _has_chars(codepoints, {BDR_N}):
        return BDR_N
    return '"' if _has_chars(codepoints, {'"'}) else BDR_N


_CACHE_VERSION = 2   # board_info gained top_fill and draws_indicator
_CACHE_PATH = Path.home() / '.diagpdf' / 'fontcache.json'


def _fonts_fingerprint(fonts_dir: Path) -> list[list]:
    """Return a cheap signature of the font directory (name, size, mtime)."""
    if not fonts_dir.exists():
        return []
    return sorted(
        [path.name, stat.st_size, int(stat.st_mtime)]
        for path in fonts_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {'.ttf', '.otf'}
        for stat in (path.stat(),)
    )


def _read_font_cache(fingerprint: list[list]) -> tuple | None:
    """Return the cached discovery result when it still matches the directory."""
    try:
        cached = json.loads(_CACHE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return None
    if cached.get('version') != _CACHE_VERSION or cached.get('fingerprint') != fingerprint:
        return None
    try:
        board_files = dict(cached['board_files'])
        board_info = {name: _BoardFontInfo(*values) for name, values in cached['board_info'].items()}
        figurine_files = dict(cached['figurine_files'])
    except Exception:
        return None
    return board_files, board_info, figurine_files


def _write_font_cache(fingerprint: list[list], board_files, board_info, figurine_files) -> None:
    payload = {
        'version': _CACHE_VERSION,
        'fingerprint': fingerprint,
        'board_files': board_files,
        'board_info': {
            name: [info.file_name, info.legacy_dg, info.direct_pdf, info.family_name,
                   info.top_fill, info.draws_indicator]
            for name, info in board_info.items()
        },
        'figurine_files': figurine_files,
    }
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(payload), encoding='utf-8')
    except Exception:
        pass   # a missing cache only costs time, never correctness


def _scan_fonts() -> tuple[dict[str, str], dict[str, _BoardFontInfo], dict[str, str]]:
    """Read every bundled font to work out its character map and family name.

    This opens each TTF with fontTools, which costs a few hundred milliseconds
    for the bundled set — hence the cache in _discover_fonts.
    """
    fonts_dir = _resource('Fonts')
    board_files: dict[str, str] = {}
    board_info: dict[str, _BoardFontInfo] = {}
    figurine_files: dict[str, str] = {}

    if fonts_dir.exists():
        for path in sorted(fonts_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in {'.ttf', '.otf'}:
                continue
            stem = path.stem
            # Copies this program writes itself to work around a malformed VDMX
            # table. Offering one as a font would list the same typeface twice.
            if stem.endswith('_patch'):
                continue
            if 'figurine' in stem.lower():
                fig_name = re.sub(r'figurine$', '', stem, flags=re.IGNORECASE).strip() or stem
                figurine_files[fig_name] = path.name
                continue

            font_name = stem
            cps = _font_codepoints(path)
            legacy = _uses_alpha_layout(cps, font_name)
            required = _ALPHA_REQUIRED_CHARS if legacy else _MERIDA_REQUIRED_CHARS
            direct_pdf = not _supports_pua_for_chars(cps, required)
            # A font that has no glyph for the to-move symbols cannot draw the
            # indicator into the board; the renderers fall back to a Unicode one.
            draws_indicator = legacy and _has_chars(
                cps, {ch for pair in SYMBOL_CHARS.values() for ch in pair})

            board_files[font_name] = path.name
            board_info[font_name] = _BoardFontInfo(
                path.name, legacy, direct_pdf, _font_family_name(path),
                top_fill=_board_top_fill(cps), draws_indicator=draws_indicator)

    if not board_files:
        board_files = dict(_FALLBACK_FONT_FILES)
        board_info = {
            name: _BoardFontInfo(fname, name.endswith('DG') or name == 'AlphaDG', False, Path(fname).stem)
            for name, fname in board_files.items()
        }
    if not figurine_files:
        figurine_files = dict(_FALLBACK_FIGURINE_FILES)

    ordered_board = _ordered_names(
        list(board_files.keys()),
        ['ChessMerida', 'AlphaDG', 'LeipzigDG', 'CondalDG', 'KingdomDG'],
    )
    ordered_fig = _ordered_names(list(figurine_files.keys()), ['Zurich', 'Hastings', 'Linares'])

    board_files = {name: board_files[name] for name in ordered_board}
    board_info = {name: board_info[name] for name in ordered_board}
    figurine_files = {name: figurine_files[name] for name in ordered_fig}
    return board_files, board_info, figurine_files


def _discover_fonts(use_cache: bool = True) -> tuple[dict[str, str], dict[str, _BoardFontInfo], dict[str, str]]:
    """Return the available fonts, reading them from disk only when needed.

    The scan is keyed on the name, size and mtime of everything in ``Fonts/``,
    so adding, replacing or removing a font invalidates the cache by itself.
    """
    fingerprint = _fonts_fingerprint(_resource('Fonts'))
    if use_cache:
        cached = _read_font_cache(fingerprint)
        if cached is not None:
            return cached
    result = _scan_fonts()
    if use_cache:
        _write_font_cache(fingerprint, *result)
    return result


FONT_FILES, _BOARD_FONT_INFO, FIGURINE_FILES = _discover_fonts()
FONT_NAMES = list(FONT_FILES.keys())
MERIDA_COMPATIBLE_FONTS = frozenset(name for name, info in _BOARD_FONT_INFO.items() if not info.legacy_dg)
# Merida-layout fonts never carried the symbol, and neither do Alpha-layout
# fonts that turn out to have no glyph for it.
FONTS_WITHOUT_EMBEDDED_INDICATOR = frozenset(
    name for name, info in _BOARD_FONT_INFO.items() if not info.draws_indicator)
BOARD_TOP_FILL = {name: info.top_fill for name, info in _BOARD_FONT_INFO.items()}
DIRECT_PDF_CHESS_FONTS = frozenset(name for name, info in _BOARD_FONT_INFO.items() if info.direct_pdf)

# Figurine fonts for the answers section (piece letters only, standard ASCII)
# Encoding: K/Q/R/B/N/P = white pieces (uppercase), k/q/r/b/n/p = black (lowercase)
# In move notation we only render uppercase piece initials (K Q R B N).
FIGURINE_NAMES = list(FIGURINE_FILES.keys())

def _default_board_font_name() -> str:
    if 'ChessMerida' in FONT_FILES:
        return 'ChessMerida'
    if 'AlphaDG' in FONT_FILES:
        return 'AlphaDG'
    return FONT_NAMES[0] if FONT_NAMES else 'AlphaDG'


def _default_board_font_file() -> str:
    if FONT_FILES:
        return next(iter(FONT_FILES.values()))
    return 'AlphaDG.ttf'


def _default_figurine_font_name() -> str:
    if 'Zurich' in FIGURINE_FILES:
        return 'Zurich'
    if 'Hastings' in FIGURINE_FILES:
        return 'Hastings'
    return FIGURINE_NAMES[0] if FIGURINE_NAMES else 'Zurich'


def _board_font_family_name(font_name: str) -> str:
    """Return the internal family name used by Word/RTF for a board font."""
    info = _BOARD_FONT_INFO.get(font_name)
    return info.family_name if info and info.family_name else font_name

def _ensure_chess_font_patched(font_orig: Path, font_patched: Path) -> str:
    """Remove the broken VDMX table from a chess font TTF if present.

    fpdf2 crashes on fonts with a malformed VDMX table (AlphaDG.ttf).
    The patched copy is saved once and reused on subsequent runs.
    Returns the path to the usable font file (patched or original).
    """
    if font_patched.exists():
        return str(font_patched)
    if not font_orig.exists():
        raise FileNotFoundError(f'Chess font not found: {font_orig}')
    try:
        from fontTools import ttLib
        fnt = ttLib.TTFont(str(font_orig))
        if 'VDMX' not in fnt:
            return str(font_orig)   # no patching needed for this font
        del fnt['VDMX']
        fnt.save(str(font_patched))
    except Exception:
        font_patched.unlink(missing_ok=True)   # remove partial/corrupted file
        return str(font_orig)
    return str(font_patched if font_patched.exists() else font_orig)


def resolve_board_font(font_name: str) -> str:
    """Return the file name of a board font, or raise listing what is available.

    Falling back to an arbitrary file used to corrupt output silently: the wrong
    TTF was served while ``fen_to_diagram`` still used the requested font's
    character map, so every glyph came out wrong.
    """
    if font_name in FONT_FILES:
        return FONT_FILES[font_name]
    available = ', '.join(FONT_NAMES) or '(none found in Fonts/)'
    raise UnknownFontError(f'Unknown board font {font_name!r}. Available: {available}')


def coerce_board_font(font_name: str) -> str:
    """Return a usable board font name, warning when *font_name* is unknown.

    For entry points that must not crash on a stale setting (saved config).
    """
    if font_name in FONT_FILES:
        return font_name
    fallback = _default_board_font_name()
    _warn(f'unknown board font {font_name!r} - using {fallback!r} instead')
    return fallback


def get_chess_font_path(font_name: str, fonts_dir: Path) -> str:
    """Resolve the path to a chess font, patching it if necessary."""
    fname = resolve_board_font(font_name)
    orig    = fonts_dir / fname
    patched = fonts_dir / (Path(fname).stem + '_patch.ttf')
    return _ensure_chess_font_patched(orig, patched)


def font_embedding_allowed(font_path: Path) -> tuple[bool, bool]:
    """Return (can_embed, can_subset) from the font's OS/2 fsType flags.

    Applied by every exporter that embeds a font — PDF, EPUB and DOCX — so the
    policy no longer depends on which format the user happened to pick.
    """
    try:
        from fontTools.ttLib import TTFont
        font = TTFont(str(font_path))
        fs_type = int(getattr(font['OS/2'], 'fsType', 0)) if 'OS/2' in font else 0
        font.close()
    except Exception:
        return True, True

    restricted = bool(fs_type & 0x0002)
    bitmap_only = bool(fs_type & 0x0200)
    no_subsetting = bool(fs_type & 0x0100)
    return (not restricted and not bitmap_only), (not no_subsetting)


def check_embedding_permitted(font_path: Path, fmt: str, allow_restricted: bool) -> bool:
    """Return True when *font_path* may be embedded into a *fmt* document."""
    can_embed, _ = font_embedding_allowed(font_path)
    if can_embed:
        return True
    if allow_restricted:
        _warn(
            f'{font_path.name} is licensed as non-embeddable but '
            f'--allow-restricted-fonts was given — embedding into {fmt} anyway'
        )
        return True
    _warn(
        f'{font_path.name} is licensed as non-embeddable - not embedded in the '
        f'{fmt}. The document will need the font installed to display correctly '
        f'(use --allow-restricted-fonts to override)'
    )
    return False


def _get_text_font_candidates() -> list[str]:
    """Return system font paths to try as the Unicode text font."""
    candidates: list[str] = []
    if sys.platform == 'win32':
        wf = Path(os.environ.get('SystemRoot', os.environ.get('WINDIR', r'C:\Windows'))) / 'Fonts'
        uf = Path(os.environ.get('LOCALAPPDATA', '')) / 'Microsoft' / 'Windows' / 'Fonts'
        for name in ('arial.ttf', 'Arial.ttf', 'arialuni.ttf',
                     'calibri.ttf', 'Calibri.ttf',
                     'segoeui.ttf', 'SegoeUI.ttf',
                     'tahoma.ttf', 'Tahoma.ttf',
                     'verdana.ttf', 'Verdana.ttf'):
            for base in (wf, uf):
                p = base / name
                if p.exists():
                    candidates.append(str(p))
    elif sys.platform == 'darwin':
        for p in (Path('/Library/Fonts/Arial.ttf'),
                  Path('/Library/Fonts/Tahoma.ttf'),
                  Path('/System/Library/Fonts/Geneva.ttf')):
            if p.exists():
                candidates.append(str(p))
    else:
        for p in (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
                  Path('/usr/share/fonts/TTF/DejaVuSans.ttf'),
                  Path('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'),
                  Path('/usr/share/fonts/truetype/freefont/FreeSans.ttf')):
            if p.exists():
                candidates.append(str(p))
    return candidates


class FontManager:
    """Loads and registers chess, text, and figurine fonts into an fpdf2 PDF object."""

    def __init__(self, script_dir: Path) -> None:
        self.fonts_dir = script_dir / 'Fonts'

    def load_chess(self, pdf, font_name: str) -> None:
        """Register chess font as 'Chess' in pdf."""
        path = get_chess_font_path(font_name, self.fonts_dir)
        pdf.add_font('Chess', fname=path)

    def load_text(self, pdf) -> str:
        """Register best available Unicode text font as 'TextUni' in pdf.

        Returns the font name to use: 'TextUni' on success, 'helvetica' as fallback.
        """
        for candidate in _get_text_font_candidates():
            try:
                pdf.add_font('TextUni', fname=candidate)
            except Exception as e:
                print(f'TextUni regular load failed ({candidate}): {e}', file=sys.stderr)
                continue
            try:
                pdf.add_font('TextUni', style='B', fname=candidate)
            except Exception:
                pass
            return 'TextUni'
        return 'helvetica'

    def load_figurine(self, pdf, figurine_font: str, fallback: str) -> str:
        """Register figurine font as 'Figurine' in pdf.

        Returns 'Figurine' on success, fallback font name otherwise.
        """
        if not FIGURINE_NAMES:
            return fallback
        fname = FIGURINE_FILES.get(figurine_font, next(iter(FIGURINE_FILES.values()), ''))
        path  = self.fonts_dir / fname
        if path.exists():
            try:
                pdf.add_font('Figurine', fname=str(path))
                return 'Figurine'
            except Exception as e:
                print(f'Figurine font load failed ({path.name}): {e}', file=sys.stderr)
        return fallback

def _font_data_uri(font_path: Path) -> str:
    """Return *font_path* as a base64 ``data:`` URI for embedding in CSS."""
    mime = 'font/otf' if font_path.suffix.lower() == '.otf' else 'font/ttf'
    payload = base64.b64encode(font_path.read_bytes()).decode('ascii')
    return f'data:{mime};base64,{payload}'
