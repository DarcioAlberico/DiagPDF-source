"""Markdown output.

The other five formats draw the board with a chess font. Markdown has no way to
carry one, and a Markdown file that needs a folder of images beside it is no
longer one file — so the board is written with the Unicode chess pieces, inside
a fenced block. That renders on GitHub, in any editor and in any static-site
generator, with nothing to install and nothing to ship alongside.

What Markdown has no answer for — running headers, page numbers, a fixed sheet,
columns — is declared missing in the capability matrix and reported rather than
dropped in silence.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..fen import board_is_flipped, parse_fen
from ..fonts import resolve_board_font
from ..i18n import _answers_heading, _lichess_label, tr
from ..model import PositionDict
from ..options import RenderOptions
from ..parsers import _clean_moves
from .common import (
    _anchor_id,
    _chapter_groups,
    _format_number,
    _lichess_analysis_url,
    _make_title,
    _numbering,
    _side_indicator_text,
    _split_title_number_prefix,
)

# The pieces as the reader will see them. Black and white are the two Unicode
# chess ranges; an empty square is a middle dot, which keeps the grid legible
# without competing with the pieces.
PIECE_CHARS = {
    'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
    'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟',
}
EMPTY_SQUARE = '·'
FILE_LABELS = 'abcdefgh'

# Piece letters in the movetext, shown as symbols when a figurine is asked for.
FIGURINE_CHARS = {
    'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘',
}

# Only the characters that start markup *inline*. Escaping the full CommonMark
# set as well (- . + # ( ) !) is legal but turns an ordinary sentence into
# "\- this is \-\- unreadable\.", and none of them mean anything mid-line: the
# titles and chapter names written here are single lines, never line starts.
_ESCAPE_RE = re.compile(r'([\\`*_\[\]<>|])')


def _escape(text: str) -> str:
    """Escape Markdown markup in text that came from the input file."""
    return _ESCAPE_RE.sub(r'\\\1', text or '')


def _board_block(fen: str, opts: RenderOptions) -> list[str]:
    """Return the fenced block holding one position."""
    board, side = parse_fen(fen)
    flipped = board_is_flipped(side, opts.flip, opts.flip_auto)

    ranks = range(7, -1, -1) if not flipped else range(0, 8)
    files = range(0, 8) if not flipped else range(7, -1, -1)
    labels = FILE_LABELS if not flipped else FILE_LABELS[::-1]

    rows: list[str] = []
    for rank in ranks:
        squares = ' '.join(PIECE_CHARS.get(board[rank][f] or '', EMPTY_SQUARE) for f in files)
        rows.append(f'{rank + 1} {squares}' if opts.coords else squares)

    if opts.coords:
        rows.append('  ' + ' '.join(labels))
    # Which side moves is part of the position, and there is no font drawing it
    # into the board here. The glyph follows --symbol, as in every other format;
    # the words follow --lang, because a text format has no other clue to give.
    indicator = _side_indicator_text(side, opts.symbol)
    rows.append(f'{indicator} {tr("black_to_move" if side == "b" else "white_to_move", opts.lang)}')
    return ['```text', *rows, '```']


def _notation_lines(opts: RenderOptions, side: str) -> list[str]:
    """Return the blank lines left for writing moves by hand."""
    if opts.lines_count <= 0:
        return []
    blank = '\\_' * 8
    out: list[str] = []
    for index in range(opts.lines_count):
        if opts.lines_mode == 'numbered':
            # Black to move: the first move number belongs to White, so only
            # Black's blank is offered on that line.
            if index == 0 and side == 'b':
                out.append(f'{index + 1}. ... {blank}')
            else:
                out.append(f'{index + 1}. {blank} {blank}')
        else:
            out.append(f'{blank} {blank}')
    return ['', *[f'> {line}' for line in out]]


def _moves_text(moves: str, opts: RenderOptions) -> str:
    """Return the movetext, with piece letters as symbols when asked."""
    cleaned = _clean_moves(moves)
    if not cleaned:
        return ''
    shown = ''.join(FIGURINE_CHARS.get(ch, ch) for ch in cleaned)
    # The symbols are not Markdown markup, but the rest of the movetext can be.
    return _escape(shown)


def _front_matter(opts: RenderOptions) -> list[str]:
    """Return the YAML block carrying the document metadata, if there is any."""
    entries = [
        ('title', opts.doc_title.strip()),
        ('author', opts.doc_author.strip()),
        ('subject', opts.doc_subject.strip()),
        ('keywords', opts.doc_keywords.strip()),
        ('lang', (opts.doc_language.strip() or opts.lang)),
    ]
    filled = [(key, value) for key, value in entries if value]
    if not filled:
        return []
    # Quoted and with embedded quotes doubled: a title with a colon in it would
    # otherwise turn into a nested YAML mapping.
    return ['---', *[f'{k}: "{v.replace(chr(34), chr(34) * 2)}"' for k, v in filled], '---', '']


def generate_markdown(positions: list[PositionDict], opts: RenderOptions | dict,
                      out_path, progress=None) -> None:
    """Write a self-contained Markdown document, boards included."""
    opts = RenderOptions.coerce(opts)
    # The board is Unicode, so the chess font plays no part here -- but a
    # misspelled --font is still a mistake, and finding out about it only after
    # switching to another format would be worse.
    resolve_board_font(opts.font)
    valid = [p for p in positions if str(p.get('fen', '') or '').strip()]
    total = len(valid)

    parts: list[str] = _front_matter(opts)
    if opts.doc_title.strip():
        parts += [f'# {_escape(opts.doc_title.strip())}', '']

    numbers = _numbering(valid, opts)

    def flush_answers(collected: list[str]) -> None:
        """Write out the solutions gathered so far, then forget them."""
        if not collected:
            return
        parts.append(f'## {_escape(_answers_heading(opts))}')
        parts.append('')
        parts.extend(f'{line}  ' for line in collected)   # two spaces: a hard line break
        parts.append('')
        collected.clear()

    answers: list[str] = []
    for chapter, indices in _chapter_groups(valid):
        if chapter:
            parts += [f'## {_escape(chapter)}', '']
        for index in indices:
            position = valid[index]
            number = numbers[index]
            anchor = _anchor_id(index)
            title = _make_title(position, number, opts.title_template,
                                opts.title_mode, opts.title_custom, opts)
            prefix, rest = _split_title_number_prefix(title, number, opts)

            # The number links to the solution, matching every other format.
            heading = _escape(title)
            if opts.answers_section and prefix:
                heading = f'[{_escape(prefix.strip())}](#answer-{anchor})'
                if rest:
                    heading += f' {_escape(rest)}'
            parts += [f'<a id="diagram-{anchor}"></a>', '', f'### {heading}', '']
            parts += _board_block(str(position.get('fen', '')), opts)

            _, side = parse_fen(str(position.get('fen', '')))
            parts += _notation_lines(opts, side)

            if opts.lichess_link:
                url = _lichess_analysis_url(str(position.get('fen', '')))
                if url:
                    parts += ['', f'[{_escape(_lichess_label(opts))}]({url})']

            moves = _moves_text(str(position.get('moves', '') or ''), opts)
            if moves:
                if opts.answers_section:
                    answers.append(
                        f'<a id="answer-{anchor}"></a>'
                        f'[{_format_number(number, opts)}](#diagram-{anchor}). {moves}'
                    )
                else:
                    parts += ['', moves]
            parts.append('')

            if progress and total:
                progress(int((index + 1) * 100 / total))

        if opts.answers_section and opts.answers_after_chapter:
            flush_answers(answers)

    if opts.answers_section:
        flush_answers(answers)

    if progress:
        progress(100)
    Path(out_path).write_text('\n'.join(parts).rstrip() + '\n', encoding='utf-8')
