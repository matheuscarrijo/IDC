import re
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import openpyxl

DATA_DIR = Path("data/raw")
TABLE_FILENAME_RE = re.compile(
    r"^(?P<period>\d{6})_Tabelas_de_estatisticas_monetarias_e_de_credito\.xlsx$"
)

_PT_MONTHS = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4,
    "mai": 5, "jun": 6, "jul": 7, "ago": 8,
    "set": 9, "out": 10, "nov": 11, "dez": 12,
}


def _parse_pt_date(s: str) -> pd.Timestamp:
    s = str(s).strip().rstrip("*").strip()
    month_str, year_str = s.split("-")
    return pd.Timestamp(year=int(year_str), month=_PT_MONTHS[month_str.lower()], day=1)


def _is_pt_date(val) -> bool:
    if not val:
        return False
    return any(str(val).strip().lower().startswith(m) for m in _PT_MONTHS)


def _read_series(wb, sheet_name: str, sgs_code: int) -> pd.Series:
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))

    header_idx = next(
        (i for i, row in enumerate(rows) if str(row[0]).strip().upper() == "SGS"),
        None,
    )
    if header_idx is None:
        raise ValueError(f"SGS header row not found in sheet '{sheet_name}'")

    col_idx = next((i for i, v in enumerate(rows[header_idx]) if v == sgs_code), None)
    if col_idx is None:
        raise ValueError(f"SGS {sgs_code} not found in sheet '{sheet_name}'")

    data = {}
    for row in rows[header_idx + 1:]:
        if not _is_pt_date(row[0]):
            continue
        try:
            value = row[col_idx]
            if value is not None:
                data[_parse_pt_date(str(row[0]))] = float(value)
        except (ValueError, KeyError):
            continue

    return pd.Series(data, name=f"sgs_{sgs_code}")


def find_latest_bcb_table(data_dir: Path = DATA_DIR) -> Path:
    candidates = []
    for path in data_dir.glob("[0-9][0-9][0-9][0-9][0-9][0-9]/*.xlsx"):
        match = TABLE_FILENAME_RE.match(path.name)
        if match and path.parent.name == match.group("period"):
            candidates.append((match.group("period"), path))

    if not candidates:
        raise FileNotFoundError(
            "Nenhuma planilha mensal do BCB encontrada em data/raw/YYYYMM/. "
            "Execute: python -m src.download_bcb_release YYYYMM"
        )

    return max(candidates, key=lambda item: item[0])[1]


def load_raw_series(excel_path: Optional[Union[str, Path]] = None) -> pd.DataFrame:
    """Load all series required for the index from the BCB Excel file.

    Sources (all from the latest YYYYMM BCB monthly table in data/raw/YYYYMM/):
      - Tab 27, SGS 29034: comprometimento de renda das famílias (dessaz., %)
      - Tab 4,  SGS 21112: inadimplência carteira livre PF 90+ dias (%)
      - Tab 7,  SGS 20570: saldo total crédito livre PF (R$ milhões)
      - Tab 7,  SGS 20573: cheque especial (R$ milhões)
      - Tab 7,  SGS 20574: crédito pessoal não consignado (R$ milhões)
      - Tab 7,  SGS 20587: cartão de crédito rotativo (R$ milhões)
      - Tab 7,  SGS 20588: cartão de crédito parcelado (R$ milhões)
    """
    source_path = Path(excel_path) if excel_path is not None else find_latest_bcb_table()
    wb = openpyxl.load_workbook(source_path, read_only=True, data_only=True)
    try:
        df = pd.DataFrame({
            "comprometimento_renda": _read_series(wb, "Tab 27", 29034),
            "inadimplencia":         _read_series(wb, "Tab 4",  21112),
            "total_credito_pf":      _read_series(wb, "Tab 7",  20570),
            "cheque_especial":       _read_series(wb, "Tab 7",  20573),
            "credito_pessoal_nc":    _read_series(wb, "Tab 7",  20574),
            "cartao_rotativo":       _read_series(wb, "Tab 7",  20587),
            "cartao_parcelado":      _read_series(wb, "Tab 7",  20588),
        })
    finally:
        wb.close()
    return df.sort_index()
