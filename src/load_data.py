import pandas as pd
import openpyxl
from pathlib import Path

EXCEL_PATH = Path("data/estatisticas-monetarias-e-de-credito/tabelas-estatisticas-monetarias-e-de-credito.xlsx")

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
    rows = list(ws.iter_rows(min_row=7, values_only=True))

    col_idx = next((i for i, v in enumerate(rows[0]) if v == sgs_code), None)
    if col_idx is None:
        raise ValueError(f"SGS {sgs_code} not found in sheet '{sheet_name}'")

    data = {}
    for row in rows[1:]:
        if not _is_pt_date(row[0]):
            continue
        try:
            value = row[col_idx]
            if value is not None:
                data[_parse_pt_date(str(row[0]))] = float(value)
        except (ValueError, KeyError):
            continue

    return pd.Series(data, name=f"sgs_{sgs_code}")


def load_raw_series() -> pd.DataFrame:
    """Load all series required for the index from the BCB Excel file.

    Sources (all from tabelas-estatisticas-monetarias-e-de-credito.xlsx):
      - Tab 27, SGS 29034: comprometimento de renda das famílias (dessaz., %)
      - Tab 4,  SGS 21112: inadimplência carteira livre PF 90+ dias (%)
      - Tab 7,  SGS 20570: saldo total crédito livre PF (R$ milhões)
      - Tab 7,  SGS 20573: cheque especial (R$ milhões)
      - Tab 7,  SGS 20574: crédito pessoal não consignado (R$ milhões)
      - Tab 7,  SGS 20587: cartão de crédito rotativo (R$ milhões)
      - Tab 7,  SGS 20588: cartão de crédito parcelado (R$ milhões)
    """
    wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
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
