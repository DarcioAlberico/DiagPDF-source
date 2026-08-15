"""Command line interface."""

from __future__ import annotations

import argparse
import sys
from operator import attrgetter
from pathlib import Path

from . import __version__
from . import profiles as profiles_mod
from .capabilities import unsupported_options
from .chars import BORDER_STYLE_KEYS, SYMBOL_KEYS
from .errors import FenError, UnknownFontError
from .fonts import FIGURINE_NAMES, FONT_NAMES, _default_board_font_name, _default_figurine_font_name
from .gui import run_gui
from .i18n import DEFAULT_LANG, LANGS, lang_label
from .images import IMAGE_FORMATS, export_images
from .layouts import DEFAULT_LAYOUT, LAYOUTS, parse_grid
from .log import _say, _warn, configure_logging
from .moves import (
    DEFAULT_MARKER,
    MoveEngineUnavailable,
    expand_positions,
    parse_move_selection,
)
from .options import RenderOptions
from .output import generate_output
from .page import DEFAULT_MARGIN_LR, DEFAULT_MARGIN_TB, DEFAULT_PAGE_SIZE, PAGE_SIZE_KEYS
from .parsers import apply_fen_policy, parse_epd, parse_fen_file, parse_pgn, read_chess_file
from .profiles import ProfileError

# Which command-line option feeds which render option, and how to read it.
# One table serves both jobs that need it: building the options for a run, and
# working out what a --save-profile should remember. Options absent from a
# command line are absent from here too, which is what lets a profile show
# through.
OPTION_SOURCES: tuple[tuple[str, str, object], ...] = (
    ('layout',          'layout_idx',      attrgetter('layout')),
    ('font',            'font',            attrgetter('font')),
    ('font_size',       'font_size',       attrgetter('font_size')),
    ('text_size',       'text_size',       attrgetter('text_size')),
    ('no_coords',       'coords',          lambda a: not a.no_coords),
    ('flip',            'flip',            attrgetter('flip')),
    ('no_auto_flip',    'flip_auto',       lambda a: not a.no_auto_flip),
    ('header',          'header',          attrgetter('header')),
    ('footer',          'footer',          attrgetter('footer')),
    ('no_header',       'show_header',     lambda a: not a.no_header),
    ('no_footer',       'show_footer',     lambda a: not a.no_footer),
    ('symbol',          'symbol',          attrgetter('symbol')),
    ('border',          'border_style',    attrgetter('border')),
    ('lines',           'lines_count',     attrgetter('lines')),
    ('lines_numbered',  'lines_mode',      lambda a: 'numbered' if a.lines_numbered else 'plain'),
    ('title_template',  'title_template',  attrgetter('title_template')),
    ('lichess_link',    'lichess_link',    attrgetter('lichess_link')),
    ('lichess_label',   'lichess_label',   attrgetter('lichess_label')),
    ('answers',         'answers_section', attrgetter('answers')),
    ('answers_title',   'answers_title',   attrgetter('answers_title')),
    ('answers_cols',    'answers_cols',    attrgetter('answers_cols')),
    ('answers_upside_down', 'answers_upside_down', attrgetter('answers_upside_down')),
    ('answers_same_page', 'answers_new_page', lambda a: not a.answers_same_page),
    ('answers_after_chapter', 'answers_after_chapter', attrgetter('answers_after_chapter')),
    ('figurine_font',   'figurine_font',   attrgetter('figurine_font')),
    ('epub_css',        'epub_css_path',   attrgetter('epub_css')),
    ('number_start',    'number_start',    attrgetter('number_start')),
    ('number_format',   'number_format',   attrgetter('number_format')),
    ('number_restart_per_chapter', 'number_restart_per_chapter',
     attrgetter('number_restart_per_chapter')),
    ('lang',            'lang',            attrgetter('lang')),
    ('html_font_mode',  'html_font_mode',  attrgetter('html_font_mode')),
    ('doc_title',       'doc_title',       attrgetter('doc_title')),
    ('doc_author',      'doc_author',      attrgetter('doc_author')),
    ('doc_language',    'doc_language',    attrgetter('doc_language')),
    ('doc_subject',     'doc_subject',     attrgetter('doc_subject')),
    ('doc_keywords',    'doc_keywords',    attrgetter('doc_keywords')),
    ('page_size',       'page_size',       attrgetter('page_size')),
    ('landscape',       'landscape',       attrgetter('landscape')),
    ('margin_lr',       'margin_lr',       attrgetter('margin_lr')),
    ('margin_tb',       'margin_tb',       attrgetter('margin_tb')),
    ('watermark',       'watermark',       attrgetter('watermark')),
    ('watermark_opacity', 'watermark_opacity', attrgetter('watermark_opacity')),
    ('cover',           'cover',           attrgetter('cover')),
    ('cover_subtitle',  'cover_subtitle',  attrgetter('cover_subtitle')),
    ('contents',        'contents',        attrgetter('contents')),
    ('contents_title',  'contents_title',  attrgetter('contents_title')),
    ('allow_restricted_fonts', 'allow_restricted_fonts',
     attrgetter('allow_restricted_fonts')),
)


