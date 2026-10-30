"""Portuguese number formatting and LaTeX helpers matching the IDC report style.

Report conventions (see ``PIPELINE.md``): decimal comma, ``p.p.`` with a tilde
space, bold only around numbers, percentages, deltas and month-year labels.
"""
from __future__ import annotations

import math

import pandas as pd

_MES = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
        7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}


def mes(t: pd.Timestamp) -> str:
    """Abbreviated month-year, e.g. ``jul-2026``."""
    return f"{_MES[t.month]}-{t.year}"


def num(x: float, nd: int = 2, sinal: bool = False) -> str:
    """Decimal comma; optional explicit sign (hyphen-minus, as in the reports)."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "---"
    texto = f"{x:+.{nd}f}" if sinal else f"{x:.{nd}f}"
    if sinal and float(texto) == 0:
        texto = f"{0:.{nd}f}"  # avoid "+0,00" / "-0,00"
    return texto.replace(".", ",")


def pct(x: float, nd: int = 1) -> str:
    return num(x, nd) + r"\%"


def pp(x: float, nd: int = 2, sinal: bool = True) -> str:
    return num(x, nd, sinal) + "~p.p."


def b(texto: str) -> str:
    """Bold, reserved for numbers, deltas and month-year labels."""
    return r"\textbf{" + texto + "}"


def bn(x: float, nd: int = 2, sinal: bool = False) -> str:
    return b(num(x, nd, sinal))


def bpct(x: float, nd: int = 1) -> str:
    return b(pct(x, nd))


def bpp(x: float, nd: int = 2, sinal: bool = True) -> str:
    return b(pp(x, nd, sinal))


def bpct_s(x: float, nd: int = 1) -> str:
    """Bold signed percentage, e.g. \\textbf{+38,5\\%}."""
    return b(num(x, nd, True) + r"\%")


def bmes(t: pd.Timestamp) -> str:
    return b(mes(t))


def latex_escape(texto: str) -> str:
    return (texto.replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")
            .replace("≤", r"$\leq$").replace(">", r"$>$"))


def tabela_latex(titulo: str, rotulo: str, cabecalho: list[str], linhas: list[list[str]], colunas: str,
                 fonte: str, tamanho: str = r"\small", negrito_linhas: tuple[int, ...] = (),
                 separadores: tuple[int, ...] = (), posicao: str = "htbp", tabcolsep: str = "3pt") -> str:
    """Booktabs table in the style of the report, with its source note."""
    corpo = []
    for i, linha in enumerate(linhas):
        texto = " & ".join(linha) + r" \\"
        corpo.append("    " + texto)
        if i in separadores:
            corpo.append(r"    \midrule")
    return "\n".join([
        f"\\begin{{table}}[{posicao}]",
        r"  \centering",
        f"  {tamanho}",
        f"  \\setlength{{\\tabcolsep}}{{{tabcolsep}}}",
        f"  \\caption{{{titulo}}}",
        f"  \\label{{{rotulo}}}",
        f"  \\begin{{tabular}}{{{colunas}}}",
        r"    \toprule",
        "    " + " & ".join(cabecalho) + r" \\",
        r"    \midrule",
        *corpo,
        r"    \bottomrule",
        r"  \end{tabular}",
        r"\end{table}",
        "",
        f"\\fonte{{{fonte}}}",
        "",
    ])
