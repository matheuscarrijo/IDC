from itertools import combinations
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

from src import plot_overlay as overlay
from src.plot_recent import plot_recent

FIGURES_DIR = Path("outputs/figures")

_HISTORICAL_EVENTS = {
    "Pandemia\nCOVID-19": pd.Timestamp("2020-03-01"),
    "Programa\nDesenrola": pd.Timestamp("2023-06-01"),
}

# Novo Desenrola Brasil: launched on 4 May 2026 (MP 1.355), with
# renegotiations starting on 5 May. Use May for this monthly series.
# Source: https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2026/mpv/mpv1355.htm
KEY_EVENTS = {
    **_HISTORICAL_EVENTS,
    "Novo\nDesenrola": pd.Timestamp("2026-05-01"),
}

COMP_LABELS = {
    "C": "Comprometimento de Renda",
    "I": "Inadimplência (90+ dias)",
    "Q": "Crédito oneroso",
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


def num(value: float, fmt: str) -> str:
    """A value with the decimal comma of the report, e.g. ``num(0.9661, ".3f")`` is ``0,966``."""
    return f"{value:{fmt}}".replace(".", ",")


class _CommaFormatter(matplotlib.ticker.ScalarFormatter):
    """Axis tick labels with the decimal comma of the report."""

    def __call__(self, x, pos=None):
        return super().__call__(x, pos).replace(".", ",")


def _style_ax(ax, xlabel: str = None, ylabel: str = None, ylim: tuple = None) -> None:
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
    ax.yaxis.set_major_formatter(_CommaFormatter())

    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    if ylim:
        ax.set_ylim(*ylim)


def _add_events(
    ax,
    show_labels: bool = True,
    label_positions: Optional[dict] = None,
    events: Optional[dict] = None,
) -> list:
    event_texts = []
    for label, date in (KEY_EVENTS if events is None else events).items():
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
    events: Optional[dict] = None,
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
                "text": num(s.iloc[0], fmt),
            }
        )
    if include_end:
        specs.append(
            {
                "kind": "end",
                "label_key": "end",
                "date": s.index[-1],
                "value": s.iloc[-1],
                "text": num(s.iloc[-1], fmt),
            }
        )
    if include_max:
        specs.append(
            {
                "kind": "max",
                "label_key": "max",
                "date": s.idxmax(),
                "value": s.max(),
                "text": num(s.max(), fmt),
            }
        )

    if include_events:
        for ev_label, ev_date in (KEY_EVENTS if events is None else events).items():
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
                    "text": num(s.loc[date], fmt),
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
                    "text": num(post_pandemic.min(), fmt),
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
                    "text": num(post_desenrola.min(), fmt),
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


_COMPONENT_MIN_SEPARATION_PT = 45.0

# When two labelled points are too close, only one keeps its marker and label: the last month first, then the
# first month, the minimum after an event, and the point that marks an event.
_LABEL_PRIORITY = {"end": 0, "end_near_max": 0, "start": 1, "post_pandemic_min": 2, "post_desenrola_min": 2,
                   "max": 3, "max_near_end": 3, "max_near_end_left": 3, "event": 4}


def _drop_crowded_specs(ax, specs: list, min_separation_pt: float) -> list:
    """The labelled points without the ones closer than ``min_separation_pt`` to a point of higher priority.

    Two labels for nearby points cannot be told apart (which value belongs to which point), so the less important
    point is left unmarked and unlabelled.
    """
    limit = min_separation_pt * ax.figure.dpi / 72
    kept = []
    for spec in sorted(specs, key=lambda sp: (_LABEL_PRIORITY.get(sp["kind"], 5), sp["date"])):
        x, y = ax.transData.transform((mdates.date2num(spec["date"]), spec["value"]))
        if all(np.hypot(x - kx, y - ky) >= limit for kx, ky, _ in kept):
            kept.append((x, y, spec))
    return sorted((spec for _, _, spec in kept), key=lambda sp: sp["date"])


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
    events: Optional[dict] = None,
    min_separation_pt: float = 0.0,
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
        events=events,
    )
    for spec in specs:
        if not candidate_overrides:
            continue
        if spec["label_key"] in candidate_overrides:
            spec["candidate_overrides"] = candidate_overrides[spec["label_key"]]
        elif spec["kind"] in candidate_overrides:
            spec["candidate_overrides"] = candidate_overrides[spec["kind"]]

    if min_separation_pt:
        ax.figure.canvas.draw()
        specs = _drop_crowded_specs(ax, specs, min_separation_pt)

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
    "event::Novo\nDesenrola": [
        (6, -7, "left", "top"),
        (8, -8, "left", "top"),
        (10, -10, "left", "top"),
        (6, 7, "left", "bottom"),
        (-6, -14, "right", "top"),
        (-12, -18, "right", "top"),
    ],
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


