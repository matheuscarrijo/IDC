import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src import lenses as L
from src import low_income as LI
from src.income_idc import BAIXA_RENDA, c_normalizado, idc_baixa_renda, indice_por_faixa, primeira_exibicao
from synthetic import T1, componentes, faixa_bruta, indice_geral


class IdcBaixaRendaTests(unittest.TestCase):
    def setUp(self):
        self.comp = componentes()
        self.p = L.painel(faixa_bruta(), "faixa")
        self.idc = indice_por_faixa(self.p, c_normalizado(self.comp))
        self.low = idc_baixa_renda(self.idc)

    def test_low_income_idc_is_the_lowest_bracket(self):
        pd.testing.assert_frame_equal(self.low, self.idc[BAIXA_RENDA])
        self.assertEqual(set(self.low.columns), {"I", "Q", "I_norm", "Q_norm", "C_norm", "IDC"})

    def test_idc_is_the_mean_of_the_three_normalised_components(self):
        media = (self.low["C_norm"] + self.low["I_norm"] + self.low["Q_norm"]) / 3
        pd.testing.assert_series_equal(self.low["IDC"], media, check_names=False)

    def test_group_includes_the_borrowers_without_income(self):
        peso = L.taxas(self.p)["peso"].xs(BAIXA_RENDA, level="grupo")
        self.assertAlmostEqual(peso.iloc[0], 100 * (0.02 + 0.10 + 0.18), places=9)  # sem rendimento + até 1 SM + 1 a 2 SM

    def test_national_c_is_shared_by_every_bracket(self):
        for faixa in L.FAIXAS_INDICE:
            pd.testing.assert_series_equal(self.idc[(faixa, "C_norm")], self.low["C_norm"], check_names=False)

    def test_display_starts_34_months_after_the_window(self):
        self.assertEqual(primeira_exibicao(), pd.Timestamp("2015-05-01"))
        self.assertEqual(self.low.index[0], pd.Timestamp("2012-07-01"))


