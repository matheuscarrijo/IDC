"""Camada 1 — "anatomia do mês": what moved I, Q and C in the IDC month.

Every number comes from official SGS series, so the decomposition uses the same
source and vintage as the IDC itself:

* I (SGS 21112) is exactly the balance-weighted average of the delinquency
  rates by modality (SGS 21113-21131), weights = balances (SGS 20570-20592).
  The additive (midpoint / Shapley) decomposition of its change into a
  "within modality" part and a "composition" part reproduces the official
  change within ~0.01 p.p. (rounding of the published series).
* Q is the share of four modalities in the total balance, so its change splits
  trivially into four share changes.
* C (SGS 29034) is the sum of the interest (29033) and amortisation (29036)
  commitments.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# key -> (label, balance SGS, delinquency SGS or None, report group)
PRODUTOS: dict[str, tuple[str, int, int | None, str]] = {
    "consig_servidores": ("Consignado — servidores públicos", 20577, 21117, "Consignado"),
    "consig_inss": ("Consignado — beneficiários do INSS", 20578, 21118, "Consignado"),
    "consig_privado": ("Consignado — setor privado", 20576, 21116, "Consignado"),
    "nao_consignado": ("Crédito pessoal não consignado", 20574, 21114, "Pessoal não consignado"),
    "cartao_vista": ("Cartão — à vista e parcelado lojista", 20589, None, "Cartão à vista e lojista"),
    "cartao_rotativo": ("Cartão — rotativo", 20587, 21127, "Cartão rotativo e parcelado"),
    "cartao_parcelado": ("Cartão — parcelado", 20588, 21128, "Cartão rotativo e parcelado"),
    "veiculos": ("Aquisição de veículos", 20581, 21121, "Veículos"),
    "composicao_dividas": ("Composição de dívidas", 20575, 21115, "Demais"),
    "cheque_especial": ("Cheque especial", 20573, 21113, "Cheque especial"),
    "outros_bens": ("Aquisição de outros bens", 20582, 21122, "Demais"),
    "desconto_cheques": ("Desconto de cheques", 20591, 21130, "Demais"),
    "arrend_outros_bens": ("Arrendamento — outros bens", 20585, 21125, "Demais"),
    "arrend_veiculos": ("Arrendamento — veículos", 20584, 21124, "Demais"),
    "outros": ("Outros", 20592, 21131, "Demais"),
}
# The four modalities in the numerator of Q (same as src/build_index.py).
Q_MODALIDADES = ("cheque_especial", "nao_consignado", "cartao_rotativo", "cartao_parcelado")

SGS_CODES: dict[str, int] = {
    "saldo_total": 20570,
    "inad_total": 21112,
    "C_total": 29034,
    "C_juros": 29033,
    "C_amort": 29036,
    "C_ex_hab": 29035,
    "endiv": 29037,
    "endiv_ex_hab": 29038,
}
for _key, (_label, _saldo, _inad, _grupo) in PRODUTOS.items():
    SGS_CODES[f"saldo_{_key}"] = _saldo
    if _inad is not None:
        SGS_CODES[f"inad_{_key}"] = _inad

TOLERANCIA_RESIDUO_PP = 0.02  # rounding of the published series


@dataclass(frozen=True)
class Atribuicao:
    """Result of an additive attribution of a change in an aggregate rate."""

    tabela: pd.DataFrame      # one row per unit
    delta_oficial: float      # change of the official aggregate (p.p.)
    delta_modelo: float       # change of the reconstructed aggregate (p.p.)
    soma: float               # sum of the unit contributions (p.p.)
    residuo: float            # official change minus sum of contributions (p.p.)

    @property
    def dentro(self) -> float:
        return float(self.tabela["dentro"].sum())

    @property
    def composicao(self) -> float:
        return float(self.tabela["composicao"].sum())


def _check_months(frame: pd.DataFrame, *months: pd.Timestamp) -> None:
    for month in months:
        if month not in frame.index:
            raise KeyError(f"month {month:%Y-%m} is not in the series")


def reconstruir_inadimplencia(sgs: pd.DataFrame) -> pd.Series:
    """Balance-weighted average of the delinquency rate by modality (percent)."""
    saldos = sgs[[f"saldo_{p}" for p in PRODUTOS]]
    taxas = pd.DataFrame({
        p: (sgs[f"inad_{p}"] if f"inad_{p}" in sgs else 0.0) for p in PRODUTOS
    }).fillna(0.0)
    pesos = saldos.div(saldos.sum(axis=1), axis=0)
    pesos.columns = list(PRODUTOS)
    return (pesos * taxas).sum(axis=1)


def atribuir_variacao_I(sgs: pd.DataFrame, t0: pd.Timestamp, t1: pd.Timestamp) -> Atribuicao:
    """Additive decomposition of the change in I between ``t0`` and ``t1``.

    contribution_p = mean weight_p * change in rate_p      ("dentro")
                   + mean rate_p   * change in weight_p    ("composição")
    """
    _check_months(sgs, t0, t1)
    produtos = list(PRODUTOS)
    saldos = sgs[[f"saldo_{p}" for p in produtos]].copy()
    saldos.columns = produtos
    pesos = saldos.div(saldos.sum(axis=1), axis=0)
    taxas = pd.DataFrame({
        p: (sgs[f"inad_{p}"] if f"inad_{p}" in sgs else 0.0) for p in produtos
    }).fillna(0.0)

    peso_medio = (pesos.loc[t0] + pesos.loc[t1]) / 2
    taxa_media = (taxas.loc[t0] + taxas.loc[t1]) / 2
    dentro = peso_medio * (taxas.loc[t1] - taxas.loc[t0])
    composicao = taxa_media * (pesos.loc[t1] - pesos.loc[t0])

    tabela = pd.DataFrame({
        "produto": [PRODUTOS[p][0] for p in produtos],
        "grupo": [PRODUTOS[p][3] for p in produtos],
        "peso_t0": 100 * pesos.loc[t0].values,
        "peso_t1": 100 * pesos.loc[t1].values,
        "I_t0": taxas.loc[t0].values,
        "I_t1": taxas.loc[t1].values,
        "dentro": dentro.values,
        "composicao": composicao.values,
    }, index=produtos)
    tabela["total"] = tabela["dentro"] + tabela["composicao"]
    modelo = reconstruir_inadimplencia(sgs)
    delta_oficial = float(sgs["inad_total"].loc[t1] - sgs["inad_total"].loc[t0])
    soma = float(tabela["total"].sum())
    return Atribuicao(tabela, delta_oficial, float(modelo.loc[t1] - modelo.loc[t0]), soma,
                      delta_oficial - soma)


def agrupar(atribuicao: Atribuicao) -> pd.DataFrame:
    """Aggregate the product table into the report groups."""
    t = atribuicao.tabela
    g = t.groupby("grupo").agg(peso_t1=("peso_t1", "sum"), dentro=("dentro", "sum"),
                               composicao=("composicao", "sum"), total=("total", "sum"))
    # delinquency of the group = balance-weighted average of its products
    for suffix, peso in (("t0", "peso_t0"), ("t1", "peso_t1")):
        ponderado = (t["I_" + suffix] * t[peso]).groupby(t["grupo"]).sum()
        g["I_" + suffix] = ponderado / t.groupby("grupo")[peso].sum()
    ordem = ["Cartão rotativo e parcelado", "Pessoal não consignado", "Consignado", "Veículos",
             "Cheque especial", "Cartão à vista e lojista", "Demais"]
    return g.loc[ordem, ["peso_t1", "I_t0", "I_t1", "dentro", "composicao", "total"]]


def atribuir_variacao_Q(sgs: pd.DataFrame, t0: pd.Timestamp, t1: pd.Timestamp) -> pd.DataFrame:
    """Contribution of each of the four costly modalities to the change in Q (p.p.)."""
    _check_months(sgs, t0, t1)
    total = sgs["saldo_total"]
    linhas = {}
    for p in Q_MODALIDADES:
        share = 100 * sgs[f"saldo_{p}"] / total
        linhas[p] = {"produto": PRODUTOS[p][0], "peso_t0": share.loc[t0], "peso_t1": share.loc[t1],
                     "contribuicao": share.loc[t1] - share.loc[t0]}
    tabela = pd.DataFrame(linhas).T
    for col in ("peso_t0", "peso_t1", "contribuicao"):
        tabela[col] = tabela[col].astype(float)
    return tabela


def decompor_C(sgs: pd.DataFrame, t0: pd.Timestamp, t1: pd.Timestamp) -> pd.DataFrame:
    """Levels and changes of C and its parts (interest, amortisation)."""
    _check_months(sgs, t0, t1)
    linhas = {
        "C — serviço da dívida (SGS 29034)": "C_total",
        "dos quais juros (SGS 29033)": "C_juros",
        "dos quais amortização (SGS 29036)": "C_amort",
        "C sem financiamento imobiliário (SGS 29035)": "C_ex_hab",
        "Endividamento (dívida/renda de 12 meses, SGS 29037)": "endiv",
    }
    out = pd.DataFrame({
        "t0": [sgs[c].loc[t0] for c in linhas.values()],
        "t1": [sgs[c].loc[t1] for c in linhas.values()],
    }, index=list(linhas))
    out["delta"] = out["t1"] - out["t0"]
    return out


def preco_e_fluxo(taxas: pd.DataFrame, concessoes: pd.DataFrame, t1: pd.Timestamp) -> pd.DataFrame:
    """Average lending rates and 12-month new lending by modality (workbook Tabs 16 and 11).

    ``taxas`` is Tab 16 (% a.a.), ``concessoes`` is Tab 11 (R$ million per month).
    New lending is the sum of the last 12 months, compared with the previous 12.
    Revolving modalities (cartão rotativo, cheque especial) report utilisation,
    not new loans, so their flow is left out.
    """
    t0 = t1 - pd.DateOffset(years=1)
    modalidades = {
        "Crédito pessoal — consignado, setor privado": "Crédito pessoal - Consignado - Trabalhadores setor privado",
        "Crédito pessoal — consignado, INSS": "Crédito pessoal - Consignado - Beneficiários do INSS",
        "Crédito pessoal — consignado, servidores": "Crédito pessoal - Consignado - Servidores públicos",
        "Crédito pessoal não consignado": "Crédito pessoal - Não consignado - Total",
        "Cartão — parcelado": "Cartão de crédito - Parcelado",
        "Cartão — rotativo": "Cartão de crédito - Rotativo",
        "Cheque especial": "Cheque especial",
        "Aquisição de veículos": "Aquisição de veículos",
        "Total do crédito livre PF": "Total",
    }
    sem_fluxo = {"Cartão — rotativo", "Cheque especial"}
    janela = lambda s, fim: s.loc[fim - pd.DateOffset(months=11): fim].sum()  # noqa: E731
    linhas = []
    for rotulo, coluna in modalidades.items():
        taxa_t1, taxa_t0 = taxas[coluna].loc[t1], taxas[coluna].loc[t0]
        fluxo = {"fluxo_12m_bi": float("nan"), "fluxo_var_pct": float("nan")}
        if rotulo not in sem_fluxo:
            atual, anterior = janela(concessoes[coluna], t1), janela(concessoes[coluna], t0)
            fluxo = {"fluxo_12m_bi": atual / 1000, "fluxo_var_pct": 100 * (atual / anterior - 1)}
        linhas.append({"modalidade": rotulo, "taxa_t1": taxa_t1, "taxa_t0": taxa_t0,
                       "taxa_delta": taxa_t1 - taxa_t0, **fluxo})
    return pd.DataFrame(linhas).set_index("modalidade")