def _local_peak_dates_near_events(
    series: pd.Series,
    window_months: int = 6,
    events: Optional[dict] = None,
) -> dict:
    s = series.dropna()
    anchor_dates = {}
    for ev_label, ev_date in (KEY_EVENTS if events is None else events).items():
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


def _component_event_anchors(comp: str, series: pd.Series) -> dict:
    """Months whose values mark the historical events in the panel of ``comp``."""
    if comp == "C":
        return _local_peak_dates_near_events(series, window_months=6, events=_HISTORICAL_EVENTS)
    return {"Pandemia\nCOVID-19": _nearest_local_peak_after_date(series, KEY_EVENTS["Pandemia\nCOVID-19"], window_months=6)}


def _plot_raw_component_panel(
    ax,
    comp: str,
    series: pd.Series,
    unit: str,
    low: Optional[pd.Series] = None,
    low_label: Optional[str] = None,
    tight_layout: bool = False,
) -> Optional[Line2D]:
    """One component in raw values, with its events, its labelled points and, when given, the dashed low-income line.

    The labelled points are the first and last months, the months that mark the events and the minimum after the
    pandemic; of two points too close to be told apart by their labels only the more important one is kept
    (``_drop_crowded_specs``).  The labels cover no line (the dashed one included), marker, event name or other
    label (``_strict_value_labels``).  Returns the dashed line, if any, for a legend.
    """
    ax.plot(series.index, series.values, color=COMP_COLORS[comp])
    # Preserve enough horizontal room for endpoint labels as the series grows.
    ax.margins(x=0.08)
    ymin, ymax = series.min(), series.max()
    rng = ymax - ymin
    _style_ax(ax, xlabel=None, ylabel=unit, ylim=(ymin - rng * 0.05, ymax + rng * 0.20))
    ax.set_title(COMP_LABELS[comp])
    event_positions = {
        "Novo\nDesenrola": {"coords": "data", "y": {"C": 25.0, "I": 5.5, "Q": 22.0}[comp]},
        **({"Programa\nDesenrola": {"coords": "data", "y": 22.5}} if comp == "C" else {}),
    }
    event_texts = _add_events(ax, label_positions=event_positions)
    lines, points, dashed = [series], [], None
    if low is not None:
        try:  # the general figure must be produced whatever happens with the low-income line
            dashed = overlay._dashed(ax, low, label=low_label, end_label=False)
            lines.append(low)
            points.append((low.index[-1], float(low.iloc[-1]), overlay.COLOR, "end"))
        except Exception as exc:  # noqa: BLE001
            print(f"  aviso: linha de baixa renda omitida ({exc!r})")
    if tight_layout:
        ax.figure.tight_layout()
    ax.figure.canvas.draw()
    specs = _label_specs(
        series,
        ".1f",
        include_max=False,
        include_start=True,
        include_end=True,
        include_events=True,
        include_post_pandemic_min=True,
        event_anchor_dates=_component_event_anchors(comp, series),
    )
    specs = _drop_crowded_specs(ax, specs, _COMPONENT_MIN_SEPARATION_PT)
    points = [(spec["date"], spec["value"], COMP_COLORS[comp], spec["kind"]) for spec in specs] + points
    _strict_value_labels(ax, points, event_texts, lines, fmt=".1f")
    return dashed


def _overlay(draw, *args) -> None:
    """Draw the optional low-income lines; a failure leaves the figure with the general series only."""
    try:
        draw(*args)
    except Exception as exc:  # noqa: BLE001 - the general figures must be produced whatever happens here
        print(f"  aviso: linhas de baixa renda omitidas ({exc!r})")


