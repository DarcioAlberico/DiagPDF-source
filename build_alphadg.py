"""Rebuild ``Fonts/AlphaDG.ttf`` from the copies embedded in the 2011 examples.

Chess Alpha DG is the one board font the project never had a file for. Three of
the example PDFs shipped in 2011 carry it embedded, and ``Fonts-recovered/``
keeps those subsets. Between them they hold 52 of the 56 characters the layout
needs; this script merges them, gives the result a character map again, and
draws the four that are missing.

Run it from the project root::

    python build_alphadg.py            # writes Fonts/AlphaDG.ttf
    python build_alphadg.py --check    # says what it would do, writes nothing

.. note::

   The real font turned up after this was written — the v0.2.3 release in the
   author's public repository has it — and it judged the result: **54 of the 56
   characters came back identical**, both mirrored border pieces included. Only
   the two drawn triangles differ. So this is no longer the way to obtain the
   font; it is the record of how a CID-keyed subset is read back out of a PDF,
   and a check with something to be checked against.

Nothing here is guessed. Each step below says what it is derived from, and
``--check`` prints the evidence so the claims can be re-tested rather than
believed:

* **The glyph order.** The subsets have no character map: they are CID-keyed,
  and the mapping lives in the PDF instead. It is read back from each file's
  ToUnicode CMap through its CIDToGIDMap — the code in the page text is a CID,
  not a glyph id, and treating it as one silently produces a font whose king is
  a border strip.
* **The bottom border fill** ``'``. In this font the bottom row of the frame is
  the top row mirrored about the middle of the em: it holds exactly for both
  corner pairs that Alpha still has (``!``→``&`` and ``#``→``(``), and for the
  fill pair in LeipzigDG and KingdomDG, which have both. So ``'`` is ``z``
  mirrored, with the contour reversed to keep the winding.
* **The left border edge** ``$``. The same rule on the other axis, and the same
  reason it is missing: every one of those PDFs was drawn with coordinates, and
  with coordinates the left edge comes inside the rank characters. It only
  shows up under ``--no-coords``. LeipzigDG, CondalDG and KingdomDG all draw it
  as the right edge mirrored left to right, to the unit.
* **The triangle to-move indicators** ``f`` and ``i``. These have no source
  anywhere; they are drawn. LeipzigDG, CondalDG and KingdomDG carry the same
  triangle to the unit, so the shape is a family constant rather than a design
  choice per font. It is fitted to Alpha's own proportions: Alpha draws its
  symbols in a 1200×1200 box where the others use 1400×1400, sharing the corner
  at (2000, 200), and the family triangle already spans Alpha's x range. So the
  height is scaled by 6/7 and the hollow one is inset by 100 units — the stroke
  Alpha uses for its own hollow square and circle.
"""
from __future__ import annotations

import argparse
import re
import sys
import zlib
from pathlib import Path

from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

ROOT = Path(__file__).resolve().parent
RECOVERED = ROOT / 'Fonts-recovered'
OUT = ROOT / 'Fonts' / 'AlphaDG.ttf'

# The subset with the square indicators is the base; the one from ex1 is the
# only file that carries the circle. ex4 is byte-identical in every glyph it
# shares with ex2, and adds nothing.
BASE = ('ChessAlphaDG--from-ex2_2col_alpha_lines.ttf', 'ex2_2col_alpha_lines.pdf')
CIRCLE = ('ChessAlphaDG--from-ex1_2col_alpha_plain.ttf', 'ex1_2col_alpha_plain.pdf')

UPEM = 2048
ADVANCE = 2048          # every glyph in this font is one em wide
STROKE = 100            # Alpha's hollow square: outer 800..2000, inner 900..1900


# ── reading the mapping back out of the PDFs ─────────────────────────────────

def _objects(data: bytes) -> dict[int, bytes]:
    return {int(m.group(1)): m.group(2)
            for m in re.finditer(rb'(\d+)\s+0\s+obj\b(.*?)\bendobj', data, re.S)}


def _stream(body: bytes) -> bytes | None:
    m = re.search(rb'stream\r?\n(.*?)\r?\nendstream', body, re.S)
    if not m:
        return None
    raw = m.group(1)
    if b'/FlateDecode' not in body:
        return raw
    try:
        return zlib.decompress(raw)
    except zlib.error:
        return None


