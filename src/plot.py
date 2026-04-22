from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

FIGURES_DIR = Path("outputs/figures")

KEY_EVENTS = {
    "Pandemia\nCOVID-19": pd.Timestamp("2020-03-01"),
    "Programa\nDesenrola": pd.Timestamp("2023-06-01"),
}

COMP_LABELS = {
    "C": "Comprometimento de Renda",
    "I": "Inadimplência (90+ dias)",
    "Q": "Qualidade do Crédito",
}

# Excel default Office color palette
COMP_COLORS = {
    "C": "#4472C4",
    "I": "#ED7D31",
    "Q": "#70AD47",
}

INDEX_COLOR = "#4472C4"

# Target display width in a Word/A4 document: ~6.5 inches (≈16.5 cm).
# Figures generated at this width at DPI=200 embed without scaling,
# so fonts and line widths appear exactly as specified.
_FIG_W  = 6.5   # inches — single-panel width
_FIG_H  = 4.0   # inches — single-panel height
_DPI    = 200


def _apply_excel_style() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Calibri", "Arial", "Helvetica Neue", "Helvetica", "DejaVu Sans"],
        "font.size": 11,

        "figure.facecolor": "white",
        "figure.edgecolor": "white",
        "figure.dpi": _DPI,

        "axes.facecolor": "white",
        "axes.edgecolor": "#808080",
        "axes.linewidth": 0.8,
        "axes.grid": False,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlepad": 8,
        "axes.labelsize": 11,
        "axes.labelcolor": "#404040",

        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "xtick.color": "#404040",
        "ytick.color": "#404040",
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 4,
        "ytick.major.size": 0,   # gridlines replace y-tick marks
        "xtick.major.width": 0.8,

        "lines.linewidth": 2.0,

        "legend.fontsize": 10,
        "legend.framealpha": 1.0,
        "legend.edgecolor": "#808080",
        "legend.frameon": True,

        "savefig.facecolor": "white",
        "savefig.edgecolor": "white",
        "savefig.bbox": "tight",
    })


def _style_ax(ax, xlabel: str = "Data", ylabel: str = None, ylim: tuple = None) -> None:
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("#808080")
        spine.set_linewidth(0.8)

    ax.yaxis.grid(True, color="#D9D9D9", linewidth=0.8, linestyle="-")
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)

    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(axis="y", length=0)

    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    if ylim:
        ax.set_ylim(*ylim)


def _add_events(ax, show_labels: bool = True) -> None:
    for label, date in KEY_EVENTS.items():
        ax.axvline(date, color="#BBBBBB", linestyle="--", linewidth=0.9, zorder=1)
        if show_labels:
            ax.text(
                date, 0.97, label,
                transform=ax.get_xaxis_transform(),
                fontsize=8, color="#555555",
                ha="center", va="top", linespacing=1.2,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=1.5),
                zorder=5,
            )


def _save(fig, filename: str) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / filename
    fig.savefig(path, dpi=_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  {filename}")


def _rebase100(s: pd.Series) -> pd.Series:
    first_valid = s.dropna().iloc[0]
    return (s / first_valid) * 100


def _plot_components_raw(components: pd.DataFrame) -> None:
    """Three stacked panels (shared x-axis) — fits A4 page width."""
    fig, axes = plt.subplots(3, 1, figsize=(_FIG_W, 8.0), sharex=True)
    fig.subplots_adjust(hspace=0.4)

    configs = [
        ("C", components["C"],       "% da renda"),
        ("I", components["I"],       "%"),
        ("Q", components["Q"] * 100, "%"),
    ]

    for i, (ax, (comp, series, unit)) in enumerate(zip(axes, configs)):
        ax.plot(series.index, series.values, color=COMP_COLORS[comp])
        _style_ax(ax, xlabel=None, ylabel=unit)
        ax.set_title(COMP_LABELS[comp])
        _add_events(ax, show_labels=(i == 0))

    axes[-1].set_xlabel("Data")

    fig.suptitle(
        "Componentes do Índice — Valores Brutos (não normalizados)",
        fontsize=14, fontweight="bold", y=1.01,
    )
    _save(fig, "components_raw.png")


def _plot_components_base100(components: pd.DataFrame) -> None:
    START = "2014-01"
    components = components.loc[START:]

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H))

    for comp in ["C", "I", "Q"]:
        rebased = _rebase100(components[comp])
        ax.plot(rebased.index, rebased.values, label=COMP_LABELS[comp], color=COMP_COLORS[comp])

    ax.axhline(100, color="#808080", linestyle="--", linewidth=0.8)
    base_date = components.index[0].strftime("%b-%Y")
    _style_ax(ax, ylabel=f"Base 100 = {base_date}")
    _add_events(ax)
    ax.legend(loc="upper left")
    ax.set_title(f"Componentes do Índice — Evolução Base 100 ({base_date})")

    fig.tight_layout()
    _save(fig, "components_base100.png")


