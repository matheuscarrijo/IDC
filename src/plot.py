from itertools import combinations
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
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
_LABEL_STYLE = dict(facecolor="white", edgecolor="none", alpha=0.85, pad=1.5)
_LABEL_CANDIDATES = {
    "start": [
        (12, 12, "left", "bottom"),
        (12, -12, "left", "top"),
        (20, 0, "left", "center"),
        (22, 12, "left", "bottom"),
        (22, -12, "left", "top"),
        (32, 14, "left", "bottom"),
        (32, -14, "left", "top"),
    ],
    "end": [
        (-12, 12, "right", "bottom"),
        (-12, -12, "right", "top"),
        (0, -18, "center", "top"),
        (-20, 0, "right", "center"),
        (-22, 12, "right", "bottom"),
        (-22, -12, "right", "top"),
        (-24, -22, "right", "top"),
        (-32, 14, "right", "bottom"),
        (-32, -14, "right", "top"),
        (-40, -20, "right", "top"),
        (-42, 0, "right", "center"),
        (-52, -10, "right", "top"),
    ],
    "end_near_max": [
        # Upward — use ylim headroom when the max label is placed to the left.
        (-10, 8, "right", "bottom"),
        (-14, 12, "right", "bottom"),
        (0, 8, "center", "bottom"),
        (-20, 14, "right", "bottom"),
        (-18, 18, "right", "bottom"),
        # Downward fallbacks (kept for cases with no headroom).
        (0, -20, "center", "top"),
        (-18, -18, "right", "top"),
        (0, -26, "center", "top"),
        (-20, -22, "right", "top"),
        (-34, -18, "right", "top"),
        (-20, -34, "right", "top"),
        (-44, -10, "right", "top"),
        (-54, -18, "right", "top"),
    ],
    "max": [
        (0, -12, "center", "top"),
        (-12, -12, "right", "top"),
        (12, -12, "left", "top"),
        (0, 12, "center", "bottom"),
        (0, -22, "center", "top"),
        (-16, 0, "right", "center"),
        (16, 0, "left", "center"),
        (-28, -16, "right", "top"),
        (28, -16, "left", "top"),
        (-36, -22, "right", "top"),
        (-28, 12, "right", "bottom"),
        (28, 12, "left", "bottom"),
    ],
    "max_near_end": [
        (-24, -12, "right", "top"),
        (-36, -12, "right", "top"),
        (-26, 0, "right", "center"),
        (-40, 0, "right", "center"),
        (-18, 18, "right", "bottom"),
        (-30, 18, "right", "bottom"),
        (-18, 28, "right", "bottom"),
        (-36, 26, "right", "bottom"),
        (0, 22, "center", "bottom"),
        (-12, 34, "right", "bottom"),
    ],
    "max_near_end_left": [
        (-22, 0, "right", "center"),
        (-28, 0, "right", "center"),
        (-22, 8, "right", "bottom"),
        (-22, -8, "right", "top"),
        (-28, 10, "right", "bottom"),
        (-36, -10, "right", "top"),
        (-36, 10, "right", "bottom"),
        (-46, -12, "right", "top"),
        (-46, 12, "right", "bottom"),
        (-58, 0, "right", "center"),
    ],
    "event": [
        (12, -12, "left", "top"),
        (-12, -12, "right", "top"),
        (12, 12, "left", "bottom"),
        (-12, 12, "right", "bottom"),
        (18, 0, "left", "center"),
        (-18, 0, "right", "center"),
        (28, -14, "left", "top"),
        (-28, -14, "right", "top"),
        (28, 12, "left", "bottom"),
        (-28, 12, "right", "bottom"),
    ],
}
_MONTHS_CLOSE_TO_END = 6


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


