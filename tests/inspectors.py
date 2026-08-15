"""Read generated documents back as structural facts.

Tests assert on these facts rather than on golden bytes: a byte-for-byte
baseline breaks on every harmless change (timestamps, object ordering, font
subsetting), while structure catches the failures that actually matter —
missing diagrams, dangling links, malformed packages.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path

W_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
OPF_NS = '{http://www.idpf.org/2007/opf}'


# ── PDF ───────────────────────────────────────────────────────────────────────

@dataclass
class PdfFacts:
    pages: int
    link_annotations: int
    external_links: int
    media_box: tuple[float, float]
    half_turns: int = 0
    quarter_turns: int = 0
    fill_opacities: set[str] = field(default_factory=set)
    link_rects: list[tuple[float, float, float, float]] = field(default_factory=list)
    # Every /Title in the file, in order: the outline entries, and the document
    # title from the metadata dictionary if one was set.
    titles: list[str] = field(default_factory=list)


def inspect_pdf(path: Path) -> PdfFacts:
    raw = path.read_bytes()
    assert raw.startswith(b'%PDF-'), 'not a PDF'
    assert b'%%EOF' in raw, 'PDF trailer missing'

    # '/Type /Page' also prefixes '/Type /Pages', so exclude the plural.
    pages = len(re.findall(rb'/Type\s*/Page(?![s])', raw))
    links = len(re.findall(rb'/Subtype\s*/Link', raw))
    # fpdf2 writes '/A << /S /URI /URI (...) >>' — two literals per external link.
    external = len(re.findall(rb'/URI', raw)) // 2

    box = re.search(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]', raw)
    size = (float(box.group(1)), float(box.group(2))) if box else (0.0, 0.0)

    rects = [tuple(round(float(g), 1) for g in m.groups()) for m in re.finditer(
        rb'/Rect\s*\[\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\]', raw)]

    half, quarter = _count_turns(raw)
    return PdfFacts(pages, links, external, size,
                    half_turns=half, quarter_turns=quarter,
                    fill_opacities={m.decode() for m in re.findall(rb'/ca ([\d.]+)', raw)},
                    link_rects=rects,
                    titles=[m.decode('latin-1') for m in
                            re.findall(rb'/Title\s*\(([^)]*)\)', raw)])


def _count_turns(raw: bytes) -> tuple[int, int]:
    """Count the 180- and 45-degree transforms in the page content.

    Content streams are deflated, so the operators are only visible after
    decompressing — searching the raw file finds nothing and would quietly
    report that no rotation was applied.
    """
    half = quarter = 0
    for match in re.finditer(rb'stream\r?\n(.*?)endstream', raw, re.S):
        try:
            content = zlib.decompress(match.group(1))
        except zlib.error:
            continue
        # The two translation components can be negative, depending on where the
        # pivot lands: matching digits only would find nothing and report that
        # no rotation had been applied.
        half += len(re.findall(rb'-1 0 -0 -1 [-\d.]+ [-\d.]+ cm', content))
        # cos 45 = sin 45 = 0.7071…, whichever way fpdf2 rounds it.
        quarter += len(re.findall(rb'0\.7071\d* [-\d.]+ [-\d.]+ 0\.7071\d* [-\d.]+ [-\d.]+ cm',
                                  content))
    return half, quarter


# ── HTML / XHTML ──────────────────────────────────────────────────────────────

@dataclass
class HtmlFacts:
    diagram_ids: list[str]
    answer_ids: list[str]
    anchor_targets: list[str]
    board_rows: int
    css_variables_used: set[str]
    css_variables_defined: set[str]
    embedded_font_mimes: list[str]
    external_urls: list[str]
    title: str
    text: str


def inspect_html(text: str) -> HtmlFacts:
    return HtmlFacts(
        diagram_ids=re.findall(r"id='(diagram-\d+)'", text),
        answer_ids=re.findall(r"id='(answer-\d+)'", text),
        anchor_targets=re.findall(r"href='#([^']+)'", text),
        board_rows=len(re.findall(r"<span class='board-row'>", text)),
        css_variables_used=set(re.findall(r'var\((--[a-z-]+)\)', text)),
        css_variables_defined=set(re.findall(r'(--[a-z-]+)\s*:', text)),
        embedded_font_mimes=re.findall(r'url\("data:(font/[a-z]+);base64,', text),
        external_urls=re.findall(r"href='(https?://[^']+)'", text),
        title=(re.search(r'<title>(.*?)</title>', text, re.S) or [None, ''])[1],
        text=text,
    )


def assert_well_formed_xml(text: str) -> None:
    """XHTML must parse as XML — EPUB readers are not forgiving."""
    ET.fromstring(text)


def dangling_anchors(facts: HtmlFacts) -> list[str]:
    known = set(facts.diagram_ids) | set(facts.answer_ids)
    return sorted({t for t in facts.anchor_targets if t not in known})


def undefined_css_variables(facts: HtmlFacts) -> list[str]:
    return sorted(facts.css_variables_used - facts.css_variables_defined)


# ── EPUB ──────────────────────────────────────────────────────────────────────

@dataclass
class EpubFacts:
    names: list[str]
    first_entry: str
    first_entry_stored: bool
    identifier: str
    title: str
    creator: str
    language: str
    modified: str
    has_nav_property: bool
    manifest_hrefs: list[str]
    spine_idrefs: list[str]
    content: str
    stylesheets: dict[str, str] = field(default_factory=dict)


def inspect_epub(path: Path) -> EpubFacts:
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        names = z.namelist()
        for name in names:
            if name.endswith(('.xhtml', '.opf', '.ncx', '.xml')):
                ET.fromstring(z.read(name))   # raises if malformed

        opf_root = ET.fromstring(z.read('OEBPS/content.opf'))
        content = z.read('OEBPS/content.xhtml').decode('utf-8')
        styles = {
            n.rsplit('/', 1)[-1]: z.read(n).decode('utf-8')
            for n in names if n.endswith('.css')
        }

    def meta_text(tag: str) -> str:
        node = opf_root.find(f'.//{{http://purl.org/dc/elements/1.1/}}{tag}')
        return (node.text or '') if node is not None else ''

    modified = ''
    for meta in opf_root.iter(f'{OPF_NS}meta'):
        if meta.get('property') == 'dcterms:modified':
            modified = meta.text or ''

    items = list(opf_root.iter(f'{OPF_NS}item'))
    return EpubFacts(
        names=names,
        first_entry=infos[0].filename,
        first_entry_stored=infos[0].compress_type == zipfile.ZIP_STORED,
        identifier=meta_text('identifier'),
        title=meta_text('title'),
        creator=meta_text('creator'),
        language=meta_text('language'),
        modified=modified,
        has_nav_property=any('nav' in (i.get('properties') or '').split() for i in items),
        manifest_hrefs=[i.get('href', '') for i in items],
        spine_idrefs=[r.get('idref', '') for r in opf_root.iter(f'{OPF_NS}itemref')],
        content=content,
        stylesheets=styles,
    )


def epub3_problems(facts: EpubFacts) -> list[str]:
    """Return the EPUB 3 conformance failures a validator would report."""
    problems: list[str] = []
    if facts.first_entry != 'mimetype':
        problems.append('mimetype must be the first zip entry')
    if not facts.first_entry_stored:
        problems.append('mimetype must be stored uncompressed')
    if not facts.modified:
        problems.append('missing <meta property="dcterms:modified">')
    if not facts.has_nav_property:
        problems.append('missing navigation document (properties="nav")')
    if not facts.identifier or facts.identifier == 'urn:uuid:12345':
        problems.append(f'identifier is not unique: {facts.identifier!r}')
    if not facts.title:
        problems.append('missing dc:title')
    if not facts.language:
        problems.append('missing dc:language')
    if facts.modified and not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', facts.modified):
        problems.append(f'dcterms:modified is not a CCYY-MM-DDThh:mm:ssZ stamp: {facts.modified!r}')
    for href in facts.manifest_hrefs:
        if f'OEBPS/{href}' not in facts.names:
            problems.append(f'manifest lists a missing file: {href}')
    return problems


# ── DOCX ──────────────────────────────────────────────────────────────────────

@dataclass
class DocxFacts:
    names: list[str]
    bookmarks: list[str]
    internal_anchors: list[str]
    external_rel_targets: list[str]
    paragraph_count: int
    fonts_used: set[str]
    embedded_font_parts: list[str]
    text: str
    # The running header parts, as XML. A watermark is a drawing anchored
    # there, so it never appears in word/document.xml.
    headers: dict[str, str] = field(default_factory=dict)


def inspect_docx(path: Path) -> DocxFacts:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        doc = ET.fromstring(z.read('word/document.xml'))
        rels_xml = z.read('word/_rels/document.xml.rels').decode('utf-8')
        headers = {name: z.read(name).decode('utf-8') for name in names
                   if re.fullmatch(r'word/header\d*\.xml', name)}

    bookmarks = [
        b.get(f'{W_NS}name') for b in doc.iter(f'{W_NS}bookmarkStart')
        if b.get(f'{W_NS}name') not in (None, '_GoBack')
    ]
    anchors = [h.get(f'{W_NS}anchor') for h in doc.iter(f'{W_NS}hyperlink')
               if h.get(f'{W_NS}anchor')]
    fonts = {
        rf.get(f'{W_NS}ascii') for rf in doc.iter(f'{W_NS}rFonts') if rf.get(f'{W_NS}ascii')
    }
    text = ''.join(node.text or '' for node in doc.iter(f'{W_NS}t'))
    external = re.findall(r'Target="(https?://[^"]+)"', rels_xml)

    return DocxFacts(
        names=names,
        bookmarks=bookmarks,
        internal_anchors=anchors,
        external_rel_targets=external,
        paragraph_count=len(list(doc.iter(f'{W_NS}p'))),
        fonts_used=fonts,
        embedded_font_parts=[n for n in names if n.endswith('.odttf')],
        text=text,
        headers=headers,
    )


# ── RTF ───────────────────────────────────────────────────────────────────────

@dataclass
class RtfFacts:
    text: str
    bookmarks: list[str]
    internal_links: list[str]
    external_links: list[str]
    font_table: list[str]
    brace_balance: int
    rows: int


def inspect_rtf(path: Path) -> RtfFacts:
    text = path.read_text(encoding='ascii')
    assert text.startswith(r'{\rtf1'), 'RTF header missing'

    # Count only unescaped braces.
    depth = balance = 0
    idx = 0
    while idx < len(text):
        ch = text[idx]
        if ch == '\\':
            idx += 2
            continue
        if ch == '{':
            depth += 1
            balance = max(balance, depth)
        elif ch == '}':
            depth -= 1
        idx += 1

    return RtfFacts(
        text=text,
        bookmarks=re.findall(r'\\\*\\bkmkstart (\w+)', text),
        internal_links=re.findall(r'HYPERLINK \\\\l "([^"]+)"', text),
        external_links=re.findall(r'HYPERLINK "([^"]+)"', text),
        font_table=re.findall(r'\\f\d+\\fnil\\fcharset\d+ ([^;]+);', text),
        brace_balance=depth,
        rows=text.count(r'\row'),
    )


# ── Markdown ──────────────────────────────────────────────────────────────────

PIECE_TO_LETTER = {
    '♔': 'K', '♕': 'Q', '♖': 'R', '♗': 'B', '♘': 'N', '♙': 'P',
    '♚': 'k', '♛': 'q', '♜': 'r', '♝': 'b', '♞': 'n', '♟': 'p',
}


@dataclass
class MarkdownFacts:
    text: str
    front_matter: dict[str, str]
    headings: list[tuple[int, str]]
    boards: list[list[str]]
    diagram_ids: list[str]
    answer_ids: list[str]
    anchor_targets: list[str]
    external_urls: list[str]
    fence_count: int


def inspect_markdown(path: Path) -> MarkdownFacts:
    text = path.read_text(encoding='utf-8')

    front: dict[str, str] = {}
    if text.startswith('---\n'):
        end = text.find('\n---\n', 3)
        for line in text[4:end].splitlines() if end > 0 else []:
            key, _, value = line.partition(':')
            front[key.strip()] = value.strip().strip('"')

    boards = [block.strip('\n').splitlines()
              for block in re.findall(r'```text\n(.*?)```', text, re.S)]

    return MarkdownFacts(
        text=text,
        front_matter=front,
        headings=[(len(h), t.strip()) for h, t in re.findall(r'^(#{1,6}) (.+)$', text, re.M)],
        boards=boards,
        diagram_ids=re.findall(r'<a id="(diagram-\d+)">', text),
        answer_ids=re.findall(r'<a id="(answer-\d+)">', text),
        anchor_targets=re.findall(r'\]\(#([^)]+)\)', text),
        external_urls=re.findall(r'\]\((https?://[^)]+)\)', text),
        fence_count=text.count('```'),
    )


def board_from_markdown(rows: list[str], has_coords: bool) -> list[list[str | None]]:
    """Decode a Markdown board block back into an 8x8 array of piece letters.

    Lets a test assert that FEN -> Unicode board -> FEN round-trips, which is
    what catches a mirrored board or a wrong piece far more clearly than
    comparing the file against a stored copy.
    """
    board: list[list[str | None]] = []
    for line in rows:
        cells = line.split()
        if has_coords:
            if not cells or not cells[0].isdigit():
                continue          # the file-label line, or the side-to-move line
            cells = cells[1:]
        elif len(cells) != 8 or any(c not in PIECE_TO_LETTER and c != '·' for c in cells):
            continue
        if len(cells) != 8:
            continue
        board.append([PIECE_TO_LETTER.get(c) for c in cells])
    return board


# ── LaTeX ─────────────────────────────────────────────────────────────────────

@dataclass
class LatexFacts:
    text: str
    packages: list[str]
    fens: list[str]
    inverse_count: int
    hypertargets: list[str]
    hyperlinks: list[str]
    external_urls: list[str]
    sections: list[str]
    environments: list[str]      # the nesting faults, empty when sound
    brace_balance: int


def inspect_latex(path: Path) -> LatexFacts:
    text = path.read_text(encoding='utf-8')
    assert text.lstrip().startswith('%') or text.lstrip().startswith(r'\document'), \
        'not a LaTeX document'

    # Count braces outside comments, ignoring escaped ones.
    depth = 0
    for line in text.splitlines():
        stripped = re.sub(r'(?<!\\)%.*$', '', line)
        stripped = re.sub(r'\\[{}]', '', stripped)
        depth += stripped.count('{') - stripped.count('}')

    return LatexFacts(
        text=text,
        packages=re.findall(r'\\usepackage(?:\[[^\]]*\])?\{([^}]+)\}', text),
        fens=re.findall(r'\\chessboard\[setfen=\{([^}]+)\}', text),
        inverse_count=len(re.findall(r'inverse=true', text)),
        hypertargets=re.findall(r'\\hypertarget\{([^}]+)\}', text),
        hyperlinks=re.findall(r'\\hyperlink\{([^}]+)\}', text),
        external_urls=re.findall(r'\\href\{([^}]+)\}', text),
        sections=re.findall(r'\\section\*?\{([^}]*)\}', text),
        environments=_environment_faults(text),
        brace_balance=depth,
    )


def _environment_faults(text: str) -> list[str]:
    """Return every \\begin/\\end that does not nest.

    Environments nest like brackets, so the closing order is the reverse of the
    opening order — comparing two flat lists would call a correct document
    broken the moment anything sits inside \\begin{document}.
    """
    faults: list[str] = []
    stack: list[str] = []
    for kind, name in re.findall(r'\\(begin|end)\{(\w+\*?)\}', text):
        if kind == 'begin':
            stack.append(name)
        elif not stack:
            faults.append(f'\\end{{{name}}} with nothing open')
        elif stack[-1] != name:
            faults.append(f'\\end{{{name}}} closes \\begin{{{stack.pop()}}}')
        else:
            stack.pop()
    faults += [f'\\begin{{{name}}} is never closed' for name in stack]
    return faults


def latex_problems(facts: LatexFacts) -> list[str]:
    """Return the structural failures that would stop a compile."""
    problems: list[str] = list(facts.environments)
    if facts.brace_balance != 0:
        problems.append(f'unbalanced braces: {facts.brace_balance:+d}')
    if 'chessboard' not in facts.packages:
        problems.append('the chessboard package is not loaded')
    if r'\begin{document}' not in facts.text:
        problems.append('no document environment')
    if r'\end{document}' not in facts.text:
        problems.append('document is not closed')
    for target in facts.hyperlinks:
        if target not in facts.hypertargets:
            problems.append(f'link to a missing target: {target}')
    return problems
