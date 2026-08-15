# DiagPDF — Chess Diagram Generator

Convert PGN / FEN / EPD files to A4 pages of chess diagrams, as
**PDF, LaTeX, HTML, EPUB, DOCX, RTF or Markdown**.

See [CHANGELOG.md](CHANGELOG.md) for what changed in each release, and
[ROADMAP.md](ROADMAP.md) / [SPEC.md](SPEC.md) for what is planned.
[README_RU.md](README_RU.md) is a condensed Russian version of this file.

## Download

Grab the latest **DiagPDF.exe** from [Releases](../../releases) — no Python required.

---

## Features

- Reads `.pgn`, `.fen`, `.epd` files (UTF-8 or cp1252, auto-detected)
- **Diagrams from a game's moves**, so an ordinary PGN works — no `[FEN]` tag needed
- Writes `.pdf`, `.tex`, `.html`, `.epub`, `.docx`, `.rtf`, `.md`
- 7 page layouts: 1–4 columns, up to 20 diagrams per page
- 17 board fonts — run `--list-fonts` for the list installed on your copy
- **Drop a font into `Fonts/` and it is picked up**, with its piece map chosen
  from the glyphs it actually carries rather than from its file name
- To-move indicator: square □■, circle ○●, triangle △▲
- Auto-flip board when Black is to move
- Board coordinates (optional)
- Flexible diagram titles via template: `{number}`, `{event}`, `{white}`, `{black}`, `{date}`, `{comment}`
- Notation lines under diagrams: plain or numbered (1–5 lines)
- **Position range filter**: generate only positions N–M from the file (`--from` / `--to`)
- **Answers section** with figurine notation, 1 or 2 columns, optionally printed
  upside down so a solution cannot be read by accident, at the end of the book or
  after each chapter (`--answers-after-chapter`)
- **Watermark** stamped diagonally across every page (`--watermark`)
- **One image per diagram**: PNG, or SVG carrying the glyph outlines themselves,
  so it scales and needs no chess font at the other end (`--export-images`)
- **Clickable links**: diagram title → answer, answer number → diagram
- **Lichess analysis links** as a labelled line under each board, translated
  to the interface language (`--lichess-label` to override)
- Header / footer with `{page}`, `{total}`, `{chapter}` variables
- Chapter support via `[Chapter "..."]` PGN tag
- Cyrillic and Unicode titles (via system fonts)
- GUI (Windows, Tkinter) + full CLI
- Interface in English, Russian, Portuguese and Spanish
- FEN validation with a per-position report (`--on-invalid`)

---

## Installation

### Option A — Executable (Windows, no Python needed)

1. Download `DiagPDF.exe` from [Releases](../../releases)
2. Place it anywhere and run

### Option B — From source

```bash
pip install -r requirements.txt
python fen2rtf.py --gui
```

Two of those are optional and the file says which: `chess` for diagrams taken
from a game's moves, and `sv-ttk` for the window's Sun Valley theme. Skip either
and the rest still works — the move options report what to install, and the GUI
falls back to a theme it styles itself.

---

## GUI Usage

Launch the GUI:
```bash
python fen2rtf.py --gui
# or
DiagPDF.exe --gui
```

| Field | Description |
|-------|-------------|
| **Input file** | Click `…` to pick a `.pgn`, `.fen`, or `.epd` file |
| **Output PDF** | Auto-filled; click `…` to change |
| **Positions (from / to)** | Generate only a range of positions (auto-filled with 1 and total count after file selection) |
| **Renumber from 1** | When checked, positions in range are numbered 1, 2, 3… instead of their original file numbers |
| **Header / Footer** | Text with `{page}`, `{total}`, `{chapter}` |
| **Layout** | Page grid preset (columns × rows) |
| **Font** | Board font (ChessMerida recommended) |
| **Board font size** | 0 = auto-fit; or enter a specific pt value |
| **Symbol** | To-move indicator shape |
| **Lines** | Notation lines per diagram (0–5), plain or numbered |
| **Orientation** | Auto / White at bottom / Black at bottom |
| **Show coordinates** | Toggle board coordinate letters/numbers |
| **Title template** | Pattern for diagram titles — click `?` for variables |
| **Lichess links** | Embed analysis link in the to-move symbol |
| **Add answers section** | Append a solutions section at the end |
| **Answers heading** | Title of the answers section |
| **Answer columns** | 1 or 2 columns in the answers section |
| **New page** | Start the answers on a page of their own |
| **Upside down** | Print the answers rotated 180°, so a solution is not read by accident |
| **Watermark** | Text stamped diagonally across every page |
| **Figurine font** | Font used for piece symbols in the answers section |
| **EPUB stylesheet** | Extra CSS bundled into EPUB exports (remembered between runs) |
| **Dark theme** | Switches the window between the light and dark palettes |

