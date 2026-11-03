import unittest
from pathlib import Path

import pandas as pd

import main
from src import low_income as LI
from synthetic import T1


def available_result() -> LI.Resultado:
    idx = pd.date_range("2012-07-01", T1, freq="MS")
    serie = pd.DataFrame({"I": 10.0, "Q": 26.5, "I_norm": 0.9, "Q_norm": 0.8, "C_norm": 1.0, "IDC": 0.9}, index=idx)
    return LI.Resultado("ok", t1=T1, serie=serie, conciliacao={"status": "ok", "status_Q": "alerta"})


class ReadmeBlockTests(unittest.TestCase):
    def test_available_index_is_summarised_in_a_table(self):
        block = main._readme_low_income_table(available_result())
        self.assertIn("| IDC Baixa Renda | — | **0,900** |", block)
        self.assertIn("| I — inadimplência 90+ dias (até 2 SM) | 10,0% | 0,900 |", block)
        self.assertIn("Último dado: dez-2016; série exibida desde mai-2015", block)

    def test_unavailable_index_says_why(self):
        block = main._readme_low_income_table(LI.Resultado("sem_cobertura", "SCR.data até jul-2026; mês de referência ago-2026", t1=T1))
        self.assertEqual(block, "IDC Baixa Renda não atualizado nesta edição: SCR.data até jul-2026; mês de referência ago-2026.")

    def test_console_message_flags_a_reconciliation_alert(self):
        self.assertIn("com alerta de conciliação", main._low_income_message(available_result()))
        self.assertIn("não atualizado nesta edição", main._low_income_message(LI.Resultado("bloqueio", "diverge", t1=T1)))

    def test_the_managed_block_of_the_readme_is_replaced_and_the_rest_is_kept(self):
        readme = f"antes\n{main.README_LOW_INCOME_START}\nvelho\n{main.README_LOW_INCOME_END}\ndepois\n"
        new = main._replace_readme_block(readme, main.README_LOW_INCOME_START, main.README_LOW_INCOME_END, "novo")
        self.assertEqual(new, f"antes\n{main.README_LOW_INCOME_START}\nnovo\n{main.README_LOW_INCOME_END}\ndepois\n")

    def test_the_repository_readme_has_the_managed_block(self):
        text = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
        self.assertIn(main.README_LOW_INCOME_START, text)
        self.assertIn(main.README_LOW_INCOME_END, text)



class WorkbookTests(unittest.TestCase):
    def setUp(self):
        idx = pd.date_range("2011-03-01", T1, freq="MS")
        self.components = pd.DataFrame({"C": 25.0, "I": 6.0, "Q": 0.245}, index=idx)
        self.index_df = pd.DataFrame({"C_norm": 1.0, "I_norm": 1.0, "Q_norm": 0.5, "index": 0.8}, index=idx)
        self.index_df.loc[self.index_df.index < "2014-01-01"] = float("nan")

    def test_the_report_sheet_has_the_series_of_the_report(self):
        table = main._report_series(self.components, self.index_df, available_result())
        self.assertEqual(list(table.columns)[:2], ["IDC Geral", "IDC Baixa Renda"])
        self.assertEqual(table.loc["2016-12-01", "Q — Crédito oneroso no crédito livre PF (%)"], 24.5)  # in %, as in the report
        self.assertTrue(pd.isna(table.loc["2015-04-01", "IDC Baixa Renda"]))  # shown from mai-2015, as in the report
        self.assertEqual(table.loc["2015-05-01", "IDC Baixa Renda"], 0.9)
        self.assertEqual(table.loc["2012-07-01", "I — Inadimplência 90+ dias, baixa renda (%)"], 10.0)

    def test_an_unavailable_low_income_index_leaves_its_columns_empty_and_says_why(self):
        sem = LI.Resultado("sem_cobertura", "SCR.data até jul-2026", t1=T1)
        table = main._report_series(self.components, self.index_df, sem)
        self.assertTrue(table["IDC Baixa Renda"].isna().all())
        self.assertIsNone(main._low_income_sheet(sem))
        self.assertIn("Não atualizado nesta edição: SCR.data até jul-2026.", main._workbook_notes("202610", sem).to_string())

    def test_the_workbook_opens_on_the_report_sheet(self):
        import tempfile

        result = available_result()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "idc_data.xlsx"
            main._write_excel_safely(self.index_df, self.components, path, report=main._report_series(self.components, self.index_df, result),
                                     low=main._low_income_sheet(result), notes=main._workbook_notes("202610", result))
            names = pd.ExcelFile(path).sheet_names
        self.assertEqual(names, [main.REPORT_SHEET, main.NOTES_SHEET, "IDC e Normalizados", "Componentes Brutos", main.LOW_INCOME_SHEET])

    def test_the_data_folder_has_its_guide(self):
        guide = (Path(__file__).resolve().parents[1] / "data" / "README.md").read_text(encoding="utf-8")
        self.assertIn("Séries do relatório", guide)
        for name in ("idc_data.xlsx", "index.csv", "components_raw.csv", "low_income_idc.csv", "series_raw.csv"):
            self.assertIn(name, guide)


if __name__ == "__main__":
    unittest.main()
