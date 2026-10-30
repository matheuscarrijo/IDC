"""Low-income series drawn over the IDC figures of ``src/plot.py``.

The report figures keep their look (labels, events, fonts); when the low-income IDC is available,
``plot.py`` calls one of these functions on the finished figure right before saving it.  ``low`` is the
frame of ``src.low_income`` with the columns ``I`` and ``Q`` (percent), ``I_norm``, ``Q_norm`` and ``IDC``
for the group of borrowers with income of up to 2 minimum wages, indexed by month from jul-2012.
"""
from __future__ import annotations

import pandas as pd
from matplotlib.lines import Line2D

from src.income_idc import primeira_exibicao

COLOR = "#C00000"
LABEL = "IDC baixa renda (até 2 SM)"
FOOTNOTE = "Linhas tracejadas: baixa renda (até 2 SM, incluindo sem rendimento), SCR.data"


def _label(ax, x, y, text, dx=6, dy=0, ha="left", va="center", color=COLOR) -> None:
    ax.annotate(text, xy=(x, y), xytext=(dx, dy), textcoords="offset points", fontsize=9, color=color,
                ha=ha, va=va, zorder=7)


def index(fig, low: pd.DataFrame, start: pd.Timestamp | None = None) -> None:
    """``index.png``: the low-income IDC line next to the headline IDC, from the end of its warm-up."""
    ax = fig.axes[0]
    series = low["IDC"].loc[start or primeira_exibicao():].dropna()
    ax.get_lines()[0].set_label("IDC geral")
    ax.plot(series.index, series.values, color=COLOR, linewidth=2.0, label=LABEL, zorder=4)
    ax.plot(series.index[[0, -1]], series.iloc[[0, -1]], "o", color=COLOR, markersize=4, zorder=6)
    _label(ax, series.index[0], series.iloc[0], f"{series.iloc[0]:.2f}", dx=-7, dy=-3, ha="right", va="top")
    _label(ax, series.index[-1], series.iloc[-1], f"{series.iloc[-1]:.2f}", dx=8, dy=0)
    ax.legend(loc="upper left")


def _dashed(ax, series: pd.Series, color: str = COLOR, label: str | None = None, end_decimals: int = 1, end_right: bool = False, end_dy: float = 0) -> Line2D:
    (line,) = ax.plot(series.index, series.values, color=color, linewidth=1.7, linestyle="--", zorder=3, label=label)
    low_y, high_y = ax.get_ylim()
    spread = series.max() - series.min()
    ax.set_ylim(min(low_y, series.min() - 0.05 * spread), max(high_y, series.max() + 0.24 * spread))
    ax.plot(series.index[-1], series.iloc[-1], "o", color=color, markersize=4, zorder=6)
    if end_right:
        _label(ax, series.index[-1], series.iloc[-1], f"{series.iloc[-1]:.{end_decimals}f}", dx=8, dy=end_dy, color=color)
    else:
        _label(ax, series.index[-1], series.iloc[-1], f"{series.iloc[-1]:.{end_decimals}f}", dx=0, dy=7, ha="center", va="bottom", color=color)
    return line


def components_raw(fig, low: pd.DataFrame) -> None:
    """``components_raw.png``: dashed low-income lines in the I and Q panels."""
    _dashed(fig.axes[1], low["I"].dropna(), end_right=True)
    _dashed(fig.axes[2], low["Q"].dropna(), end_right=True, end_dy=7)  # clear of the end labels of the total
    # in the gap between the figure title and the first panel, so that the figure keeps its height
    fig.legend(handles=[Line2D([0], [0], color=COLOR, linewidth=1.7, linestyle="--")], labels=[FOOTNOTE],
               loc="upper center", bbox_to_anchor=(0.5, 0.972), fontsize=9, frameon=False)


def component_single(fig, comp: str, low: pd.DataFrame) -> None:
    """``components_raw_i.png`` and ``components_raw_q.png``: one dashed low-income line and a legend."""
    ax = fig.axes[0]
    general = ax.get_lines()[0]
    dashed = _dashed(ax, low[comp].dropna(), label="Baixa renda (até 2 SM, SCR.data)", end_right=True)
    general.set_label("Total (SGS)")
    ax.legend(handles=[general, dashed], loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, fontsize=8.5, frameon=False)


def normalized(fig, low: pd.DataFrame, colors: dict[str, str]) -> None:
    """``components_normalized.png``: dashed I and Q positions of the low-income group in the component colors."""
    ax = fig.axes[0]
    for comp in ("I", "Q"):
        serie = low[f"{comp}_norm"].loc[primeira_exibicao():].dropna()  # the warm-up of the group's window is not shown
        ax.plot(serie.index, serie.values, color=colors[comp], linewidth=1.5, linestyle="--", label=f"{comp} — baixa renda", zorder=3)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3, frameon=False)
