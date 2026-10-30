"""Build the statistical appendix of the IDC (a separate PDF) for one BCB release.

The appendix gathers what the monthly report leaves out: the two indices of the report (general and
low-income), the anatomy of the changes of I, Q and C, the decompositions of I and Q by income class, lender,
occupation and state, the IDC for the four income classes with its limits, and the quality tests of the
SCR.data.  Every number of its text comes from the data; the document reuses the preamble and the cover data of
the filled monthly report, so it is built *after* ``outputs/report/update-AAAAMM/idc-update-AAAAMM.tex``.

Command line (from the repository root, after ``python3 main.py`` and the monthly report)::

    python3 -m src.build_appendix 202609                # writes idc-apendice-202609.tex/.pdf next to the report
    python3 -m src.build_appendix 202609 --draft        # "Versão para discussão" on the cover
    python3 -m src.build_appendix 202609 --no-sgs-update  # do not call the SGS API; use data/processed/sgs_snapshot.csv

Exit codes: 0 built; 1 error; 3 not built because the SCR.data or the SGS series cannot support it (the report
then goes out without an appendix and says nothing about it).
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src import lenses as L
from src import scr_data, sgs_api
from src.anatomy import SGS_CODES
from src.appendix_data import DadosApendice, reunir
from src.appendix_document import FIGURAS, gerar_figuras, montar_corpo
from src.pt_format import mes

REPORT_DIR = "outputs/report/update-{period}"
DATA_DIR = Path("data/processed")
CRI_CSV = Path("data/external/cri_faixa_ref202504.csv")
LUALATEX_FALLBACK = "/Library/TeX/texbin/lualatex"
MACROS = ("reporttitle", "mesreferencia", "mesref", "competencia", "mespublicacao", "janelainicio", "seriesinicio",
          "reportdate", "authorone", "authortwo", "authorthree")
SHARED_FIGURES = ("index.png", "components_raw.png")  # figures of the monthly report, with the low-income lines


class NotBuilt(Exception):
    """The appendix cannot be built in this edition for lack of data (not an error of the pipeline)."""


def load_sgs(t1: pd.Timestamp, path: Path = sgs_api.SNAPSHOT_CSV, update: bool = True, log=print) -> pd.DataFrame:
    """SGS series of the appendix: from the API (and stored), or from the stored snapshot when the API fails."""
    if update:
        try:
            frame = sgs_api.snapshot(SGS_CODES)
            sgs_api.save_snapshot(frame, path)
            return frame
        except RuntimeError as exc:
            log(f"SGS indisponível ({exc}); usando {path}")
    if path.exists():
        frame = sgs_api.load_snapshot(path)
        if frame["C_total"].dropna().index.max() >= t1:
            return frame
    raise NotBuilt("as séries do SGS não estão disponíveis e o arquivo salvo não cobre o mês de referência")


def check_sgs_vintage(sgs: pd.DataFrame, series_raw: pd.DataFrame, t1: pd.Timestamp, months: int = 24) -> list[str]:
    """Differences between the SGS API and the workbook of the release, beyond the rounding of the workbook.

    The appendix mixes both sources (the report and the index come from the workbook, the decompositions from
    the API), so they must be the same vintage.  The API is revised with each BCB release: running an old
    period after a newer release is out would silently mix vintages.
    """
    window = pd.date_range(t1 - pd.DateOffset(months=months - 1), t1, freq="MS")
    pairs = {"C_total": ("comprometimento_renda", 0.055), "inad_total": ("inadimplencia", 0.055), "saldo_total": ("total_credito_pf", 1.0)}
    problems = []
    for column, (workbook_column, tolerance) in pairs.items():
        diff = (sgs[column].reindex(window) - series_raw[workbook_column].reindex(window)).abs()
        if diff.max() > tolerance:
            month = diff.idxmax()
            problems.append(f"{column} em {mes(month)}: API {sgs.loc[month, column]:.2f} contra planilha {series_raw.loc[month, workbook_column]:.2f}")
    return problems


def load_data(period: str, update_sgs: bool = True, ignore_vintage: bool = False, log=print, reference: pd.Timestamp | None = None) -> DadosApendice:
    components = pd.read_csv(DATA_DIR / "components_raw.csv", index_col=0, parse_dates=True)
    index = pd.read_csv(DATA_DIR / "index.csv", index_col=0, parse_dates=True)
    t1 = pd.Timestamp(components.dropna().index.max()) if reference is None else pd.Timestamp(reference)
    components, index = components.loc[:t1], index.loc[:t1]  # ``reference`` re-runs an earlier month without look-ahead
    if not (scr_data.OUT_DIR / "scr_faixa.csv").exists():
        raise NotBuilt("agregados do SCR.data ausentes; rode python3 -m src.scr_data refresh")
    raw = scr_data.load_aggregates()
    panels = {lens: L.painel(frame, lens) for lens, frame in raw.items()}
    sgs = load_sgs(t1, update=update_sgs, log=log)
    problems = check_sgs_vintage(sgs, pd.read_csv(DATA_DIR / "series_raw.csv", index_col=0, parse_dates=True), t1)
    if problems:
        message = "as séries do SGS não são da mesma safra da planilha " + period + " (" + "; ".join(problems) + ")"
        if not ignore_vintage:
            raise ValueError(message + ". A API foi revisada depois da divulgação; gere o apêndice na rodada do período ou use --ignore-vintage para teste.")
        log("AVISO: " + message)
    workbook = Path(f"data/raw/{period}/{period}_Tabelas_de_estatisticas_monetarias_e_de_credito.xlsx")
    try:
        return reunir(t1, sgs, components, index, panels, raw, workbook, scr_data.load_vintage(), CRI_CSV)
    except RuntimeError as exc:  # the SCR.data does not cover the month, or does not reconcile
        raise NotBuilt(str(exc).replace("o apêndice exige a Camada 2: ", "")) from exc


def report_macros(tex: str) -> dict[str, str]:
    macros = dict(re.findall(r"\\newcommand\{\\(\w+)\}\{([^}]*)\}", tex))
    missing = [name for name in MACROS if name not in macros]
    if missing or r"\placeholder" in "".join(macros[name] for name in MACROS if name in macros):
        raise ValueError(f"o relatório mensal precisa estar preenchido (macros ausentes ou com placeholder: {missing or 'placeholder'})")
    return macros


def preamble(tex: str) -> str:
    """Preamble of the monthly report (everything before its ``DADOS DO RELATÓRIO`` block), adapted to the appendix."""
    cut = tex.index("%   DADOS DO RELATÓRIO")
    cut = tex.rfind("\n", 0, tex.rfind("% ====", 0, cut)) + 1
    head = tex[:cut]
    old_header = r"\fancyhead[L]{\small\itshape \reporttitle}"
    if old_header not in head:
        raise ValueError("cabeçalho do relatório mensal fora do padrão do template")
    head = head.replace(old_header, r"\fancyhead[L]{\small\itshape \reporttitle{} --- Apêndice Estatístico}")
    head = head.replace(r"\onehalfspacing", r"\setstretch{1.2}")
    return re.sub(r"% =+\n% Template LaTeX.*?\n% =+\n\n", "", head, flags=re.S)  # drop the template's usage notes


def document(d: DadosApendice, report_tex: str, draft: bool = False) -> str:
    macros = report_macros(report_tex)
    if macros["mesref"] != mes(d.t1):
        raise ValueError(f"o relatório mensal trata de {macros['mesref']}, mas o IDC termina em {mes(d.t1)}")
    definitions = "\n".join(rf"\newcommand{{\{name}}}{{{macros[name]}}}" for name in MACROS)
    subtitle = r"Apêndice Estatístico --- Divulgação \mespublicacao; competência \mesreferencia"
    if draft:
        subtitle += r"\\[2pt]\normalsize\textit{Versão para discussão}"
    start = rf"""% =============================================================================