def _add_events(ax, show_labels: bool = True, label_positions: Optional[dict] = None) -> list:
    event_texts = []
    for label, date in KEY_EVENTS.items():
        ax.axvline(date, color="#BBBBBB", linestyle="--", linewidth=0.9, zorder=1)
        if show_labels:
            pos = (label_positions or {}).get(label, {})
            if pos.get("coords") == "data":
                event_texts.append(ax.text(
                    date,
                    pos["y"],
                    label,
                    transform=ax.transData,
                    fontsize=8,
                    color="#555555",
                    ha=pos.get("ha", "center"),
                    va=pos.get("va", "center"),
                    linespacing=1.2,
                    bbox=_LABEL_STYLE,
                    zorder=5,
                ))
            else:
                event_texts.append(ax.text(
                    date, pos.get("y", 0.97), label,
                    transform=ax.get_xaxis_transform(),
                    fontsize=8, color="#555555",
                    ha=pos.get("ha", "center"), va=pos.get("va", "top"), linespacing=1.2,
                    bbox=_LABEL_STYLE,
                    zorder=5,
                ))
    return event_texts


def _artist_bbox(artist, renderer, xscale: float = 1.12, yscale: float = 1.25):
    return artist.get_window_extent(renderer).expanded(xscale, yscale)


def _bbox_overlap_area(bbox_a, bbox_b) -> float:
    if not bbox_a.overlaps(bbox_b):
        return 0.0
    x0 = max(bbox_a.x0, bbox_b.x0)
    x1 = min(bbox_a.x1, bbox_b.x1)
    y0 = max(bbox_a.y0, bbox_b.y0)
    y1 = min(bbox_a.y1, bbox_b.y1)
    return max(x1 - x0, 0.0) * max(y1 - y0, 0.0)


def _bbox_gap_penalty(bbox_a, bbox_b, min_gap: float = 4.0) -> float:
    dx = max(bbox_b.x0 - bbox_a.x1, bbox_a.x0 - bbox_b.x1, 0.0)
    dy = max(bbox_b.y0 - bbox_a.y1, bbox_a.y0 - bbox_b.y1, 0.0)
    if dx >= min_gap or dy >= min_gap:
        return 0.0
    return (min_gap - dx) + (min_gap - dy)


def _bbox_outside_penalty(bbox, axes_bbox) -> float:
    return (
        max(axes_bbox.x0 - bbox.x0, 0.0)
        + max(bbox.x1 - axes_bbox.x1, 0.0)
        + max(axes_bbox.y0 - bbox.y0, 0.0)
        + max(bbox.y1 - axes_bbox.y1, 0.0)
    )


def _series_line_penalty(series: pd.Series, ax, bbox, spec: dict) -> float:
    s = series.dropna()
    xy = ax.transData.transform(list(zip(mdates.date2num(s.index.to_pydatetime()), s.values)))
    x0, y0, x1, y1 = bbox.x0, bbox.y0, bbox.x1, bbox.y1
    penalty = 0.0

    anchor_x, anchor_y = ax.transData.transform(
        (mdates.date2num(spec["date"].to_pydatetime()), spec["value"])
    )
    anchor_tol = 5.0

    for idx, (px0, py0) in enumerate(xy):
        if abs(px0 - anchor_x) > anchor_tol or abs(py0 - anchor_y) > anchor_tol:
            if x0 <= px0 <= x1 and y0 <= py0 <= y1:
                penalty += 250.0

        if idx == len(xy) - 1:
            continue

        px1, py1 = xy[idx + 1]
        steps = max(int(max(abs(px1 - px0), abs(py1 - py0)) / 4.0), 1)
        for step in range(1, steps):
            t = step / steps
            px = px0 + (px1 - px0) * t
            py = py0 + (py1 - py0) * t
            if abs(px - anchor_x) <= anchor_tol and abs(py - anchor_y) <= anchor_tol:
                continue
            if x0 <= px <= x1 and y0 <= py <= y1:
                penalty += 120.0
    return penalty