def _plot_components_raw(components: pd.DataFrame, low_income: Optional[pd.DataFrame] = None, *,
                         output_path: Optional[Path] = None, low_income_legend: bool = True) -> None:
    """Three stacked panels (shared x-axis) — fits A4 page width."""
    fig, axes = plt.subplots(3, 1, figsize=(_FIG_W, 7.2), sharex=True)
    fig.subplots_adjust(hspace=0.4)

    configs = [
        ("C", components["C"],       "% da renda"),
        ("I", components["I"],       "%"),
        ("Q", components["Q"] * 100, "%"),
    ]
    for ax, (comp, series, unit) in zip(axes, configs):
        low = low_income[comp].dropna() if low_income is not None and comp in ("I", "Q") else None
        _plot_raw_component_panel(ax, comp, series, unit, low=low)

    fig.suptitle(
        "Componentes do Índice — Valores Brutos (não normalizados)",
        fontsize=14, fontweight="bold", y=1.01,
    )
    if low_income is not None and low_income_legend:
        overlay.components_legend(fig)
    if output_path is None:
        _save(fig, "components_raw.png")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=_DPI, bbox_inches="tight")
        plt.close(fig)


def _plot_components_raw_individual(components: pd.DataFrame, low_income: Optional[pd.DataFrame] = None) -> None:
    configs = [
        ("C", components["C"], "% da renda", "components_raw_c.png"),
        ("I", components["I"], "%", "components_raw_i.png"),
        ("Q", components["Q"] * 100, "%", "components_raw_q.png"),
    ]

    for comp, series, unit, filename in configs:
        fig, ax = plt.subplots(figsize=(_FIG_W, 2.7))
        low = low_income[comp].dropna() if low_income is not None and comp in ("I", "Q") else None
        dashed = _plot_raw_component_panel(ax, comp, series, unit, low=low, low_label=overlay.SINGLE_LABEL, tight_layout=True)
        if dashed is not None:
            overlay.component_legend(ax, dashed)
        fig.tight_layout()
        _save(fig, filename)


def _plot_components_normalized(index_df: pd.DataFrame, low_income: Optional[pd.DataFrame] = None) -> None:
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H))

    for comp in ["C", "I", "Q"]:
        ax.plot(
            index_df.index, index_df[f"{comp}_norm"],
            label=COMP_LABELS[comp], color=COMP_COLORS[comp],
        )

    # Leave room for the event label near the latest observations.
    ax.margins(x=0.06)
    _style_ax(ax, ylabel="[0 – 1]", ylim=(-0.02, 1.05))
    _add_events(ax, label_positions={
        "Pandemia\nCOVID-19": {"coords": "data", "y": 0.80, "ha": "center", "va": "center"},
        "Programa\nDesenrola": {"coords": "data", "y": 0.25, "ha": "center", "va": "center"},
        "Novo\nDesenrola": {"coords": "data", "y": 0.65, "ha": "center", "va": "center"},
    })
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.13),
        ncol=3,
        frameon=False,
    )
    ax.set_title("Componentes Normalizados — Min-Max — Janela Expansiva")

    fig.tight_layout(rect=[0, 0.06, 1, 1])
    if low_income is not None:
        _overlay(overlay.normalized, fig, low_income, COMP_COLORS)
    _save(fig, "components_normalized.png")


def _strict_value_labels(ax, points: list, artists: list, lines: list, fmt: str = ".3f") -> None:
    """Value labels that cover no line, marker, other label or ``artists`` (legend, event names).

    ``points`` holds ``(date, value, color, kind)``; minima (``kind`` ending in ``min``) are labelled below their
    point and the others above, at the nearest free offset (with a leader line when away from the point; see
    ``src.plot_recent``), and clearly nearer its own point than any other line, so that a value is never read as
    belonging to the other series.  The last months are placed first.  A point without a free offset keeps no label
    nor marker.
    """
    from src import plot_recent as R

    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    obstacles = [artist.get_window_extent(renderer) for artist in artists]
    obstacles += R.marker_boxes(ax, [p[0] for p in points], [p[1] for p in points])
    samples = [R.line_samples(ax, s.index, s.values) for s in lines]
    first = {"end": 0, "start": 1}
    for date, value, color, kind in sorted(points, key=lambda p: first.get(p[3], 2)):
        below = kind.endswith("min")
        candidates = _PERIOD_BELOW if below else _PERIOD_ABOVE
        if kind == "end":  # next to the last month first; then to its right, where the axes leave room
            near = [o for o in candidates if R._distance(o) <= R._LEADER_PT]
            far = [o for o in candidates if R._distance(o) > R._LEADER_PT]
            candidates = near + [(dx, dy) for dx in (24, 30) for dy in (3, -3, 9, -9)] + far
        for label in R._options(ax, renderer, date, value, num(value, fmt), color, candidates, obstacles, samples,
                                associate=True):
            obstacles.append(label.text_bbox)
            ax.plot(date, value, "o", color=color, markersize=4, zorder=6)
            break


