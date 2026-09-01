import unittest
from pathlib import Path

import pandas as pd

from src.compare_releases import (
    IDCRevision,
    PUBLIC_REVISION_MATERIALITY_THRESHOLD,
    ReleaseComparison,
    RevisionEditorialContext,
    assess_revision_materiality,
    compare_raw_vintages,
    compare_release_vintages,
    compare_releases,
    format_text,
    idc_revision_deltas_by_date,
    quantify_revision_magnitude,
)


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


def _comparison_with_idc_delta(delta):
    return ReleaseComparison(
        previous_period="202601",
        current_period="202602",
        previous_reference_date="2026-01-01",
        previous_idc=1.0,
        current_vintage_idc=1.0 + delta,
        idc_revision=delta,
        idc_revisions=(IDCRevision(
            date="2026-01-01",
            previous=1.0,
            current=1.0 + delta,
            delta=delta,
        ),),
        components=(),
        revisions=(),
    )


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

    def test_routine_public_disclosure_requires_magnitude_and_editorial_relevance(self):
        facts = quantify_revision_magnitude(_comparison_with_idc_delta(0.012))

        magnitude_only = assess_revision_materiality(facts)
        magnitude_and_relevance = assess_revision_materiality(
            facts,
            RevisionEditorialContext(affects_relevant_element=True),
        )

        self.assertTrue(facts.meets_threshold)
        self.assertFalse(magnitude_only.is_publicly_material)
        self.assertFalse(magnitude_only.routine_rule_met)
        self.assertTrue(magnitude_and_relevance.is_publicly_material)
        self.assertTrue(magnitude_and_relevance.routine_rule_met)

    def test_threshold_is_inclusive_but_does_not_replace_editorial_relevance(self):
        facts = quantify_revision_magnitude(
            _comparison_with_idc_delta(PUBLIC_REVISION_MATERIALITY_THRESHOLD)
        )

        decision = assess_revision_materiality(
            facts,
            RevisionEditorialContext(affects_relevant_element=True),
        )

        self.assertTrue(facts.meets_threshold)
        self.assertTrue(decision.is_publicly_material)

    def test_small_revision_is_not_material_even_when_editorially_relevant(self):
        facts = quantify_revision_magnitude(_comparison_with_idc_delta(0.003859))

        decision = assess_revision_materiality(
            facts,
            RevisionEditorialContext(affects_relevant_element=True),
        )

        self.assertFalse(facts.meets_threshold)
        self.assertFalse(decision.routine_rule_met)
        self.assertFalse(decision.is_publicly_material)

    def test_qualitative_overrides_bypass_numeric_threshold(self):
        facts = quantify_revision_magnitude(_comparison_with_idc_delta(0.001))
        override_fields = (
            "reverses_sign",
            "changes_record",
            "invalidates_published_statement",
            "changes_idc_methodology",
            "changes_source_or_coverage",
            "corrects_relevant_error",
        )

        for field in override_fields:
            with self.subTest(field=field):
                context = RevisionEditorialContext(**{field: True})
                decision = assess_revision_materiality(facts, context)
                self.assertTrue(decision.is_publicly_material)
                self.assertFalse(decision.routine_rule_met)
                self.assertEqual(decision.qualitative_overrides, (field,))

    def test_accumulated_net_revision_since_last_disclosure_can_meet_threshold(self):
        facts = quantify_revision_magnitude(
            _comparison_with_idc_delta(0.004),
            cumulative_idc_deltas_since_last_disclosure={
                "2025-12-01": -0.010,
                "2026-01-01": 0.006,
            },
        )

        decision = assess_revision_materiality(
            facts,
            RevisionEditorialContext(affects_relevant_element=True),
        )

        self.assertAlmostEqual(facts.largest_current_absolute_delta, 0.004)
        self.assertAlmostEqual(facts.largest_cumulative_absolute_delta, 0.010)
        self.assertAlmostEqual(facts.effective_absolute_delta, 0.010)
        self.assertTrue(facts.meets_threshold)
        self.assertTrue(decision.is_publicly_material)

    def test_explicit_vintages_produce_net_deltas_for_accumulated_check(self):
        current_comparison = compare_releases("202608", ROOT / "data/raw")
        accumulated_comparison = compare_release_vintages(
            "202606",
            "202608",
            ROOT / "data/raw",
        )
        accumulated_deltas = idc_revision_deltas_by_date(accumulated_comparison)
        facts = quantify_revision_magnitude(
            current_comparison,
            cumulative_idc_deltas_since_last_disclosure=accumulated_deltas,
        )

        self.assertEqual(accumulated_comparison.previous_period, "202606")
        self.assertEqual(accumulated_comparison.current_period, "202608")
        self.assertEqual(
            accumulated_deltas,
            {
                revision.date: revision.delta
                for revision in accumulated_comparison.idc_revisions
            },
        )
        self.assertAlmostEqual(
            facts.largest_cumulative_absolute_delta,
            0.0039362272528524755,
        )
        self.assertFalse(facts.meets_threshold)

    def test_explicit_vintage_comparison_validates_order_and_presence(self):
        with self.assertRaisesRegex(ValueError, "safra-base"):
            compare_release_vintages("202608", "202607", ROOT / "data/raw")
        with self.assertRaisesRegex(FileNotFoundError, "202599"):
            compare_release_vintages("202599", "202608", ROOT / "data/raw")

    def test_broad_202606_reprocessing_meets_strict_routine_rule(self):
        comparison = compare_releases("202606", ROOT / "data/raw")
        facts = quantify_revision_magnitude(comparison)
        decision = assess_revision_materiality(
            facts,
            RevisionEditorialContext(affects_relevant_element=True),
        )

        self.assertEqual(len(comparison.revisions), 1056)
        self.assertEqual(len(comparison.idc_revisions), 146)
        self.assertLess(
            abs(comparison.idc_revision),
            PUBLIC_REVISION_MATERIALITY_THRESHOLD,
        )
        self.assertAlmostEqual(facts.largest_current_absolute_delta, 0.0682798543774144)
        self.assertTrue(facts.meets_threshold)
        self.assertTrue(decision.routine_rule_met)
        self.assertTrue(decision.is_publicly_material)
        self.assertEqual(decision.qualitative_overrides, ())

    def test_materiality_layer_does_not_change_audit_or_serialized_output(self):
        comparison = compare_releases("202607", ROOT / "data/raw")
        before = comparison.to_dict()

        facts = quantify_revision_magnitude(comparison)
        decision = assess_revision_materiality(
            facts,
            RevisionEditorialContext(affects_relevant_element=True),
        )

        self.assertTrue(comparison.has_revisions)
        self.assertFalse(decision.is_publicly_material)
        self.assertEqual(comparison.to_dict(), before)
        self.assertNotIn("materiality", before)
        self.assertNotIn("is_publicly_material", before)

    def test_materiality_inputs_must_be_finite_and_threshold_positive(self):
        comparison = _comparison_with_idc_delta(0.001)

        with self.assertRaisesRegex(ValueError, "limiar"):
            quantify_revision_magnitude(comparison, threshold=0.0)
        with self.assertRaisesRegex(ValueError, "acumuladas"):
            quantify_revision_magnitude(
                comparison,
                cumulative_idc_deltas_since_last_disclosure={"2026-01-01": float("nan")},
            )


if __name__ == "__main__":
    unittest.main()