def _label_specs(
    series: pd.Series,
    fmt: str,
    force_left_max_near_end: bool = False,
    include_max: bool = True,
    include_start: bool = True,
    include_end: bool = True,
    include_events: bool = True,
    include_post_pandemic_min: bool = False,
    include_post_desenrola_min: bool = False,
    event_anchor_dates: Optional[dict] = None,
) -> list:
    s = series.dropna()
    specs = []
    if include_start:
        specs.append(
            {
                "kind": "start",
                "label_key": "start",
                "date": s.index[0],
                "value": s.iloc[0],
                "text": f"{s.iloc[0]:{fmt}}",
            }
        )
    if include_end:
        specs.append(
            {
                "kind": "end",
                "label_key": "end",
                "date": s.index[-1],
                "value": s.iloc[-1],
                "text": f"{s.iloc[-1]:{fmt}}",
            }
        )
    if include_max:
        specs.append(
            {
                "kind": "max",
                "label_key": "max",
                "date": s.idxmax(),
                "value": s.max(),
                "text": f"{s.max():{fmt}}",
            }
        )

    if include_events:
        for ev_label, ev_date in KEY_EVENTS.items():
            date = (event_anchor_dates or {}).get(ev_label)
            if date is None:
                loc = s.index.get_indexer([ev_date], method="nearest")[0]
                date = s.index[loc]
            specs.append(
                {
                    "kind": "event",
                    "label_key": f"event::{ev_label}",
                    "date": date,
                    "value": s.loc[date],
                    "text": f"{s.loc[date]:{fmt}}",
                }
            )

    if include_post_pandemic_min:
        post_pandemic = s.loc[s.index > KEY_EVENTS["Pandemia\nCOVID-19"]]
        if not post_pandemic.empty:
            specs.append(
                {
                    "kind": "post_pandemic_min",
                    "label_key": "post_pandemic_min",
                    "date": post_pandemic.idxmin(),
                    "value": post_pandemic.min(),
                    "text": f"{post_pandemic.min():{fmt}}",
                }
            )

    if include_post_desenrola_min:
        post_desenrola = s.loc[s.index > KEY_EVENTS["Programa\nDesenrola"]]
        if not post_desenrola.empty:
            specs.append(
                {
                    "kind": "post_desenrola_min",
                    "label_key": "post_desenrola_min",
                    "date": post_desenrola.idxmin(),
                    "value": post_desenrola.min(),
                    "text": f"{post_desenrola.min():{fmt}}",
                }
            )

    unique_specs = []
    seen_dates = set()
    for spec in specs:
        if spec["date"] not in seen_dates:
            seen_dates.add(spec["date"])
            unique_specs.append(spec)

    if include_max:
        end_spec = next(spec for spec in unique_specs if spec["kind"] == "end")
        max_spec = next(spec for spec in unique_specs if spec["kind"] == "max")
        months_apart = abs(
            (end_spec["date"].year - max_spec["date"].year) * 12
            + end_spec["date"].month
            - max_spec["date"].month
        )
        if months_apart <= _MONTHS_CLOSE_TO_END:
            end_spec["kind"] = "end_near_max"
            max_spec["kind"] = "max_near_end_left" if force_left_max_near_end else "max_near_end"

    return unique_specs


def _place_value_label(
    ax,
    spec: dict,
    renderer,
    axes_bbox,
    occupied_bboxes: list,
    series: pd.Series,
    distance_weight: float,
):
    best_annotation = None
    best_bbox = None
    best_penalty = None

    candidates = spec.get("candidate_overrides")
    if candidates is None:
        candidates = _LABEL_CANDIDATES[spec["kind"]]
    for dx, dy, ha, va in candidates:
        annotation = ax.annotate(
            spec["text"],
            xy=(spec["date"], spec["value"]),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=8,
            color="#404040",
            ha=ha,
            va=va,
            bbox=_LABEL_STYLE,
            zorder=7,
        )
        annotation._label_kind = spec["kind"]
        bbox = _artist_bbox(annotation, renderer)
        overlap_penalty = sum(_bbox_overlap_area(bbox, other) for other in occupied_bboxes)
        gap_penalty = sum(_bbox_gap_penalty(bbox, other) for other in occupied_bboxes)
        line_penalty = _series_line_penalty(series, ax, bbox, spec)
        penalty = (
            overlap_penalty
            + gap_penalty * 20
            + line_penalty
            + _bbox_outside_penalty(bbox, axes_bbox) * 5
            + (abs(dx) + abs(dy)) * distance_weight
        )

        if best_penalty is None or penalty < best_penalty:
            if best_annotation is not None:
                best_annotation.remove()
            best_annotation = annotation
            best_bbox = bbox
            best_penalty = penalty
        else:
            annotation.remove()

        if penalty == 0:
            break

    if best_annotation is None:
        raise RuntimeError("Falha ao posicionar label de valor.")

    return best_annotation, best_bbox