A **live preview** on the right shows the first position with the current
settings. Generation runs on a background thread with a progress bar and a
working **Cancel** button — the window stays responsive, and a cancelled run
leaves no half-written file behind.

Recently opened files are one click away from the button beside the input field.
Install `tkinterdnd2` to drop a PGN onto the window instead.

Press **Generate PDF**, then **Open PDF** to view the result.

---

## CLI Reference

```bash
python fen2rtf.py input.pgn [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `-o OUTPUT` | `<input>.pdf` | Output PDF path |
| `-l, --layout N` | `2` | Layout preset 0–6 |
| `-f, --font NAME` | `ChessMerida` | Board font (see `--list-fonts`) |
| `--font-size N` | `0` | Board font size in pt (0 = auto) |
| `--no-coords` | — | Hide board coordinates |
| `--flip` | — | Flip board (Black at bottom) |
| `--no-auto-flip` | — | Disable auto-flip on Black to move |
| `--symbol NAME` | `square` | `square` / `circle` / `triangle` |
| `--lines N` | `0` | Notation lines per diagram |
| `--lines-numbered` | — | Use numbered lines (1. ___ ___) |
| `--header TEXT` | filename | Header text (PDF only) |
| `--footer TEXT` | `{page}` | Footer text (PDF only) |
| `--title-template TPL` | `{number} {comment}` | Title pattern |
| `--lichess-link` | — | Embed Lichess links |
| `--answers` | — | Add answers section |
| `--answers-title TEXT` | `Solutions` | Answers heading |
| `--answers-cols N` | `1` | Answer columns (1 or 2) |
| `--answers-same-page` | — | Continue the answers after the diagrams instead of a new page |
| `--answers-after-chapter` | — | Solutions at the end of each chapter instead of one section at the end |
| `--answers-upside-down` | — | Print the answers rotated 180° (PDF, HTML, EPUB) |
| `--watermark TEXT` | — | Stamp TEXT across every page (PDF, LaTeX, HTML, DOCX, RTF) |
| `--watermark-opacity PCT` | `10` | How strong the watermark is, 1–100 |
| `--figurine-font NAME` | `Zurich` | Figurine font for answers: `Zurich` / `Hastings` / `Linares` |
| `--from N` | — | First position to include (1-based) |
| `--to N` | — | Last position to include (1-based) |
| `--keep-numbers` | — | Keep original position numbers instead of renumbering from 1 (alias: `--no-renumber`) |
| `--border STYLE` | `simple` | Merida board border: `simple` / `double` / `none` |
| `--no-header` / `--no-footer` | — | Suppress header / footer |
| `--text-size N` | `0` | Title text size in pt (0 = proportional to layout) |
| `--lang CODE` | `en` | Language of generated labels: `en` / `ru` / `pt` / `es` |
| `--lichess-label TEXT` | translated | Override the Lichess link text |
| `--html-font-mode MODE` | `embed` | Standalone HTML font: `embed` / `link` / `none` |
| `--title TEXT` | input stem | Document title (HTML / EPUB metadata) |
| `--author TEXT` | — | Document author (EPUB metadata) |
| `--language CODE` | `--lang` | Document language (EPUB metadata) |
| `--epub-css FILE` | — | Extra CSS to bundle into EPUB exports |
| `--on-invalid MODE` | `skip` | Invalid FEN handling: `skip` (warn) or `fail` |
| `--encoding NAME` | auto | Force the input file encoding |
| `--allow-restricted-fonts` | — | Embed fonts whose licence marks them non-embeddable |
| `--list-fonts` | — | List available board and figurine fonts, then exit |
| `--list-languages` | — | List the languages the generated labels come in, then exit |
| `--version` | — | Print version and exit |
| `--gui` | — | Launch GUI |

### Page setup

| Option | Default | Description |
|--------|---------|-------------|
| `--page-size NAME` | `a4` | `a3` / `a4` / `a5` / `letter` / `legal` |
| `--landscape` | — | Rotate the sheet |
| `--margin-lr MM` | `10` | Left and right margin |
| `--margin-tb MM` | `15` | Top and bottom margin |

### Diagrams from moves

A game without a `[FEN]` tag has no position to draw — unless the moves are
replayed. These options say where to stop and take a picture:

| Option | Description |
|--------|-------------|
| `--at-move N[,N...]` | After these move numbers; `last` for the final position |
| `--every N` | Every N moves |
| `--at-comment [MARKER]` | Where a comment carries MARKER (default `#diagram`) |

