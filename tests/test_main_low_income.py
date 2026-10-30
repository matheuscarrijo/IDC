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
        self.assertIn("| IDC baixa renda | — | **0,900** |", block)
        self.assertIn("| I — inadimplência 90+ dias (até 2 SM) | 10,0% | 0,900 |", block)
        self.assertIn("Último dado: dez-2016; série exibida desde mai-2015", block)

    def test_unavailable_index_says_why(self):
        block = main._readme_low_income_table(LI.Resultado("sem_cobertura", "SCR.data até jul-2026; mês de referência ago-2026", t1=T1))
        self.assertEqual(block, "IDC para baixa renda não atualizado nesta edição: SCR.data até jul-2026; mês de referência ago-2026.")

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


if __name__ == "__main__":
    unittest.main()
