import unittest
from pathlib import Path

import pandas as pd

from src.lenses import (
    FAIXA_GRUPO, agrupar_unidade, compactar, conciliar, decompor, detectar_quebras, painel, totais,
)
from src.scr_data import classify_categoria

ROOT = Path(__file__).resolve().parents[1]

T0, T1 = pd.Timestamp("2025-07-01"), pd.Timestamp("2026-07-01")


def raw_frame() -> pd.DataFrame:
    """Raw extraction layout: one row per (month, unit, oneroso flag)."""
    def rows(t, spec):
        out = []
        for unidade, (cart_n, cart_o, inad_n, inad_o) in spec.items():
            out.append({"data_base": t, "unidade": unidade, "oneroso": False, "carteira": cart_n, "inad": inad_n, "ap": 0.0, "v1590": 0.0})
            out.append({"data_base": t, "unidade": unidade, "oneroso": True, "carteira": cart_o, "inad": inad_o, "ap": 0.0, "v1590": 0.0})
        return out
    a0 = {"Banco": (700.0, 100.0, 28.0, 14.0), "Financeira": (60.0, 40.0, 6.0, 8.0), "Cooperativa": (90.0, 10.0, 4.0, 1.0)}
    a1 = {"Banco": (650.0, 150.0, 39.0, 24.0), "Financeira": (70.0, 60.0, 9.0, 12.0), "Cooperativa": (60.0, 10.0, 3.0, 1.5)}
    return pd.DataFrame(rows(T0, a0) + rows(T1, a1))


class DecomposicaoTests(unittest.TestCase):
    def setUp(self):
        self.p = painel(raw_frame(), "credor")

    def test_contributions_sum_to_national_change_for_i_and_q(self):
        nacional = totais(self.p)
        for medida in ("I", "Q"):
            d = decompor(self.p, T0, T1, medida, delta_oficial=0.0)
            esperado = nacional[medida].loc[T1] - nacional[medida].loc[T0]
            self.assertAlmostEqual(d.tabela["contribuicao"].sum(), esperado, places=10)
            self.assertAlmostEqual(d.delta_scr, esperado, places=10)

    def test_residual_is_official_change_minus_explained_part(self):
        d = decompor(self.p, T0, T1, "I", delta_oficial=1.0)
        self.assertAlmostEqual(d.residuo, 1.0 - d.tabela["contribuicao"].sum(), places=12)

    def test_compacting_small_units_keeps_the_sums(self):
        d = decompor(self.p, T0, T1, "I", delta_oficial=0.0)
        antes = d.tabela["contribuicao"].sum()
        t = compactar(d.tabela, limiar_peso=10.0)  # Cooperativa (6%) and Financeira (13%) -> only Cooperativa merges
        self.assertAlmostEqual(t["contribuicao"].sum(), antes, places=12)
        self.assertAlmostEqual(t["peso_t1"].sum(), d.tabela["peso_t1"].sum(), places=9)
        self.assertIn("Demais", t.index)


class QuebrasEConciliacaoTests(unittest.TestCase):
    def test_break_detector_flags_a_reclassification_jump(self):
        meses = pd.date_range("2025-06-01", periods=4, freq="MS")
        linhas = []
        for i, t in enumerate(meses):
            banco, fin = (800.0, 100.0) if i < 2 else (500.0, 400.0)  # a large lender moves segments
            for u, c in (("Banco", banco), ("Financeira", fin)):
                linhas.append({"data_base": t, "unidade": u, "oneroso": False, "carteira": c, "inad": 0.05 * c, "ap": 0.0, "v1590": 0.0})
        p = painel(pd.DataFrame(linhas), "credor")
        q = detectar_quebras(p, meses[0], meses[-1])
        self.assertEqual(sorted(q["unidade"]), ["Bancos", "Financeiras"])
        self.assertTrue((q["variacao_pp"].abs() > 1.0).all())
        self.assertTrue(detectar_quebras(p, meses[-2], meses[-1]).empty)  # window after the break

    def test_reconciliation_status(self):
        p = painel(raw_frame(), "credor")
        nac = totais(p)
        base = {f"saldo_{m}": 0.0 for m in ("cheque_especial", "nao_consignado", "cartao_rotativo", "cartao_parcelado")}
        def sgs(i0, i1):
            rows = []
            for t, i in ((T0, i0), (T1, i1)):
                r = dict(base); r["saldo_total"] = nac["carteira"].loc[t] / 1e6; r["inad_total"] = i
                rows.append(pd.Series(r, name=t))
            return pd.DataFrame(rows)
        ok = conciliar(p, sgs(nac["I"].loc[T0], nac["I"].loc[T1]), T0, T1)
        self.assertEqual(ok["status"], "ok")
        alerta = conciliar(p, sgs(nac["I"].loc[T0], nac["I"].loc[T1] - 0.5), T0, T1)
        self.assertEqual(alerta["status"], "alerta")
        bloqueio = conciliar(p, sgs(nac["I"].loc[T0], nac["I"].loc[T1] - 2.0), T0, T1)
        self.assertEqual(bloqueio["status"], "bloqueio")


class AgrupamentoETextosTests(unittest.TestCase):
    def test_lowest_bracket_includes_sem_rendimento(self):
        s = pd.Series(list(FAIXA_GRUPO))
        grupos = agrupar_unidade("faixa", s)
        self.assertEqual(grupos[s == "Sem rendimento"].iloc[0], "Até 2 SM")
        self.assertEqual(set(grupos), {"Até 2 SM", "2 a 5 SM", "5 a 10 SM", "Mais de 10 SM", "Renda indisponível"})

    def test_unmapped_lenders_fall_into_demais(self):
        s = pd.Series(["Banco", "Arrendamento", "Desenvolvimento/Fomento", "Outros"])
        self.assertEqual(list(agrupar_unidade("credor", s)), ["Bancos", "Demais", "Demais", "Demais"])

    def test_category_mapping_survives_trailing_spaces(self):
        mod = pd.Series(["Outros créditos", "Empréstimos", "Empréstimos", "Financiamentos rurais  (ex-financiamentos rurais e agroindustriais)"])
        sub = pd.Series([
            "Cartão de crédito - compra à vista e parcelado lojista ",  # trailing space in the BCB file
            "Cheque especial", "Crédito pessoal - sem consignação em folha de pagam.", "Custeio",
        ])
        self.assertEqual(list(classify_categoria(mod, sub)),
                         ["cartao_vista_lojista", "cheque_especial_cg", "pessoal_nao_consignado", "rural"])


if __name__ == "__main__":
    unittest.main()
