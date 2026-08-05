import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.download_bcb_release import _release_files, _validate_downloaded_file
from src.download_bcb_via_github import _copy_artifact_files, _select_run


class DownloadValidationTests(unittest.TestCase):
    def test_accepts_expected_signatures(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            xlsx = root / "release.xlsx"
            pdf = root / "release.pdf"
            xlsx.write_bytes(b"PK\x03\x04" + b"x" * 10_000)
            pdf.write_bytes(b"%PDF-" + b"x" * 10_000)

            _validate_downloaded_file(xlsx, xlsx.name)
            _validate_downloaded_file(pdf, pdf.name)

    def test_rejects_html_saved_as_xlsx(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "release.xlsx"
            path.write_bytes(b"<html" + b"x" * 10_000)

            with self.assertRaisesRegex(RuntimeError, "Conteudo invalido"):
                _validate_downloaded_file(path, path.name)


class WorkflowRunSelectionTests(unittest.TestCase):
    def test_selects_matching_period_ref_and_time(self):
        runs = [
            {
                "databaseId": 1,
                "displayTitle": "BCB release 202607",
                "headBranch": "main",
                "createdAt": "2026-08-04T20:00:00Z",
            },
            {
                "databaseId": 2,
                "displayTitle": "BCB release 202607",
                "headBranch": "main",
                "createdAt": "2026-08-04T22:00:00Z",
            },
            {
                "databaseId": 3,
                "displayTitle": "BCB release 202606",
                "headBranch": "main",
                "createdAt": "2026-08-04T22:05:00Z",
            },
        ]

        selected = _select_run(
            runs,
            period="202607",
            ref="main",
            not_before=datetime(2026, 8, 4, 21, tzinfo=timezone.utc),
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected["databaseId"], 2)


class ArtifactCopyTests(unittest.TestCase):
    def test_copies_both_validated_release_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "artifact"
            output = root / "output"
            artifact.mkdir()
            files = _release_files("202607")
            (artifact / files["table"]).write_bytes(b"PK\x03\x04" + b"x" * 10_000)
            (artifact / files["report"]).write_bytes(b"%PDF-" + b"x" * 10_000)

            _copy_artifact_files(
                artifact,
                output,
                "202607",
                overwrite=False,
            )

            for filename in files.values():
                self.assertTrue((output / "202607" / filename).is_file())


if __name__ == "__main__":
    unittest.main()
