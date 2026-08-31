import unittest
from pathlib import Path

import pandas as pd

from src.compare_releases import compare_raw_vintages, compare_releases, format_text


ROOT = Path(__file__).resolve().parents[1]


def _raw_frame(dates, c_values):
    return pd.DataFrame({
        "comprometimento_renda": c_values,
        "inadimplencia": [4.0 + index for index in range(len(dates))],
        "total_credito_pf": [100.0] * len(dates),
        "cheque_especial": [5.0 + index for index in range(len(dates))],
        "credito_pessoal_nc": [10.0] * len(dates),
        "cartao_rotativo": [5.0] * len(dates),
        "cartao_parcelado": [5.0] * len(dates),
    }, index=pd.to_datetime(dates))


class CompareReleasesTests(unittest.TestCase):
    def test_only_new_observations_yield_no_revisions(self):
        previous = _raw_frame(["2024-01-01", "2024-02-01"], [20.0, 21.0])
        current = _raw_frame(
            ["2024-01-01", "2024-02-01", "2024-03-01"],
            [20.0, 21.0, 22.0],
        )

        comparison = compare_raw_vintages(previous, current, "202401", "202402")

        self.assertFalse(comparison.has_revisions)
        self.assertEqual(comparison.revisions, ())
        self.assertEqual(comparison.idc_revisions, ())
        self.assertTrue(pd.notna(comparison.previous_idc))
        self.assertTrue(pd.notna(comparison.current_vintage_idc))

    def test_new_observation_is_not_misclassified_as_revision(self):
        previous = _raw_frame(["2024-01-01", "2024-02-01"], [20.0, 21.0])
        current = _raw_frame(
            ["2024-01-01", "2024-02-01", "2024-03-01"],
            [20.0, 21.2, 22.0],
        )

        comparison = compare_raw_vintages(previous, current, "202401", "202402")

        self.assertEqual(len(comparison.revisions), 1)
        self.assertEqual(comparison.revisions[0].date, "2024-02-01")
        self.assertEqual(comparison.revisions[0].previous, 21.0)
        self.assertEqual(comparison.revisions[0].current, 21.2)
        self.assertEqual(comparison.previous_reference_date, "2024-02-01")

    def test_historical_backfill_is_classified_as_revision(self):
        dates = ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"]
        previous = _raw_frame(dates, [20.0, None, 22.0, 23.0])
        current = _raw_frame(dates, [20.0, 30.0, 22.0, 23.0])

        comparison = compare_raw_vintages(previous, current, "202401", "202402")

        backfill = next(
            revision for revision in comparison.revisions
            if revision.series == "comprometimento_renda"
            and revision.date == "2024-02-01"
        )
        self.assertIsNone(backfill.previous)
        self.assertEqual(backfill.current, 30.0)
        self.assertIsNone(backfill.delta)
        self.assertTrue(comparison.has_revisions)
        self.assertTrue(comparison.idc_revisions)
        self.assertIn("Alterações históricas entre safras: SIM", format_text(comparison))

    def test_new_value_after_previous_series_end_is_not_a_backfill(self):
        previous = _raw_frame(
            ["2024-01-01", "2024-02-01"],
            [20.0, 21.0],
        )
        current = _raw_frame(
            ["2024-01-01", "2024-02-01", "2024-03-01"],
            [20.0, 21.0, 22.0],
        )

        comparison = compare_raw_vintages(previous, current, "202401", "202402")

        self.assertFalse(any(
            revision.date == "2024-03-01" for revision in comparison.revisions
        ))

    def test_non_finite_reference_idc_is_rejected(self):
        previous = _raw_frame(["2024-01-01"], [20.0])
        current = _raw_frame(["2024-01-01", "2024-02-01"], [20.0, 21.0])

        with self.assertRaisesRegex(ValueError, "não produz IDC"):
            compare_raw_vintages(previous, current, "202401", "202402")

    def test_202607_audit_reproduces_the_known_bcb_revision(self):
        comparison = compare_releases("202607", ROOT / "data/raw")

        self.assertEqual(comparison.previous_period, "202606")
        self.assertEqual(comparison.previous_reference_date, "2026-04-01")
        self.assertTrue(all(
            revision.date >= "2014-01-01"
            for revision in comparison.idc_revisions
        ))
        self.assertAlmostEqual(comparison.previous_idc, 0.986495158597231)
        self.assertAlmostEqual(comparison.current_vintage_idc, 0.9903545343655705)
        self.assertEqual(
            [revision.date for revision in comparison.idc_revisions],
            ["2026-03-01", "2026-04-01"],
        )
        march, april = comparison.idc_revisions
        self.assertAlmostEqual(march.previous, 0.9603739531530681)
        self.assertAlmostEqual(march.current, 0.9602990338189121)
        self.assertAlmostEqual(march.delta, -0.0000749193341560)
        self.assertAlmostEqual(april.previous, 0.986495158597231)
        self.assertAlmostEqual(april.current, 0.9903545343655705)
        self.assertAlmostEqual(april.delta, 0.0038593757683395)
        april_c = next(
            revision for revision in comparison.revisions
            if revision.series == "comprometimento_renda" and revision.date == "2026-04-01"
        )
        self.assertEqual(april_c.previous, 28.2)
        self.assertEqual(april_c.current, 28.4)


if __name__ == "__main__":
    unittest.main()