def _tounicode(cmap_text: bytes) -> dict[int, int]:
    pairs: dict[int, int] = {}
    for block in re.findall(rb'beginbfchar(.*?)endbfchar', cmap_text, re.S):
        for code, uni in re.findall(rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', block):
            pairs[int(code, 16)] = int(uni[:4], 16)
    for block in re.findall(rb'beginbfrange(.*?)endbfrange', cmap_text, re.S):
        for lo, hi, uni in re.findall(
                rb'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>', block):
            start, end, first = int(lo, 16), int(hi, 16), int(uni[:4], 16)
            for i in range(end - start + 1):
                pairs[start + i] = first + i
    return pairs


def glyph_chars(pdf: Path, base_name: str = 'ChessAlphaDG') -> dict[int, str]:
    """{glyph id: character} for *base_name* as embedded in *pdf*."""
    objs = _objects(pdf.read_bytes())
    full = tounicode = cid2gid = None
    for body in objs.values():
        if b'/Type0' in body and base_name.encode() in body:
            name = re.search(rb'/BaseFont\s*/([#\w+.-]+)', body)
            ref = re.search(rb'/ToUnicode\s+(\d+)\s+0\s+R', body)
            if name and ref:
                full, tounicode = name.group(1).decode('latin-1'), int(ref.group(1))
    if full is None or tounicode is None:
        raise SystemExit(f'{pdf.name}: no {base_name} font dictionary')
    for body in objs.values():
        if b'/CIDFontType2' in body and full.encode() in body:
            ref = re.search(rb'/CIDToGIDMap\s+(\d+)\s+0\s+R', body)
            if ref:
                cid2gid = _stream(objs[int(ref.group(1))])
    text = _stream(objs[tounicode])
    if text is None:
        raise SystemExit(f'{pdf.name}: unreadable ToUnicode stream')

    out: dict[int, str] = {}
    for cid, uni in _tounicode(text).items():
        gid = cid
        if cid2gid is not None:
            gid = int.from_bytes(cid2gid[cid * 2:cid * 2 + 2], 'big')
        ch = chr(uni - 0xF000) if 0xF000 <= uni <= 0xF0FF else chr(uni)
        if ch != '\x00':
            out[gid] = ch
    return out


# ── geometry ─────────────────────────────────────────────────────────────────

def contours(font: TTFont, glyph_name: str) -> list[list[tuple[int, int]]]:
    """Straight-line contours of a glyph. Only used on glyphs that have no curves."""
    pen = RecordingPen()
    font.getGlyphSet()[glyph_name].draw(pen)
    out, current = [], []
    for op, args in pen.value:
        if op == 'moveTo':
            current = [args[0]]
        elif op == 'lineTo':
            current.append(args[0])
        elif op in ('closePath', 'endPath'):
            if current:
                out.append(current)
            current = []
        else:
            raise ValueError(f'{glyph_name}: unexpected {op} — this helper is for polygons')
    return out


def mirrored(contour, upem: int = UPEM):
    """Flip about the middle of the em, reversed so the winding is unchanged."""
    return [(x, upem - y) for x, y in reversed(contour)]


def mirrored_x(contour, upem: int = UPEM):
    """The same, left to right: the left edge of the frame is the right one."""
    return [(upem - x, y) for x, y in reversed(contour)]


def inset_triangle(tri, distance: float = STROKE):
    """The triangle *distance* units inside *tri*, edge for edge.

    Scaling about the incentre is exact for a triangle: every edge moves in by
    the same amount, which is what a constant stroke means.
    """
    (ax, ay), (bx, by), (cx, cy) = tri
    la = ((bx - cx) ** 2 + (by - cy) ** 2) ** 0.5
    lb = ((ax - cx) ** 2 + (ay - cy) ** 2) ** 0.5
    lc = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
    perimeter = la + lb + lc
    ix = (la * ax + lb * bx + lc * cx) / perimeter
    iy = (la * ay + lb * by + lc * cy) / perimeter
    area = abs(ax * (by - cy) + bx * (cy - ay) + cx * (ay - by)) / 2
    inradius = 2 * area / perimeter
    k = (inradius - distance) / inradius
    return [(round(ix + (x - ix) * k), round(iy + (y - iy) * k)) for x, y in tri]


def triangle_for_alpha(square_box, family_triangle):
    """Fit the family triangle to Alpha's smaller symbol box.

    Both boxes are anchored at the same bottom-right corner, so the fit is a
    scale about that corner: 1200/1400 vertically, and horizontally nothing —
    the family triangle already spans exactly Alpha's width.
    """
    x0, y0, x1, y1 = square_box
    factor = (y1 - y0) / 1400
    return [(round(x), round(y0 + (y - 200) * factor)) for x, y in family_triangle]


# ── building ─────────────────────────────────────────────────────────────────

def polygon_glyph(contour_list) -> object:
    pen = TTGlyphPen(None)
    for contour in contour_list:
        pen.moveTo(contour[0])
        for point in contour[1:]:
            pen.lineTo(point)
        pen.closePath()
    return pen.glyph()


def missing_material() -> list[str]:
    """What this script needs and does not have.

    The inputs are not in the repository: the 2011 PDFs carry a commercial font
    embedded, and so do the subsets extracted from them. Whoever has the files
    puts them back under Fonts-recovered/ and runs this; a plain clone gets a
    clear message instead of a traceback.
    """
    wanted = [RECOVERED / BASE[0], RECOVERED / 'source-pdfs' / BASE[1],
              RECOVERED / CIRCLE[0], RECOVERED / 'source-pdfs' / CIRCLE[1]]
    return [str(p.relative_to(ROOT)) for p in wanted if not p.is_file()]


def build(check_only: bool) -> int:
    absent = missing_material()
    if absent:
        print('The material this font is rebuilt from is not in the repository.')
        print('Missing:')
        for item in absent:
            print(f'  {item}')
        print('\nSee Fonts-recovered/README.md. Without it, DiagPDF runs with the')
        print('17 board fonts that are bundled and reports AlphaDG as unknown.')
        return 1

    base_font = TTFont(RECOVERED / BASE[0])
    base_map = glyph_chars(RECOVERED / 'source-pdfs' / BASE[1])
    circle_font = TTFont(RECOVERED / CIRCLE[0])
    circle_map = glyph_chars(RECOVERED / 'source-pdfs' / CIRCLE[1])

    base_names = {ch: base_font.getGlyphOrder()[gid] for gid, ch in base_map.items()}
    circle_names = {ch: circle_font.getGlyphOrder()[gid] for gid, ch in circle_map.items()}

    print(f'base   {BASE[0]}: {len(base_names)} characters')
    print(f'circle {CIRCLE[0]}: adds {sorted(set(circle_names) - set(base_names))}')

    # The two subsets must agree wherever they overlap, or merging them would
    # quietly mix two different drawings of the same font.
    base_glyphs, circle_glyphs = base_font.getGlyphSet(), circle_font.getGlyphSet()
    disagree = []
    for ch in sorted(set(base_names) & set(circle_names)):
        a, b = RecordingPen(), RecordingPen()
        base_glyphs[base_names[ch]].draw(a)
        circle_glyphs[circle_names[ch]].draw(b)
        if a.value != b.value:
            disagree.append(ch)
    print(f'shared characters: {len(set(base_names) & set(circle_names))}, '
          f'differing drawings: {disagree if disagree else "none"}')
    if disagree:
        raise SystemExit('the subsets disagree — refusing to merge them')

    # 1. the bottom fill, from the top fill
    top_fill = contours(base_font, base_names['z'])
    bottom_fill = [mirrored(c) for c in top_fill]
    for top, bottom, what in [('!', '&', 'NW/SW'), ('#', '(', 'NE/SE')]:
        made = [mirrored(c) for c in contours(base_font, base_names[top])]
        real = contours(base_font, base_names[bottom])
        same = sorted(map(sorted, made)) == sorted(map(sorted, real))
        print(f"rule check: mirror({top!r}) == {bottom!r}: {'yes' if same else 'NO'}   ({what})")
        if not same:
            raise SystemExit('the mirror rule does not hold — not deriving the bottom fill from it')
    print(f"derived {chr(39)!r} (bottom border fill) = mirrored 'z': {bottom_fill}")

    # 1b. the left edge, from the right edge. Same idea, other axis: LeipzigDG,
    # CondalDG and KingdomDG all draw '$' as '%' mirrored left to right, to
    # within the unit their designer rounded to. Alpha never carried '$'
    # because the examples were all drawn with coordinates, which put the left
    # edge inside the rank characters instead.
    left_edge = [mirrored_x(c) for c in contours(base_font, base_names['%'])]
    for check in ('LeipzigDG', 'CondalDG', 'KingdomDG'):
        other = TTFont(ROOT / 'Fonts' / f'{check}.ttf')
        names = {}
        for table in other['cmap'].tables:
            if (table.platformID, table.platEncID) == (3, 0):
                names = {chr(cp - 0xF000): n for cp, n in table.cmap.items()}
        made = [p for c in (mirrored_x(c) for c in contours(other, names['%'])) for p in c]
        real = [p for c in contours(other, names['$']) for p in c]
        worst = max(abs(a[0] - b[0]) + abs(a[1] - b[1])
                    for a, b in zip(sorted(made), sorted(real), strict=True))
        print(f"rule check: mirror_x('%') == '$' in {check}: off by at most {worst} unit(s)")
        if worst > 2:
            raise SystemExit('the left edge is not the mirrored right edge — not deriving it')
    print(f"derived '$' (left border edge) = mirrored '%': {left_edge}")

    # 2. the triangles, from the family shape fitted to Alpha's own box
    square = contours(base_font, base_names['M'])          # bar + solid square
    bar = [c for c in square if max(x for x, _ in c) <= 200]
    box_contour = [c for c in square if c not in bar][0]
    xs = [x for x, _ in box_contour]
    ys = [y for _, y in box_contour]
    square_box = (min(xs), min(ys), max(xs), max(ys))
    family_triangle = [(1400, 1800), (800, 200), (2000, 200)]   # Leipzig = Condal = Kingdom
    outer = triangle_for_alpha(square_box, family_triangle)
    inner = inset_triangle(outer)
    print(f'alpha symbol box {square_box}, edge bar {bar[0]}')
    print(f'triangle outer {outer}')
    print(f'triangle inner {inner}  (stroke {STROKE})')

    new_glyphs = {
        "'": bottom_fill,
        '$': left_edge,
        'i': [*bar, outer],                       # solid  = black to move
        'f': [*bar, outer, list(reversed(inner))],  # hollow = white to move
    }

    if check_only:
        print('\n--check: nothing written')
        return 0

    # 3. assemble: base font, plus the circle pair, plus the three made here.
    # recalcTimestamp=False or fontTools stamps the save time into head.modified
    # and two builds of the same input stop matching byte for byte.
    font = TTFont(RECOVERED / BASE[0], recalcTimestamp=False)
    glyf, hmtx = font['glyf'], font['hmtx']
    order = list(font.getGlyphOrder())
    char_to_glyph = dict(base_names)

    for ch in sorted(set(circle_names) - set(base_names)):
        name = f'uni{0xF000 + ord(ch):04X}'
        glyf[name] = circle_font['glyf'][circle_names[ch]]
        hmtx[name] = (ADVANCE, circle_font['hmtx'][circle_names[ch]][1])
        order.append(name)
        char_to_glyph[ch] = name

    for ch, contour_list in new_glyphs.items():
        name = f'uni{0xF000 + ord(ch):04X}'
        glyf[name] = polygon_glyph(contour_list)
        hmtx[name] = (ADVANCE, min(x for c in contour_list for x, _ in c))
        order.append(name)
        char_to_glyph[ch] = name

    font.setGlyphOrder(order)
    font['maxp'].numGlyphs = len(order)

    # 4. a character map, which the extraction threw away
    # The same two subtables the other DG fonts carry: a Mac byte table and a
    # Windows symbolic one in the private area, which is where fpdf2 and Pillow
    # look for a font like this.
    cmap = newTable('cmap')
    cmap.tableVersion = 0
    mac = CmapSubtable.newSubtable(0)
    mac.platformID, mac.platEncID, mac.language = 1, 0, 0
    mac.cmap = {ord(ch): name for ch, name in char_to_glyph.items()}
    win = CmapSubtable.newSubtable(4)
    win.platformID, win.platEncID, win.language = 3, 0, 0
    win.cmap = {0xF000 + ord(ch): name for ch, name in char_to_glyph.items()}
    cmap.tables = [mac, win]
    font['cmap'] = cmap

    # 5. names, and the timestamps the extraction corrupted
    name = font['name']
    for nid, value in [(1, 'Chess Alpha DG'), (2, 'Regular'),
                       (3, 'Chess Alpha DG; rebuilt from the 2011 example PDFs'),
                       (4, 'Chess Alpha DG'), (6, 'ChessAlphaDG')]:
        name.setName(value, nid, 3, 1, 0x409)
        name.setName(value, nid, 1, 0, 0)
    head = font['head']
    head.created = head.modified = 3849984000       # 2026-01-01, a plain fixed date
    font['OS/2'].fsType = 0

    OUT.parent.mkdir(exist_ok=True)
    font.save(OUT)
    print(f'\nwrote {OUT.relative_to(ROOT)}: {len(order)} glyphs, '
          f'{len(char_to_glyph)} characters mapped')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--check', action='store_true',
                        help='print the derivation and its checks, write nothing')
    args = parser.parse_args()
    return build(args.check)


if __name__ == '__main__':
    sys.exit(main())
