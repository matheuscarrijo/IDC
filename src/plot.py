from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

FIGURES_DIR = Path("outputs/figures")

KEY_EVENTS = {
    "Pandemia\nCOVID-19": pd.Timestamp("2020-03-01"),
    "Programa\nDesenrola": pd.Timestamp("2023-06-01"),
}

NORM_LABELS = {
    "minmax":     "Min-Max",
    "robust":     "Min-Max Robusto (Q10/Q90)",
    "percentile": "Rank Percentil",
}

NORM_COLORS = {
    "minmax":     "#1f77b4",
    "robust":     "#d62728",
    "percentile": "#2ca02c",
}

COMP_LABELS = {
    "C": "Comprometimento de Renda",
    "I": "Inadimplência (90+ dias)",
    "Q": "Qualidade do Crédito",
}

COMP_COLORS = {
    "C": "#1f77b4",
    "I": "#d62728",
    "Q": "#9467bd",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def _style_ax(ax, ylabel: str = None, ylim: tuple = None) -> None:
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(axis="x", labelsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(True, axis="y", alpha=0.3, linestyle="--", linewidth=0.7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9)
    if ylim:
        ax.set_ylim(*ylim)


def _add_events(ax) -> None:
    for label, date in KEY_EVENTS.items():
        ax.axvline(date, color="grey", linestyle="--", linewidth=0.9, alpha=0.6)
        ax.text(
            date, 0.97, label,
            transform=ax.get_xaxis_transform(),
            fontsize=6.5, color="#555555",
            ha="center", va="top", linespacing=1.3,
        )


# ── figures ───────────────────────────────────────────────────────────────────

def plot_index_comparison(index_df: pd.DataFrame) -> None:
    """Figure 01 — three index versions overlaid."""
    fig, ax = plt.subplots(figsize=(12, 5))

    for method, label in NORM_LABELS.items():
        ax.plot(
            index_df.index, index_df[f"index_{method}"],
            label=label, color=NORM_COLORS[method], linewidth=1.8,
        )

    _style_ax(ax, ylabel="Índice [0 – 1]", ylim=(0, 1.05))
    _add_events(ax)
    ax.legend(loc="upper left", framealpha=0.9, fontsize=9, edgecolor="#cccccc")
    ax.set_title(
        "Índice de Desconforto Financeiro — Comparação entre Normalizações",
        fontsize=12, fontweight="bold", pad=12,
    )

    fig.tight_layout()
    _save(fig, "01_index_comparison.png")


def plot_components_raw(components: pd.DataFrame) -> None:
    """Figure 02 — raw (unnormalized) components."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

    configs = [
        ("C", components["C"],         "% da renda"),
        ("I", components["I"],         "%"),
        ("Q", components["Q"] * 100,   "%"),
    ]

    for ax, (comp, series, unit) in zip(axes, configs):
        ax.plot(series.index, series.values, color=COMP_COLORS[comp], linewidth=1.5)
        _style_ax(ax, ylabel=unit)
        _add_events(ax)
        ax.set_title(COMP_LABELS[comp], fontsize=10, fontweight="bold")

    fig.suptitle(
        "Componentes do Índice — Valores Brutos (não normalizados)",
        fontsize=12, fontweight="bold", y=1.01,
    )
    fig.tight_layout()
    _save(fig, "02_components_raw.png")


def _plot_components_normalized(index_df: pd.DataFrame, method: str, fig_num: int) -> None:
    """Figures 03–05 — normalized components for a single method."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=True)

    for ax, comp in zip(axes, ["C", "I", "Q"]):
        ax.plot(
            index_df.index, index_df[f"{comp}_{method}"],
            color=COMP_COLORS[comp], linewidth=1.5,
        )
        _style_ax(
            ax,
            ylabel="[0 – 1]" if comp == "C" else None,
            ylim=(-0.02, 1.05),
        )
        _add_events(ax)
        ax.set_title(COMP_LABELS[comp], fontsize=10, fontweight="bold")

    fig.suptitle(
        f"Componentes Normalizados — {NORM_LABELS[method]}",
        fontsize=12, fontweight="bold", y=1.01,
    )
    fig.tight_layout()
    _save(fig, f"0{fig_num}_components_{method}.png")


def _plot_index_single(index_df: pd.DataFrame, method: str, fig_num: int) -> None:
    """Figures 06–08 — one index version shown individually."""
    label = NORM_LABELS[method]
    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(
        index_df.index, index_df[f"index_{method}"],
        color=NORM_COLORS[method], linewidth=1.8,
    )

    _style_ax(ax, ylabel="Índice [0 – 1]", ylim=(0, 1.05))
    _add_events(ax)
    ax.set_title(
        f"Índice de Desconforto Financeiro — {label}",
        fontsize=12, fontweight="bold", pad=12,
    )

    fig.tight_layout()
    _save(fig, f"0{fig_num}_index_{method}.png")


def _save(fig, filename: str) -> None:
    path = FIGURES_DIR / filename
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  {filename}")


# ── entry point ───────────────────────────────────────────────────────────────

def plot_all(components: pd.DataFrame, index_df: pd.DataFrame) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans"})

    print("Salvando figuras em outputs/figures/:")
    plot_index_comparison(index_df)
    plot_components_raw(components)
    for fig_num, method in enumerate(["minmax", "robust", "percentile"], start=3):
        _plot_components_normalized(index_df, method, fig_num)
    for fig_num, method in enumerate(["minmax", "robust", "percentile"], start=6):
        _plot_index_single(index_df, method, fig_num)
