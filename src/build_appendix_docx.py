"""Convert the generated statistical appendix to editable Word content.

Pandoc converts the LaTeX mathematics to native Office Math; text, tables and
figures are generated from the same LaTeX source with python-docx.
"""
from __future__ import annotations

import copy
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt

from src import build_report_docx as R

MATH_PATTERN = re.compile(r"\\\[(.*?)\\\]|(?<!\\)\$(.*?)(?<!\\)\$", re.S)
TOKEN_PATTERN = re.compile(r"IDC_MATH_(\d+)_END")
BLOCKS = re.compile(
    r"\\begin\{(?P<env>table|figure|itemize)\}(?:\[[^]]*\])?.*?\\end\{(?P=env)\}"
    r"|\\(?P<heading>subsubsection|subsection|section)\{[^{}]*\}(?:\\label\{[^{}]*\})?",
    re.S,
)



def _prepare_math(source: str) -> tuple[str, list[str]]:
    """Use stacked fractions and spell out underbrace labels in nearby text.

    Word stores both variants as editable math. Some LibreOffice versions render
    the Unicode brace used by Pandoc's underbrace mapping as a missing glyph;
    spelling out the labels keeps the same decomposition legible there as well.
    """
    labels = []
    cursor = 0
    result = []
    while match := re.search(r"\\underbrace\s*\{", source[cursor:]):
        start = cursor + match.start()
        brace = cursor + match.end() - 1
        expression, end = R._extract_group(source, brace)
        following = re.match(r"\s*_\s*\{", source[end:])
        if following is None:
            raise ValueError("Fórmula com underbrace sem rótulo")
        label_brace = end + following.end() - 1
        label, cursor = R._extract_group(source, label_brace)
        labels.append(R._plain_latex(label))
        # Preserve every part of the expression, replacing only the brace.
        result.append(source[:start] if not result else source[previous_end:start])
        result.append("{" + expression + "}")
        previous_end = cursor
    if labels:
        if labels != ["dentro", "composição"] or r"\bar w_u" not in source or r"\bar x_u" not in source:
            raise ValueError("Fórmula com rótulos underbrace não reconhecidos")
        result.append(source[cursor:])
        source = "".join(result)
        # Pandoc's overbar accent can be rendered as an acute accent by
        # LibreOffice. Superscript m denotes the same arithmetic averages.
        source = source.replace(r"\bar w_u", r"w^{m}_u").replace(r"\bar x_u", r"x^{m}_u")
    return source.replace(r"\tfrac", r"\frac"), labels

