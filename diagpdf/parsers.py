"""Readers for the PGN, FEN-file and EPD input formats."""

from __future__ import annotations

import re
from pathlib import Path

from .errors import FenError
from .fen import validate_fen
from .log import _warn
from .model import PositionDict


def _first_text_comment(moves_raw: str) -> str:
    """Return first non-markup comment from PGN game text, or empty string."""
    for m in re.finditer(r'\{([^}]*)\}', moves_raw):
        text = re.sub(r'\[%[^\]]+\]', '', m.group(1)).strip()
        if text:
            return text
    return ''


def _clean_moves(moves_raw: str) -> str:
    """Extract clean move text from a raw PGN game body.

    Removes {comments}, NAG glyphs ($1, !?, etc.) and result tokens.
    Preserves move numbers, moves, and parenthesised variations.

    Example input:
        1. Qxd8+ {тактический удар} $1 Kxd8 2. Ne4+ Kc8 (2... Ke8 3. Rb8#) 3. Rd8# 1-0
    Example output:
        1. Qxd8+ Kxd8 2. Ne4+ Kc8 (2... Ke8 3. Rb8#) 3. Rd8#
    """
    # Strip escape lines (% in column 1) — PGN §6
    text = re.sub(r'(?m)^%.*$', ' ', moves_raw)
    # Strip {comments} (including multi-line). Brace comments do not nest (§8.2.5).
    text = re.sub(r'\{[^}]*\}', ' ', text)
    # Strip rest-of-line comments (; …) — PGN §8.2.5
    text = re.sub(r';[^\n]*', ' ', text)
    # Strip NAG codes ($1 .. $255)
    text = re.sub(r'\$\d+', '', text)
    # Strip annotation glyphs (!, ?, !!, ??, !?, ?!)
    text = re.sub(r'[!?]+', '', text)
    # Strip result tokens. The word boundary has to stay outside the '*'
    # alternative: '*' is not a word character, so \b could never match before
    # it and an unfinished-game marker was left in the answer text.
    text = re.sub(r'(?:\b(?:1-0|0-1|1/2-1/2)|\*)\s*$', '', text.rstrip())
    # Collapse all whitespace, including the line wrapping PGN files use at
    # column 80. Those breaks are a file-format artefact, and each exporter
    # rendered a stray newline differently (PDF broke the line, HTML showed a
    # space, Word dropped it). Parenthesised variations are kept intact.
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'\s+\)', ')', text)
    return text.strip()




_TAG_PAIR = r'\[\s*[A-Za-z0-9_]+\s+"(?:[^"\\]|\\.)*"\s*\]'
# Export format puts one tag pair per line, but import format allows several
# (PGN §3.2), so a tag line is any line made up entirely of tag pairs.
_TAG_LINE_RE = re.compile(rf'^(?:\s*{_TAG_PAIR})+\s*$')
_TAG_ANY_RE = re.compile(r'\[\s*([A-Za-z0-9_]+)\s+"((?:[^"\\]|\\.)*)"\s*\]')


def _unescape_tag_value(value: str) -> str:
    """Undo the backslash escaping allowed inside PGN tag values (PGN §8.1.1)."""
    return re.sub(r'\\(.)', r'\1', value)


def _comment_state_after(line: str, in_comment: bool) -> bool:
    """Return the ``{...}`` comment state after consuming *line*.

    PGN brace comments do not nest (§8.2.5), so a single flag is enough.
    A ``;`` starts a rest-of-line comment and ``%`` in column 1 escapes the
    whole line — neither can open or close a brace comment.
    """
    for idx, ch in enumerate(line):
        if in_comment:
            if ch == '}':
                in_comment = False
        elif ch == '{':
            in_comment = True
        elif ch == ';' or ch == '%' and idx == 0:
            break
    return in_comment


def _split_pgn_games(content: str) -> list[str]:
    """Split PGN text into one block per game.

    A new game starts at a tag line that follows movetext. Tag-looking lines
    inside a brace comment are ignored, so a ``[Event "..."]`` written at column
    one inside a comment no longer truncates the game.
    """
    games: list[str] = []
    current: list[str] = []
    seen_movetext = False
    in_comment = False

    for line in content.splitlines(keepends=True):
        stripped = line.strip()
        is_tag = bool(stripped) and not in_comment and _TAG_LINE_RE.match(stripped) is not None

        if is_tag and seen_movetext and current:
            games.append(''.join(current))
            current = []
            seen_movetext = False

        current.append(line)

        if is_tag:
            continue
        in_comment = _comment_state_after(line, in_comment)
        if stripped:
            seen_movetext = True

    if current:
        games.append(''.join(current))
    return [block for block in games if block.strip()]


