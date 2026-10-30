"""Synthetic data shared by the tests of the low-income IDC and of the statistical appendix."""
import numpy as np
import pandas as pd

from src.normalize import expanding_minmax

MESES_C = pd.date_range("2011-03-01", "2016-12-01", freq="MS")
MESES = pd.date_range("2012-07-01", "2016-12-01", freq="MS")
T1 = pd.Timestamp("2016-12-01")
# raw SCR.data income classes and their weight in the portfolio (the first three form the low-income group)
UNIDADES = {"Sem rendimento": 0.02, "Até 1 salário mínimo": 0.10, "Mais de 1 a 2 salários mínimos": 0.18,
            "Mais de 2 a 3 salários mínimos": 0.15, "Mais de 3 a 5 salários mínimos": 0.15,
            "Mais de 5 a 10 salários mínimos": 0.15, "Acima de 20 salários mínimos": 0.25}


def faixa_bruta(meses=MESES, semente=0) -> pd.DataFrame:
    """Raw extraction layout: one row per (month, income class, oneroso flag)."""
    rng = np.random.default_rng(semente)
    linhas = []
    for i, t in enumerate(meses):
        for k, (unidade, peso) in enumerate(UNIDADES.items()):
            carteira = 1000 * peso * (1 + 0.002 * i)
            inad = carteira * (0.04 + 0.01 * rng.random() + 0.0004 * i)
            onerosa = 0.20 + 0.0005 * i + 0.01 * k + 0.01 * rng.random()  # varies, so that no normalised series is degenerate
            for oneroso, parte in ((False, 1 - onerosa), (True, onerosa)):
                linhas.append({"data_base": t, "unidade": unidade, "oneroso": oneroso, "carteira": carteira * parte,
                               "inad": inad * parte, "ap": 0.0, "v1590": 0.0})
    return pd.DataFrame(linhas)


def componentes() -> pd.DataFrame:
    rng = np.random.default_rng(1)
    c = pd.Series(20 + np.linspace(0, 8, len(MESES_C)) + rng.normal(0, 0.3, len(MESES_C)), MESES_C)
    return pd.DataFrame({"C": c, "I": 4 + np.linspace(0, 3, len(MESES_C)), "Q": 0.20 + np.linspace(0, 0.05, len(MESES_C))})


def indice_geral(comp: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"C_norm": expanding_minmax(comp["C"]), "I_norm": expanding_minmax(comp["I"]), "Q_norm": expanding_minmax(comp["Q"])})
