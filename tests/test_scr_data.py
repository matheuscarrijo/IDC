import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from src import scr_data


def fake_results(year: int, months: int = 12, scale: float = 1.0):
    """What ``_extract_year`` returns: one tuple (member, aggregates by lens, zip date) per month."""
    results = []
    for m in range(1, months + 1):
        month = pd.Timestamp(year, m, 1)
        lenses = {}
        for lens in scr_data.LENS_FIELDS:
            rows = [{"data_base": month, "unidade": u, "oneroso": o, "carteira": 100.0 * scale, "inad": 5.0 * scale, "ap": 0.0, "v1590": 0.0, "a90": 0.0}
                    for u in ("A", "B") for o in (False, True)]
            lenses[lens] = pd.DataFrame(rows)
        results.append((f"scrdata_{year}{m:02d}.csv", lenses, (2026, 3, 24, 10, 0, 0)))
    return results


class RefreshTests(unittest.TestCase):
    def test_years_to_refresh_selects_missing_changed_and_unpublished_years(self):
        vintage = pd.DataFrame({"member": ["scrdata_202501.csv", "scrdata_202601.csv"], "zip_year": [2025, 2026],
                                "zip_last_modified": ["Mon, 01 Jan 2026", "Tue, 02 Jun 2026"], "generated": ["x", "y"]})
        published = {2025: "Mon, 01 Jan 2026", 2026: "Wed, 07 Oct 2026", 2027: None, 2024: "Fri, 05 Jan 2024"}
        self.assertEqual(scr_data.years_to_refresh(vintage, published), [2024, 2026])
        self.assertEqual(scr_data.years_to_refresh(vintage, published, full=True), [2024, 2025, 2026])
        self.assertEqual(scr_data.years_to_refresh(vintage.iloc[0:0], {2025: "x"}), [2025])

    def test_refresh_downloads_only_the_years_that_changed_and_replaces_their_rows(self):
        stamps = {2024: "Mon, 01 Jan 2024", 2025: "Mon, 01 Jan 2025"}
        calls = []

        def extract(year, workdir, workers, log):
            calls.append(year)
            return fake_results(year, scale=2.0 if stamps[year].endswith("v2") else 1.0), {"last_modified": stamps[year]}

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(scr_data, "last_modified", side_effect=lambda year: stamps.get(year)), \
                mock.patch.object(scr_data, "_extract_year", side_effect=extract):
            out, work = Path(tmp) / "scr", Path(tmp) / "zip"
            log = lambda *_: None  # noqa: E731
            vintage = scr_data.refresh(out, work, years=[2024, 2025], log=log)
            self.assertEqual(calls, [2024, 2025])
            self.assertEqual(len(vintage), 24)

            scr_data.refresh(out, work, years=[2024, 2025], log=log)  # nothing changed on the server
            self.assertEqual(calls, [2024, 2025])

            stamps[2025] = "Tue, 07 Oct 2025 v2"
            vintage = scr_data.refresh(out, work, years=[2024, 2025], log=log)
            self.assertEqual(calls, [2024, 2025, 2025])
            faixa = scr_data.load_aggregates(out)["faixa"]
            by_year = faixa.assign(ano=pd.to_datetime(faixa["data_base"]).dt.year).groupby("ano")["carteira"].sum()
            self.assertAlmostEqual(by_year[2024], 12 * 4 * 100.0)  # untouched
            self.assertAlmostEqual(by_year[2025], 12 * 4 * 200.0)  # replaced by the new version
            self.assertEqual(len(vintage), 24)
            self.assertEqual(set(vintage.loc[vintage["zip_year"] == 2025, "zip_last_modified"]), {stamps[2025]})
            self.assertFalse(list(out.glob("*.tmp")))

    def test_refresh_keeps_stored_years_when_the_server_cannot_be_asked(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, work = Path(tmp) / "scr", Path(tmp) / "zip"
            with mock.patch.object(scr_data, "last_modified", return_value="stamp"), \
                    mock.patch.object(scr_data, "_extract_year", side_effect=lambda y, w, k, l: (fake_results(y, 3), {"last_modified": "stamp"})):
                scr_data.refresh(out, work, years=[2025], log=lambda *_: None)
            with mock.patch.object(scr_data, "last_modified", side_effect=RuntimeError("sem rede")):
                vintage = scr_data.refresh(out, work, years=[2025], log=lambda *_: None)
            self.assertEqual(len(vintage), 3)
            with mock.patch.object(scr_data, "last_modified", side_effect=RuntimeError("sem rede")):
                with self.assertRaisesRegex(RuntimeError, "sem rede"):
                    scr_data.refresh(out, work, years=[2024], log=lambda *_: None)  # a year never downloaded cannot be skipped

    def test_unpublished_year_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(scr_data, "last_modified", return_value=None):
            vintage = scr_data.refresh(Path(tmp) / "scr", Path(tmp) / "zip", years=[2027], log=lambda *_: None)
            self.assertEqual(len(vintage), 0)


if __name__ == "__main__":
    unittest.main()
