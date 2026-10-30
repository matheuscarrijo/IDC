"""SGS (Banco Central do Brasil) time-series client with retries.

The monthly BCB workbook stores several series rounded to one decimal place (for example C = 28,7% and
I = 7,8% in jul-2026), whereas the SGS API returns two decimals (28,72% and 7,78%).  The decompositions of
the statistical appendix need the extra precision and the balances and delinquency rates by modality,
which the IDC itself does not use, so the appendix reads the API and keeps the snapshot in
``data/processed/sgs_snapshot.csv`` (one column per series, indexed by month).

Command line (from the repository root)::

    python3 -m src.sgs_api snapshot            # fetch every series of the appendix and save the CSV
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

API_URL = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
    "?formato=json&dataInicial={start}&dataFinal={end}"
)
SNAPSHOT_CSV = Path("data/processed/sgs_snapshot.csv")


def fetch_series(code: int, start: dt.date = dt.date(2011, 3, 1), end: dt.date | None = None,
                 retries: int = 6) -> list[dict]:
    """Return the raw JSON rows for one SGS series (chunked in 9-year windows)."""
    end = end or dt.date.today()
    rows: list[dict] = []
    window_start = start
    while window_start <= end:
        window_end = min(dt.date(window_start.year + 9, 12, 31), end)
        url = API_URL.format(code=code, start=f"{window_start:%d/%m/%Y}", end=f"{window_end:%d/%m/%Y}")
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=90) as response:
                    rows += json.loads(response.read())
                break
            except Exception:  # noqa: BLE001 - the API answers 502/empty bodies intermittently
                time.sleep(2 * (attempt + 1))
        else:
            raise RuntimeError(f"SGS {code}: não foi possível obter {window_start}..{window_end}")
        window_start = dt.date(window_end.year + 1, 1, 1)
    return rows


def to_series(rows: list[dict], name: str) -> pd.Series:
    df = pd.DataFrame(rows)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    series = df.set_index("data")["valor"].rename(name)
    series.index = series.index.to_period("M").to_timestamp()
    return series[~series.index.duplicated(keep="last")].sort_index()


def snapshot(codes: dict[str, int], end: dt.date | None = None) -> pd.DataFrame:
    """Fetch every series and return one frame (a column per series name)."""
    columns = {name: to_series(fetch_series(code, end=end), name) for name, code in codes.items()}
    return pd.DataFrame(columns).sort_index()


def save_snapshot(frame: pd.DataFrame, path: Path = SNAPSHOT_CSV) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.rename_axis("data").to_csv(path)


def load_snapshot(path: Path = SNAPSHOT_CSV) -> pd.DataFrame:
    return pd.read_csv(path, index_col=0, parse_dates=True)


def main(argv: list[str] | None = None) -> int:
    from src.anatomy import SGS_CODES  # imported here: ``anatomy`` is not needed to fetch series in general

    parser = argparse.ArgumentParser(description="Baixa as séries do SGS usadas no apêndice estatístico.")
    parser.add_argument("command", choices=["snapshot"])
    parser.parse_args(argv)
    try:
        frame = snapshot(SGS_CODES)
    except RuntimeError as exc:
        print(f"Falha: {exc}", file=sys.stderr)
        return 1
    save_snapshot(frame)
    print(f"SGS: {frame.shape[1]} séries, de {frame.index.min():%b-%Y} a {frame.index.max():%b-%Y}, salvas em {SNAPSHOT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
