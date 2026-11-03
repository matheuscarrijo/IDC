"""Low-income series drawn over the IDC figures of ``src/plot.py``.

The report figures keep their look (labels, events, fonts); when the low-income IDC is available,
``plot.py`` calls one of these functions on the finished figure right before saving it (the index figures draw the
low-income line themselves, with the label and color defined here).  ``low`` is the
frame of ``src.low_income`` with the columns ``I`` and ``Q`` (percent), ``I_norm``, ``Q_norm`` and ``IDC``
for the group of borrowers with income of up to 2 minimum wages, indexed by month from jul-2012.
"""
from __future__ import annotations

import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.text import Text

from src.income_idc import primeira_exibicao

COLOR = "#C00000"
LABEL = "IDC Baixa Renda (até 2 SM)"
FOOTNOTE = "Linhas tracejadas: baixa renda (até 2 SM, incluindo sem rendimento), SCR.data"


def _label(ax, x, y, text, dx=6, dy=0, ha="left", va="center", color=COLOR) -> None:
    ax.annotate(text, xy=(x, y), xytext=(dx, dy), textcoords="offset points", fontsize=9, color=color,
                ha=ha, va=va, zorder=7)


def _keep_event_labels(ax, old_ylim: tuple[float, float]) -> None:
    """Keep the event labels placed in y data units at the same pixel distance below the total series.

    ``plot.py`` chooses their height for the range of the total series; a wider range squeezes the total series
    against them and the value labels of its end would cover the text.
    """
    low, high = ax.get_ylim()
    scale = (high - low) / (old_ylim[1] - old_ylim[0])
    if abs(scale - 1) < 1e-9:
        return
    total = ax.get_lines()[0]
    xs = mdates.date2num(np.asarray(total.get_xdata(), dtype="datetime64[ns]"))
    ys = np.asarray(total.get_ydata(), dtype=float)
    for text in ax.texts:
        if type(text) is not Text or text.get_transform() is not ax.transData:  # value labels are Annotations
            continue
        x, y_old = text.convert_xunits(text.get_position()[0]), text.get_position()[1]
        y_ref = float(np.interp(x, xs, ys))
        text.set_y(max(y_ref - (y_ref - y_old) * scale, low + 0.10 * (high - low)))


def _dashed(ax, series: pd.Series, color: str = COLOR, label: str | None = None, end_decimals: int = 1, end_right: bool = False,
            end_dy: float = 0, end_label: bool = True) -> Line2D:
    (line,) = ax.plot(series.index, series.values, color=color, linewidth=1.7, linestyle="--", zorder=3, label=label)
    low_y, high_y = ax.get_ylim()
    spread = series.max() - series.min()
    ax.set_ylim(min(low_y, series.min() - 0.05 * spread), max(high_y, series.max() + 0.24 * spread))
    _keep_event_labels(ax, (low_y, high_y))
    ax.plot(series.index[-1], series.iloc[-1], "o", color=color, markersize=4, zorder=6)
    if not end_label:  # the caller labels the last month itself
        return line
    if end_right:
        _label(ax, series.index[-1], series.iloc[-1], f"{series.iloc[-1]:.{end_decimals}f}".replace(".", ","), dx=8, dy=end_dy, color=color)
    else:
        _label(ax, series.index[-1], series.iloc[-1], f"{series.iloc[-1]:.{end_decimals}f}".replace(".", ","), dx=0, dy=7, ha="center", va="bottom", color=color)
    return line


SINGLE_LABEL = "Baixa renda (até 2 SM, SCR.data)"


def components_legend(fig) -> None:
    """``components_raw.png``: the note on the dashed low-income lines of the I and Q panels.

    It sits in the gap between the figure title and the first panel, so that the figure keeps its height.
    """
    fig.legend(handles=[Line2D([0], [0], color=COLOR, linewidth=1.7, linestyle="--")], labels=[FOOTNOTE],
               loc="upper center", bbox_to_anchor=(0.5, 0.972), fontsize=9, frameon=False)


def component_legend(ax, dashed: Line2D) -> None:
    """``components_raw_i.png`` and ``components_raw_q.png``: legend of the total and of the dashed low-income line."""
    general = ax.get_lines()[0]
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
