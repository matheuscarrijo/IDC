import pandas as pd
from src.normalize import minmax, robust_minmax, percentile_rank

NORM_METHODS: dict = {
    "minmax":     minmax,
    "robust":     robust_minmax,
    "percentile": percentile_rank,
}


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
    """Apply all three normalization methods and aggregate into a composite index.

    For each method, normalizes C, I, Q independently and computes:
        index = (C_norm + I_norm + Q_norm) / 3

    Returns a DataFrame with columns {C,I,Q,index}_{minmax,robust,percentile}.
    """
    results = {}
    for name, fn in NORM_METHODS.items():
        C = fn(components["C"])
        I = fn(components["I"])
        Q = fn(components["Q"])
        results[f"C_{name}"]     = C
        results[f"I_{name}"]     = I
        results[f"Q_{name}"]     = Q
        results[f"index_{name}"] = (C + I + Q) / 3
    return pd.DataFrame(results, index=components.index)