def _make_parser() -> argparse.ArgumentParser:
    """Build the command-line parser.

    Separate from :func:`main` so the accepted options can be inspected — by a
    test, or by anything embedding the CLI — without running a conversion.
    """
    parser = argparse.ArgumentParser(
        description='Convert PGN/FEN/EPD chess files into chess diagrams: '
                    'PDF, LaTeX, HTML, EPUB, DOCX, RTF or Markdown.'
    )
    parser.add_argument('--version', action='version', version=f'DiagPDF {__version__}')
    parser.add_argument('input', nargs='*', help='Input file(s): .pgn, .fen, .epd')
    parser.add_argument('-o', '--output', help='Output file (default: <input>.pdf)')
    parser.add_argument('-l', '--layout', type=int, default=DEFAULT_LAYOUT,
                        help=f'Layout preset 0–{len(LAYOUTS)-1} (default {DEFAULT_LAYOUT}: 2-col 6/4)')
    _default_font = _default_board_font_name()
    _default_fig = _default_figurine_font_name()
    parser.add_argument('-f', '--font', choices=FONT_NAMES, default=_default_font,
                        help=f'Chess font (default: {_default_font})')
    parser.add_argument('--no-coords', action='store_true', help='Hide board coordinates')
    parser.add_argument('--flip', action='store_true', help='Flip board (black at bottom)')
    parser.add_argument('--no-auto-flip', action='store_true',
                        help='Disable auto-flip when Black is to move')
    parser.add_argument('--header', default='', help='Header text (default: filename stem)')
    parser.add_argument('--footer', default='', help='Footer prefix (default: page number only)')
    parser.add_argument('--no-header', action='store_true', help='Suppress header')
    parser.add_argument('--no-footer', action='store_true', help='Suppress footer')
    parser.add_argument('--symbol', choices=SYMBOL_KEYS, default='square',
                        help='To-move indicator symbol (default: square)')
    parser.add_argument('--border', choices=BORDER_STYLE_KEYS, default='simple',
                        help='Merida border style: simple, double, or none (default: simple)')
    parser.add_argument('--lines', type=int, default=0, choices=range(6),
                        help='Notation lines per diagram (default: 0)')
    parser.add_argument('--lines-numbered', action='store_true',
                        help='Prefix notation lines with move numbers')
    parser.add_argument('--title-template', default='',
                        help='Title template, e.g. "{number} {comment}" (vars: number, event, white, black, date, comment)')
    parser.add_argument('--font-size', type=int, default=0,
                        help='Board font size in pt (0 = auto)')
    parser.add_argument('--lichess-link', action='store_true',
                        help='Embed clickable Lichess analysis links in position titles')
    parser.add_argument('--answers', action='store_true',
                        help='Append answers section at the end of the document')
    parser.add_argument('--answers-title', default='',
                        help='Heading for the answers section (default: translated "Solutions")')
    parser.add_argument('--answers-cols', type=int, default=1, choices=[1, 2],
                        help='Columns in the answers section (1 or 2, default: 1)')
    parser.add_argument('--answers-same-page', action='store_true',
                        help='Continue the answers straight after the diagrams instead '
                             'of starting them on a new page')
    parser.add_argument('--answers-after-chapter', action='store_true',
                        help='Put the solutions at the end of each chapter instead '
                             'of one section at the end of the document')
    parser.add_argument('--answers-upside-down', action='store_true',
                        help='Print the answers rotated 180 degrees, so a solution '
                             'cannot be read by accident (PDF, HTML, EPUB)')
    parser.add_argument('--figurine-font', default=_default_fig,
                        choices=FIGURINE_NAMES if FIGURINE_NAMES else [_default_fig],
                        help=f'Figurine font for piece symbols in answers (default: {_default_fig})')
    parser.add_argument('--epub-css', default='',
                        help='Optional CSS file to bundle into EPUB exports')
    parser.add_argument('--from', dest='pos_from', type=int, default=0, metavar='N',
                        help='Start from position N (1-based, default: 1)')
    parser.add_argument('--to', dest='pos_to', type=int, default=0, metavar='N',
                        help='End at position N inclusive (default: last)')
    parser.add_argument('--keep-numbers', '--no-renumber', action='store_true',
                        dest='keep_numbers',
                        help='Keep original position numbers instead of renumbering from 1')
    parser.add_argument('--text-size', type=int, default=0,
                        help='Title/text size in pt (0 = proportional to the layout)')
    parser.add_argument('--lang', choices=LANGS, default='en',
                        help='Language of generated labels (default: en)')
    parser.add_argument('--lichess-label', default='',
                        help='Override the text of the Lichess analysis link')
    parser.add_argument('--html-font-mode', choices=('embed', 'link', 'none'), default='embed',
                        help='How standalone HTML gets the board font (default: embed)')
    parser.add_argument('--title', dest='doc_title', default='',
                        help='Document title (HTML/EPUB metadata)')
    parser.add_argument('--author', dest='doc_author', default='',
                        help='Document author (EPUB metadata)')
    parser.add_argument('--language', dest='doc_language', default='',
                        help='Document language code (EPUB metadata, default: --lang)')
    parser.add_argument('--allow-restricted-fonts', action='store_true',
                        help='Embed fonts whose licence marks them non-embeddable')
    parser.add_argument('--on-invalid', choices=('skip', 'fail'), default='skip',
                        help='What to do with invalid FEN positions (default: skip with a warning)')
    parser.add_argument('--encoding', default='',
                        help='Input file encoding (default: utf-8, falling back to cp1252)')
    parser.add_argument('--list-fonts', action='store_true',
                        help='List the available board and figurine fonts, then exit')
    parser.add_argument('--list-languages', action='store_true',
                        help='List the languages the generated labels come in, then exit')
    page = parser.add_argument_group('page setup')
    page.add_argument('--page-size', choices=PAGE_SIZE_KEYS, default=DEFAULT_PAGE_SIZE,
                      help=f'Paper size (default: {DEFAULT_PAGE_SIZE})')
    page.add_argument('--landscape', action='store_true', help='Rotate the sheet')
    page.add_argument('--margin-lr', type=float, default=DEFAULT_MARGIN_LR, metavar='MM',
                      help=f'Left and right margin in mm (default: {DEFAULT_MARGIN_LR:g})')
    page.add_argument('--margin-tb', type=float, default=DEFAULT_MARGIN_TB, metavar='MM',
                      help=f'Top and bottom margin in mm (default: {DEFAULT_MARGIN_TB:g})')

    front = parser.add_argument_group('front matter')
    front.add_argument('--watermark', default='', metavar='TEXT',
                       help='Stamp TEXT across every page (PDF, LaTeX, HTML, DOCX, RTF)')
    front.add_argument('--watermark-opacity', type=int, default=10, metavar='PCT',
                       help='How strong the watermark is, 1-100 (default: 10)')
    front.add_argument('--cover', action='store_true', help='Add a title page (PDF)')
    front.add_argument('--cover-subtitle', default='', help='Subtitle shown on the cover')
    front.add_argument('--contents', action='store_true',
                       help='Add a table of contents listing the chapters (PDF)')
    front.add_argument('--contents-title', default='',
                       help='Heading of the table of contents (default: translated)')
    front.add_argument('--subject', dest='doc_subject', default='', help='Document subject')
    front.add_argument('--keywords', dest='doc_keywords', default='', help='Document keywords')

    grid = parser.add_argument_group('grid and numbering')
    grid.add_argument('--grid', default='', metavar='COLSxROWS',
                      help='Free-form diagram grid, e.g. 3x4 (overrides --layout)')
    grid.add_argument('--number-start', type=int, default=1, metavar='N',
                      help='Number of the first diagram (default: 1)')
    grid.add_argument('--number-format', default='', metavar='TPL',
                      help='How a diagram number is written, e.g. "#{n}" or "Ex. {n}"')
    grid.add_argument('--number-restart-per-chapter', action='store_true',
                      help='Start numbering again from --number-start in every chapter')

    moves = parser.add_argument_group('diagrams from moves')
    moves.add_argument('--at-move', default='', metavar='N[,N...]',
                       help='Take a diagram after these move numbers; "last" for the final position')
    moves.add_argument('--every', type=int, default=0, metavar='N',
                       help='Take a diagram every N moves')
    moves.add_argument('--at-comment', nargs='?', const=DEFAULT_MARKER, default='',
                       metavar='MARKER',
                       help=f'Take a diagram where a comment carries MARKER (default: {DEFAULT_MARKER})')

    extra = parser.add_argument_group('other outputs')
    extra.add_argument('--export-images', default='', metavar='DIR',
                       help='Also write one image per diagram into DIR')
    extra.add_argument('--image-format', choices=IMAGE_FORMATS, default='png',
                       help='Format of the exported images (default: png)')
    extra.add_argument('--image-size', type=int, default=40, metavar='PX',
                       help='Board row height for exported images (default: 40)')
    extra.add_argument('--merge', action='store_true',
                       help='With several inputs, produce one document instead of one each')
    extra.add_argument('--dry-run', action='store_true',
                       help='Report what would be produced without writing anything')
    extra.add_argument('--list-layouts', action='store_true',
                       help='List the layout presets, then exit')

    saved = parser.add_argument_group('saved option sets')
    saved.add_argument('--profile', default='', metavar='NAME',
                       help='Start from the options saved under NAME; any flag given here wins')
    saved.add_argument('--save-profile', default='', metavar='NAME',
                       help='Save the options given on this command line under NAME')
    saved.add_argument('--list-profiles', action='store_true',
                       help='List the saved profiles and what they set, then exit')
    saved.add_argument('--delete-profile', default='', metavar='NAME',
                       help='Delete the profile called NAME, then exit')

    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Show library diagnostics that are hidden by default')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Suppress warnings')
    parser.add_argument('--gui', action='store_true', help='Launch GUI')
    return parser


