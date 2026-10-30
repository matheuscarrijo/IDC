"""Camada 2 — lentes por credor, ocupação, UF e faixa de renda (SCR.data, PF).

Each lens splits the national I and Q of the household free-resources credit
universe into additive contributions, using the midpoint (Shapley) split:

    contribution_u = mean weight_u * change in rate_u     ("dentro")
                   + mean rate_u   * change in weight_u   ("composição")

Because SCR.data is not identical to the SGS series behind the IDC, every table
carries an explicit reconciliation line (``conciliar``) and the decomposition
is normally read over 12 months, where the two sources agree on the sign of the
change in 96-100% of the months (checked from jan-2016 to jul-2026).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# --- grouping of raw SCR.data units into reporting units ---------------------
FAIXA_GRUPO = {
    "Sem rendimento": "Até 2 SM",
    "Até 1 salário mínimo": "Até 2 SM",
    "Mais de 1 a 2 salários mínimos": "Até 2 SM",
    "Mais de 2 a 3 salários mínimos": "2 a 5 SM",
    "Mais de 3 a 5 salários mínimos": "2 a 5 SM",
    "Mais de 5 a 10 salários mínimos": "5 a 10 SM",
    "Mais de 10 a 20 salários mínimos": "Mais de 10 SM",
    "Acima de 20 salários mínimos": "Mais de 10 SM",
    "Indisponível": "Renda indisponível",
}
FAIXA_ORDEM = ["Até 2 SM", "2 a 5 SM", "5 a 10 SM", "Mais de 10 SM", "Renda indisponível"]
FAIXAS_INDICE = FAIXA_ORDEM[:4]  # brackets that enter the "IDC por faixa"

CREDOR_GRUPO = {
    "Banco": "Bancos",
    "Financeira": "Financeiras",
    "Cooperativa": "Cooperativas",
    "Fintech": "Fintechs",
    "Instituição de pagamento": "Instituições de pagamento",
}
CREDOR_ORDEM = ["Bancos", "Financeiras", "Cooperativas", "Fintechs", "Instituições de pagamento", "Demais"]

# --- reconciliation thresholds (p.p.), calibrated on the 127 months from jan-2016 to jul-2026 ---
CONCILIACAO_ALERTA_PP = 0.25
CONCILIACAO_BLOQUEIO_PP = 0.75
QUEBRA_PARTICIPACAO_PP = 1.0  # monthly change in a unit's weight flagged as a break


# Official national series of the monthly workbook (``series_raw.csv``) in the layout that ``conciliar`` expects
# (the layout of the SGS snapshot used by the statistical appendix).
OFICIAL_COLUNAS = {
    "inadimplencia": "inad_total", "total_credito_pf": "saldo_total", "cheque_especial": "saldo_cheque_especial",
    "credito_pessoal_nc": "saldo_nao_consignado", "cartao_rotativo": "saldo_cartao_rotativo",
    "cartao_parcelado": "saldo_cartao_parcelado",
}


def oficial_da_planilha(raw: pd.DataFrame) -> pd.DataFrame:
    """Official I and balances of the monthly BCB workbook, renamed for :func:`conciliar` (R$ million, I in %)."""
    return raw.rename(columns=OFICIAL_COLUNAS)[list(OFICIAL_COLUNAS.values())]


def agrupar_unidade(lente: str, unidade: pd.Series) -> pd.Series:
    """Map raw SCR.data unit labels to the reporting units of each lens."""
    if lente == "faixa":
        return unidade.map(FAIXA_GRUPO).fillna("Renda indisponível")
    if lente == "credor":
        return unidade.map(CREDOR_GRUPO).fillna("Demais")
    return unidade


def painel(df: pd.DataFrame, lente: str) -> pd.DataFrame:
    """Tidy panel indexed by (month, unit): carteira, inad, onerosa, ap, v1590."""
    df = df.copy()
    df["data_base"] = pd.to_datetime(df["data_base"], format="mixed").dt.to_period("M").dt.to_timestamp()
    df["grupo"] = agrupar_unidade(lente, df["unidade"])
    df["onerosa"] = df["carteira"].where(df["oneroso"], 0.0)
    out = df.groupby(["data_base", "grupo"])[["carteira", "inad", "onerosa", "ap", "v1590"]].sum()
    return out


def totais(p: pd.DataFrame) -> pd.DataFrame:
    """National totals (percent) implied by a panel."""
    t = p.groupby(level="data_base")[["carteira", "inad", "onerosa", "ap", "v1590"]].sum()
    t["I"] = 100 * t["inad"] / t["carteira"]
    t["Q"] = 100 * t["onerosa"] / t["carteira"]
    t["AP"] = 100 * t["ap"] / t["carteira"]
    return t


def taxas(p: pd.DataFrame) -> pd.DataFrame:
    """Per-unit I and Q (percent) and weights (percent), index (month, unit)."""
    w = 100 * p["carteira"] / p.groupby(level="data_base")["carteira"].transform("sum")
    return pd.DataFrame({
        "peso": w,
        "I": 100 * p["inad"] / p["carteira"],
        "Q": 100 * p["onerosa"] / p["carteira"],
    })


@dataclass(frozen=True)
class Decomposicao:
    tabela: pd.DataFrame
    delta_scr: float          # change of the national rate implied by SCR.data (p.p.)
    delta_oficial: float      # change of the official SGS aggregate (p.p.)

    @property
    def residuo(self) -> float:
        """Official change minus the part explained by the units (p.p.)."""
        return self.delta_oficial - float(self.tabela["contribuicao"].sum())


def decompor(p: pd.DataFrame, t0: pd.Timestamp, t1: pd.Timestamp, medida: str,
             delta_oficial: float) -> Decomposicao:
    """Additive split of the change in the national I or Q between two months."""
    if medida not in {"I", "Q"}:
        raise ValueError("medida must be 'I' or 'Q'")
    r = taxas(p)
    w = r["peso"].unstack() / 100
    x = r[medida].unstack()
    unidades = w.columns
    w0, w1 = w.loc[t0].reindex(unidades).fillna(0), w.loc[t1].reindex(unidades).fillna(0)
    x0, x1 = x.loc[t0].reindex(unidades).fillna(0), x.loc[t1].reindex(unidades).fillna(0)
    dentro = (w0 + w1) / 2 * (x1 - x0)
    comp = (x0 + x1) / 2 * (w1 - w0)
    tab = pd.DataFrame({
        "peso_t1": 100 * w1, "x_t0": x0, "x_t1": x1, "dx": x1 - x0,
        "dentro": dentro, "composicao": comp,
    })
    tab["contribuicao"] = tab["dentro"] + tab["composicao"]
    nacional = totais(p)[medida]
    return Decomposicao(tab, float(nacional.loc[t1] - nacional.loc[t0]), delta_oficial)


def compactar(tab: pd.DataFrame, ordem: list[str] | None = None, limiar_peso: float = 0.5,
              nome_demais: str = "Demais") -> pd.DataFrame:
    """Merge units lighter than ``limiar_peso`` percent into one row (sums stay exact)."""
    pequenos = tab.index[(tab["peso_t1"] < limiar_peso) & (tab.index != nome_demais)]
    if len(pequenos) == 0:
        return tab if ordem is None else tab.reindex([u for u in ordem if u in tab.index])
    resto = tab.loc[pequenos]
    peso = resto["peso_t1"].sum()
    linha = {"peso_t1": peso}
    for col in ("dentro", "composicao", "contribuicao"):
        linha[col] = resto[col].sum()
    for col in ("x_t0", "x_t1"):  # weight-averaged rate of the merged units
        linha[col] = (resto[col] * resto["peso_t1"]).sum() / peso if peso else np.nan
    linha["dx"] = linha["x_t1"] - linha["x_t0"]
    out = pd.concat([tab.drop(index=pequenos), pd.DataFrame(linha, index=[nome_demais])])
    return out


def detectar_quebras(p: pd.DataFrame, t0: pd.Timestamp, t1: pd.Timestamp,
                     limiar_pp: float = QUEBRA_PARTICIPACAO_PP) -> pd.DataFrame:
    """Units whose weight moved by more than ``limiar_pp`` in a single month of (t0, t1]."""
    w = taxas(p)["peso"].unstack()
    mudanca = w.diff().loc[(w.index > t0) & (w.index <= t1)]
    achados = mudanca.stack()
    achados = achados[achados.abs() > limiar_pp]
    return achados.rename("variacao_pp").reset_index().rename(columns={"grupo": "unidade"})


def bloqueado(conc: dict) -> bool:
    """True when the SCR.data diverges from the official I or Q by more than the blocking threshold."""
    return conc["status"] == "bloqueio" or conc["status_Q"] == "bloqueio"


def _status(pior_pp: float) -> str:
    return ("ok" if pior_pp <= CONCILIACAO_ALERTA_PP
            else "alerta" if pior_pp <= CONCILIACAO_BLOQUEIO_PP else "bloqueio")


def conciliar(p: pd.DataFrame, sgs: pd.DataFrame, t0: pd.Timestamp, t1: pd.Timestamp) -> dict:
    """Compare the national I and Q implied by SCR.data with the official SGS values.

    ``status`` (for I) uses the level gap at ``t1`` and the gap in the change from
    ``t0`` to ``t1``; ``status_Q`` uses only the gap in the change, because the SCR
    category mapping of Q sits a stable 0.1-0.5 p.p. below the SGS level.
    """
    nacional = totais(p)
    q_oficial = 100 * sum(sgs[f"saldo_{m}"] for m in
                          ("cheque_especial", "nao_consignado", "cartao_rotativo", "cartao_parcelado")) / sgs["saldo_total"]
    gap = {
        "I_scr_t1": float(nacional["I"].loc[t1]), "I_sgs_t1": float(sgs["inad_total"].loc[t1]),
        "Q_scr_t1": float(nacional["Q"].loc[t1]), "Q_sgs_t1": float(q_oficial.loc[t1]),
    }
    gap["gap_I_nivel"] = gap["I_scr_t1"] - gap["I_sgs_t1"]
    gap["gap_Q_nivel"] = gap["Q_scr_t1"] - gap["Q_sgs_t1"]
    gap["gap_I_delta"] = float(nacional["I"].loc[t1] - nacional["I"].loc[t0]) - float(
        sgs["inad_total"].loc[t1] - sgs["inad_total"].loc[t0])
    gap["gap_Q_delta"] = float(nacional["Q"].loc[t1] - nacional["Q"].loc[t0]) - float(q_oficial.loc[t1] - q_oficial.loc[t0])
    gap["gap_carteira_pct"] = 100 * (float(nacional["carteira"].loc[t1]) / 1e6 / float(sgs["saldo_total"].loc[t1]) - 1)
    gap["status"] = _status(max(abs(gap["gap_I_nivel"]), abs(gap["gap_I_delta"])))
    gap["status_Q"] = _status(abs(gap["gap_Q_delta"]))
    return gap