# Start of the figure of the recent period (``index_since_2022.png``): six months before the Programa Desenrola,
# so that both programs and the months before each of them are shown with the format of ``index.png``.
RECENT_START = pd.Timestamp("2022-12-01")


def _plot_index(
    index_df: pd.DataFrame,
    low_income: Optional[pd.DataFrame] = None,
    *,
    start: Optional[pd.Timestamp] = None,
    filename: str = "index.png",
) -> None:
    """``index.png`` (full history) or, with ``start``, the same figure from ``start`` on (``index_since_2022.png``)."""
    if start is not None:
        _plot_index_since(index_df, low_income, start, filename)
        return
    # Figure 1 has its own full-width annex page. A square source uses the page
    # vertically without changing fonts, the 150 mm width, or the data scale.
    fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_W))

    ax.plot(
        index_df.index, index_df["index"],
        color=INDEX_COLOR,
        label="Índice de Desconforto de Crédito",
    )

    _style_ax(ax, ylabel="Índice [0 – 1]", ylim=(0, 1.05))
    # Room after the last month for the labels of its values (three decimals), clear of both lines.
    last = index_df["index"].dropna().index[-1]
    ax.set_xlim(right=mdates.date2num(last + pd.DateOffset(months=10)))
    event_texts = _add_events(ax, label_positions={
        "Pandemia\nCOVID-19": {
            "coords": "data",
            "y": 0.90,
            "ha": "center",
            "va": "center",
        },
        "Novo\nDesenrola": {
            "coords": "data",
            "y": 0.85,
            "ha": "center",
            "va": "center",
        },
    })
    lines = [index_df["index"].dropna()]
    if low_income is not None:
        low = low_income["IDC"].loc[overlay.primeira_exibicao():].dropna()
        ax.get_lines()[0].set_label("IDC Geral")
        ax.plot(low.index, low.values, color=overlay.COLOR, linewidth=2.0, label=overlay.LABEL, zorder=4)
        lines.append(low)
    legend = ax.legend(loc="upper left")
    ax.set_title(f"IDC desde {_mes_ano(index_df['index'].dropna().index[0])}")  # simple titles, as in index_12m.png

    fig.tight_layout()
    # Preserve the historical peak labels; label the new event at its own month.
    event_anchor_dates = _local_peak_dates_near_events(
        index_df["index"], window_months=6, events=_HISTORICAL_EVENTS,
    )
    specs = _label_specs(
        index_df["index"],
        ".3f",
        include_max=False,
        include_start=True,
        include_end=True,
        include_events=True,
        include_post_pandemic_min=True,
        include_post_desenrola_min=True,
        event_anchor_dates=event_anchor_dates,
    )
    points = [(spec["date"], spec["value"], INDEX_COLOR, spec["kind"]) for spec in specs]
    if low_income is not None:
        points += [(low.index[0], float(low.iloc[0]), overlay.COLOR, "start"), (low.index[-1], float(low.iloc[-1]), overlay.COLOR, "end")]
    _strict_value_labels(ax, points, [legend, *event_texts], lines)
    _save(fig, filename)


# Value labels of the figure from ``RECENT_START``: besides the first and last months and the months of the events,
# every turning point of each series, i.e. a month that is the highest (or lowest) of the months within
# ``_TURNING_WINDOW`` on each side and stands at least ``_TURNING_MIN_MOVE`` above (or below) the lowest (highest).
_TURNING_WINDOW = 4
_TURNING_MIN_MOVE = 0.02
# In the latest months, only the points that are hard to read are labelled (see ``_hard_to_read``), on a ladder:
# the label of the higher value of a month above the series and of the lower one below, in staggered rows, each
# joined to its point by a vertical leader line.  Months are about 9 pt apart in this figure, so labels of nearby
# months need different rows.
_PERIOD_LAST_MONTHS = 6
_LADDER_GAP_PT = 10   # between the highest (lowest) point of the latest months and the nearest row
_LADDER_STEP_PT = 13  # between rows
# Offsets of the other labels (first month, events, turning points), nearest first.
_PERIOD_GRID = sorted(((dx, dy) for dy in (7, 11, 15, 20, 26, 33) for dx in (0, -8, 8, -14, 14, -20, 20)),
                      key=lambda o: (o[0] ** 2 + o[1] ** 2, abs(o[0])))
