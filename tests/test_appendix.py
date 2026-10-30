import re
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src import appendix_data as AP
from src import appendix_document as DOC
from src import appendix_text as TA
from src import lenses as L
from src.income_idc import BAIXA_RENDA, c_normalizado, indice_por_faixa
from src.normalize import expanding_minmax
from src.ref_check import avaliar_c_nacional
from src.pt_format import tabela_latex
from synthetic import componentes, faixa_bruta

ROOT = Path(__file__).resolve().parents[1]


class SubstituirVariacoesTests(unittest.TestCase):
    def setUp(self):
        self.meses = pd.date_range("2015-02-01", periods=12, freq="MS")  # Feb-2015 .. Jan-2016: the display starts in May-2015
        self.c = pd.Series(np.linspace(0.2, 0.9, 12), self.meses)
        self.ger_i = pd.Series(5.0 + 0.1 * np.arange(12) + 0.4 * np.sin(np.arange(12)), self.meses)  # not monotone, so the normalisation moves
        self.ger_q = pd.Series(20.0 + 0.15 * np.arange(12) + 0.2 * (np.arange(12) % 3), self.meses)
        self.low = pd.DataFrame({"I": self.ger_i.values + np.where(np.arange(12) >= 3, 4.0, 0.0), "Q": self.ger_q.values + 3}, self.meses)  # jump of +4 in the 4th month
        self.low["IDC"] = (self.c + expanding_minmax(self.low["I"]) + expanding_minmax(self.low["Q"])) / 3

    def test_no_month_replaced_returns_the_observed_index(self):
        alt = AP._substituir_variacoes(self.low, self.ger_i, self.ger_q, self.c, [])
        pd.testing.assert_series_equal(alt, self.low["IDC"], check_names=False)

    def test_replacing_the_jump_month_removes_the_jump(self):
        alt = AP._substituir_variacoes(self.low, self.ger_i, self.ger_q, self.c, [self.meses[3]])
        esperado = (self.c + expanding_minmax(self.ger_i) + expanding_minmax(self.low["Q"])) / 3
        pd.testing.assert_series_equal(alt, esperado, check_names=False)

    def test_a_group_that_moves_like_the_general_series_is_unchanged(self):
        low = self.low.copy()
        low["I"], low["Q"] = self.ger_i, self.ger_q
        low["IDC"] = (self.c + expanding_minmax(low["I"]) + expanding_minmax(low["Q"])) / 3
        alt = AP._substituir_variacoes(low, self.ger_i, self.ger_q, self.c, list(self.meses[1:]))
        pd.testing.assert_series_equal(alt, low["IDC"], check_names=False)

    def test_scenarios_report_the_change_against_the_observed_index(self):
        jan = [m for m in self.meses if m.month == 1]
        cen = AP._cenarios(self.low, self.ger_i, self.ger_q, self.c, jan, [self.meses[3]])
        self.assertEqual(list(cen.index), ["janeiros", "fora_jan", "ambos"])
        alt = AP._substituir_variacoes(self.low, self.ger_i, self.ger_q, self.c, [self.meses[3]])
        self.assertAlmostEqual(cen.loc["fora_jan", "idc_t1"], alt.iloc[-1])
        self.assertAlmostEqual(cen.loc["fora_jan", "var_t1"], alt.iloc[-1] - self.low["IDC"].iloc[-1])
        self.assertEqual(cen.loc["ambos", "n_meses"], cen.loc["janeiros", "n_meses"] + cen.loc["fora_jan", "n_meses"])
        self.assertGreater(cen.loc["fora_jan", "max_abs"], 0.0)  # removing a +4 jump of I changes the index along the way


class TextoApendiceTests(unittest.TestCase):
    def test_consecutive_months_are_written_as_a_range(self):
        meses = list(pd.date_range("2026-02-01", "2026-06-01", freq="MS"))
        self.assertEqual(TA._meses(meses), "fev-2026 a jun-2026")
        self.assertEqual(TA._meses(meses[:2]), "fev-2026 e mar-2026")
        self.assertEqual(TA._meses([pd.Timestamp("2016-01-01"), pd.Timestamp("2017-01-01"), pd.Timestamp("2018-01-01")]), "jan-2016, jan-2017 e jan-2018")
        self.assertEqual(TA._meses([pd.Timestamp("2025-09-01"), pd.Timestamp("2026-05-01")]), "set-2025 e mai-2026")

    def test_year_lists(self):
        self.assertEqual(TA._periodo([2017, 2018, 2019, 2020]), "de 2017 a 2020")
        self.assertEqual(TA._periodo([2017, 2019]), "em 2017 e 2019")
        self.assertEqual(TA._periodo([2021, 2022], "de"), "de 2021 e 2022")

    def test_cross_references_keep_the_appendix_numbering(self):
        self.assertEqual(TA.T("tab:x"), r"Tabela~\ref{tab:x}")
        self.assertEqual(TA.Fs("fig:a", "fig:b"), r"Figuras~\ref{fig:a} e~\ref{fig:b}")


class CNacionalTests(unittest.TestCase):
    def test_a_bracket_commitment_equal_to_the_national_one_gives_no_error(self):
        comp = componentes()
        idc = indice_por_faixa(L.painel(faixa_bruta(), "faixa"), c_normalizado(comp))
        cri = pd.DataFrame({c: comp["C"] for c in ("ate_2_sm", "2_a_5_sm", "5_a_10_sm", "mais_de_10_sm")})
        r = avaliar_c_nacional(comp, idc, cri, inicio="2014-01-01", fim="2016-12-01")
        self.assertEqual(list(r.index), list(L.FAIXAS_INDICE))
        self.assertTrue((r["corr_c_d12"] > 0.999999).all())
        self.assertLess(r["erro_max_idc"].astype(float).max(), 1e-12)
        self.assertEqual(r["ult_mes"].iloc[0], pd.Timestamp("2016-12-01"))