def _split_tags_and_movetext(block: str) -> tuple[dict[str, str], str]:
    """Split one PGN game block into its tag pairs and its movetext."""
    tags: dict[str, str] = {}
    movetext_start = 0
    offset = 0

    for line in block.splitlines(keepends=True):
        stripped = line.strip()
        if not stripped:
            offset += len(line)
            continue
        if _TAG_LINE_RE.match(stripped) is None:
            break
        for name, value in _TAG_ANY_RE.findall(stripped):
            tags[name] = _unescape_tag_value(value)
        offset += len(line)
        movetext_start = offset

    return tags, block[movetext_start:].strip()


def parse_pgn(content: str, *, require_fen: bool = True) -> list[PositionDict]:
    """Parse a PGN file and return a list of position dicts.

    Each dict contains: fen, white, black, event, date, chapter, comment, moves.
    The 'comment' field is the first text comment from the game body (used as title).

    Args:
        content: the PGN text.
        require_fen: when True (the default) only games carrying a ``[FEN]`` tag
            are returned, because a game without one has no position to draw.
            Pass False to keep complete games as well — their diagrams come from
            replaying the moves (see :mod:`diagpdf.moves`).
    """
    positions: list[PositionDict] = []
    for block in _split_pgn_games(content):
        tags, movetext = _split_tags_and_movetext(block)
        fen = tags.get('FEN')
        if not fen and require_fen:
            continue
        moves_raw = re.sub(r'\s*(1-0|0-1|1/2-1/2|\*)\s*$', '', movetext).strip()
        positions.append({
            'fen':     fen or '',
            'white':   tags.get('White', ''),
            'black':   tags.get('Black', ''),
            'event':   tags.get('Event', ''),
            'date':    tags.get('Date', ''),
            'chapter': tags.get('Chapter', ''),
            'comment': _first_text_comment(moves_raw),
            'moves':   moves_raw,
        })
    return positions


def parse_fen_file(content: str) -> list[PositionDict]:
    """Parse a .fen file containing [FEN "..."] tags and return position dicts."""
    return [{'fen': m.group(1), 'white': '', 'black': '', 'event': '',
             'date': '', 'chapter': '', 'comment': '', 'moves': ''}
            for m in re.finditer(r'\[FEN\s+"([^"]*)"\]', content)]


def parse_epd(content: str) -> list[PositionDict]:
    """Parse an EPD file (one position per line) and return position dicts.

    Extracts 'id' operand as white, 'bm' operand as black. FEN is reconstructed
    with placeholder move counters (0 1).
    """
    positions = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith(';'):
            continue
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        fen = ' '.join(parts[:4]) + ' 0 1'
        rest = parts[4] if len(parts) > 4 else ''
        id_m = re.search(r'id\s+"([^"]*)"', rest)
        bm_m = re.search(r'bm\s+([^;]+)', rest)
        positions.append({
            'fen':     fen or '',
            'white':   id_m.group(1).strip() if id_m else '',
            'black':   bm_m.group(1).strip().rstrip(';') if bm_m else '',
            'event':   '', 'date': '', 'chapter': '', 'comment': '', 'moves': '',
        })
    return positions


def read_chess_file(path: Path, encoding: str = '') -> str:
    """Read a PGN/FEN/EPD file, guessing the encoding when none is given.

    PGN files are routinely saved as cp1252/latin-1. Decoding those as UTF-8
    with ``errors='replace'`` used to turn every accented character into U+FFFD
    without telling anyone.
    """
    raw = path.read_bytes()
    if encoding:
        return raw.decode(encoding)   # raises LookupError on an unknown codec

    for candidate in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            text = raw.decode(candidate)
        except UnicodeDecodeError:
            continue
        if candidate != 'utf-8-sig':
            _warn(f'{path.name} is not valid UTF-8 - decoded as {candidate}')
        return text

    _warn(f'{path.name} could not be decoded cleanly - unreadable characters replaced')
    return raw.decode('utf-8', errors='replace')


def apply_fen_policy(positions: list[PositionDict], mode: str = 'skip') -> list[PositionDict]:
    """Drop or reject positions whose FEN is invalid.

    Args:
        positions: parsed positions.
        mode: ``'skip'`` warns and drops them, ``'fail'`` raises on the first one.

    Raises:
        FenError: when *mode* is ``'fail'`` and a position is invalid.
    """
    kept: list[PositionDict] = []
    dropped = 0
    for idx, pos in enumerate(positions, start=1):
        problems = validate_fen(pos.get('fen', ''))
        if not problems:
            kept.append(pos)
            continue
        detail = '; '.join(problems)
        if mode == 'fail':
            raise FenError(f'position {idx}: invalid FEN ({detail})')
        dropped += 1
        _warn(f'position {idx} skipped - invalid FEN ({detail})')
    if dropped:
        _warn(
            f'{dropped} position(s) skipped; the remaining diagrams are renumbered. '
            f'Use --on-invalid fail to stop instead'
        )
    return kept