class CalcularTests(unittest.TestCase):
    """The quality gate: the SCR.data must cover the reference month and reconcile with the official series."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.scr = Path(cls.tmp.name) / "scr"
        cls.scr.mkdir()
        bruto = faixa_bruta()
        bruto.to_csv(cls.scr / "scr_faixa.csv", index=False)
        cls.comp = componentes()
        nac = L.totais(L.painel(bruto, "faixa"))  # official series that match the synthetic panel
        cls.raw = pd.DataFrame({
            "inadimplencia": nac["I"], "total_credito_pf": nac["carteira"] / 1e6, "cheque_especial": 0.0,
            "credito_pessoal_nc": 0.0, "cartao_rotativo": nac["onerosa"] / 1e6, "cartao_parcelado": 0.0,
        })

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_available_when_the_scr_data_covers_the_month_and_reconciles(self):
        res = LI.calcular(self.comp, self.raw, self.scr)
        self.assertEqual(res.status, "ok")
        self.assertTrue(res.disponivel)
        self.assertEqual(res.t1, T1)
        self.assertEqual((res.serie.index[0], res.serie.index[-1]), (pd.Timestamp("2012-07-01"), T1))
        self.assertEqual(res.conciliacao["status"], "ok")

    def test_months_after_the_reference_month_are_ignored(self):
        extra = faixa_bruta(pd.date_range("2012-07-01", "2017-03-01", freq="MS"))
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "scr_faixa.csv").write_text(extra.to_csv(index=False), encoding="utf-8")
            longer = LI.calcular(self.comp, self.raw, Path(tmp))
        base = LI.calcular(self.comp, self.raw, self.scr)
        self.assertEqual(longer.status, "ok")
        pd.testing.assert_frame_equal(longer.serie.loc[:T1], base.serie)

    def test_blocked_when_the_official_delinquency_diverges_by_more_than_the_threshold(self):
        res = LI.calcular(self.comp, self.raw.assign(inadimplencia=self.raw["inadimplencia"] + 2.0), self.scr)
        self.assertEqual(res.status, "bloqueio")
        self.assertFalse(res.disponivel)
        self.assertIn("diverge", res.motivo)

    def test_no_coverage_when_the_scr_data_stops_before_the_reference_month(self):
        longer = self.comp.reindex(pd.date_range("2011-03-01", "2017-03-01", freq="MS")).ffill()
        res = LI.calcular(longer, self.raw, self.scr)
        self.assertEqual(res.status, "sem_cobertura")
        self.assertIn("dez-2016", res.motivo)
        self.assertIn("mar-2017", res.motivo)

    def test_no_data_when_the_aggregates_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(LI.calcular(self.comp, self.raw, Path(tmp)).status, "sem_dados")

    def test_status_and_series_are_stored_and_read_back(self):
        res = LI.calcular(self.comp, self.raw, self.scr)
        with tempfile.TemporaryDirectory() as tmp:
            csv, status = Path(tmp, "low.csv"), Path(tmp, "status.json")
            LI.gravar(res, csv, status)
            back = LI.carregar(csv, status)
            self.assertEqual((back.status, back.t1), ("ok", T1))
            pd.testing.assert_frame_equal(back.serie, res.serie, check_freq=False, check_names=False, atol=1e-12)
            status.write_text(status.read_text(encoding="utf-8").replace("2016-12", "2016-11"), encoding="utf-8")
            self.assertEqual(LI.carregar(csv, status).status, "sem_dados")  # the series does not end in the stated month

    def test_unavailable_edition_is_stated_without_pointing_to_other_documents(self):
        for res in (LI.Resultado("bloqueio", "x", t1=T1), LI.Resultado("sem_cobertura", "x", t1=T1), LI.Resultado("sem_dados", "x")):
            texto = LI.par_indisponivel(res)
            self.assertIn("não foi atualizado nesta edição", texto)
            self.assertNotRegex(texto.lower(), "ap[êe]ndice")


class FatosBaixaRendaTests(unittest.TestCase):
    def setUp(self):
        self.comp = componentes()
        self.idx = indice_geral(self.comp)
        p = L.painel(faixa_bruta(), "faixa")
        self.low = idc_baixa_renda(indice_por_faixa(p, c_normalizado(self.comp)))
        self.geral = (self.low["IDC"] - 0.05).rename("index")

    def fatos(self, geral=None):
        return LI.fatos(self.low, self.geral if geral is None else geral, self.comp, self.idx, T1)

    def test_facts_follow_the_series(self):
        f = self.fatos()
        s = self.low["IDC"].loc[primeira_exibicao():T1]
        self.assertEqual(f.inicio, pd.Timestamp("2015-05-01"))
        self.assertAlmostEqual(f.idc["t1"], s.loc[T1])
        self.assertEqual(f.n_obs, len(s))
        self.assertEqual(f.rank, int((s > s.loc[T1] + 1e-12).sum() + 1))
        self.assertAlmostEqual(f.relacao["share_acima"], 1.0)  # the group index is 0.05 above the general one in every month
        self.assertAlmostEqual(f.relacao["media_dif"], 0.05)

    def test_ordinals(self):
        self.assertEqual(LI.ordinal(7), "sétimo")
        self.assertEqual(LI.ordinal(11), "11º")

    def test_summary_paragraph_uses_bold_decimal_commas_and_the_display_start(self):
        f = self.fatos()
        texto = LI.par_resumo(f)
        self.assertIn(r"\textbf{" + f"{f.idc['t1']:.3f}".replace(".", ",") + "}", texto)
        self.assertIn(r"\textbf{mai-2015}", texto)

    def test_results_paragraph_says_when_the_two_indices_are_equal(self):
        f = self.fatos(geral=self.low["IDC"])
        self.assertIn("valor igual ao do IDC geral", LI.pars_resultados(f))
        f = self.fatos()
        self.assertIn("acima do IDC geral", LI.pars_resultados(f))

    def test_components_table_has_the_two_indices_side_by_side(self):
        tex = LI.tabela_componentes(self.fatos())
        self.assertIn(r"\multicolumn{2}{c}{IDC geral}", tex)
        self.assertIn(r"\multicolumn{2}{c}{IDC para baixa renda}", tex)
        self.assertNotIn(r"\fonte", tex)  # the note keeps the source line of the report
        self.assertIn(r"\fonte{teste}", LI.tabela_componentes(self.fatos(), fonte="teste"))


if __name__ == "__main__":
    unittest.main()