def main(argv: list[str] | None = None):
    args = _make_parser().parse_args(argv)
    configure_logging(verbose=args.verbose, quiet=args.quiet)

    if args.list_fonts:
        _say('Board fonts:')
        for name in FONT_NAMES:
            marker = ' (default)' if name == _default_board_font_name() else ''
            _say(f'  {name}{marker}')
        _say('Figurine fonts:')
        for name in FIGURINE_NAMES:
            marker = ' (default)' if name == _default_figurine_font_name() else ''
            _say(f'  {name}{marker}')
        return

    if args.list_layouts:
        _say('Layout presets (--layout N):')
        for index, layout in enumerate(LAYOUTS):
            marker = ' (default)' if index == DEFAULT_LAYOUT else ''
            _say(f'  {index}  {layout.label_en:20s} {layout.cols} col x '
                 f'{layout.rows_plain} rows ({layout.rows_lined} with notation lines){marker}')
        _say()
        _say('Or give a free-form grid with --grid COLSxROWS, e.g. --grid 3x4.')
        return

    if args.list_languages:
        _say('Languages (--lang CODE):')
        for code in LANGS:
            marker = ' (default)' if code == DEFAULT_LANG else ''
            _say(f'  {code}  {lang_label(code)}{marker}')
        _say()
        _say('Sets the language of the labels DiagPDF writes into the document '
             '(solutions heading, contents, Lichess link).')
        return

    if args.list_profiles:
        _print_profiles()
        return

    # The grid is needed before the input is, because --save-profile can run
    # without one.
    grid_size: tuple[int, int] | None = None
    if args.grid:
        try:
            grid_size = parse_grid(args.grid)
        except ValueError as exc:
            print(f'Error: {exc}', file=sys.stderr)
            sys.exit(1)

    typed = _typed_dests(argv)
    try:
        if args.delete_profile:
            print(f'Deleted profile "{profiles_mod.delete(args.delete_profile)}".')
            return
        profile = profiles_mod.load(args.profile) if args.profile else {}
        if args.save_profile:
            name = profiles_mod.save(
                args.save_profile, _asked_for(args, typed, profile, grid_size))
            print(f'Saved profile "{name}".')
            if not args.input:
                return
    except ProfileError as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)

    if args.gui or not args.input:
        run_gui()
        return

    try:
        selection = parse_move_selection(args.at_move, every=args.every, marker=args.at_comment)
    except ValueError as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)

    inputs = [Path(name) for name in args.input]
    missing = [path for path in inputs if not path.exists()]
    if missing:
        for path in missing:
            print(f'Error: file not found: {path}', file=sys.stderr)
        sys.exit(1)

    if len(inputs) > 1 and args.output and not args.merge:
        print('Error: -o takes a single output; use --merge to combine several inputs',
              file=sys.stderr)
        sys.exit(1)

    jobs = [(inputs, Path(args.output) if args.output else inputs[0].with_suffix('.pdf'))]         if args.merge or len(inputs) == 1 else [([path], path.with_suffix('.pdf')) for path in inputs]
    if args.merge and not args.output:
        jobs = [(inputs, inputs[0].with_suffix('.pdf'))]

    report = _RunReport()
    for sources, target in jobs:
        _run_one(args, sources, target, selection, grid_size, report,
                 profile=profile, typed=typed)
    report.summarise(args.dry_run)
    return


