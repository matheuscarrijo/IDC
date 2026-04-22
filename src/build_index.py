import pandas as pd

from src.normalize import expanding_minmax


def build_components(raw: pd.DataFrame) -> pd.DataFrame:
    """Compute raw C, I, Q components from loaded series.

    C — comprometimento de renda (%)
    I — inadimplência carteira livre PF 90+ dias (%)
    Q — participação do crédito oneroso no total livre PF (fração)
    """
    df = pd.DataFrame(index=raw.index)
    df["C"] = raw["comprometimento_renda"]
    df["I"] = raw["inadimplencia"]
    df["Q"] = (
        raw["cheque_especial"] + raw["credito_pessoal_nc"]
        + raw["cartao_rotativo"] + raw["cartao_parcelado"]
    ) / raw["total_credito_pf"]
    return df.dropna()


def build_index(components: pd.DataFrame) -> pd.DataFrame:
    """Apply expanding min-max normalization and aggregate into a composite index.

    Normalizes C, I, Q independently and computes:
        index = (C_norm + I_norm + Q_norm) / 3

    Returns a DataFrame with columns C_norm, I_norm, Q_norm, index.
    """
    C = expanding_minmax(components["C"])
    I = expanding_minmax(components["I"])
    Q = expanding_minmax(components["Q"])
    return pd.DataFrame({
        "C_norm":  C,
        "I_norm":  I,
        "Q_norm":  Q,
        "index":   (C + I + Q) / 3,
    }, index=components.index)