def _validate_label_layout(ax, labels: list, obstacle_artists: Optional[list] = None) -> None:
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    axes_bbox = ax.get_window_extent(renderer).padded(-1)
    raw_label_bboxes = [_artist_bbox(label, renderer, 1.0, 1.0) for label in labels]
    label_bboxes = [_artist_bbox(label, renderer) for label in labels]

    for label, bbox in zip(labels, raw_label_bboxes):
        if _bbox_outside_penalty(bbox, axes_bbox) > 0:
            raise RuntimeError(
                f"Label fora da área útil: '{label.get_text()}' em '{ax.get_title()}' "
                f"({getattr(label, '_label_kind', 'desconhecido')})."
            )

    for bbox_a, bbox_b in combinations(label_bboxes, 2):
        if bbox_a.overlaps(bbox_b):
            raise RuntimeError("Há sobreposição entre labels de valores.")

    for artist in obstacle_artists or []:
        obstacle_bbox = _artist_bbox(artist, renderer)
        for label_bbox in label_bboxes:
            if label_bbox.overlaps(obstacle_bbox):
                raise RuntimeError("Há sobreposição entre labels de valores e outros elementos do gráfico.")


def _add_value_labels(
    ax,
    series: pd.Series,
    color: str,
    fmt: str,
    obstacle_artists: Optional[list] = None,
    force_left_max_near_end: bool = False,
    include_max: bool = True,
    include_start: bool = True,
    include_end: bool = True,
    include_events: bool = True,
    include_post_pandemic_min: bool = False,
    include_post_desenrola_min: bool = False,
    event_anchor_dates: Optional[dict] = None,
    candidate_overrides: Optional[dict] = None,
    distance_weight: float = 0.25,
) -> None:
    specs = _label_specs(
        series,
        fmt,
        force_left_max_near_end=force_left_max_near_end,
        include_max=include_max,
        include_start=include_start,
        include_end=include_end,
        include_events=include_events,
        include_post_pandemic_min=include_post_pandemic_min,
        include_post_desenrola_min=include_post_desenrola_min,
        event_anchor_dates=event_anchor_dates,
    )
    for spec in specs:
        if not candidate_overrides:
            continue
        if spec["label_key"] in candidate_overrides:
            spec["candidate_overrides"] = candidate_overrides[spec["label_key"]]
        elif spec["kind"] in candidate_overrides:
            spec["candidate_overrides"] = candidate_overrides[spec["kind"]]

    for spec in specs:
        ax.plot(spec["date"], spec["value"], "o", color=color, markersize=4, zorder=6)

    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    axes_bbox = ax.get_window_extent(renderer).padded(-3)
    occupied_bboxes = [_artist_bbox(artist, renderer) for artist in obstacle_artists or []]
    placed_labels = []

    for spec in specs:
        annotation, bbox = _place_value_label(
            ax,
            spec,
            renderer,
            axes_bbox,
            occupied_bboxes,
            series,
            distance_weight,
        )
        placed_labels.append(annotation)
        occupied_bboxes.append(bbox)

    _validate_label_layout(ax, placed_labels, obstacle_artists)


