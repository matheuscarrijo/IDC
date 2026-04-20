import pandas as pd


def minmax(series: pd.Series) -> pd.Series:
    """Min-max normalization over the full sample."""
    mn, mx = series.min(), series.max()
    return (series - mn) / (mx - mn)


def robust_minmax(series: pd.Series, q_low: float = 0.10, q_high: float = 0.90) -> pd.Series:
    """Min-max normalization using Q10/Q90 as anchors, clipped to [0, 1]."""
    q10 = series.quantile(q_low)
    q90 = series.quantile(q_high)
    return ((series - q10) / (q90 - q10)).clip(0.0, 1.0)


def percentile_rank(series: pd.Series) -> pd.Series:
    """Empirical percentile rank over the full sample."""
    return series.rank(pct=True)
