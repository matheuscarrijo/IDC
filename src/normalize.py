import pandas as pd


def expanding_minmax(series: pd.Series) -> pd.Series:
    """Min-max normalization using expanding window — no lookahead.

    At each t, anchors are min/max of series[0:t+1]. Returns NaN where
    min == max (all values identical; 0/0 is indeterminate). Clip guards
    against floating-point rounding slightly outside [0, 1].
    """
    mn = series.expanding().min()
    mx = series.expanding().max()
    return ((series - mn) / (mx - mn)).clip(0.0, 1.0)