def _math_objects(text: str) -> tuple[str, list]:
    # A prose sentence can continue immediately after the displayed formula.
    # Once the explanatory labels become their own sentence, preserve grammar.
    text = re.sub(r"(\\\][ \t\r\n]*)e a soma das duas partes", r"\1A soma das duas partes", text)
    matches = list(MATH_PATTERN.finditer(text))
    if not matches:
        return text, []
    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise RuntimeError("pandoc é necessário para gerar as fórmulas editáveis do apêndice")
    # One paragraph per expression gives a stable one-to-one correspondence.
    prepared = [_prepare_math(m.group(1) if m.group(1) is not None else m.group(2)) for m in matches]
    markdown = "\n\n".join(r"\(" + expression.replace("\n", " ") + r"\)" for expression, _ in prepared)
    with tempfile.TemporaryDirectory() as directory:
        destination = Path(directory) / "math.docx"
        result = subprocess.run([pandoc, "-f", "latex", "-t", "docx", "-o", str(destination)], input=markdown, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(f"Falha ao converter fórmulas com pandoc: {result.stderr.strip()}")
        with ZipFile(destination) as archive:
            xml = ET.fromstring(archive.read("word/document.xml"))
        ns = {"m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}
        equations = xml.findall(".//m:oMath", ns)
        if len(equations) != len(matches):
            raise ValueError(f"Pandoc converteu {len(equations)} das {len(matches)} fórmulas")
        # Reparse as lxml elements compatible with python-docx's XML tree.
        from docx.oxml import parse_xml
        equations = [parse_xml(ET.tostring(eq, encoding="unicode")) for eq in equations]
    index = iter(range(len(matches)))

    def replace(match):
        n = next(index)
        labels = prepared[n][1]
        note = ""
        if labels:
            if len(labels) != 2:
                raise ValueError("Fórmula com número inesperado de rótulos underbrace")
            note = (f"As duas parcelas da soma correspondem, respectivamente, aos efeitos {labels[0]} e {labels[1]}. "
                    "O expoente m indica a média entre as duas datas.")
        if match.group(1) is not None:
            return f"\n\nIDC_MATH_{n}_END\n\n{note}\n\n"
        return f"IDC_MATH_{n}_END" + (f" ({note})" if note else "")

    return MATH_PATTERN.sub(replace, text), equations


def _inline(paragraph, text: str, refs: dict[str, str], maths: list, *, italic: bool = False) -> None:
    text = text.replace(r"\emph{", r"\textit{").replace("``", "“").replace("''", "”").replace("---", "—").replace("--", "–")
    cursor = 0
    for match in TOKEN_PATTERN.finditer(text):
        R._append_inline(paragraph, text[cursor:match.start()], refs=refs, italic=italic)
        paragraph._p.append(copy.deepcopy(maths[int(match.group(1))]))
        cursor = match.end()
    R._append_inline(paragraph, text[cursor:], refs=refs, italic=italic)


def _references(body: str) -> dict[str, str]:
    refs: dict[str, str] = {}
    counts = {"section": 0, "table": 0, "figure": 0}
    for match in BLOCKS.finditer(body):
        kind = match.group("env") or match.group("heading")
        if kind not in counts:
            continue
        counts[kind] += 1
        label = R._optional_command_argument(match.group(), "label")
        if label:
            if label[0] in refs:
                raise ValueError(f"Rótulo duplicado no apêndice: {label[0]}")
            refs[label[0]] = ("A" if kind != "section" else "") + str(counts[kind])
    unresolved = set(re.findall(r"\\ref\{([^}]+)\}", body)) - refs.keys()
    if unresolved:
        raise ValueError(f"Referências não resolvidas no apêndice: {', '.join(sorted(unresolved))}")
    return refs


def _caption(document, label: str, number: str, text: str, refs, maths):
    p = document.add_paragraph(style="IDC Caption")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"{label} {number}. ")
    run.bold = True
    _inline(p, R._collapse_source(text), refs, maths, italic=True)


def _source(document, source, refs, maths):
    p = document.add_paragraph(style="IDC Source")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("Fonte: ").italic = True
    _inline(p, R._collapse_source(source), refs, maths, italic=True)


def _table(document, block: str, number: int, refs, maths):
    caption, rows, source = R._parse_table(block, expected_columns=tuple(range(2, 25)), table_name=f"Tabela A{number}")
    _caption(document, "Tabela", f"A{number}", caption, refs, maths)
    n = len(rows[0])
    table = document.add_table(rows=len(rows), cols=n)
    table.autofit = False
    # The leading descriptor receives more room than numeric columns.
    first = 0.32 if n > 3 else 1 / n
    widths = [round(8504 * first)] + [round(8504 * (1 - first) / (n - 1))] * (n - 1)
    R._set_table_geometry(table, widths)
    for i, row in enumerate(rows):
        for j, cell_text in enumerate(row):
            if cell_text == R.SPAN:
                continue
            span = 1
            while j + span < n and row[j + span] == R.SPAN:
                span += 1
            cell = table.cell(i, j)
            if span > 1:
                cell = cell.merge(table.cell(i, j + span - 1))
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if j == 0 and span == 1 else WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(0)
            # Keep the source note with the last row when a table spans pages.
            p.paragraph_format.keep_with_next = i == len(rows) - 1
            _inline(p, cell_text, refs, maths)
            for run in p.runs:
                R._set_run_font(run, size=8 if n > 5 else 9)
            borders = {}
            if i == 0:
                borders["top"] = {"val": "single", "sz": "8", "color": "000000"}
                borders["bottom"] = {"val": "single", "sz": "4", "color": "000000"}
            if i == len(rows) - 1:
                borders["bottom"] = {"val": "single", "sz": "8", "color": "000000"}
            R._set_cell_borders(cell, **borders)
    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    for row in table.rows:
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
    if source is None:
        raise ValueError(f"Tabela A{number} sem fonte")
    _source(document, source, refs, maths)


def _figure(document, block: str, number: int, assets: Path, refs, maths):
    found = re.search(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", block)
    if not found:
        raise ValueError(f"Figura A{number} sem imagem")
    path = assets / found.group(1)
    if not path.is_file():
        raise FileNotFoundError(f"Figura não encontrada: {path}")
    caption = R._command_argument(block, "caption")[0]
    source = R._command_argument(block, "fonte")[0]
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.keep_with_next = True
    from docx.image.image import Image
    im = Image.from_file(str(path))
    width = min(138, 165 * im.px_width / im.px_height)
    drawing = p.add_run().add_picture(str(path), width=Mm(width))
    drawing._inline.docPr.set("descr", R._plain_latex(caption))
    _caption(document, "Figura", f"A{number}", caption, refs, maths)
    _source(document, source, refs, maths)


def _prose(document, text, refs, maths):
    text = R._strip_comments(text)
    text = re.sub(r"\\(?:clearpage|newpage|FloatBarrier)\b", "", text)
    for fragment in re.split(r"\n\s*\n", text):
        fragment = R._collapse_source(fragment)
        if not fragment:
            continue
        p = document.add_paragraph()
        R._set_paragraph_body(p)
        p.paragraph_format.line_spacing = 1.2
        if TOKEN_PATTERN.fullmatch(fragment):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.first_line_indent = Mm(0)
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(6)
        # Run-in paragraph headings (Organização, Convenções, etc.).
        head = re.match(r"\\paragraph\{([^{}]*)\}\s*", fragment)
        if head:
            run = p.add_run(head.group(1) + " ")
            run.bold = True
            fragment = fragment[head.end():]
        _inline(p, fragment, refs, maths)


def build_docx(tex_path: Path, output_path: Path, *, assets_dir: Path | None = None) -> None:
    text = tex_path.read_text(encoding="utf-8")
    if r"\placeholder{" in R._strip_comments(text):
        raise ValueError("O apêndice contém placeholders")
    macros = R._extract_macros(text)
    assets_dir = assets_dir or tex_path.parent
    if not (assets_dir / "logo.png").is_file():
        raise FileNotFoundError(f"Logotipo não encontrado: {assets_dir / 'logo.png'}")
    start = text.find(r"\section{", text.find(r"\tableofcontents"))
    end = text.find(r"\end{document}", start)
    if start < 0 or end < 0:
        raise ValueError("Estrutura do apêndice incompleta")
    body = R._expand_macros(text[start:end], macros)
    refs = _references(body)
    body, maths = _math_objects(body)
    document = Document()
    R._configure_styles(document)
    cover = {key: R._expand_macros(value, macros) for key, value in macros.items()}
    # The draft marker uses presentation commands and a LaTeX line break.
    cover["reportsubtitle"] = re.sub(r"\\\\\[[^]]*\]\\normalsize\\textit\{([^{}]*)\}", r" — \1", cover["reportsubtitle"])
    R._add_cover(document, cover, assets_dir / "logo.png")
    document.core_properties.title = R._plain_latex(cover["reporttitle"]) + " — Apêndice Estatístico"
    document.core_properties.subject = "Apêndice Estatístico do IDC"
    document.core_properties.author = "; ".join(cover[k] for k in ("authorone", "authortwo", "authorthree"))
    section = document.add_section(WD_SECTION.NEW_PAGE)
    R._configure_page(section)
    R._restart_page_number(section, 1)
    R._configure_content_header_footer(
        section,
        R._plain_latex(cover["reporttitle"]) + " — Apêndice Estatístico",
        R._plain_latex(cover.get("reportinstitution", R.DEFAULT_INSTITUTION)),
    )
    # Editable, populated contents avoids an empty field in renderers that do
    # not update TOC fields automatically. The headings are the source of truth.
    document.add_heading("Sumário", level=1)
    summary_counts = {"section": 0, "subsection": 0, "subsubsection": 0}
    for entry in BLOCKS.finditer(body):
        kind = entry.group("heading")
        if not kind:
            continue
        summary_counts[kind] += 1
        if kind == "section":
            summary_counts["subsection"] = summary_counts["subsubsection"] = 0
        elif kind == "subsection":
            summary_counts["subsubsection"] = 0
        level = {"section": 1, "subsection": 2, "subsubsection": 3}[kind]
        number = ".".join(str(summary_counts[k]) for k in ("section", "subsection", "subsubsection")[:level])
        p = document.add_paragraph()
        p.paragraph_format.left_indent = Mm(5 * (level - 1))
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.space_after = Pt(2)
        _inline(p, f"{number} {R._command_argument(entry.group(), kind)[0]}", refs, maths)
    document.add_page_break()
    counts = {"section": 0, "subsection": 0, "subsubsection": 0, "table": 0, "figure": 0}
    cursor = 0
    for match in BLOCKS.finditer(body):
        _prose(document, body[cursor:match.start()], refs, maths)
        kind, block = match.group("env") or match.group("heading"), match.group()
        if kind in ("section", "subsection", "subsubsection"):
            counts[kind] += 1
            if kind == "section":
                counts["subsection"] = counts["subsubsection"] = 0
            elif kind == "subsection":
                counts["subsubsection"] = 0
            level = {"section": 1, "subsection": 2, "subsubsection": 3}[kind]
            number = ".".join(str(counts[k]) for k in ("section", "subsection", "subsubsection")[:level])
            title = R._command_argument(block, kind)[0]
            p = document.add_paragraph(style=f"Heading {level}")
            _inline(p, f"{number} {title}", refs, maths)
        elif kind == "table":
            counts[kind] += 1
            _table(document, block, counts[kind], refs, maths)
        elif kind == "figure":
            counts[kind] += 1
            _figure(document, block, counts[kind], assets_dir, refs, maths)
        else:
            for item in re.split(r"\\item\b", block)[1:]:
                item = item.replace(r"\end{itemize}", "")
                p = document.add_paragraph(style="List Bullet")
                _inline(p, R._collapse_source(item), refs, maths)
        cursor = match.end()
    _prose(document, body[cursor:], refs, maths)
    settings = document.settings._element
    update = settings.find(qn("w:updateFields"))
    if update is None:
        update = OxmlElement("w:updateFields")
        settings.append(update)
    update.set(qn("w:val"), "true")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)