def _print_profiles() -> None:
    """List every saved profile with the options it pins."""
    saved = profiles_mod.load_all()
    if not saved:
        _say('No profiles saved yet. Create one with:')
        _say('  diagpdf book.pgn -o book.pdf --answers --cover --save-profile studies')
        return
    _say(f'Profiles in {profiles_mod.PROFILES_PATH}:')
    for name in sorted(saved):
        lines = profiles_mod.describe(saved[name])
        _say(f'\n  {name}' + ('' if lines else '   (nothing set - same as the defaults)'))
        for line in lines:
            _say(f'      {line}')


class _RunReport:
    """What a run produced, summarised at the end."""

    def __init__(self) -> None:
        self.documents: list[tuple[Path, int]] = []
        self.images = 0
        self.skipped = 0
        self.ignored: set[str] = set()

    def summarise(self, dry_run: bool) -> None:
        verb = 'Would convert' if dry_run else 'Converted'
        for target, count in self.documents:
            print(f'{verb} {count} position(s) -> {target}')
        if self.images:
            print(f'{"Would write" if dry_run else "Wrote"} {self.images} image(s)')
        # Through _warn so --quiet silences these the way it silences the rest.
        if self.skipped:
            _warn(f'{self.skipped} position(s) skipped as invalid')
        for label in sorted(self.ignored):
            _warn(f'ignored by the target format: {label}')


