"""Readers for extra tables of the monthly BCB workbook.

The IDC pipeline (``src/load_data.py``) only reads the SGS columns it needs.
This module reads whole tables by header, which is what the "preço e fluxo"
exhibits (average interest rates and new lending by modality) require.
"""
from __future__ import annotations

import re
from pathlib import Path

import openpyxl
import pandas as pd

_PT_MONTHS = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
              "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}
_DATE_RE = re.compile(r"^[a-z]{3}-\d{4}\*?$")


def _clean(label: object) -> str:
    text = re.sub(r"\s+", " ", str(label)).strip()
    return re.sub(r"\d/", "", text).strip()  # drop footnote markers such as "1/"


def read_table(path: Path, sheet: str) -> tuple[pd.DataFrame, dict[str, object]]:
    """Return (frame indexed by month, column -> SGS code) for one workbook tab.

    Values flagged with ``*`` (preliminary) are kept.  Columns without a header
    are dropped.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = list(wb[sheet].iter_rows(values_only=True))
    finally:
        wb.close()
    header_idx = next(i for i, row in enumerate(rows) if row and row[0] == "Período")
    sgs_row = next(row for row in rows[header_idx:header_idx + 8]
                   if row and str(row[0]).strip().upper() == "SGS")
    columns = [_clean(c) if c is not None else f"col{j}" for j, c in enumerate(rows[header_idx])]
    data = [row for row in rows[header_idx + 1:]
            if row and isinstance(row[0], str) and _DATE_RE.match(row[0].strip())]
    frame = pd.DataFrame(data, columns=columns)
    index = []
    for label in frame["Período"]:
        month, year = label.strip().rstrip("*").split("-")
        index.append(pd.Timestamp(int(year), _PT_MONTHS[month], 1))
    frame = frame.drop(columns="Período")
    frame.index = pd.DatetimeIndex(index)
    sgs = {c: s for c, s in zip(columns, sgs_row) if c != "Período"}
    frame = frame[[c for c in frame.columns if not c.startswith("col")]]
    return frame.apply(pd.to_numeric, errors="coerce"), sgs
