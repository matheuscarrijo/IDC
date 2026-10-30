"""IDC por faixa de renda — I and Q of each income bracket, C held at the national value.

    IDC_b = (C_norm + I_norm_b + Q_norm_b) / 3

* ``C_norm`` is the headline IDC component (window from mar-2011), identical for
  every bracket because the BCB publishes no commitment-of-income series by
  income (the REF chart by bracket was discontinued after the Apr/2025 edition).
* ``I_norm_b`` and ``Q_norm_b`` are expanding min-max positions of each bracket's
  own series, with the window starting in jul-2012 (first SCR.data month) and
  display starting 34 months later (may-2015), mirroring the headline rule of
  34 months of warm-up.
* The lowest bracket includes "sem rendimento".
"""
from __future__ import annotations

import pandas as pd

from src.lenses import FAIXAS_INDICE, taxas, totais
from src.normalize import expanding_minmax

JANELA_INICIO = pd.Timestamp("2012-07-01")
AQUECIMENTO_MESES = 34  # warm-up of the headline IDC (mar-2011 -> jan-2014)


def primeira_exibicao(inicio: pd.Timestamp = JANELA_INICIO) -> pd.Timestamp:
    return inicio + pd.DateOffset(months=AQUECIMENTO_MESES)


def c_normalizado(componentes: pd.DataFrame) -> pd.Series:
    """Headline C_norm recomputed from the raw C series (window from mar-2011)."""
    return expanding_minmax(componentes["C"].dropna())


def indice_por_faixa(p_faixa: pd.DataFrame, c_norm: pd.Series, inicio: pd.Timestamp = JANELA_INICIO,
                     escala_oficial: dict[str, pd.Series] | None = None) -> pd.DataFrame:
    """IDC by income bracket.

    ``escala_oficial`` (optional) holds ``{"I": factor, "Q": factor}`` monthly
    benchmarking factors (official / SCR.data) used only for sensitivity checks.
    """
    r = taxas(p_faixa)
    colunas = {}
    for faixa in FAIXAS_INDICE:
        i = r["I"].xs(faixa, level="grupo").sort_index()
        q = r["Q"].xs(faixa, level="grupo").sort_index()
        if escala_oficial:
            i = i * escala_oficial["I"].reindex(i.index)
            q = q * escala_oficial["Q"].reindex(q.index)
        i, q = i.loc[inicio:], q.loc[inicio:]
        i_norm, q_norm = expanding_minmax(i), expanding_minmax(q)
        c = c_norm.reindex(i.index)
        colunas[(faixa, "I")], colunas[(faixa, "Q")] = i, q
        colunas[(faixa, "I_norm")], colunas[(faixa, "Q_norm")] = i_norm, q_norm
        colunas[(faixa, "C_norm")] = c
        colunas[(faixa, "IDC")] = (c + i_norm + q_norm) / 3
    out = pd.DataFrame(colunas)
    out.columns = pd.MultiIndex.from_tuples(out.columns)
    return out


def fatores_de_referencia(p_faixa: pd.DataFrame, sgs: pd.DataFrame) -> dict[str, pd.Series]:
    """Monthly factors that scale the SCR.data national I and Q to the SGS values."""
    nacional = totais(p_faixa)
    q_oficial = 100 * sum(sgs[f"saldo_{m}"] for m in
                          ("cheque_especial", "nao_consignado", "cartao_rotativo", "cartao_parcelado")) / sgs["saldo_total"]
    return {"I": (sgs["inad_total"] / nacional["I"]).dropna(), "Q": (q_oficial / nacional["Q"]).dropna()}


def sensibilidade(p_faixa: pd.DataFrame, c_norm: pd.Series, sgs: pd.DataFrame, t: pd.Timestamp) -> pd.DataFrame:
    """IDC_b at month ``t`` under alternative design choices (robustness table)."""
    base = indice_por_faixa(p_faixa, c_norm)
    variantes = {
        "Base (janela jul/2012)": base,
        "Janela desde jan/2014": indice_por_faixa(p_faixa, c_norm, inicio=pd.Timestamp("2014-01-01")),
        "I e Q reescalados ao SGS": indice_por_faixa(p_faixa, c_norm, escala_oficial=fatores_de_referencia(p_faixa, sgs)),
    }
    linhas = {nome: {f: float(v[(f, "IDC")].loc[t]) for f in FAIXAS_INDICE} for nome, v in variantes.items()}
    out = pd.DataFrame(linhas).T
    exibir = primeira_exibicao()
    diffs = {}
    for nome, v in variantes.items():
        if nome.startswith("Base"):
            continue
        d = pd.concat([(v[(f, "IDC")] - base[(f, "IDC")]).loc[exibir:] for f in FAIXAS_INDICE], axis=1)
        diffs[nome] = float(d.abs().max().max())
    out["máx |dif. vs base| (2015-)"] = [0.0] + list(diffs.values())
    return out


# --------------------------------------------------------------------------- low-income IDC
BAIXA_RENDA = "Até 2 SM"  # tomadores PF com renda de até 2 salários mínimos, incluindo sem rendimento


def idc_baixa_renda(idc_faixa: pd.DataFrame) -> pd.DataFrame:
    """Columns I, Q (percent), I_norm, Q_norm, C_norm and IDC of the low-income group."""
    return idc_faixa[BAIXA_RENDA].copy()