def _read_positions(path: Path, args, selection) -> list:
    """Read one input file into positions, replaying moves when asked."""
    content = read_chess_file(path, args.encoding)
    suffix = path.suffix.lower()
    if suffix == '.pgn':
        # Without a move selection a game needs a [FEN] tag to draw anything;
        # with one, complete games are replayed instead.
        positions = parse_pgn(content, require_fen=not bool(selection))
        if selection:
            positions = expand_positions(positions, selection)
    elif suffix == '.fen':
        positions = parse_fen_file(content)
    elif suffix == '.epd':
        positions = parse_epd(content)
    else:
        raise ValueError(f'unknown extension "{suffix}" (expected .pgn, .fen, .epd)')
    return positions


def _typed_dests(argv: list[str] | None = None) -> set[str]:
    """Return the options the user actually typed.

    argparse fills in every default, so a parsed namespace cannot tell
    ``--layout 2`` from ``--layout`` never given when 2 is the default. That
    difference decides whether a flag beats the profile behind it, so the same
    command line is parsed a second time with every default suppressed: what
    survives is exactly what was typed.
    """
    parser = _make_parser()
    for action in parser._actions:      # argparse exposes no public way to do this
        action.default = argparse.SUPPRESS
    return set(vars(parser.parse_args(argv)))


