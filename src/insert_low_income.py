"""Insert the low-income IDC into the filled monthly report (``idc-update-YYYYMM.tex``).

The monthly report is written by the agent from the local template, which is not versioned.  This step adds
what the low-income IDC needs, anchoring on the section structure that ``src.build_report_docx`` already
requires, so it works on any filled report without changing the template:

* a paragraph in ``Resumo``;
* the results table with the two IDCs side by side (replaces the one of the template);
* the paragraphs on the group, at the end of ``Resultados``;
* a paragraph on the figures, at the end of ``Trajetória do índice``;
* the note on the method, in ``Notas``;
* the captions and sources of the two annex figures.

When the SCR.data could not be used in the edition (status other than ``ok``), a single sentence says so and
nothing else changes.  The text never refers to any other document: the report is self-contained.
The report and the processed data must refer to the same month (``\\mesref`` against the last month of the
data); otherwise nothing is written, so that numbers of another release never enter a filled report.

Every inserted block sits between ``% >>> IDC baixa renda (...)`` and ``% <<< IDC baixa renda (...)`` comment
lines, so running the step again regenerates the blocks instead of duplicating them.  The agent reviews the
text afterwards (style rules in PIPELINE.md); the numbers must not be changed by hand.

Command line (from the repository root, after ``python3 main.py``)::

    python3 -m src.insert_low_income 202609            # writes outputs/report/update-202609/idc-update-202609.tex
    python3 -m src.insert_low_income 202609 --check    # only validates the current file
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

from src import low_income as LI
from src.income_idc import JANELA_INICIO, primeira_exibicao
from src.pt_format import mes

REPORT_DIR = "outputs/report/update-{period}"
REPORT_NAME = "idc-update-{period}.tex"

BEGIN = "% >>> IDC baixa renda ({name}): gerado por src.insert_low_income; revise o texto sem alterar os números"
END = "% <<< IDC baixa renda ({name})"
_BLOCK = re.compile(r"% >>> IDC baixa renda \((?P<name>[^)]+)\):[^\n]*\n(?P<body>.*?)% <<< IDC baixa renda \((?P=name)\)\n\n?", re.S)

# Anchors: the structure that the DOCX converter already requires of every monthly report.
SECTION_RESULTS = r"\section{Resultados de"
SECTION_TRAJECTORY = r"\section{Trajetória do índice}"
SECTION_NEXT = r"\section{Próxima atualização}"
SECTION_REVISIONS = r"\section{Revisões dos dados}"
COMMENT_REVISIONS = "% SEÇÃO OPCIONAL — REVISÕES DOS DADOS"
NOTE_REVISIONS = "Revisões dos dados. Os valores históricos"

# What a bold span may contain in the report: numbers, percentages, deltas and abbreviated month-years.
_BOLD_OK = re.compile(r"^(?:[+\-−]?\d+(?:,\d+)?(?:~ponto|~p\.p\.|\\%)?|[a-z]{3}-\d{4}|\\(?:mesref|mesanterior|mesproximo))$")


def _wrap(name: str, body: str) -> str:
    return f"{BEGIN.format(name=name)}\n{body.strip()}\n{END.format(name=name)}\n"


def remove_blocks(tex: str, keep: tuple[str, ...] = ()) -> tuple[str, list[str]]:
    """Remove the blocks inserted by an earlier run (except those named in ``keep``); returns the text and the names removed."""
    names = [m.group("name") for m in _BLOCK.finditer(tex) if m.group("name") not in keep]
    return _BLOCK.sub(lambda m: m.group(0) if m.group("name") in keep else "", tex), names


def invalid_bold(tex: str) -> list[str]:
    """Bold spans that break the style rule (bold only for numbers, percentages, deltas and month-years)."""
    found = []
    for m in re.finditer(r"\\textbf\{([^{}]*)\}", tex):
        if not _BOLD_OK.match(m.group(1).strip()):
            found.append(m.group(1))
    return found


def _find(tex: str, anchor: str, start: int = 0) -> int:
    i = tex.find(anchor, start)
    if i < 0:
        raise ValueError(f"âncora não encontrada no relatório: {anchor!r}. O relatório preenchido precisa manter a estrutura do template.")
    return i


def _insert_before(tex: str, anchor: str, name: str, body: str, start: int = 0) -> str:
    i = _find(tex, anchor, start)
    return tex[:i] + _wrap(name, body) + "\n" + tex[i:]


def _replace_table(tex: str, table: str) -> str:
    """Put the two-index table in place of the table of the template (or of the one inserted by an earlier run)."""
    previous = [m for m in _BLOCK.finditer(tex) if m.group("name") == "tabela"]
    if previous:
        return tex[:previous[0].start()] + _wrap("tabela", table) + "\n" + tex[previous[0].end():]
    results = _find(tex, SECTION_RESULTS)
    begin = _find(tex, r"\begin{table}", results)
    end = _find(tex, r"\end{table}", begin) + len(r"\end{table}")
    return tex[:begin] + _wrap("tabela", table).rstrip("\n") + tex[end:]


def _update_table_source(tex: str) -> str:
    """Mention the SCR.data in the source line that follows the results table."""
    if re.search(r"\\fonte\{[^}]*SCR\.data para o IDC", tex):
        return tex
    pattern = re.compile(r"(\\fonte\{Banco Central do Brasil \(Estatísticas Monetárias e de Crédito,\s*divulgação \\competencia)\)(, elaboração própria\.\})")
    new, n = pattern.subn(r"\1; SCR.data para o IDC para baixa renda)\2", tex, count=1)
    if n != 1:
        raise ValueError("fonte da tabela de resultados não encontrada (esperado: 'Banco Central do Brasil (Estatísticas Monetárias e de Crédito, divulgação \\competencia), elaboração própria.')")
    return new


def _update_figures(tex: str) -> str:
    """Captions and sources of the two annex figures."""
    low_start = mes(primeira_exibicao())
    series_start = mes(JANELA_INICIO)
    captions = [
        (r"\caption{Evolução do Índice de Desconforto de Crédito (\janelainicio{} a \mesref).}",
         rf"\caption{{Evolução do Índice de Desconforto de Crédito geral (\janelainicio{{}} a \mesref) e para baixa renda ({low_start} a \mesref).}}"),
        (r"\caption{Evolução das componentes brutas C, I e Q (\seriesinicio{} a \mesref).}",
         rf"\caption{{Evolução das componentes brutas C, I e Q (\seriesinicio{{}} a \mesref); I e Q também para baixa renda ({series_start} a \mesref).}}"),
    ]
    for old, new in captions:
        if new in tex:
            continue
        if old not in tex:
            raise ValueError(f"legenda de figura não encontrada: {old!r}")
        tex = tex.replace(old, new, 1)

    def source(m: re.Match) -> str:
        text = m.group(1)
        if "SCR.data" in text:
            return m.group(0)
        if text.strip() == "BCB, elaboração própria.":
            return r"\fonte{BCB (SGS e SCR.data), elaboração própria.}"
        return "\\fonte{" + text.replace(", elaboração própria", "; SCR.data, elaboração própria") + "}"

    def figure(m: re.Match) -> str:
        return re.sub(r"\\fonte\{([^{}]*)\}", source, m.group(0))

    return re.sub(r"\\begin\{figure\}.*?\\end\{figure\}", figure, tex, flags=re.S)


def report_month(tex: str) -> str | None:
    """Reference month written in the report (``\\mesref``), or ``None`` when the macro is missing."""
    found = re.search(r"^\\newcommand\{\\mesref\}\{(.*?)\}[ \t]*(?:%.*)?$", tex, re.M)
    return found.group(1) if found else None


def _check_month(tex: str, resultado: LI.Resultado) -> None:
    mesref = report_month(tex)
    if mesref is None or "placeholder" in mesref:
        raise ValueError("o relatório precisa estar preenchido antes da inserção (\\mesref ausente ou ainda com placeholder)")
    if resultado.t1 is not None and mesref != mes(resultado.t1):
        raise ValueError(f"o relatório trata de {mesref}, mas os dados do IDC para baixa renda terminam em {mes(resultado.t1)}; "
                         "rode python3 main.py com o release do relatório")


def insert(tex: str, resultado: LI.Resultado, facts: LI.FatosBaixaRenda | None) -> str:
    """Return ``tex`` with the low-income blocks for this edition (regenerating blocks of a previous run)."""
    _check_month(tex, resultado)
    tex, _ = remove_blocks(tex, keep=("tabela",))
    if _find(tex, SECTION_RESULTS) > _find(tex, SECTION_TRAJECTORY):
        raise ValueError("seções do relatório fora da ordem esperada (Resultados antes de Trajetória do índice)")
    results_start = _find(tex, SECTION_RESULTS)
    present = [(tex.find(a, results_start), a) for a in (SECTION_REVISIONS, COMMENT_REVISIONS, SECTION_TRAJECTORY)]
    anchor_results_end = min((pos, a) for pos, a in present if pos >= 0)[1]  # the first of them in the document
    if not resultado.disponivel:
        if any(m.group("name") == "tabela" for m in _BLOCK.finditer(tex)):
            raise ValueError("o relatório já tem a tabela do IDC para baixa renda de uma rodada anterior; recomece do template")
        return _insert_before(tex, anchor_results_end, "indisponível", LI.par_indisponivel(resultado), _find(tex, SECTION_RESULTS))
    assert facts is not None
    tex = _insert_before(tex, SECTION_RESULTS, "resumo", LI.par_resumo(facts))
    tex = _replace_table(tex, LI.tabela_componentes(facts))
    tex = _update_table_source(tex)
    tex = _insert_before(tex, anchor_results_end, "resultados", LI.pars_resultados(facts), _find(tex, SECTION_RESULTS))
    tex = _insert_before(tex, SECTION_NEXT, "trajetória", LI.par_trajetoria(facts), _find(tex, SECTION_TRAJECTORY))
    tex = _insert_before(tex, NOTE_REVISIONS, "nota", LI.nota_baixa_renda())
    tex = _update_figures(tex)
    return tex


def validate(tex: str) -> list[str]:
    """Problems that must be fixed before the report is compiled (empty when everything is in order)."""
    problems = []
    blocks = "\n".join(m.group("body") for m in _BLOCK.finditer(tex))
    visible = "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in tex.splitlines())  # LaTeX comments are not part of the report
    if re.search(r"ap[êe]ndice", visible, re.I):
        problems.append("o relatório menciona o apêndice; a nota principal não pode citá-lo")
    problems += [f"negrito fora da regra: {b}" for b in invalid_bold(blocks)]
    if tex.count(r"\begin{table}") and "tab:componentes" not in tex:
        problems.append("a tabela de resultados perdeu o rótulo tab:componentes")
    return problems


def facts_from_data(period: str, data_dir: Path = Path("data/processed")) -> tuple[LI.Resultado, LI.FatosBaixaRenda | None]:
    """Facts for the edition from the files written by ``main.py``; ``None`` facts when the index is unavailable."""
    resultado = LI.carregar(data_dir / "low_income_idc.csv", data_dir / "low_income_status.json")
    if not resultado.disponivel:
        return resultado, None
    comp = pd.read_csv(data_dir / "components_raw.csv", index_col=0, parse_dates=True)
    idx = pd.read_csv(data_dir / "index.csv", index_col=0, parse_dates=True)
    t1 = pd.Timestamp(comp.dropna().index.max())
    if resultado.t1 != t1:
        raise ValueError(f"o IDC baixa renda termina em {mes(resultado.t1)}, mas o IDC geral termina em {mes(t1)}; rode python3 main.py de novo")
    return resultado, LI.fatos(resultado.serie, idx["index"], comp, idx, t1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Insere o IDC para baixa renda no relatório mensal preenchido.")
    parser.add_argument("period", help="competência da divulgação do BCB (AAAAMM)")
    parser.add_argument("--check", action="store_true", help="só valida o arquivo atual, sem escrever")
    parser.add_argument("--tex", type=Path, help="caminho do .tex (padrão: outputs/report/update-AAAAMM/idc-update-AAAAMM.tex)")
    args = parser.parse_args(argv)
    path = args.tex or Path(REPORT_DIR.format(period=args.period)) / REPORT_NAME.format(period=args.period)
    if not path.exists():
        print(f"Relatório não encontrado: {path}", file=sys.stderr)
        return 1
    tex = path.read_text(encoding="utf-8")
    if args.check:
        problems = validate(tex)
        print("\n".join(problems) if problems else "Blocos do IDC baixa renda válidos.")
        return 1 if problems else 0
    try:
        resultado, facts = facts_from_data(args.period)
        new = insert(tex, resultado, facts)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Falha: {exc}", file=sys.stderr)
        return 1
    problems = validate(new)
    if problems:
        print("Falha na validação:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    path.write_text(new, encoding="utf-8")
    print(f"IDC para baixa renda {'inserido' if resultado.disponivel else 'indisponível (' + resultado.motivo + '); aviso inserido'} em {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
