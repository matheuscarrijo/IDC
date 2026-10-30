import unittest
from pathlib import Path

import pandas as pd

from src import lenses as L
from src.extras import construir
from src.income_idc import c_normalizado, indice_por_faixa

ROOT = Path(__file__).resolve().parents[1]

WORKBOOK = ROOT / "data/raw/202609/202609_Tabelas_de_estatisticas_monetarias_e_de_credito.xlsx"
SGS = ROOT / "data/processed/sgs_snapshot.csv"
SCR = ROOT / "data/processed/scr"
T1 = pd.Timestamp("2026-07-01")
HAS_DATA = all(p.exists() for p in (WORKBOOK, SGS, SCR / "scr_faixa.csv", ROOT / "data/processed/components_raw.csv"))


@unittest.skipUnless(HAS_DATA, "requires data/processed/sgs_snapshot.csv and data/processed/scr/")
class ExtrasIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sgs = pd.read_csv(SGS, index_col=0, parse_dates=True)
        cls.comp = pd.read_csv(ROOT / "data/processed/components_raw.csv", index_col=0, parse_dates=True)
        cls.idx = pd.read_csv(ROOT / "data/processed/index.csv", index_col=0, parse_dates=True)
        cls.brutos = {n: pd.read_csv(SCR / f"scr_{n}.csv") for n in ["credor", "ocupacao", "uf", "faixa"]}
        cls.paineis = {n: L.painel(b, n) for n, b in cls.brutos.items()}

    def build(self, t1=T1, paineis="default", sgs=None):
        paineis = self.paineis if paineis == "default" else paineis
        return construir(t1, self.sgs if sgs is None else sgs, self.comp, self.idx, paineis, WORKBOOK, self.brutos)

    def test_full_build_produces_every_exhibit(self):
        r = self.build()
        self.assertEqual(r.camada2, "ok")
        for nome in ("anatomia", "c_q", "preco_fluxo", "faixa", "credor", "ocupacao", "uf", "idc_faixa"):
            self.assertIn(nome, r.tabelas)
        for nome in ("anatomia", "preco_fluxo", "lentes", "idc_faixa"):
            self.assertTrue(r.textos[nome].strip())

    def test_layer1_survives_a_missing_scr_data(self):
        r = self.build(paineis=None)
        self.assertEqual(r.camada2, "SCR.data indisponível")
        self.assertIn("anatomia", r.tabelas)
        self.assertNotIn("faixa", r.tabelas)

    def test_layer2_is_skipped_when_scr_data_does_not_cover_the_month(self):
        curtos = {n: p[p.index.get_level_values("data_base") < T1] for n, p in self.paineis.items()}
        r = self.build(paineis=curtos)
        self.assertTrue(r.camada2.startswith("SCR.data não cobre"))
        self.assertIn("anatomia", r.tabelas)

    def test_layer2_is_blocked_when_the_reconciliation_fails(self):
        torto = self.sgs.copy()
        torto.loc[T1, "inad_total"] += 3.0  # official I far from the SCR.data total
        r = self.build(sgs=torto)
        self.assertTrue(r.camada2.startswith("conciliação"))
        self.assertNotIn("uf", r.tabelas)

    def test_income_index_has_no_look_ahead(self):
        completo = indice_por_faixa(self.paineis["faixa"], c_normalizado(self.comp))
        for t1 in (pd.Timestamp("2019-06-01"), pd.Timestamp("2023-12-01"), T1):
            parcial = indice_por_faixa(self.paineis["faixa"][self.paineis["faixa"].index.get_level_values(0) <= t1],
                                       c_normalizado(self.comp.loc[:t1]))
            for faixa in L.FAIXAS_INDICE:
                self.assertAlmostEqual(parcial[(faixa, "IDC")].loc[t1], completo[(faixa, "IDC")].loc[t1], places=12)

    def test_national_component_matches_the_published_headline(self):
        c = c_normalizado(self.comp)
        self.assertLess((c.reindex(self.idx.index) - self.idx["C_norm"]).loc["2014":].abs().max(), 1e-12)

    def test_the_income_index_reuses_the_repository_normalisation(self):
        from src import income_idc, normalize

        self.assertIs(income_idc.expanding_minmax, normalize.expanding_minmax)  # one definition of the min-max window


if __name__ == "__main__":
    unittest.main()