%   DADOS DO RELATÓRIO — Apêndice Estatístico do IDC
% =============================================================================
\usepackage{{amsmath}}
\usepackage{{adjustbox}}
\renewcommand{{\topfraction}}{{0.9}}
\renewcommand{{\bottomfraction}}{{0.8}}
\renewcommand{{\textfraction}}{{0.1}}
\renewcommand{{\floatpagefraction}}{{0.7}}
\setcounter{{topnumber}}{{3}}
\setcounter{{totalnumber}}{{4}}
\renewcommand{{\thetable}}{{A\arabic{{table}}}}
\renewcommand{{\thefigure}}{{A\arabic{{figure}}}}

{definitions}
\newcommand{{\reportsubtitle}}{{{subtitle}}}

\hypersetup{{
  pdftitle={{\reporttitle{{}} --- Apêndice Estatístico}},
  pdfauthor={{\authorone; \authortwo; \authorthree}},
  pdfsubject={{Apêndice Estatístico do IDC}},
  pdfkeywords={{crédito, endividamento, Brasil, BCB, FGV}}
}}

\begin{{document}}

\hypersetup{{pageanchor=false}}
\begin{{titlepage}}
  \noindent\hfill\includegraphics[width=79mm]{{logo.png}}

  \vspace{{18mm}}

  \begin{{center}}
    {{\LARGE\bfseries \reporttitle\par}}
    \vspace{{3mm}}
    {{\large\itshape \reportsubtitle\par}}
  \end{{center}}

  \vspace{{12mm}}

  \begin{{flushright}}
    \large
    \authorone\\[2pt]
    \authortwo\\[2pt]
    \authorthree
  \end{{flushright}}

  \vfill

  \begin{{center}}
    \reportdate
  \end{{center}}