class TabelasDoApendiceTests(unittest.TestCase):
    def test_a_table_is_scaled_to_the_text_width_only_when_it_is_wider(self):
        tex = tabela_latex("Titulo.", "tab:x", ["A", "B"], [["1", "2"]], "lr", "origem")
        self.assertIn(r"\begin{adjustbox}{max width=\textwidth}", tex)
        self.assertLess(tex.index(r"\end{tabular}"), tex.index(r"\end{adjustbox}"))
        self.assertLess(tex.index(r"\end{adjustbox}"), tex.index(r"\end{table}"))

    def test_source_note_moves_inside_the_float_and_the_table_floats(self):
        entrada = "\\begin{table}[H]\n  corpo (ver Notas)\n\\end{table}\n\n\\fonte{origem}\n"
        saida = AP.preparar_tabela(entrada)
        self.assertIn("\\begin{table}[htbp]", saida)
        self.assertIn("(ver " + AP.SECAO_METODOLOGIA + ")", saida)
        self.assertLess(saida.index("\\fonte{origem}"), saida.index("\\end{table}"))


WORKBOOK = ROOT / "data/raw/202609/202609_Tabelas_de_estatisticas_monetarias_e_de_credito.xlsx"
SGS = ROOT / "data/processed/sgs_snapshot.csv"
SCR = ROOT / "data/processed/scr"
CRI = ROOT / "data/external/cri_faixa_ref202504.csv"
HAS_DATA = all(p.exists() for p in (WORKBOOK, SGS, SCR / "scr_faixa.csv", SCR / "scr_vintage.csv", CRI, ROOT / "data/processed/components_raw.csv"))


@unittest.skipUnless(HAS_DATA, "requires data/processed/sgs_snapshot.csv and data/processed/scr/")
class ApendiceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sgs = pd.read_csv(SGS, index_col=0, parse_dates=True)
        comp = pd.read_csv(ROOT / "data/processed/components_raw.csv", index_col=0, parse_dates=True)
        idx = pd.read_csv(ROOT / "data/processed/index.csv", index_col=0, parse_dates=True)
        brutos = {n: pd.read_csv(SCR / f"scr_{n}.csv") for n in ["credor", "ocupacao", "uf", "faixa"]}
        paineis = {n: L.painel(b, n) for n, b in brutos.items()}
        cls.t1 = pd.Timestamp("2026-07-01")  # the month of the 202609 workbook, whatever the processed data hold today
        comp, idx = comp.loc[: cls.t1], idx.loc[: cls.t1]
        cls.sgs, cls.comp = sgs, comp
        cls.d = AP.reunir(cls.t1, sgs, comp, idx, paineis, brutos, WORKBOOK, pd.read_csv(SCR / "scr_vintage.csv"), CRI)
        cls.corpo = DOC.montar_corpo(cls.d)

    def test_low_income_index_is_the_lowest_bracket_of_the_bracket_index(self):
        pd.testing.assert_frame_equal(self.d.low, self.d.ext.dados["idc_faixa"][BAIXA_RENDA].loc[: self.t1])

    def test_no_replacement_reproduces_the_observed_series(self):
        from src.anatomy import Q_MODALIDADES
        ger_q = 100 * sum(self.sgs[f"saldo_{m}"] for m in Q_MODALIDADES) / self.sgs["saldo_total"]
        alt = AP._substituir_variacoes(self.d.low, self.sgs["inad_total"], ger_q, c_normalizado(self.comp), [])
        self.assertLess((alt - self.d.low["IDC"]).abs().max(), 1e-12)

    def test_scenario_table_is_consistent_with_the_series(self):
        c = self.d.cenarios
        for k in ("janeiros", "fora_jan", "ambos"):
            self.assertAlmostEqual(c.loc[k, "var_t1"], c.loc[k, "idc_t1"] - self.d.low["IDC"].iloc[-1], places=12)
        self.assertGreater(c.loc["ambos", "n_meses"], c.loc["janeiros", "n_meses"])

    def test_every_table_keeps_its_source_inside_the_float(self):
        for nome, tex in DOC.montar_tabelas(self.d).items():
            fonte, fim = tex.find(r"\fonte{"), tex.find(r"\end{table}")
            self.assertTrue(0 < fonte < fim, nome)

    def test_labels_are_unique_and_every_reference_resolves(self):
        labels = re.findall(r"\\label\{([^}]+)\}", self.corpo)
        self.assertEqual(len(labels), len(set(labels)), sorted(l for l in labels if labels.count(l) > 1))
        self.assertLessEqual(set(re.findall(r"\\ref\{([^}]+)\}", self.corpo)), set(labels))

    def test_text_has_no_template_leftovers_and_quotes_the_data(self):
        self.assertIsNone(re.search(r"\bnan\b|\bNone\b|\{\{|\binf\b", self.corpo))
        self.assertIn(f"{self.d.f.idc['t1']:.3f}".replace(".", ","), self.corpo)
        self.assertIn(f"{self.d.cenarios.loc['ambos', 'var_t1']:+.3f}".replace(".", ","), self.corpo)
        self.assertNotIn(r"\textbf", re.sub(r"\\begin\{table\}.*?\\end\{table\}", "", self.corpo, flags=re.S))  # bold is a convention of the note

    def test_appendix_tables_use_the_appendix_numbering_only_through_the_document_class(self):
        self.assertNotIn("(ver Notas)", self.corpo)


if __name__ == "__main__":
    unittest.main()
