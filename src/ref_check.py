"""Validity test of the national C inside the income-bracket IDC.

The BCB's Financial Stability Report (REF) of April 2025 published the individual
income commitment (CRI) by income bracket, monthly from dec-2018 to dec-2024, and
dropped the chart afterwards.  With it we can measure how much the IDC of each
bracket changes when the national C is replaced by the bracket's own commitment
series.  The REF series refers to borrowers with income, so the "até 2 SM" bracket
there excludes those with no income, unlike the low-income group of the IDC.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.income_idc import c_normalizado
from src.normalize import expanding_minmax

REF_COLUNAS = {"Até 2 SM": "ate_2_sm", "2 a 5 SM": "2_a_5_sm", "5 a 10 SM": "5_a_10_sm", "Mais de 10 SM": "mais_de_10_sm"}


def carregar_cri(caminho: Path) -> pd.DataFrame:
    return pd.read_csv(caminho, index_col=0, parse_dates=True)


def avaliar_c_nacional(comp: pd.DataFrame, idc_faixa: pd.DataFrame, cri: pd.DataFrame,
                     inicio: str = "2020-12-01", fim: str = "2024-12-01") -> pd.DataFrame:
    """One row per bracket: how far the IDC with the national C is from the IDC with the bracket's own CRI."""
    c_nac = c_normalizado(comp)
    linhas = {}
    for faixa, coluna in REF_COLUNAS.items():
        c_faixa = expanding_minmax(cri[coluna])
        i_n, q_n = idc_faixa[(faixa, "I_norm")], idc_faixa[(faixa, "Q_norm")]
        d = pd.DataFrame({"c_nac": c_nac, "c_faixa": c_faixa, "i": i_n, "q": q_n}).loc[inicio:fim].dropna()
        d["idc_nac"] = (d.c_nac + d.i + d.q) / 3
        d["idc_faixa"] = (d.c_faixa + d.i + d.q) / 3
        erro = d.idc_nac - d.idc_faixa
        ultimo = d.index[-1]
        linhas[faixa] = {
            "corr_c_d12": float(d.c_faixa.diff(12).corr(d.c_nac.diff(12))),
            "vies_c": float((d.c_nac - d.c_faixa).mean()),
            "erro_medio_idc": float(erro.mean()),
            "erro_max_idc": float(erro.abs().max()),
            "corr_idc_d12": float(d.idc_nac.diff(12).corr(d.idc_faixa.diff(12))),
            "ult_mes": ultimo,
            "c_nac_ult": float(d.c_nac.iloc[-1]), "c_faixa_ult": float(d.c_faixa.iloc[-1]),
            "idc_nac_ult": float(d.idc_nac.iloc[-1]), "idc_faixa_ult": float(d.idc_faixa.iloc[-1]),
        }
    return pd.DataFrame(linhas).T