\end{{titlepage}}
\hypersetup{{pageanchor=true}}
\thispagestyle{{firstpage}}

\tableofcontents
"""
    return preamble(report_tex) + start + montar_corpo(d) + "\n\\end{document}\n"


def compile_pdf(tex: Path) -> list[str]:
    """Compile with LuaLaTeX (three passes: references and table of contents) and return the problems found."""
    lualatex = shutil.which("lualatex") or LUALATEX_FALLBACK
    if not (shutil.which("lualatex") or Path(LUALATEX_FALLBACK).exists()):
        return ["lualatex não encontrado"]
    for _ in range(3):
        result = subprocess.run([lualatex, "-interaction=nonstopmode", tex.name], cwd=tex.parent, capture_output=True, text=True)
    log = tex.with_suffix(".log").read_text(errors="ignore")
    problems = [ln for ln in log.splitlines() if ln.startswith("!")][:5]
    problems += sorted(set(f"referência indefinida: {r}" for r in re.findall(r"Reference `([^']+)' on page", log)))
    overfull = [ln.strip() for ln in log.splitlines() if "Overfull \\hbox" in ln]
    if overfull:
        problems.append(f"{len(overfull)} aviso(s) Overfull \\hbox; inspecione o PDF")
    if result.returncode != 0 and not problems:
        problems.append(f"lualatex terminou com código {result.returncode}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera o apêndice estatístico do IDC (PDF) de uma divulgação do BCB.")
    parser.add_argument("period", help="competência da divulgação do BCB (AAAAMM)")
    parser.add_argument("--draft", action="store_true", help='marca a capa com "Versão para discussão"')
    parser.add_argument("--no-sgs-update", action="store_true", help="não consulta a API do SGS; usa data/processed/sgs_snapshot.csv")
    parser.add_argument("--no-pdf", action="store_true", help="só escreve o .tex")
    parser.add_argument("--ignore-vintage", action="store_true", help="aceita séries do SGS de safra diferente da planilha (só para testes)")
    args = parser.parse_args(argv)
    folder = Path(REPORT_DIR.format(period=args.period))
    report = folder / f"idc-update-{args.period}.tex"
    if not report.exists():
        print(f"Falha: relatório mensal ausente ({report}); gere a nota antes do apêndice.", file=sys.stderr)
        return 1
    try:
        d = load_data(args.period, update_sgs=not args.no_sgs_update, ignore_vintage=args.ignore_vintage)
    except NotBuilt as exc:
        print(f"Apêndice não gerado nesta edição: {exc}")
        return 3
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"Falha: {exc!r}", file=sys.stderr)
        return 1
    try:
        gerar_figuras(d, folder)
        logo = folder / "logo.png"
        missing = [p for p in [logo, *(folder / n for n in SHARED_FIGURES)] if not p.exists()]
        if missing:
            raise FileNotFoundError(f"arquivos ausentes em {folder}: {', '.join(p.name for p in missing)} (passo 5a do PIPELINE)")
        text = document(d, report.read_text(encoding="utf-8"), draft=args.draft)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Falha: {exc}", file=sys.stderr)
        return 1
    tex = folder / f"idc-apendice-{args.period}.tex"
    tex.write_text(text, encoding="utf-8")
    print(f"Escrito: {tex} ({len(FIGURAS)} figuras próprias + {len(SHARED_FIGURES)} do relatório)")
    if args.no_pdf:
        return 0
    problems = compile_pdf(tex)
    pdf = tex.with_suffix(".pdf")
    if problems:
        print("Problemas na compilação:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1 if not pdf.exists() or any(p.startswith(("!", "lualatex")) for p in problems) else 0
    print(f"PDF compilado: {pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
