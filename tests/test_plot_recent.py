import itertools
import unittest

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import plot_overlay as overlay
from src import plot_recent as R
from src.plot import INDEX_COLOR, _apply_excel_style

MONTHS = pd.date_range("2025-09-01", periods=12, freq="MS")
# Hard cases of the 12-month window: both series at the same peak, crossings, equal values and steep V shapes.
GERAL = [0.960, 0.964, 0.960, 0.963, 0.996, 1.000, 0.960, 0.990, 0.983, 0.950, 0.963, 0.966]
BAIXA = [0.945, 0.970, 0.963, 0.975, 0.982, 1.000, 0.981, 0.999, 1.000, 0.941, 0.963, 0.974]


def series(geral=GERAL, baixa=BAIXA):
    out = [("IDC Geral", pd.Series(geral, MONTHS), INDEX_COLOR)]
    if baixa is not None:
        out.append(("IDC Baixa Renda", pd.Series(baixa, MONTHS), overlay.COLOR))
    return out


class RecentFigureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _apply_excel_style()

    def labels(self, data, height=5.0):
        fig, _ = R._draw(data, height, 12)
        ax = fig.axes[0]
        renderer = fig.canvas.get_renderer()
        texts = [t for t in ax.texts if hasattr(t, "text_bbox")]
        return fig, ax, renderer, texts

    def test_every_month_of_both_indices_is_labelled_with_its_value(self):
        fig, _, _, texts = self.labels(series())
        self.assertEqual(sorted(t.get_text() for t in texts), sorted(f"{v:.3f}".replace(".", ",") for v in GERAL + BAIXA))
        plt.close(fig)

    def test_no_label_overlaps_another_label_or_leaves_the_axes(self):
        fig, ax, renderer, texts = self.labels(series())
        frame = ax.get_window_extent(renderer)
        boxes = [t.text_bbox for t in texts]
        for a, b in itertools.combinations(boxes, 2):
            self.assertFalse(a.overlaps(b))
        for box in boxes:
            self.assertTrue(frame.x0 <= box.x0 and box.x1 <= frame.x1 and frame.y0 <= box.y0 and box.y1 <= frame.y1)
        plt.close(fig)

    def test_no_label_covers_a_line(self):
        fig, ax, _, texts = self.labels(series())
        lines = [R.line_samples(ax, s.index, s.values) for _, s, _ in series()]
        for t in texts:
            self.assertFalse(R._crosses(t.text_bbox, lines, 0.0), t.get_text())
        plt.close(fig)

    def test_the_general_index_alone_and_flat_series_are_drawn(self):
        for data in (series(baixa=None), series(geral=[0.5] * 12, baixa=[0.5] * 12)):
            fig, _ = R._draw(data, 4.6, 12)
            plt.close(fig)

    def test_the_figure_is_saved_from_the_index_files(self, tmp=None):
        import tempfile
        from pathlib import Path

        idx = pd.DataFrame({"index": [np.nan] * 3 + GERAL}, index=pd.date_range("2025-06-01", periods=15, freq="MS"))
        low = pd.DataFrame({"IDC": BAIXA}, index=MONTHS)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "index_12m.png"
            R.plot_recent(idx, low, path)
            self.assertTrue(path.stat().st_size > 0)
        self.assertEqual(list(R.recent_window(idx).index), list(MONTHS))


class SinceDecember2022FigureTests(unittest.TestCase):
    def test_the_index_figure_is_drawn_from_december_2022_with_both_programs(self):
        import tempfile
        from pathlib import Path

        from src import plot as P

        P._apply_excel_style()
        months = pd.date_range("2014-01-01", "2026-08-01", freq="MS")
        values = 0.5 + 0.45 * np.sin(np.linspace(0, 9, len(months)))
        idx = pd.DataFrame({"index": values}, index=months)
        low = pd.DataFrame({"IDC": np.clip(values + 0.02, 0, 1)}, index=months)
        original = P.FIGURES_DIR
        with tempfile.TemporaryDirectory() as folder:
            try:
                P.FIGURES_DIR = Path(folder)
                P._plot_index(idx, low, start=P.RECENT_START, filename="index_since_2022.png")
            finally:
                P.FIGURES_DIR = original
            self.assertTrue((Path(folder) / "index_since_2022.png").stat().st_size > 0)
        self.assertEqual(P.RECENT_START, pd.Timestamp("2022-12-01"))

    def test_turning_points_are_the_local_extremes_that_move_enough(self):
        from src import plot as P

        months = pd.date_range("2023-01-01", periods=13, freq="MS")
        s = pd.Series([0.5, 0.6, 0.7, 0.8, 0.7, 0.6, 0.5, 0.52, 0.51, 0.6, 0.7, 0.7, 0.8], months)
        self.assertEqual(P.turning_points(s), {months[3]: "max", months[6]: "min"})  # the 0,01 wiggle is ignored

    def test_only_the_hard_to_read_latest_points_are_chosen(self):
        from src import plot as P

        months = MONTHS[-6:]  # mar-2026 to ago-2026
        events = {"Novo\nDesenrola": pd.Timestamp("2026-05-01")}
        geral, baixa = pd.Series(GERAL, MONTHS), pd.Series(BAIXA, MONTHS)
        # The turns (mar, abr, jun), the event month and the last month; jul continues the rise.
        self.assertEqual([d.strftime("%Y-%m") for d in P._hard_to_read(geral, months, events)],
                         ["2026-03", "2026-04", "2026-05", "2026-06", "2026-08"])
        # 0,999 and 1,000 are read on the gridline of the maximum: never labelled.
        self.assertEqual([d.strftime("%Y-%m") for d in P._hard_to_read(baixa, months, events)], ["2026-03", "2026-06", "2026-08"])

    def test_ladder_labels_never_overlap_and_sit_on_their_month(self):
        from matplotlib.text import Text

        from src import plot as P

        P._apply_excel_style()
        months = MONTHS[-6:]
        fig, ax = plt.subplots(figsize=(6.5, 6.5))
        ax.plot(MONTHS, GERAL, color=INDEX_COLOR)
        ax.plot(MONTHS, BAIXA, color=overlay.COLOR)
        ax.set_ylim(0.85, 1.08)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        zone = []
        for d, g, b in zip(months, GERAL[-6:], BAIXA[-6:]):
            (lo, lc), (hi, hc) = sorted([(g, INDEX_COLOR), (b, overlay.COLOR)])
            zone.append((d, [(lo, lc, "below"), (hi, hc, "above")]))
        labels = P._ladder(ax, renderer, zone, 3, lambda y: P.num(y, ".3f"), max(GERAL[-6:] + BAIXA[-6:]), min(GERAL[-6:] + BAIXA[-6:]))
        self.assertEqual(len(labels), 12)
        boxes = [Text.get_window_extent(label, renderer) for label in labels]
        for a, b in itertools.combinations(boxes, 2):
            self.assertFalse(a.overlaps(b))
        for label, (date, _) in zip(labels, [z for z in zone for _ in (0, 1)]):
            self.assertAlmostEqual(label.xyann[0], mdates.date2num(date) if not isinstance(label.xyann[0], pd.Timestamp) else label.xyann[0])
        self.assertEqual(labels[0].get_text(), P.num(min(GERAL[-6], BAIXA[-6]), ".3f"))  # decimal comma, three decimals
        plt.close(fig)

if __name__ == "__main__":
    unittest.main()
