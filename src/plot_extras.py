"""Figures for the "anatomia do mês" and the lenses, in the style of ``src/plot.py``.

The new figures reuse the style helpers of ``src/plot.py`` (``_apply_excel_style``, ``_style_ax``,
``_add_events``) so that they match the charts of the monthly report.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.lenses import FAIXAS_INDICE  # noqa: E402
from src.plot import KEY_EVENTS, _add_events, _apply_excel_style, _style_ax  # noqa: E402

FIG_W = 6.5
DPI = 200
GRUPO_CORES = {
    "Cartão rotativo e parcelado": "#ED7D31",
    "Pessoal não consignado": "#4472C4",
    "Consignado": "#70AD47",
    "Veículos": "#7F7F7F",
    "Cheque especial": "#FFC000",
    "Cartão à vista e lojista": "#9DC3E6",
    "Demais": "#BFBFBF",
}
FAIXA_CORES = {"Até 2 SM": "#C00000", "2 a 5 SM": "#ED7D31", "5 a 10 SM": "#70AD47", "Mais de 10 SM": "#264478"}
PT_MES = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
          7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}


def _save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def _pt(x: float, nd: int = 2, sinal: bool = False) -> str:
    texto = f"{x:+.{nd}f}" if sinal else f"{x:.{nd}f}"
    return texto.replace(".", ",")


def fig_atribuicao_mensal_I(contribuicoes: pd.DataFrame, oficial: pd.Series, path: Path) -> None:
    """Stacked monthly contributions of each product group to the change in I."""
    _apply_excel_style()
    fig, ax = plt.subplots(figsize=(FIG_W, 5.4))
    x = np.arange(len(contribuicoes))
    base_pos, base_neg = np.zeros(len(x)), np.zeros(len(x))
    for grupo, cor in GRUPO_CORES.items():
        v = contribuicoes[grupo].values
        ax.bar(x, np.where(v > 0, v, 0), bottom=base_pos, color=cor, width=0.75, label=grupo, linewidth=0)
        ax.bar(x, np.where(v < 0, v, 0), bottom=base_neg, color=cor, width=0.75, linewidth=0)
        base_pos += np.where(v > 0, v, 0)
        base_neg += np.where(v < 0, v, 0)
    ax.plot(x, oficial.values, color="black", marker="o", markersize=3.5, linewidth=1.2,
            label="Variação oficial de I (SGS 21112)", zorder=5)
    ax.axhline(0, color="#404040", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{PT_MES[d.month]}-{d.year}" for d in contribuicoes.index], rotation=90, fontsize=8.5)
    _style_ax(ax, ylabel="p.p. (variação mensal)")
    ax.xaxis.set_major_locator(plt.FixedLocator(x))
    ax.xaxis.set_major_formatter(plt.FixedFormatter([f"{PT_MES[d.month]}-{d.year}" for d in contribuicoes.index]))
    ax.tick_params(axis="x", labelrotation=90, labelsize=8.5)
    ax.set_ylim(min(-0.45, base_neg.min() - 0.05), max(1.0, base_pos.max() + 0.05) + 0.2)
    ax.legend(loc="upper left", fontsize=8.5, ncol=2)
    ax.set_title("Contribuição de cada produto à variação mensal da inadimplência (I)", fontsize=11.5)
    fig.tight_layout()
    _save(fig, path)


def _separar_rotulos(valores: dict[str, float], minimo: float = 0.032) -> dict[str, float]:
    """Vertical positions for end-of-line labels with a minimum gap (simple repel)."""
    ordem = sorted(valores, key=valores.get)
    pos = {k: valores[k] for k in ordem}
    for _ in range(50):
        mudou = False
        for a, b_ in zip(ordem, ordem[1:]):
            gap = pos[b_] - pos[a]
            if gap < minimo:
                ajuste = (minimo - gap) / 2
                pos[a] -= ajuste
                pos[b_] += ajuste
                mudou = True
        if not mudou:
            break
    return pos


def fig_idc_por_faixa(idc: pd.DataFrame, headline: pd.Series, path: Path) -> None:
    """IDC by income bracket (national C) against the headline IDC."""
    _apply_excel_style()
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_W))
    inicio = idc.dropna(how="all").index.min()
    finais, cores = {}, {}
    for faixa in FAIXAS_INDICE:
        serie = idc[(faixa, "IDC")].dropna()
        ax.plot(serie.index, serie.values, color=FAIXA_CORES[faixa], linewidth=1.9, label=faixa)
        finais[faixa], cores[faixa] = float(serie.iloc[-1]), FAIXA_CORES[faixa]
    h = headline.loc[inicio:].dropna()
    ax.plot(h.index, h.values, color="black", linestyle="--", linewidth=1.4, label="IDC (todas as faixas)")
    finais["IDC"], cores["IDC"] = float(h.iloc[-1]), "black"
    x_fim = idc.index.max()
    posicoes = _separar_rotulos(finais)
    for nome, y in posicoes.items():
        ax.annotate(_pt(finais[nome], 3), xy=(x_fim, finais[nome]), xytext=(x_fim + pd.DateOffset(months=3), y), fontsize=8.5,
                    color=cores[nome], va="center", ha="left",
                    arrowprops=dict(arrowstyle="-", color=cores[nome], lw=0.6, shrinkA=0, shrinkB=0))
    _style_ax(ax, ylabel="Índice [0 – 1]", ylim=(0, 1.05))
    ax.set_xlim(inicio, x_fim + pd.DateOffset(months=16))
    _add_events(ax, label_positions={k: {"coords": "data", "y": 0.04, "ha": "center", "va": "center"}
                                     for k in ("Pandemia\nCOVID-19", "Programa\nDesenrola", "Novo\nDesenrola")},
                events={k: v for k, v in KEY_EVENTS.items() if v >= inicio})
    ax.legend(loc="upper center", fontsize=9, ncol=3, bbox_to_anchor=(0.5, -0.07))
    ax.set_title("IDC por faixa de renda — C nacional, I e Q de cada faixa", fontsize=11.5)
    fig.tight_layout()
    _save(fig, path)


def fig_lentes(decomps: dict[str, pd.DataFrame], residuos: dict[str, float], path: Path,
               titulo: str = "Contribuição à alta de I em 12 meses (p.p.)") -> None:
    """Horizontal bars of the 12-month contributions for several lenses."""
    _apply_excel_style()
    nomes = list(decomps)
    alturas = [max(len(t), 3) for t in decomps.values()]
    fig, axes = plt.subplots(len(nomes), 1, figsize=(FIG_W, 1.25 + 0.34 * sum(alturas)),
                             gridspec_kw={"height_ratios": alturas}, sharex=True)
    axes = np.atleast_1d(axes)
    limite = max(abs(t["contribuicao"]).max() for t in decomps.values()) * 1.25
    for ax, nome in zip(axes, nomes):
        t = decomps[nome].sort_values("contribuicao")
        cores = ["#C00000" if v > 0 else "#4472C4" for v in t["contribuicao"]]
        y = np.arange(len(t))
        ax.barh(y, t["contribuicao"], color=cores, height=0.65)
        ax.set_yticks(y)
        ax.set_yticklabels(t.index, fontsize=8.8)
        for yi, (v, w) in enumerate(zip(t["contribuicao"], t["peso_t1"])):
            ax.text(max(v, 0) + 0.012 * limite, yi, f"{_pt(v, 2, True)}  ({_pt(w, 0) if w >= 1 else _pt(w, 1)}% da carteira)",
                    va="center", ha="left", fontsize=7.8, color="#404040")
        ax.axvline(0, color="#404040", linewidth=0.8)
        ax.set_title(f"{nome}", fontsize=10, loc="left", fontweight="bold")
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        ax.xaxis.grid(True, color="#D9D9D9", linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
        ax.set_xlim(-limite * 0.35, limite * 1.9)
    axes[-1].set_xlabel("p.p. (contribuição à variação de I em 12 meses)", fontsize=9)
    fig.suptitle(titulo, fontsize=11.5, fontweight="bold", x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    _save(fig, path)


def fig_uf(tabela_uf: pd.DataFrame, path: Path) -> None:
    """Dumbbell chart: I by state at t-12 and t, sorted by the latest value."""
    _apply_excel_style()
    t = tabela_uf.sort_values("x_t1")
    fig, ax = plt.subplots(figsize=(FIG_W, 7.4))
    y = np.arange(len(t))
    ax.hlines(y, t["x_t0"], t["x_t1"], color="#BFBFBF", linewidth=2.2, zorder=1)
    ax.scatter(t["x_t0"], y, color="#7F7F7F", s=22, zorder=3, label="12 meses antes")
    ax.scatter(t["x_t1"], y, color="#C00000", s=28, zorder=4, label="Mês de referência")
    ax.set_yticks(y)
    ax.set_yticklabels(t.index, fontsize=9)
    for yi, (a, b) in enumerate(zip(t["x_t0"], t["x_t1"])):
        ax.text(b + 0.12, yi, f"{_pt(b, 1)}%  ({_pt(b - a, 1, True)} p.p.)", va="center", fontsize=7.8, color="#404040")
    ax.xaxis.grid(True, color="#D9D9D9", linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.set_xlabel("Inadimplência 90+ dias no crédito livre PF (%)")
    ax.set_xlim(t["x_t0"].min() - 0.6, t["x_t1"].max() + 2.2)
    ax.tick_params(axis="y", length=0)
    ax.legend(loc="lower right", fontsize=9)
    ax.set_title("Inadimplência por unidade da federação", fontsize=11.5, fontweight="bold", loc="left")
    fig.tight_layout()
    _save(fig, path)
