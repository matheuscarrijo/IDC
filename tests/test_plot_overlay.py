import unittest

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import plot_overlay as overlay


class EventLabelTests(unittest.TestCase):
    def setUp(self):
        self.idx = pd.date_range("2024-01-01", periods=24, freq="MS")
        self.fig, self.ax = plt.subplots()
        self.ax.plot(self.idx, 20.0 + 0.1 * np.arange(24))
        self.ax.set_ylim(18, 24)
        self.event = self.ax.text(self.idx[12], 19.5, "Evento", transform=self.ax.transData)  # 1.7 below the total (21.2)
        self.value_label = self.ax.annotate("21.2", xy=(self.idx[12], 21.2), xytext=(0, -6), textcoords="offset points")
        self.group = pd.Series(23.0 + 0.1 * np.arange(24), self.idx)  # above the total: widens the top of the y range

    def tearDown(self):
        plt.close(self.fig)

    def pixels_below_total(self) -> float:
        x, y = self.event.convert_xunits(self.event.get_position()[0]), self.event.get_position()[1]
        total_at_event = self.ax.get_lines()[0].get_ydata()[12]
        return self.ax.transData.transform((x, total_at_event))[1] - self.ax.transData.transform((x, y))[1]

    def test_event_label_keeps_its_pixel_distance_to_the_total_series_when_the_range_widens(self):
        self.fig.canvas.draw()
        before = self.pixels_below_total()
        overlay._dashed(self.ax, self.group)
        self.fig.canvas.draw()
        self.assertGreater(self.ax.get_ylim()[1], 24)  # the range did widen
        self.assertAlmostEqual(self.pixels_below_total(), before, places=6)

    def test_value_labels_are_left_where_they_are(self):
        position = self.value_label.xy
        overlay._dashed(self.ax, self.group)
        self.assertEqual(self.value_label.xy, position)

    def test_event_label_stays_inside_the_axes(self):
        self.event.set_y(18.3)  # near the bottom edge
        overlay._dashed(self.ax, pd.Series(10.0 + 0.2 * np.arange(24), self.idx))  # widens the range downwards too
        low, high = self.ax.get_ylim()
        self.assertGreaterEqual(self.event.get_position()[1], low + 0.10 * (high - low) - 1e-9)

    def test_nothing_moves_when_the_range_is_unchanged(self):
        inside = pd.Series(21.0 + 0.05 * np.arange(24), self.idx)
        overlay._dashed(self.ax, inside)
        self.assertEqual(self.ax.get_ylim(), (18, 24))
        self.assertEqual(self.event.get_position()[1], 19.5)


if __name__ == "__main__":
    unittest.main()
