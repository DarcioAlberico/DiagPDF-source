"""Diagrams taken from a game's moves rather than from a ``[FEN]`` tag.

Until now a game had to carry a ``[FEN]`` tag to produce anything: a normal PGN
of complete games yielded zero diagrams, which ruled out the most ordinary input
there is. Replaying the movetext fills that gap.

The replay is delegated to `python-chess`. Writing a SAN parser and move
generator is not hard to start and very hard to finish — castling rights, en
passant, promotion, and the disambiguation rules all have to be exactly right,
and a subtle error would produce a wrong diagram, which is the worst thing this
program could do. The dependency is optional: without it the feature reports
what to install instead of failing obscurely.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .log import _warn
from .model import PositionDict

DEFAULT_MARKER = '#diagram'


class MoveEngineUnavailable(RuntimeError):
    """Raised when move replay is requested but python-chess is not installed."""


@dataclass(frozen=True)
class MoveSelection:
    """Which positions of a game to turn into diagrams."""

    at_moves: tuple[int, ...] = ()     # after these full-move numbers
    every: int = 0                     # after every N full moves
    last: bool = False                 # the final position
    marker: str = ''                   # where a comment carries this marker

    def __bool__(self) -> bool:
        return bool(self.at_moves or self.every or self.last or self.marker)


def parse_move_selection(text: str, *, every: int = 0, marker: str = '') -> MoveSelection:
    """Build a selection from the ``--at-move`` argument.

    Accepts ``20``, ``20,25,30`` and ``last`` (alone or mixed in).
    """
    at_moves: list[int] = []
    last = False
    for token in str(text or '').replace(';', ',').split(','):
        token = token.strip().lower()
        if not token:
            continue
        if token in ('last', 'end', 'final'):
            last = True
            continue
        try:
            number = int(token)
        except ValueError as exc:
            raise ValueError(f'invalid --at-move value: {token!r}') from exc
        if number < 1:
            raise ValueError(f'--at-move must be 1 or greater, got {number}')
        at_moves.append(number)
    return MoveSelection(tuple(sorted(set(at_moves))), max(0, int(every)), last, marker.strip())


# ── Movetext tokenising ───────────────────────────────────────────────────────

_TOKEN_RE = re.compile(r"""
    (?P<comment>\{[^}]*\})            # brace comment
  | (?P<rav_open>\()                  # start of a variation
  | (?P<rav_close>\))
  | (?P<nag>\$\d+)
  | (?P<number>\d+\.(?:\.\.)?)        # move number, possibly "12..."
  | (?P<result>1-0|0-1|1/2-1/2|\*)
  | (?P<san>[OoA-Za-z][A-Za-z0-9=+#!?-]*)
""", re.VERBOSE)


@dataclass(frozen=True)
class _Move:
    san: str
    comment: str


def _mainline_moves(movetext: str) -> list[_Move]:
    """Return the mainline SAN tokens, each with the comment that follows it.

    Variations in parentheses are skipped: they are alternatives, not the line
    the diagram should follow.
    """
    moves: list[_Move] = []
    depth = 0
    pending_comment = ''
    for match in _TOKEN_RE.finditer(re.sub(r'(?m)^%.*$', ' ', movetext)):
        kind = match.lastgroup
        value = match.group()
        if kind == 'rav_open':
            depth += 1
        elif kind == 'rav_close':
            depth = max(0, depth - 1)
        elif depth:
            continue
        elif kind == 'comment':
            if moves:
                moves[-1] = _Move(moves[-1].san, (moves[-1].comment + ' ' + value[1:-1]).strip())
            else:
                pending_comment = value[1:-1].strip()
        elif kind == 'san':
            san = value.rstrip('!?')
            if san:
                moves.append(_Move(san, pending_comment))
                pending_comment = ''
    return moves


# ── Replay ────────────────────────────────────────────────────────────────────

def _require_engine():
    try:
        import chess
    except ImportError as exc:
        raise MoveEngineUnavailable(
            'reading diagrams from moves needs python-chess - install it with: pip install chess'
        ) from exc
    return chess


def selected_plies(move_count: int, selection: MoveSelection, marked: set[int]) -> list[int]:
    """Return the ply indices (1-based) the selection asks for.

    A full move number *n* means the position after Black's *n*-th move, which
    is ply ``2n`` — or the last ply, when the game ends on White's move.
    """
    plies: set[int] = set(marked)
    for number in selection.at_moves:
        plies.add(min(number * 2, move_count))
    if selection.every > 0:
        for number in range(selection.every, move_count // 2 + 1, selection.every):
            plies.add(number * 2)
    if selection.last:
        plies.add(move_count)
    return sorted(ply for ply in plies if 1 <= ply <= move_count)


def positions_from_moves(
    game: PositionDict,
    selection: MoveSelection,
    *,
    start_fen: str = '',
) -> list[PositionDict]:
    """Replay a game's movetext and return one position per selected point.

    Args:
        game: a parsed game; its ``moves`` field carries the movetext.
        selection: which positions to keep.
        start_fen: starting position, for games that also carry a ``[FEN]`` tag.

    Raises:
        MoveEngineUnavailable: python-chess is not installed.
    """
    chess = _require_engine()
    moves = _mainline_moves(game.get('moves', ''))
    if not moves:
        return []

    board = chess.Board(start_fen) if start_fen else chess.Board()
    marker = (selection.marker or '').lower()
    fens: list[str] = []
    marked: set[int] = set()
    comments: list[str] = []

    for index, move in enumerate(moves, start=1):
        try:
            board.push_san(move.san)
        except ValueError:
            _warn(
                f'{game.get("event", "") or "game"}: could not play {move.san!r} '
                f'at move {(index + 1) // 2} - the rest of the game was skipped'
            )
            break
        fens.append(board.fen())
        comments.append(move.comment)
        if marker and marker in move.comment.lower():
            marked.add(index)

    if not fens:
        return []

    out: list[PositionDict] = []
    for ply in selected_plies(len(fens), selection, marked):
        position = dict(game)
        position['fen'] = fens[ply - 1]
        position['moves'] = ''            # the diagram is the position, not a puzzle
        comment = comments[ply - 1]
        if marker:
            comment = re.sub(re.escape(selection.marker), '', comment, flags=re.IGNORECASE).strip()
        position['comment'] = comment or _describe_ply(ply)
        position['ply'] = ply
        out.append(position)
    return out


def _describe_ply(ply: int) -> str:
    """Return a short label such as '12...' or '13.' for a ply index."""
    number = (ply + 1) // 2
    return f'{number}.' if ply % 2 else f'{number}...'


def expand_positions(
    positions: list[PositionDict],
    selection: MoveSelection,
) -> list[PositionDict]:
    """Turn parsed games into diagram positions according to *selection*.

    Games that already carry a FEN are kept as they are when no selection is
    given; with a selection, the moves are replayed from that FEN.
    """
    if not selection:
        return positions

    out: list[PositionDict] = []
    for game in positions:
        start_fen = str(game.get('fen', '') or '').strip()
        replayed = positions_from_moves(game, selection, start_fen=start_fen)
        if replayed:
            out.extend(replayed)
        elif start_fen:
            out.append(game)          # nothing to replay, keep the tagged position
    return out
