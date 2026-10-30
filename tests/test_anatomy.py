import unittest
from pathlib import Path

import pandas as pd

from src.anatomy import (
    PRODUTOS, TOLERANCIA_RESIDUO_PP, atribuir_variacao_I, atribuir_variacao_Q,
    decompor_C, reconstruir_inadimplencia,
)

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/processed/sgs_snapshot.csv"
T0, T1 = pd.Timestamp("2026-06-01"), pd.Timestamp("2026-07-01")


def synthetic_sgs() -> pd.DataFrame:
    """Two active products (the others have zero balance) over two months."""
    rows = []
    for t, (s_a, s_b, i_a, i_b) in {T0: (100.0, 300.0, 10.0, 2.0), T1: (150.0, 250.0, 12.0, 2.0)}.items():
        row = {f"saldo_{p}": 0.0 for p in PRODUTOS}
        row.update({f"inad_{p}": 0.0 for p in PRODUTOS if PRODUTOS[p][2] is not None})
        row["saldo_nao_consignado"], row["saldo_consig_inss"] = s_a, s_b
        row["inad_nao_consignado"], row["inad_consig_inss"] = i_a, i_b
        row["saldo_total"] = s_a + s_b
        row["inad_total"] = (s_a * i_a + s_b * i_b) / (s_a + s_b)
        rows.append(pd.Series(row, name=t))
    return pd.DataFrame(rows)


class AtribuicaoSinteticaTests(unittest.TestCase):
    def test_contributions_add_up_to_the_official_change(self):
        at = atribuir_variacao_I(synthetic_sgs(), T0, T1)
        # I: (100*10 + 300*2)/400 = 4.0  ->  (150*12 + 250*2)/400 = 5.75
        self.assertAlmostEqual(at.delta_oficial, 1.75)
        self.assertAlmostEqual(at.soma, 1.75, places=10)
        self.assertAlmostEqual(at.residuo, 0.0, places=10)

    def test_within_and_composition_parts(self):
        at = atribuir_variacao_I(synthetic_sgs(), T0, T1)
        a = at.tabela.loc["nao_consignado"]
        # weights 0.25 -> 0.375 (mean 0.3125); rates 10 -> 12 (mean 11)
        self.assertAlmostEqual(a["dentro"], 0.3125 * 2)
        self.assertAlmostEqual(a["composicao"], 11 * 0.125)

    def test_q_contributions_add_up(self):
        sgs = synthetic_sgs()
        q = atribuir_variacao_Q(sgs, T0, T1)
        # only "nao_consignado" is costly: share 25% -> 37.5%
        self.assertAlmostEqual(q["contribuicao"].sum(), 12.5)

    def test_unknown_month_raises(self):
        with self.assertRaises(KeyError):
            atribuir_variacao_I(synthetic_sgs(), T0, pd.Timestamp("2030-01-01"))


@unittest.skipUnless(SNAPSHOT.is_file(), "requires the SGS snapshot produced by run_layer1.py")
class AtribuicaoRealTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sgs = pd.read_csv(SNAPSHOT, index_col=0, parse_dates=True)

    def test_modalities_partition_the_total_balance(self):
        saldos = self.sgs[[f"saldo_{p}" for p in PRODUTOS]].sum(axis=1)
        erro = (saldos / self.sgs["saldo_total"] - 1).abs().dropna()
        self.assertLess(erro.max(), 1e-3)

    def test_reconstructed_delinquency_matches_the_official_series(self):
        erro = (reconstruir_inadimplencia(self.sgs) - self.sgs["inad_total"]).abs().dropna()
        self.assertLessEqual(erro.max(), 0.011)

    def test_monthly_and_annual_attributions_close_within_rounding(self):
        meses = self.sgs["inad_total"].dropna().index
        for t1 in meses[-24:]:
            for t0 in (t1 - pd.DateOffset(months=1), t1 - pd.DateOffset(years=1)):
                if t0 not in self.sgs.index:
                    continue
                at = atribuir_variacao_I(self.sgs, t0, t1)
                self.assertLessEqual(abs(at.residuo), TOLERANCIA_RESIDUO_PP, f"{t0:%Y-%m}->{t1:%Y-%m}")

    def test_commitment_is_interest_plus_amortisation(self):
        c = decompor_C(self.sgs, T0, T1)
        soma = c.loc["dos quais juros (SGS 29033)", "t1"] + c.loc["dos quais amortização (SGS 29036)", "t1"]
        self.assertAlmostEqual(soma, c.loc["C — serviço da dívida (SGS 29034)", "t1"], delta=0.011)


if __name__ == "__main__":
    unittest.main()