```bash
python fen2rtf.py immortal.pgn -o book.pdf --at-move 10,20,last
python fen2rtf.py games.pgn    -o book.pdf --every 5 --grid 3x4
```

Move replay needs [python-chess](https://pypi.org/project/chess/)
(`pip install chess`); it ships inside the executable. Variations in parentheses
are not followed, and an illegal move stops that game with a warning rather than
producing a wrong diagram.

### Grid, numbering and batches

| Option | Description |
|--------|-------------|
| `--grid COLSxROWS` | Free-form grid, e.g. `3x4` (overrides `--layout`) |
| `--number-start N` | Number of the first diagram |
| `--number-format TPL` | How a number is written, e.g. `"#{n}"` or `"Ex. {n}"` |
| `--number-restart-per-chapter` | Start again from `--number-start` in every chapter |
| `--export-images DIR` | Also write one image per diagram |
| `--image-format FMT` | `png` (default) or `svg` |
| `--image-size PX` | Board row height for the exported images |
| `--merge` | With several inputs, produce one document instead of one each |
| `--dry-run` | Report what would be produced, write nothing |
| `--list-layouts` | List the layout presets |

Several inputs at once produce one document each; add `--merge` to combine them.

### Front matter and metadata

| Option | Description |
|--------|-------------|
| `--cover` | Add a title page (PDF) |
| `--cover-subtitle TEXT` | Subtitle shown on the cover |
| `--contents` | Add a table of contents listing the chapters (PDF) |
| `--contents-title TEXT` | Heading of the table of contents |
| `--subject TEXT` | Document subject |
| `--keywords TEXT` | Document keywords |

Chapters also become PDF outline entries, so a reader's side panel navigates the
book. `--title` and `--author` fill both the metadata and the cover.

```bash
python fen2rtf.py puzzles.pgn -o book.pdf     --page-size a5 --cover --contents --answers     --title "Tactics" --author "Your Name"
```

The output format follows the extension of `-o`:

```bash
python fen2rtf.py puzzles.pgn -o book.pdf     # PDF
python fen2rtf.py puzzles.pgn -o book.epub    # EPUB 3
python fen2rtf.py puzzles.pgn -o book.docx    # Word
```

---

## Which options apply to which format

| Option | PDF | LaTeX | HTML | EPUB | DOCX | RTF | MD |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Board symbol, orientation, coordinates | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Board font, border style | ✅ | — | ✅ | ✅ | ✅ | ✅ | — |
| Title template, answers section, Lichess links | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `--font-size` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Layout columns (`--layout`) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| `--lines` notation lines | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `--answers-cols` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Answers on a new page | ✅ | ✅ | print | — | ✅ | ✅ | — |
| Answers after each chapter | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `--answers-upside-down` | ✅ | — | ✅ | ✅ | — | — | — |
| `--watermark` | ✅ | ✅ | ✅ | — | ✅ | ✅ | — |
| `--figurine-font` in the answers | ✅ | — | ✅ | ✅ | ✅ | ✅ | Unicode |
| Chapters (`[Chapter]` tag) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| A chapter starts a new page | ✅ | ✅ | print | — | ✅ | ✅ | — |
| Page size, orientation, margins | ✅ | ✅ | print only | — | ✅ | ✅ | — |
| Document metadata | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | front matter |
| Cover, contents, outline | ✅ | ✅ | — | nav doc | — | — | — |
| `--header` / `--footer` | ✅ | ✅ | print only | — | ✅ | ✅ | — |
| `{page}` / `{total}` | ✅ | ✅ | — | — | ✅ | ✅ | — |

The gaps are properties of the formats, not omissions:

- **EPUB is reflowable.** The reading system paginates it, so the document has
  no pages of its own to carry a running header.
- **A browser cannot number printed pages from markup.** Page counters live in
  CSS paged-media margin boxes, which browsers do not implement. HTML headers
  and footers are emitted and repeat on every printed sheet, but `{page}` and
  `{total}` are dropped.
- **A watermark needs a page to stamp.** The PDF draws it over every page,
  LaTeX asks `draftwatermark` for it, and HTML positions it fixed — though
  browsers differ on whether a fixed box repeats on every *printed* sheet.
  Word and RTF get a WordArt shape anchored in the header — the header being the
  only part of those formats that repeats on every page. EPUB is reflowable and
  has no page to stamp.
- **Upside-down answers need a page to turn.** The whole answers block is
  rotated 180° as one, so the reader turns the sheet and reads it in the usual
  order. Word can only rotate text inside a drawing shape and RTF has no turned
  text at all; in LaTeX a turned box cannot break across pages, so a long
  answers section would run off the first one instead of continuing.
- **Markdown is a stream of text.** It has no pages, no sheet and no fonts, so
  everything about the printed page falls away. Its board is written with the
  Unicode chess pieces, which is also where the answers get their figurines.
- **LaTeX draws the board from the FEN**, through the `chessboard` package, so
  the chess fonts this program ships — and the border styles that come with
  them — play no part. The movetext is set in the document font rather than a
  figurine one.

Anything a format cannot honour is reported on stderr rather than silently
ignored:

```
Warning: EPUB does not support page header/footer (--header/--footer) - the option will be ignored
```

---

## PGN Format Tips

### Diagram titles

DiagPDF reads position data from PGN tags and the first comment.
Use the title template to compose any title you need:

```
--title-template "{number}. {event} ({date})"
--title-template "{number} {comment}"
```

### Chapters

Add a `[Chapter "Chapter name"]` tag before a group of games.
Use `{chapter}` in the header/footer to display the current chapter:

```pgn
[Chapter "Tactics — Pin"]
[Event "1.1 Example"]
[FEN "..."]

1. Ng7! 1-0
```

Only the first game of a chapter needs the tag: a game without one continues the
chapter before it. That is what decides where a page breaks, where the numbering
restarts and where a per-chapter answers section ends.

Every paginated format starts a chapter on a new page — never before the first
one, which would only add a blank sheet. In LaTeX that means an explicit
`\clearpage`: a `\section` flows by design, so left alone a chapter would begin
halfway down the page the last one ended on.

### Answers section

Moves in the PGN game body become the answers.
Comments `{...}` and NAG codes `$1` are automatically stripped.
Variations in parentheses `(2...Ke8 3.Rb8#)` are preserved.

By default every solution goes into one section at the end of the document. In a
book of themed chapters the other arrangement is usually wanted — solutions after
the chapter they belong to, and exercises numbered from 1 within each chapter:

```bash
python fen2rtf.py book.pgn -o book.pdf     --answers --answers-after-chapter --number-restart-per-chapter
```

The links follow: a diagram in chapter 2 points at chapter 2's solution, not at a
section at the back. The numbers on the page repeat between chapters, so the link
anchors count positions through the document rather than using those numbers.

---

## File Structure

```
diagpdf/            The package
  gui/              app, settings, filetypes, preview, worker, theme
  options.py        Every render setting, typed, defaulted and validated
  profiles.py       Named option sets, shared by the CLI and the window
  fen.py            FEN parsing, validation, diagram rows
  parsers.py        PGN / FEN-file / EPD readers
  fonts.py          Discovery (cached), resolution, licence policy
  page.py           Paper size, orientation, margins
  moves.py          Replaying a game's moves into positions
  images.py         One image file per diagram
  svg.py            The vector one, drawn from the font's glyph outlines
  geometry.py       Page and grid geometry
  capabilities.py   What each format can honour
  i18n.py           Strings in four languages
  render/           pdf.py html.py epub.py docx.py rtf.py markdown.py latex.py
  cli.py, gui.py    Entry points
fen2rtf.py          Compatibility shim — keeps the old imports working
fen2pdf.spec        PyInstaller build config
pyproject.toml      Packaging, ruff and pytest configuration
.github/workflows/  CI: the suite on two systems, LaTeX, and the .exe
tests/              pytest suite (1427 tests)
test_smoke.py       One file per output format
test_batch.py       Batch test: all setting combinations
output_snapshot.py  Proves a refactor did not change the generated documents
build_alphadg.py    Rebuilds the AlphaDG board font from Fonts-recovered/
requirements.txt    Runtime dependencies
requirements-dev.txt Test dependencies
icon.ico            Application icon
Fonts/              Chess diagram fonts (TTF)
Fonts-recovered/    Fonts pulled out of PDFs: reference only, not loaded
Example/            Sample PGNs (including a chaptered one) and demo PDFs,
                    with the command behind each one in its README
ROADMAP.md          Phased plan
SPEC.md             Defect analysis and acceptance criteria
CHANGELOG.md        Release notes
```

---

## Markdown and LaTeX

```bash
diagpdf puzzles.pgn -o book.md    --answers
diagpdf puzzles.pgn -o book.tex   --answers --cover --contents
```

**Markdown** is one self-contained file: the board is written with the Unicode
chess pieces inside a fenced block, so it renders on GitHub, in an editor
preview and in any static-site generator with nothing to install and no images
to ship beside it.

````markdown
### [1](#answer-1) Mate in two

```text
8 ♜ · · · · ♝ ♜ ♚
7 · · · · · ♟ · ♟
...
  a b c d e f g h
□ White to move
```
````

Document metadata becomes YAML front matter, chapters become headings, and the
answers link back to their diagrams.

**LaTeX** emits a source file that draws each board with the
[`chessboard`](https://ctan.org/pkg/chessboard) package, straight from the FEN:

```latex
\chessboard[setfen={r4brk/5p1p/2bp1P2/p3p2N/1pq1P3/5N1Q/PPP4P/1K1RR3 w - - 0 1}]
```

To compile it you need that package — TeX Live's `collection-games`, or the
MiKTeX package of the same name — and two passes, so the table of contents and
`{total}` settle:

```bash
pdflatex book.tex && pdflatex book.tex
```

Everything stylistic about the board is set on a single `\setchessboard` line in
the preamble, so a document can be restyled — or adjusted for a different
version of the package — by editing one line. Per diagram, only `setfen` is
used, plus `inverse=true` when the position is seen from Black's side.

The font encoding follows the text: `T1` is the default, which sets accented
Latin as single glyphs, unless the document carries Cyrillic — then `T2A` goes
last and becomes the default instead, because T1 has no Cyrillic at all and
pdflatex stops on the first such letter. A document mixing the two compiles
either way.

The output is compiled, not only inspected: `tests/test_text_formats.py` runs
`pdflatex` over a plain document, a Cyrillic one, an accented-Latin one and one
with every option turned on. Those tests skip when no TeX is installed.

---

## Saved profiles

A book is a dozen flags, and retyping them per chapter is how two chapters end
up not matching. Save them once under a name:

```bash
diagpdf chapter1.pgn -o c1.pdf --answers --answers-cols 2 --cover \
        --page-size a5 --save-profile studies

diagpdf chapter2.pgn -o c2.pdf --profile studies
diagpdf chapter3.pgn -o c3.pdf --profile studies --lines 3
```

A flag given on the command line always beats the profile behind it, so a
profile is a starting point rather than a straitjacket:

```bash
diagpdf ch4.pgn -o c4.pdf --profile studies --page-size letter   # Letter, still with answers
```

| Option | Does |
|--------|------|
| `--profile NAME` | Start from the options saved as NAME |
| `--save-profile NAME` | Save the options given on this command line as NAME |
| `--list-profiles` | List every profile and what it sets |
| `--delete-profile NAME` | Remove one |

`--save-profile` works with or without an input file, and combines with
`--profile` to derive one profile from another:

```bash
diagpdf --profile studies --lines 3 --save-profile studies-lined
```

Profiles live in `~/.diagpdf/profiles.json` and hold only the options that
differ from the defaults, so the file stays readable and a default improved in
a later release still reaches profiles that never pinned it. The window reads
and writes the same file — a profile saved from the command line appears in its
dropdown, and the reverse. Loading a profile in the window does not change the
interface language or theme, which belong to the window rather than to a
document style.

---

## Using it as a library

```python
from pathlib import Path
from diagpdf import RenderOptions, generate_output, parse_pgn, read_chess_file

positions = parse_pgn(read_chess_file(Path('puzzles.pgn')))
opts = RenderOptions(layout_idx=2, answers_section=True)
generate_output(positions, opts, 'book.pdf')
```

`RenderOptions` declares every setting, its type and its default in one place,
and checks them on construction: an unusable value is reported and replaced
rather than quietly changing what the document looks like.

```python
RenderOptions(symbol='hexagon')      # Warning: symbol: 'hexagon' is not one of
                                     # square, circle, triangle - using 'square'
RenderOptions(answers_cols=9)        # clamped to 2
RenderOptions(layout_idx=99)         # clamped to the last preset
```

A plain dict of the same keys is still accepted everywhere an options object is,
so existing scripts keep working:

```python
generate_output(positions, {'layout_idx': 2, 'answers_section': True}, 'book.pdf')
```

Installed as a package it also provides the `diagpdf` command:

```bash
pip install -e .
diagpdf puzzles.pgn -o book.pdf
```

`fen2rtf.py` remains as a thin shim over the package, so existing scripts and
the frozen executable keep working unchanged.

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

| Module | Covers |
|--------|--------|
| `tests/test_fen.py` | FEN parsing and validation, diagram rendering, square colours, flipping, borders |
| `tests/test_parsers.py` | PGN / FEN-file / EPD parsing, malformed input, encoding detection |
| `tests/test_moves.py` | Movetext cleaning, title templates, figurine segmentation |
| `tests/test_geometry.py` | Every layout × notation-line combination fits the page |
| `tests/test_fonts.py` | Discovery, resolution, licence policy, VDMX patching |
| `tests/test_outputs.py` | Structural invariants of every output format |
| `tests/test_cli.py` | Exit codes, messages, option plumbing |
| `tests/test_gui.py` | i18n coverage, settings validation, worker thread, preview |
| `tests/test_parity.py` | Every capability the matrix declares |
| `tests/test_package.py` | Module layout, compatibility shim, font cache |
| `tests/test_page.py` | Paper sizes, margins, metadata, outline, cover, contents |
| `tests/test_features.py` | Move replay, custom grids, numbering, batch, images |
| `tests/test_options.py` | Option defaults, normalisation, validation, the dict boundary |
| `tests/test_profiles.py` | Profile storage, precedence over typed flags, both front ends |
| `tests/test_text_formats.py` | Markdown and LaTeX: board round-trip, escaping, links, structure |
| `tests/test_regression.py` | One guard per defect fixed in 0.2.4 |

### Checking that a refactor changed nothing

The suite checks invariants, not exact bytes — deliberately, so a harmless
change of ordering does not fail a hundred tests. When the point of a change is
that the output must *not* move, `output_snapshot.py` checks that directly:

```bash
python output_snapshot.py save before     # on the unchanged code
python output_snapshot.py save after      # after the change
python output_snapshot.py compare         # exits non-zero if anything differs
```

It renders 182 documents — every option group in all seven formats — through
the real command line and compares them. Each format stamps a timestamp or a
fresh identifier into every build, so those fields (and only those) are blanked
before hashing; the module docstring lists them and explains why.

Save the same code under two labels first. If those two do not come out
identical, the normalisation is incomplete and no later comparison means
anything.

Tests assert on document *structure* — page and link counts, resolvable anchors,
EPUB 3 conformance, balanced RTF groups — rather than on golden bytes, which
would break on every harmless change in object ordering or font subsetting.

EPUB output is additionally checked with `epubcheck` when it is installed; set
`EPUBCHECK_JAR` to point at the jar. Without it that one test is skipped and the
same rules are still verified in `tests/inspectors.py`.

### Continuous integration

`.github/workflows/ci.yml` runs on every push to `main`, on pull requests, and
on demand:

| Job | What it does |
|-----|--------------|
| `pytest` | The suite on Ubuntu and Windows, on Python 3.10 and 3.12, plus `ruff`. It fetches epubcheck and points `EPUBCHECK_JAR` at it, then checks that the conformance test **ran** — a validator that is missing makes its test skip, and a skipped test is green. Linux runs under Xvfb, because the GUI tests open a real window. |
| `latex` | Installs TeX Live and compiles the LaTeX corpus. Separate from the matrix: a slow, heavy install that nothing else in the suite needs. |
| `windows-exe` | Builds `DiagPDF.exe` with PyInstaller and uploads it as an artifact of the run. |

The same checks locally:

```bash
ruff check .
pytest
```

---

## Building the Executable

```bash
pip install pyinstaller pillow
pyinstaller fen2pdf.spec
# Output: dist/DiagPDF.exe
```

---

## Fonts

Run `python fen2rtf.py --list-fonts` to see exactly what your copy has.

Two families ship with different character maps:

| Family | Fonts | Notes |
|--------|-------|-------|
| Merida-compatible | `ChessMerida` and the `Chess *` set | Default; supports `--border simple/double/none` |
| Legacy DG | `AlphaDG`, `LeipzigDG`, `CondalDG`, `KingdomDG` | Draws the to-move marker inside the board frame |

Figurine fonts (answers section): `ZurichFigurine.TTF`, `HastingsFigurine.TTF`,
`LinaresFigurine.TTF`. Only the piece initials `K Q R B N` are set in the
figurine font; the rest of the movetext stays in the text font.

`ZurichFigurine.TTF` and `LinaresFigurine.TTF` were recovered from the embedded
copies in `fonts_6a7de6c2db0e9/chesswin.pdf`, so they carry only the glyphs that
PDF used. That covers every character DiagPDF asks of a figurine font, but they
are not the complete typefaces — Zurich in particular has no lowercase piece
letters and no full alphabet. The recovery was checked against the extracted
`HastingsFigurine`, whose outlines match the bundled original exactly.

Fonts with a broken VDMX table are patched automatically on first run; the
patched copy is saved as `*_patch.ttf` and reused.

> **`AlphaDG` is not distributed here — neither the font nor what it is made
> from.** Chess Alpha DG is a commercial typeface. A clone has the other 17
> fonts and reports `AlphaDG` as unknown, with the available names listed.
>
> What is versioned is the method. The 2011 example PDFs carry the font
> embedded, and 52 of the 56 characters the renderers need survive there;
> [`build_alphadg.py`](build_alphadg.py) merges those subsets, restores the
> character map the extraction dropped, and derives the four that are missing:
>
> | Character | What it is | Where it comes from |
> |---|---|---|
> | `'` | bottom border fill | `z` mirrored — the rule holds exactly for both corner pairs Alpha still has |
> | `$` | left border edge | `%` mirrored left to right, as LeipzigDG, CondalDG and KingdomDG all draw it |
> | `f` `i` | triangle to-move markers | drawn: the shape is the one all three of those fonts share, fitted to Alpha's own symbol box and stroke |
>
> The first board of `ex1` renders pixel-for-pixel identical to the 2011
> original, which is what says the recovered mapping is right. The two triangles
> are the only part of the font that is a drawing rather than a recovery.
>
> If you own the font, or the PDFs it was recovered from, put them back under
> `Fonts-recovered/` as its README describes and run `python build_alphadg.py`
> (`--check` prints each derivation and its test). Without them the script says
> what is missing and stops.

Two of the bundled fonts (`Chess Adventurer`, `Chess Cases`) are licensed as
non-embeddable. DiagPDF leaves them out of EPUB and DOCX packages and says so;
pass `--allow-restricted-fonts` to override.