def _plot_components_normalized(index_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H))

    for comp in ["C", "I", "Q"]:
        ax.plot(
            index_df.index, index_df[f"{comp}_norm"],
            label=COMP_LABELS[comp], color=COMP_COLORS[comp],
        )

    _style_ax(ax, ylabel="[0 – 1]", ylim=(-0.02, 1.05))
    _add_events(ax)
    ax.legend(loc="upper left")
    ax.set_title("Componentes Normalizados — Min-Max — Janela Expansiva")

    fig.tight_layout()
    _save(fig, "components_normalized.png")


def _plot_components_normalized_base100(index_df: pd.DataFrame) -> None:
    START = "2014-01"
    df = index_df.loc[START:]

    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H))

    for comp in ["C", "I", "Q"]:
        rebased = _rebase100(df[f"{comp}_norm"])
        ax.plot(rebased.index, rebased.values, label=COMP_LABELS[comp], color=COMP_COLORS[comp])

    ax.axhline(100, color="#808080", linestyle="--", linewidth=0.8)
    base_date = df["C_norm"].dropna().index[0].strftime("%b-%Y")
    _style_ax(ax, ylabel=f"Base 100 = {base_date}")
    _add_events(ax)
    ax.legend(loc="upper left")
    ax.set_title(f"Componentes Normalizados — Evolução Base 100 ({base_date})")

    fig.tight_layout()
    _save(fig, "components_normalized_base100.png")


def _plot_index(index_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H))

    ax.plot(
        index_df.index, index_df["index"],
        color=INDEX_COLOR,
        label="Índice de Desconforto de Crédito",
    )

    _style_ax(ax, ylabel="Índice [0 – 1]", ylim=(0, 1.05))
    _add_events(ax)
    ax.legend(loc="upper left")
    ax.set_title("Índice de Desconforto de Crédito — Min-Max — Janela Expansiva")

    fig.tight_layout()
    _save(fig, "index.png")


def _plot_index_base100(index_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H))

    rebased = _rebase100(index_df["index"])
    ax.plot(
        rebased.index, rebased.values,
        color=INDEX_COLOR,
        label="Índice de Desconforto de Crédito",
    )

    ax.axhline(100, color="#808080", linestyle="--", linewidth=0.8)
    base_date = index_df["index"].dropna().index[0].strftime("%b-%Y")
    _style_ax(ax, ylabel=f"Base 100 = {base_date}")
    _add_events(ax)
    ax.legend(loc="upper left")
    ax.set_title(f"Índice de Desconforto de Crédito — Base 100 ({base_date})")

    fig.tight_layout()
    _save(fig, "index_base100.png")


def plot_all(components: pd.DataFrame, index_df: pd.DataFrame) -> None:
    _apply_excel_style()
    print("Salvando figuras em outputs/figures/:")
    _plot_components_raw(components)
    _plot_components_base100(components)
    _plot_components_normalized(index_df)
    _plot_components_normalized_base100(index_df)
    _plot_index(index_df)
    _plot_index_base100(index_df)