_PERIOD_ABOVE = _PERIOD_GRID + [(dx, -dy) for dx, dy in _PERIOD_GRID]
_PERIOD_BELOW = [(dx, -dy) for dx, dy in _PERIOD_GRID] + _PERIOD_GRID


def turning_points(series: pd.Series, window: int = _TURNING_WINDOW, min_move: float = _TURNING_MIN_MOVE) -> dict:
    """Months of the local maxima (``"max"``) and minima (``"min"``) of ``series`` (first and last months excluded)."""
    s = series.dropna()
    points = {}
    for i in range(1, len(s) - 1):
        around = s.iloc[max(0, i - window):i + window + 1]
        value = s.iloc[i]
        if value == around.max() and value - around.min() >= min_move:
            points[s.index[i]] = "max"
        elif value == around.min() and around.max() - value >= min_move:
            points[s.index[i]] = "min"
    return points


def _on_the_bounds(value: float) -> bool:
    """A value read on the gridlines of the bounds of the index (1,000 and 0,000) needs no label."""
    return round(value, 3) in (0.0, 1.0)


def _hard_to_read(series: pd.Series, months: pd.DatetimeIndex, events: dict) -> list:
    """Latest months of ``series`` whose value is hard to read on the figure.

    The last month, the months of the events, and the months where the series turns (it rises and then falls, or
    the reverse): there the line zigzags and crosses the other series, so the eye cannot follow it to the axis.
    Values on the bounds of the index (1,000 and 0,000) are read on their gridlines and are left out.
    """
    s = series.dropna()
    chosen = []
    for date in months:
        if date not in s.index or _on_the_bounds(float(s.loc[date])):
            continue
        i = s.index.get_loc(date)
        turns = 0 < i < len(s) - 1 and (s.iloc[i] - s.iloc[i - 1]) * (s.iloc[i + 1] - s.iloc[i]) < 0
        if date == s.index[-1] or date in events.values() or turns:
            chosen.append(date)
    return chosen


def _period_label_months(series: pd.Series, events: dict, ladder_start: pd.Timestamp) -> dict:
    """Months before the ladder to label in one series, with their kind: ``"start"``, ``"event"``, ``"max"`` or ``"min"``."""
    s = series.dropna().loc[:ladder_start - pd.DateOffset(months=1)]
    months = dict(turning_points(series.dropna()))
    months = {date: kind for date, kind in months.items() if date < ladder_start}
    for date in events.values():
        if s.index[0] <= date <= s.index[-1]:
            months[date] = "event"
    months[s.index[0]] = "start"
    return {date: kind for date, kind in months.items() if not _on_the_bounds(float(series.loc[date]))}


_MES_ABREV = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
              7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}


def _mes_ano(date) -> str:
    """``dez-2022``, the month-year format of the report."""
    return f"{_MES_ABREV[date.month]}-{date.year}"


def _ladder(ax, renderer, zone: list, rows: int, fmt, top: float, bottom: float) -> list:
    """Labels of the latest months on staggered rows above ``top`` and below ``bottom``, with vertical leader lines.

    ``zone`` holds ``(date, [(value, color, side)])`` with ``side`` ``"above"`` or ``"below"``; the rows of each side
    are taken in turn, so that labels of nearby months do not meet.
    """
    pt = ax.figure.dpi / 72
    to_data = (ax.get_ylim()[1] - ax.get_ylim()[0]) / ax.get_window_extent(renderer).height  # data units per pixel
    labels = []
    turn = {"above": 0, "below": 0}
    for date, points in zone:
        placed = []
        for y, color, side in points:
            row = turn[side] % rows
            turn[side] += 1
            gap = (_LADDER_GAP_PT + row * _LADDER_STEP_PT) * pt * to_data
            placed.append(((y, color), top + gap if side == "above" else bottom - gap, "bottom" if side == "above" else "top"))
        for (y, color), y_text, va in placed:
            label = ax.annotate(fmt(y), xy=(date, y), xytext=(date, y_text), textcoords="data", ha="center", va=va,
                                fontsize=8.5, color=color, zorder=8, bbox=dict(facecolor="white", edgecolor="none", alpha=0.9, pad=0.8),
                                arrowprops=dict(arrowstyle="-", color=color, linewidth=0.6, shrinkA=0, shrinkB=3))
            label.update_positions(renderer)
            labels.append(label)
    return labels


