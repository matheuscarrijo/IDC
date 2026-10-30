import re
import unittest
from pathlib import Path

import pandas as pd

from src import build_appendix as BA

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "filled_report.tex"
PREAMBLE = r"""\documentclass[11pt,a4paper]{article}
\onehalfspacing
\fancyhead[L]{\small\itshape \reporttitle}
% =============================================================================
%   DADOS DO RELATÓRIO — editar a cada atualização mensal
% =============================================================================
"""


class VintageGuardTests(unittest.TestCase):
    def setUp(self):
        self.meses = pd.date_range("2024-01-01", "2026-07-01", freq="MS")
        self.sgs = pd.DataFrame({"C_total": 28.0, "inad_total": 7.0, "saldo_total": 2_500_000.0}, index=self.meses)
        self.raw = pd.DataFrame({"comprometimento_renda": 28.0, "inadimplencia": 7.0, "total_credito_pf": 2_500_000.0}, index=self.meses)
        self.t1 = self.meses[-1]

    def test_same_vintage_passes_despite_the_rounding_of_the_workbook(self):
        self.sgs["C_total"] += 0.04  # 2 decimals in the API against 1 decimal in the workbook
        self.assertEqual(BA.check_sgs_vintage(self.sgs, self.raw, self.t1), [])

    def test_a_revised_series_is_reported_with_the_month_and_both_values(self):
        self.sgs.loc[self.t1, "C_total"] = 28.83
        problems = BA.check_sgs_vintage(self.sgs, self.raw, self.t1)
        self.assertEqual(len(problems), 1)
        self.assertIn("C_total em jul-2026", problems[0])
        self.assertIn("28.83", problems[0])

    def test_months_outside_the_window_are_ignored(self):
        self.sgs.loc["2024-01-01", "saldo_total"] += 5_000
        self.assertEqual(BA.check_sgs_vintage(self.sgs, self.raw, self.t1, months=12), [])


class ReportDataTests(unittest.TestCase):
    def test_macros_are_read_from_the_filled_report(self):
        macros = BA.report_macros(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual((macros["mesref"], macros["competencia"], macros["reportdate"]), ("jul-2026", "202609", "Setembro de 2026"))

    def test_an_unfilled_report_is_rejected(self):
        tex = FIXTURE.read_text(encoding="utf-8").replace(r"\newcommand{\mesref}{jul-2026}", r"\newcommand{\mesref}{\placeholder{mmm-AAAA}}")
        with self.assertRaisesRegex(ValueError, "preenchido"):
            BA.report_macros(tex)

    def test_preamble_is_the_one_of_the_report_with_the_appendix_header_and_tighter_spacing(self):
        head = BA.preamble(PREAMBLE + r"\begin{document}")
        self.assertIn(r"\setstretch{1.2}", head)
        self.assertNotIn(r"\onehalfspacing", head)
        self.assertIn("Apêndice Estatístico}", head)
        self.assertNotIn("DADOS DO RELATÓRIO", head)
        self.assertNotIn(r"\begin{document}", head)

    def test_a_preamble_outside_the_template_pattern_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "fora do padrão"):
            BA.preamble(PREAMBLE.replace(r"\fancyhead[L]{\small\itshape \reporttitle}", ""))


SGS = ROOT / "data/processed/sgs_snapshot.csv"
HAS_DATA = all(p.exists() for p in (SGS, ROOT / "data/processed/scr/scr_faixa.csv", ROOT / "data/external/cri_faixa_ref202504.csv",
                                    ROOT / "data/raw/202609/202609_Tabelas_de_estatisticas_monetarias_e_de_credito.xlsx"))


@unittest.skipUnless(HAS_DATA, "requires data/processed/sgs_snapshot.csv, data/processed/scr/ and the 202609 workbook")
class DocumentTests(unittest.TestCase):
    def test_document_has_cover_contents_and_all_seven_sections_and_never_the_draft_mark_by_default(self):
        import os

        cwd = os.getcwd()
        os.chdir(ROOT)  # the loaders use paths relative to the repository root
        try:
            d = BA.load_data("202609", update_sgs=False, ignore_vintage=True, log=lambda *_: None, reference=pd.Timestamp("2026-07-01"))
        finally:
            os.chdir(cwd)
        text = BA.document(d, FIXTURE.read_text(encoding="utf-8").replace(r"\documentclass[11pt,a4paper]{article}", PREAMBLE + r"\usepackage{hyperref}"))
        self.assertEqual(len(re.findall(r"\\section\{", text)), 7)
        self.assertIn(r"\tableofcontents", text)
        self.assertIn(r"Apêndice Estatístico --- Divulgação \mespublicacao; competência \mesreferencia", text)
        self.assertNotIn("Versão para discussão", text)
        draft = BA.document(d, FIXTURE.read_text(encoding="utf-8").replace(r"\documentclass[11pt,a4paper]{article}", PREAMBLE), draft=True)
        self.assertIn("Versão para discussão", draft)
        labels = re.findall(r"\\label\{([^}]+)\}", text)
        self.assertEqual(len(labels), len(set(labels)))
        self.assertLessEqual(set(re.findall(r"\\ref\{([^}]+)\}", text)), set(labels))

    def test_a_report_of_another_month_is_refused(self):
        import os

        cwd = os.getcwd()
        os.chdir(ROOT)
        try:
            d = BA.load_data("202609", update_sgs=False, ignore_vintage=True, log=lambda *_: None, reference=pd.Timestamp("2026-07-01"))
        finally:
            os.chdir(cwd)
        other = FIXTURE.read_text(encoding="utf-8").replace(r"\newcommand{\mesref}{jul-2026}", r"\newcommand{\mesref}{ago-2026}")
        with self.assertRaisesRegex(ValueError, "ago-2026"):
            BA.document(d, other.replace(r"\documentclass[11pt,a4paper]{article}", PREAMBLE))


if __name__ == "__main__":
    unittest.main()
