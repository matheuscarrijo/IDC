"""``index_12m.png``: the IDC Geral and the IDC Baixa Renda in the last 12 months, with the value of every month.

The figure of the full history (``index.png``) keeps the long-run view; at its scale the latest months are hard
to read.  This one zooms on the last 12 reference months and writes the value of every point.  Each label is
placed where it overlaps no other label, marker, the legend or the axes border; when no candidate position is
free the function raises instead of saving an unreadable figure.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.text import Text
from matplotlib.transforms import Bbox

from src import plot_overlay as overlay

MONTHS = 12
_MES = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
        7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}
_LABEL_BOX = dict(facecolor="white", edgecolor="none", alpha=0.9, pad=0.8)
# Offsets in points from the marker, tried from the nearest: the label of the upper series prefers the positions
# above its point and the label of the lower series those below it, so that the two labels of a month do not meet;
# the other side is tried only when the preferred one is taken (e.g. both series at a peak).  A label farther than
# ``_LEADER_PT`` from its point gets a thin leader line, so that it is never read as the value of another month.
_GRID = sorted(((dx, dy) for dy in (7, 11, 15, 20, 26, 33) for dx in (0, -8, 8, -14, 14, -20, 20)),
               key=lambda o: (o[0] ** 2 + o[1] ** 2, abs(o[0])))
_LEADER_PT = 16
_NEAR_PT = 26  # farthest label accepted at the tallest height
# Heights (inches) tried in order, at the fixed width of 6.5 in: the tallest one whose labels all find a free
# position is saved.  The page of the annex fits any of them at full text width.
HEIGHTS = (5.4, 5.0, 4.6, 4.2, 3.8)


def _distance(offset: tuple[float, float]) -> float:
    return float(np.hypot(*offset))


class LabelLayoutError(RuntimeError):
    """No free position for a value label."""
_ABOVE = _GRID + [(dx, -dy) for dx, dy in _GRID]
_BELOW = [(dx, -dy) for dx, dy in _GRID] + _GRID


def recent_window(index_df: pd.DataFrame, months: int = MONTHS) -> pd.Series:
    """The last ``months`` observations of the IDC Geral."""
    return index_df["index"].dropna().iloc[-months:]


def _fmt(value: float) -> str:
    return f"{value:.3f}".replace(".", ",")


def _overlaps(bbox, others, pad: float = 1.5) -> bool:
    return any(bbox.x0 < o.x1 + pad and bbox.x1 > o.x0 - pad and bbox.y0 < o.y1 + pad and bbox.y1 > o.y0 - pad for o in others)


def _inside(bbox, frame, pad: float = 2.0) -> bool:
    return bbox.x0 >= frame.x0 + pad and bbox.x1 <= frame.x1 - pad and bbox.y0 >= frame.y0 + pad and bbox.y1 <= frame.y1 - pad


def _crosses(bbox, lines, pad: float = 1.0) -> bool:
    return any(((pts[:, 0] > bbox.x0 - pad) & (pts[:, 0] < bbox.x1 + pad) & (pts[:, 1] > bbox.y0 - pad) & (pts[:, 1] < bbox.y1 + pad)).any()
               for pts in lines)


def _leader_blocked(ax, x, y, bbox, obstacles, lines=()) -> bool:
    """True when the leader line from the point to the label passes over another label (or marker, or the legend),
    or crosses a line away from its own point."""
    start = ax.transData.transform((mdates.date2num(x), y))
    end = np.array([np.clip(start[0], bbox.x0, bbox.x1), np.clip(start[1], bbox.y0, bbox.y1)])
    samples = np.array([start + (end - start) * t for t in np.linspace(0, 1, 30)])
    others = [o for o in obstacles if not o.contains(*start)]  # the marker of the point itself
    if any(o.contains(px, py) for o in others for px, py in samples):
        return True
    clear = 6 * ax.figure.dpi / 72  # the leader leaves the point on its own line: ignore its first points
    away = samples[np.hypot(*(samples - start).T) > clear]
    return any((np.hypot(*(pts[:, None, :] - away[None, :, :]).transpose(2, 0, 1)) < 1.5).any() for pts in lines) if len(away) else False


_OTHER_SERIES_CLEARANCE_PT = 6  # least distance from a label with a leader line to the lines of the other series


def _distance_to_box(bbox, points: np.ndarray) -> np.ndarray:
    """Distance (pixels) from each point to the nearest edge of ``bbox`` (0 inside it)."""
    dx = np.maximum(np.maximum(bbox.x0 - points[:, 0], points[:, 0] - bbox.x1), 0)
    dy = np.maximum(np.maximum(bbox.y0 - points[:, 1], points[:, 1] - bbox.y1), 0)
    return np.hypot(dx, dy)


def _closer_to_other_series(ax, x, y, bbox, lines, far: bool = False) -> bool:
    """True when the label would be read as belonging to another series.

    A reader matches a value with the nearest line, so a label next to its point must be clearly nearer its own
    point or its own line (the one through the point) than any other line.  A label away from its point is tied to
    it by its leader line, but it must still keep clear of the other lines (``_OTHER_SERIES_CLEARANCE_PT``).
    """
    anchor = ax.transData.transform((mdates.date2num(x), y))
    own = float(_distance_to_box(bbox, anchor[None, :])[0])
    others = []
    for pts in lines:
        if np.hypot(*(pts - anchor).T).min() <= 2:  # the line of the point itself
            own = min(own, float(_distance_to_box(bbox, pts).min()))
        else:
            others.append(pts)
    if far:
        clearance = _OTHER_SERIES_CLEARANCE_PT * ax.figure.dpi / 72
        return any(_distance_to_box(bbox, pts).min() < clearance for pts in others)
    margin = 4 * ax.figure.dpi / 72
    return any(_distance_to_box(bbox, pts).min() < max(own * 1.5, own + margin) for pts in others)


def _options(ax, renderer, x, y, text, color, candidates, obstacles, lines, fontsize: float = 8.5, associate: bool = False):
    """Labels at every candidate offset inside the axes and clear of ``obstacles`` and of the ``lines``, nearest first.

    Each label is drawn when yielded; the caller removes the ones it does not keep.  The text extent excludes the
    white box around the label and the lines are 2 pt wide, so the clearance covers both (in pixels at the figure
    resolution).  With ``associate``, a label next to its point must also be clearly nearer its own series than any
    other one; a label away from its point is tied to it by its leader line, which crosses no other line.
    """
    frame = ax.get_window_extent(renderer)
    clearance = (_LABEL_BOX["pad"] + 1.0 + 1.0) * ax.figure.dpi / 72
    for dx, dy in candidates:
        far = _distance((dx, dy)) > _LEADER_PT
        label = ax.annotate(text, xy=(x, y), xytext=(dx, dy), textcoords="offset points", ha="center",
                            va="bottom" if dy > 0 else "top", fontsize=fontsize, color=color, zorder=8, bbox=_LABEL_BOX,
                            arrowprops=dict(arrowstyle="-", color=color, linewidth=0.6, shrinkA=0, shrinkB=3) if far else None)
        label.update_positions(renderer)
        bbox = Text.get_window_extent(label, renderer)  # the text only: a leader line ends on the point, by design
        if (_inside(bbox, frame) and not _overlaps(bbox, obstacles, clearance) and not _crosses(bbox, lines, clearance)
                and not (far and _leader_blocked(ax, x, y, bbox, obstacles, lines))
                and not (associate and _closer_to_other_series(ax, x, y, bbox, lines, far))):
            label.offset, label.far, label.text_bbox = _distance((dx, dy)), far, bbox
            yield label
        label.remove()


def place_month(ax, renderer, t, points, obstacles, lines, *, fmt=_fmt, single=None, fontsize: float = 8.5,
                figure: str = "index_12m.png", above=None, below=None) -> list:
    """Labels of the values of one month: the upper one above its point, the lower one below (when they fit).

    ``points`` holds one or two ``(value, color)`` pairs, sorted by value.  The two labels are placed together, so
    that the first one never takes the only free room of the second (e.g. when both series reach the same peak).
    ``single`` is the order of the candidate offsets of a lone label (above first by default); ``above`` and
    ``below`` replace the candidate offsets of the upper and lower labels.
    """
    above, below = above or _ABOVE, below or _BELOW
    if len(points) == 1:
        (y, color), = points
        for label in _options(ax, renderer, t, y, fmt(y), color, single or above + below, obstacles, lines, fontsize):
            obstacles.append(label.text_bbox)
            return [label]
        raise LabelLayoutError(f"{figure}: no free position for the label {fmt(y)} of {t:%Y-%m}")
    (low_y, low_c), (high_y, high_c) = points
    for high in _options(ax, renderer, t, high_y, fmt(high_y), high_c, above, obstacles, lines, fontsize):
        for low in _options(ax, renderer, t, low_y, fmt(low_y), low_c, below, obstacles + [high.text_bbox], lines, fontsize):
            if high.far and _leader_blocked(ax, t, high_y, high.text_bbox, [low.text_bbox]):
                continue
            obstacles += [high.text_bbox, low.text_bbox]
            return [high, low]
    raise LabelLayoutError(f"{figure}: no free position for the labels of {t:%Y-%m}")


def marker_boxes(ax, xs, ys, radius: float = 3.0):
    points = ax.transData.transform(np.column_stack([mdates.date2num(xs), ys]))
    return [Bbox([[px - radius, py - radius], [px + radius, py + radius]]) for px, py in points]


def line_samples(ax, xs, ys, per_segment: int = 40) -> np.ndarray:
    """Points along the drawn line, in display coordinates."""
    points = ax.transData.transform(np.column_stack([mdates.date2num(xs), ys]))
    steps = np.linspace(0, 1, per_segment, endpoint=False)
    samples = [a + (b - a) * t for a, b in zip(points[:-1], points[1:]) for t in steps]
    return np.array(samples + [points[-1]])


def _draw(series: list[tuple[str, pd.Series, str]], height: float, months: int):
    """The figure at ``height`` with every value labelled; raises ``LabelLayoutError`` when a label does not fit."""
    from src.plot import _style_ax  # the same look as the other IDC figures

    geral = series[0][1]
    fig, ax = plt.subplots(figsize=(6.5, height))
    for name, s, color in series:
        ax.plot(s.index, s.values, color=color, linewidth=2.0, marker="o", markersize=4, label=name, zorder=4)
    _style_ax(ax, ylabel="Índice [0 – 1]")
    values = np.concatenate([s.values for _, s, _ in series])
    spread = max(values.max() - values.min(), 0.02)
    ax.set_ylim(values.min() - 0.30 * spread, values.max() + 0.30 * spread)
    ax.set_xlim(geral.index[0] - pd.DateOffset(days=20), geral.index[-1] + pd.DateOffset(days=20))
    ax.set_xticks(geral.index)
    ax.set_xticklabels([f"{_MES[t.month]}\n{t.year}" if t.month == 1 or t == geral.index[0] else _MES[t.month] for t in geral.index])
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.2f}".replace(".", ",")))
    ax.set_title(f"IDC nos últimos {months} meses")
    legend = ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=len(series), frameon=False)
    fig.tight_layout()

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    obstacles = [legend.get_window_extent(renderer)]
    lines = [line_samples(ax, s.index, s.values) for _, s, _ in series]
    for _, s, _ in series:
        obstacles += marker_boxes(ax, s.index, s.values)
    labels = []
    try:
        for t in geral.index:
            points = sorted(((s.loc[t], color) for _, s, color in series), key=lambda p: p[0])
            labels += place_month(ax, renderer, t, points, obstacles, lines)
    except LabelLayoutError:
        plt.close(fig)
        raise
    return fig, max(label.offset for label in labels)


def plot_recent(index_df: pd.DataFrame, low_income: Optional[pd.DataFrame], path: Path, *, months: int = MONTHS) -> None:
    """Save the figure of the last ``months`` months to ``path``; ``low_income`` adds the IDC Baixa Renda."""
    from src.plot import INDEX_COLOR

    geral = recent_window(index_df, months)
    series = [("IDC Geral", geral, INDEX_COLOR)]
    if low_income is not None:
        baixa = low_income["IDC"].reindex(geral.index)
        if baixa.notna().all():
            series.append(("IDC Baixa Renda (até 2 SM)", baixa, overlay.COLOR))
    # Keep the tallest height whose labels all stay near their points; failing that, the one with the nearest labels.
    best, failure = None, None
    for height in HEIGHTS:
        try:
            fig, farthest = _draw(series, height, months)
        except LabelLayoutError as exc:
            failure = exc
            continue
        if farthest <= _NEAR_PT:
            if best is not None:
                plt.close(best[0])
            best = (fig, farthest)
            break
        if best is None or farthest < best[1] - 1e-9:
            if best is not None:
                plt.close(best[0])
            best = (fig, farthest)
        else:
            plt.close(fig)
    if best is None:
        raise failure
    path.parent.mkdir(parents=True, exist_ok=True)
    best[0].savefig(path, dpi=200, bbox_inches="tight")
    plt.close(best[0])