_CLOSE_LABEL_OVERRIDES = {
    "start": [
        (6, 3, "left", "bottom"),
        (6, -3, "left", "top"),
        (7, 0, "left", "center"),
        (8, 4, "left", "bottom"),
        (8, -4, "left", "top"),
        (10, 0, "left", "center"),
    ],
    "end": [
        (-6, 3, "right", "bottom"),
        (-6, -3, "right", "top"),
        (-7, 0, "right", "center"),
        (-8, 4, "right", "bottom"),
        (-8, -4, "right", "top"),
        (-10, 0, "right", "center"),
    ],
    "event": [
        (6, 3, "left", "bottom"),
        (6, -3, "left", "top"),
        (-6, 3, "right", "bottom"),
        (-6, -3, "right", "top"),
        (7, 0, "left", "center"),
        (-7, 0, "right", "center"),
        (8, 4, "left", "bottom"),
        (8, -4, "left", "top"),
        (-8, 4, "right", "bottom"),
        (-8, -4, "right", "top"),
        (10, 0, "left", "center"),
        (-10, 0, "right", "center"),
    ],
    "post_pandemic_min": [
        (0, 7, "center", "bottom"),
        (6, 6, "left", "bottom"),
        (-6, 6, "right", "bottom"),
        (8, 3, "left", "bottom"),
        (-8, 3, "right", "bottom"),
        (10, 0, "left", "center"),
        (-10, 0, "right", "center"),
    ],
}