def _ladder_room(rows: int) -> float:
    """Points needed above (or below) the latest months for the ladder."""
    return _LADDER_GAP_PT + (rows - 1) * _LADDER_STEP_PT + 14


def _plot_index_since(index_df: pd.DataFrame, low_income: Optional[pd.DataFrame], start: pd.Timestamp, filename: str) -> None:
    """The index figure restricted to the months from ``start``, with a vertical scale fitted to the period.

    It keeps the look of ``index.png`` (size, title, colors, event lines) and labels more points.  In the latest
    ``_PERIOD_LAST_MONTHS`` months, the points that are hard to read (``_hard_to_read``) are labelled on a ladder
    (``_ladder``).  Before them, the first month, the months of the events and the turning points of each series
    are labelled by the routine of
    ``index_12m.png`` (clear of the lines, markers, other labels and event names, with a leader line when away from
    their point).  Values of 1,000 and 0,000 are read on their gridlines and never labelled.  A label that finds no
    free place is left out, since the window grows every month.  If the ladder
    itself does not fit, the figure is not saved.  The horizontal axis has slanted month ticks, one per quarter while
    the window has up to four years.
    """
    from matplotlib.text import Text

    from src import plot_recent as R

    series = [("IDC Geral", index_df["index"].loc[start:].dropna(), INDEX_COLOR)]
    if low_income is not None:
        low = low_income["IDC"].loc[max(start, overlay.primeira_exibicao()):].dropna()
        if not low.empty:
            series.append((overlay.LABEL, low, overlay.COLOR))
    events = {label: date for label, date in KEY_EVENTS.items() if date >= start}
    zone_months = series[0][1].index[-_PERIOD_LAST_MONTHS:]
    # Hard-to-read points of the latest months; the higher value of a month is labelled above the series and the
    # lower one below, so that a vertical leader never crosses the other series.
    chosen = {name: set(_hard_to_read(s, zone_months, events)) for name, s, _ in series}
    zone = []
    for date in zone_months:
        at_date = sorted(((float(s.loc[date]), color, name) for name, s, color in series if date in s.index), key=lambda p: p[0])
        points = [(y, color, "above" if i == len(at_date) - 1 else "below")
                  for i, (y, color, name) in enumerate(at_date) if date in chosen[name]]
        if points:
            zone.append((date, points))
    zone_values = [float(s.loc[d]) for _, s, _ in series for d in zone_months if d in s.index]
    fmt = lambda y: num(y, ".3f")  # noqa: E731 - three decimals and a decimal comma, as in the text of the report
    values = pd.concat([s for _, s, _ in series])
    zone_top, zone_bottom = max(zone_values), min(zone_values)

    for rows in (3, 4, 5):
        fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_W))
        for name, s, color in series:
            ax.plot(s.index, s.values, color=color, label=name, zorder=4)
        _style_ax(ax, ylabel="Índice [0 – 1]")
        # Slanted month ticks: every quarter (dez, mar, jun, set) while the window has up to four years, then every
        # half-year (dez, jun) and every year (dez); never after the last month.
        n_months = len(series[0][1])
        tick_months = (3, 6, 9, 12) if n_months <= 48 else (6, 12) if n_months <= 96 else (12,)
        ticks = [d for d in series[0][1].index if d.month in tick_months]
        ax.xaxis.set_major_locator(plt.FixedLocator(mdates.date2num(ticks)))
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: _mes_ano(mdates.num2date(x))))
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
        # Room on the right for the label of the last month, centred on its point.
        span = series[0][1].index[-1] - series[0][1].index[0]
        ax.set_xlim(series[0][1].index[0] - pd.DateOffset(days=20),
                    series[0][1].index[-1] + max(pd.Timedelta(days=50), span * 0.035))
        event_texts = _add_events(ax, label_positions={label: {"y": 0.03, "va": "bottom"} for label in events}, events=events)
        legend = ax.legend(loc="upper center")  # in the free band above the trough of 2024
        ax.set_title(f"IDC desde {_mes_ano(start)}")
        # The vertical scale fits the period and leaves room for the ladder; ticks only within [0, 1].
        low_y, high_y = values.min() - 0.03, values.max() + 0.03
        for _ in range(4):
            ax.set_ylim(low_y, high_y)
            fig.tight_layout()
            fig.canvas.draw()
            per_pt = (high_y - low_y) / ax.get_window_extent(fig.canvas.get_renderer()).height * fig.dpi / 72
            low_y = max(0.0, min(values.min() - 0.03, zone_bottom - _ladder_room(rows) * per_pt))
            high_y = max(values.max() + 0.03, zone_top + _ladder_room(rows) * per_pt)
        ax.set_ylim(low_y, high_y)
        ax.set_yticks([t for t in np.arange(np.ceil(low_y / 0.05) * 0.05, 1.0001, 0.05) if t <= high_y])
        fig.tight_layout()
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        ladder = _ladder(ax, renderer, zone, rows, fmt, zone_top, zone_bottom)
        boxes = [Text.get_window_extent(label, renderer) for label in ladder]
        frame = ax.get_window_extent(renderer)
        clear = all(not a.overlaps(b) for i, a in enumerate(boxes) for b in boxes[i + 1:])
        if clear and all(R._inside(box, frame) for box in boxes):
            break
        plt.close(fig)
    else:
        raise R.LabelLayoutError(f"{filename}: the labels of the latest months do not fit")

    # Other months to label, the required ones first; months shared by the two series are labelled together.
    wanted: dict = {}
    for _, s, color in series:
        for date, kind in _period_label_months(s, events, zone_months[0]).items():
            wanted.setdefault(date, []).append((float(s.loc[date]), color, kind))
    order = {"event": 0, "start": 1, "max": 2, "min": 2}
    months = sorted(wanted, key=lambda d: (min(order[k] for _, _, k in wanted[d]), d))

    obstacles = [legend.get_window_extent(renderer), *(text.get_window_extent(renderer) for text in event_texts), *boxes]
    lines = [R.line_samples(ax, s.index, s.values) for _, s, _ in series]
    for date in months:
        obstacles += R.marker_boxes(ax, [date] * len(wanted[date]), [y for y, _, _ in wanted[date]])
    for date, points in zone:
        obstacles += R.marker_boxes(ax, [date] * len(points), [y for y, _, _ in points])
        for y, color, _ in points:
            ax.plot(date, y, "o", color=color, markersize=4, zorder=6)
    for date in months:
        points = sorted(wanted[date], key=lambda p: p[0])
        kinds = {k for _, _, k in points}
        single = _PERIOD_BELOW if kinds == {"min"} else _PERIOD_ABOVE
        try:
            R.place_month(ax, renderer, date, [(y, c) for y, c, _ in points], obstacles, lines, fmt=fmt, single=single,
                          figure=filename, above=_PERIOD_ABOVE, below=_PERIOD_BELOW)
        except R.LabelLayoutError:
            continue  # a month without room keeps no label nor marker (the event lines are always drawn)
        for y, color, _ in points:
            ax.plot(date, y, "o", color=color, markersize=4, zorder=6)
    _save(fig, filename)


def plot_all(components: pd.DataFrame, index_df: pd.DataFrame, low_income: Optional[pd.DataFrame] = None) -> None:
    """Save the eight figures; ``low_income`` (see ``src.low_income``) adds the low-income series to six of them."""
    _apply_excel_style()
    print("Salvando figuras em outputs/figures/:")
    _plot_components_raw(components, low_income)
    _plot_components_raw_individual(components, low_income)
    _plot_components_normalized(index_df, low_income)
    _plot_index(index_df, low_income)
    _plot_index(index_df, low_income, start=RECENT_START, filename="index_since_2022.png")
    plot_recent(index_df, low_income, FIGURES_DIR / "index_12m.png")
    print("  index_12m.png")