def _asked_for(args, typed: set[str] | None, profile: dict, grid_size) -> dict:
    """Return the options as asked for: the profile, then what was typed over it.

    *typed* of None means "everything on the command line counts", which is the
    behaviour when no profile is in play.
    """
    values = dict(profile)
    for dest, field, read in OPTION_SOURCES:
        if typed is None or dest in typed:
            values[field] = read(args)
    if grid_size is not None and (typed is None or 'grid' in typed):
        values['grid'] = grid_size
    return values


def _build_opts(args, stem: str, number_offset: int, grid_size,
                *, profile: dict | None = None, typed: set[str] | None = None) -> RenderOptions:
    """Translate parsed arguments into the options the renderers take.

    Ranges are not clamped here: RenderOptions does it once, for every caller.
    """
    values = _asked_for(args, typed, profile or {}, grid_size)
    # What the run supplies rather than an option: the input's name stands in
    # for an unset header or title, and the range selection sets the offset.
    values['number_offset'] = number_offset
    values['header'] = values.get('header') or stem
    values['doc_title'] = values.get('doc_title') or stem
    values['footer'] = values.get('footer') or '{page}'
    values['title_template'] = values.get('title_template') or '{number} {comment}'
    return RenderOptions.from_dict(values)


def _run_one(args, sources: list[Path], target: Path, selection, grid_size, report,
             *, profile: dict | None = None, typed: set[str] | None = None) -> None:
    """Produce one output document from one or more input files."""
    positions: list = []
    for path in sources:
        try:
            positions.extend(_read_positions(path, args, selection))
        except MoveEngineUnavailable as exc:
            print(f'Error: {exc}', file=sys.stderr)
            sys.exit(1)
        except (OSError, LookupError, ValueError) as exc:
            print(f'Error: {exc}', file=sys.stderr)
            sys.exit(1)

    if not positions:
        names = ', '.join(path.name for path in sources)
        print(f'Warning: no positions found in {names}.', file=sys.stderr)

    before = len(positions)
    try:
        positions = apply_fen_policy(positions, args.on_invalid)
    except FenError as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
    report.skipped += before - len(positions)

    number_offset = 0
    if args.pos_from > 0 or args.pos_to > 0:
        start = max(0, args.pos_from - 1) if args.pos_from > 0 else 0
        end = args.pos_to if args.pos_to > 0 else None
        positions = positions[start:end]
        if not positions:
            print('Warning: no positions in selected range.', file=sys.stderr)
            sys.exit(1)
        if args.keep_numbers:
            number_offset = start

    opts = _build_opts(args, sources[0].stem, number_offset, grid_size,
                       profile=profile, typed=typed)
    report.ignored.update(unsupported_options(
        opts, target.suffix, any(position.get('chapter') for position in positions)))

    if args.dry_run:
        report.documents.append((target, len(positions)))
        if args.export_images:
            report.images += len(positions)
        return

    try:
        generate_output(positions, opts, target)
    except OSError as exc:
        print(f'Error writing output: {exc}', file=sys.stderr)
        sys.exit(1)
    except (UnknownFontError, FenError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)
    report.documents.append((target, len(positions)))

    if args.export_images:
        try:
            written = export_images(positions, opts, args.export_images,
                                    image_format=args.image_format, row_px=args.image_size)
        except (OSError, ValueError) as exc:
            print(f'Error writing images: {exc}', file=sys.stderr)
            sys.exit(1)
        report.images += len(written)