def _save(fig, filename: str) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / filename
    fig.savefig(path, dpi=_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  {filename}")


def _local_peak_dates_near_events(series: pd.Series, window_months: int = 6) -> dict:
    s = series.dropna()
    anchor_dates = {}
    for ev_label, ev_date in KEY_EVENTS.items():
        start = ev_date - pd.DateOffset(months=window_months)
        end = ev_date + pd.DateOffset(months=window_months)
        window = s.loc[(s.index >= start) & (s.index <= end)]
        if not window.empty:
            local_peaks = []
            for i in range(1, len(window) - 1):
                prev_val = window.iloc[i - 1]
                cur_val = window.iloc[i]
                next_val = window.iloc[i + 1]
                if cur_val >= prev_val and cur_val >= next_val:
                    local_peaks.append(window.index[i])

            if local_peaks:
                anchor_dates[ev_label] = min(
                    local_peaks,
                    key=lambda date: (abs((date - ev_date).days), -float(window.loc[date])),
                )
            else:
                anchor_dates[ev_label] = window.idxmax()
    return anchor_dates


def _nearest_local_peak_after_date(
    series: pd.Series,
    event_date: pd.Timestamp,
    window_months: int = 6,
) -> pd.Timestamp:
    s = series.dropna()
    window = s.loc[
        (s.index >= event_date) & (s.index <= event_date + pd.DateOffset(months=window_months))
    ]
    local_peaks = []
    for i in range(1, len(window) - 1):
        prev_val = window.iloc[i - 1]
        cur_val = window.iloc[i]
        next_val = window.iloc[i + 1]
        if cur_val >= prev_val and cur_val >= next_val:
            local_peaks.append(window.index[i])

    if local_peaks:
        return min(local_peaks, key=lambda date: (abs((date - event_date).days), -float(window.loc[date])))
    return window.idxmax()


def _plot_raw_component_panel(
    ax,
    comp: str,
    series: pd.Series,
    unit: str,
    show_event_labels: bool = False,
    event_positions: Optional[dict] = None,
    show_xlabel: bool = False,
    include_post_pandemic_min: bool = False,
    event_anchor_dates: Optional[dict] = None,
    candidate_overrides: Optional[dict] = None,
) -> None:
    ax.plot(series.index, series.values, color=COMP_COLORS[comp])
    ymin, ymax = series.min(), series.max()
    rng = ymax - ymin
    _style_ax(
        ax,
        xlabel="Data" if show_xlabel else None,
        ylabel=unit,
        ylim=(ymin - rng * 0.05, ymax + rng * 0.20),
    )
    ax.set_title(COMP_LABELS[comp])
    event_texts = _add_events(ax, show_labels=show_event_labels, label_positions=event_positions)
    _add_value_labels(
        ax,
        series,
        COMP_COLORS[comp],
        ".1f",
        obstacle_artists=event_texts,
        force_left_max_near_end=False,
        include_max=False,
        include_start=True,
        include_end=True,
        include_events=True,
        include_post_pandemic_min=include_post_pandemic_min,
        event_anchor_dates=event_anchor_dates,
        candidate_overrides=candidate_overrides or _CLOSE_LABEL_OVERRIDES,
        distance_weight=0.9,
    )


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
        event_positions = None
        if i == 0:
            event_positions = {"Programa\nDesenrola": {"coords": "data", "y": 22.5}}
        _plot_raw_component_panel(
            ax,
            comp,
            series,
            unit,
            show_event_labels=(i == 0),
            event_positions=event_positions,
            show_xlabel=(i == len(configs) - 1),
            include_post_pandemic_min=False,
        )

    fig.suptitle(
        "Componentes do Índice — Valores Brutos (não normalizados)",
        fontsize=14, fontweight="bold", y=1.01,
    )
    _save(fig, "components_raw.png")


def _plot_components_raw_individual(components: pd.DataFrame) -> None:
    configs = [
        ("C", components["C"], "% da renda", "components_raw_c.png"),
        ("I", components["I"], "%", "components_raw_i.png"),
        ("Q", components["Q"] * 100, "%", "components_raw_q.png"),
    ]

    for comp, series, unit, filename in configs:
        fig, ax = plt.subplots(figsize=(_FIG_W, 2.7))
        event_positions = None
        candidate_overrides = None
        event_anchor_dates = None
        if comp == "C":
            event_positions = {"Programa\nDesenrola": {"coords": "data", "y": 22.5}}
            candidate_overrides = {
                **_CLOSE_LABEL_OVERRIDES,
                "start": [
                    (0, -7, "center", "top"),
                    (-1, -7, "center", "top"),
                    (2, -7, "left", "top"),
                    (-2, -5, "center", "top"),
                    (3, -5, "left", "top"),
                ],
                "end": [
                    (2, 7, "left", "bottom"),
                    (0, 7, "center", "bottom"),
                    (-2, 7, "right", "bottom"),
                    (4, 5, "left", "bottom"),
                    (-4, 7, "right", "bottom"),
                ],
            }
            event_anchor_dates = _local_peak_dates_near_events(series, window_months=6)
        elif comp == "I":
            candidate_overrides = {
                **_CLOSE_LABEL_OVERRIDES,
                "end": [
                    (2, 7, "left", "bottom"),
                    (0, 7, "center", "bottom"),
                    (4, 5, "left", "bottom"),
                    (-2, 7, "right", "bottom"),
                    (-4, 7, "right", "bottom"),
                ],
            }
            event_anchor_dates = {
                "Pandemia\nCOVID-19": _nearest_local_peak_after_date(
                    series,
                    KEY_EVENTS["Pandemia\nCOVID-19"],
                    window_months=6,
                )
            }
        elif comp == "Q":
            candidate_overrides = {
                **_CLOSE_LABEL_OVERRIDES,
                "start": [
                    (-2, -5, "right", "top"),
                    (-1, -7, "right", "top"),
                    (-3, -3, "right", "top"),
                    (-2, 0, "right", "center"),
                    (0, -7, "center", "top"),
                ],
                "end": [
                    (2, 7, "left", "bottom"),
                    (0, 7, "center", "bottom"),
                    (4, 5, "left", "bottom"),
                    (-2, 7, "right", "bottom"),
                    (-4, 7, "right", "bottom"),
                ],
                "event::Programa\nDesenrola": [
                    (0, -7, "center", "top"),
                    (2, -7, "left", "top"),
                    (-2, -7, "right", "top"),
                    (4, -5, "left", "top"),
                    (-4, -5, "right", "top"),
                ],
                "post_pandemic_min": [
                    (-6, 0, "right", "center"),
                    (-6, 3, "right", "bottom"),
                    (-6, -3, "right", "top"),
                    (-8, 0, "right", "center"),
                    (-8, 3, "right", "bottom"),
                ],
            }
            event_anchor_dates = {
                "Pandemia\nCOVID-19": _nearest_local_peak_after_date(
                    series,
                    KEY_EVENTS["Pandemia\nCOVID-19"],
                    window_months=6,
                )
            }
        _plot_raw_component_panel(
            ax,
            comp,
            series,
            unit,
            show_event_labels=True,
            event_positions=event_positions,
            show_xlabel=True,
            include_post_pandemic_min=True,
            event_anchor_dates=event_anchor_dates,
            candidate_overrides=candidate_overrides,
        )
        fig.tight_layout()
        _save(fig, filename)


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


def _plot_index(index_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H))

    ax.plot(
        index_df.index, index_df["index"],
        color=INDEX_COLOR,
        label="Índice de Desconforto de Crédito",
    )

    _style_ax(ax, ylabel="Índice [0 – 1]", ylim=(0, 1.05))
    event_texts = _add_events(ax)
    legend = ax.legend(loc="upper left")
    ax.set_title("Índice de Desconforto de Crédito — Min-Max — Janela Expansiva")

    fig.tight_layout()
    event_anchor_dates = _local_peak_dates_near_events(index_df["index"], window_months=6)
    _add_value_labels(
        ax,
        index_df["index"],
        INDEX_COLOR,
        ".2f",
        obstacle_artists=[*event_texts, legend],
        force_left_max_near_end=False,
        include_max=False,
        include_start=True,
        include_end=True,
        include_events=True,
        include_post_pandemic_min=True,
        include_post_desenrola_min=True,
        event_anchor_dates=event_anchor_dates,
        candidate_overrides={
            "start": [
                (6, -3, "left", "top"),
                (6, 3, "left", "bottom"),
                (7, 0, "left", "center"),
                (8, -4, "left", "top"),
                (8, 4, "left", "bottom"),
                (10, 0, "left", "center"),
            ],
            "end": [
                (-6, -3, "right", "top"),
                (-8, -4, "right", "top"),
                (-10, 0, "right", "center"),
                (-10, -6, "right", "top"),
                (0, -8, "center", "top"),
                (2, 7, "left", "bottom"),
                (0, 7, "center", "bottom"),
                (4, 5, "left", "bottom"),
                (-2, 7, "right", "bottom"),
                (-4, 7, "right", "bottom"),
                (2, 5, "left", "bottom"),
            ],
            "event::Pandemia\nCOVID-19": [
                (6, 0, "left", "center"),
                (6, -3, "left", "top"),
                (6, 3, "left", "bottom"),
                (-6, 0, "right", "center"),
                (8, 0, "left", "center"),
                (8, -4, "left", "top"),
                (8, 4, "left", "bottom"),
                (-8, 0, "right", "center"),
            ],
            "event::Programa\nDesenrola": [
                (6, 3, "left", "bottom"),
                (6, -3, "left", "top"),
                (-6, 3, "right", "bottom"),
                (-6, -3, "right", "top"),
                (8, 4, "left", "bottom"),
                (8, -4, "left", "top"),
                (-8, 4, "right", "bottom"),
                (-8, -4, "right", "top"),
            ],
            "post_pandemic_min": [
                (8, 0, "left", "center"),
                (8, 4, "left", "bottom"),
                (8, -4, "left", "top"),
                (10, 0, "left", "center"),
                (10, 4, "left", "bottom"),
                (6, 0, "left", "center"),
            ],
            "post_desenrola_min": [
                (8, -4, "left", "top"),
                (8, 0, "left", "center"),
                (-8, -4, "right", "top"),
                (10, -2, "left", "top"),
                (-10, -2, "right", "top"),
                (0, -8, "center", "top"),
            ],
        },
        distance_weight=1.0,
    )
    _save(fig, "index.png")


def plot_all(components: pd.DataFrame, index_df: pd.DataFrame) -> None:
    _apply_excel_style()
    print("Salvando figuras em outputs/figures/:")
    _plot_components_raw(components)
    _plot_components_raw_individual(components)
    _plot_components_normalized(index_df)
    _plot_index(index_df)
