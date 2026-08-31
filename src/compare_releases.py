"""Compare consecutive BCB workbooks and disclose historical data revisions.

The monthly release usually adds new observations, but it may also revise or
backfill values inside the historical coverage of the preceding workbook.  This
module separates those historical changes from genuinely new observations and
reports their effect on the previous IDC reference month, which is the comparison
base used by the new monthly report.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.build_index import build_components, build_index
from src.load_data import DATA_DIR, TABLE_FILENAME_RE, load_raw_series


SERIES_LABELS = {
    "comprometimento_renda": "Comprometimento de renda (SGS 29034)",
    "inadimplencia": "Inadimplência (SGS 21112)",
    "total_credito_pf": "Crédito livre PF total (SGS 20570)",
    "cheque_especial": "Cheque especial (SGS 20573)",
    "credito_pessoal_nc": "Crédito pessoal não consignado (SGS 20574)",
    "cartao_rotativo": "Cartão rotativo (SGS 20587)",
    "cartao_parcelado": "Cartão parcelado (SGS 20588)",
}

IDC_PUBLICATION_START = pd.Timestamp("2014-01-01")


@dataclass(frozen=True)
class RawRevision:
    series: str
    date: str
    previous: Optional[float]
    current: Optional[float]
    delta: Optional[float]


@dataclass(frozen=True)
class ComponentComparison:
    component: str
    previous_raw: float
    current_raw: float
    previous_normalized: float
    current_normalized: float


@dataclass(frozen=True)
class IDCRevision:
    date: str
    previous: float
    current: float
    delta: float


@dataclass(frozen=True)
class ReleaseComparison:
    previous_period: str
    current_period: str
    previous_reference_date: str
    previous_idc: float
    current_vintage_idc: float
    idc_revision: float
    idc_revisions: tuple[IDCRevision, ...]
    components: tuple[ComponentComparison, ...]
    revisions: tuple[RawRevision, ...]

    @property
    def has_revisions(self) -> bool:
        return bool(self.revisions or self.idc_revisions)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["has_revisions"] = self.has_revisions
        return payload


def _period_from_path(path: Path) -> str:
    match = TABLE_FILENAME_RE.match(path.name)
    if not match or path.parent.name != match.group("period"):
        raise ValueError(f"Planilha fora do padrão data/raw/YYYYMM: {path}")
    return match.group("period")


def _release_tables(data_dir: Path = DATA_DIR) -> list[tuple[str, Path]]:
    tables: list[tuple[str, Path]] = []
    for path in data_dir.glob("[0-9][0-9][0-9][0-9][0-9][0-9]/*.xlsx"):
        try:
            period = _period_from_path(path)
        except ValueError:
            continue
        tables.append((period, path))
    return sorted(tables)


def find_release_pair(period: str, data_dir: Path = DATA_DIR) -> tuple[Path, Path]:
    tables = _release_tables(data_dir)
    current_matches = [path for candidate, path in tables if candidate == period]
    if not current_matches:
        raise FileNotFoundError(f"Planilha do BCB não encontrada para {period} em {data_dir}")

    previous_matches = [(candidate, path) for candidate, path in tables if candidate < period]
    if not previous_matches:
        raise FileNotFoundError(f"Não há divulgação anterior a {period} em {data_dir}")

    return previous_matches[-1][1], current_matches[-1]


def _optional_float(value) -> Optional[float]:
    return None if pd.isna(value) else float(value)


def compare_raw_vintages(
    previous_raw: pd.DataFrame,
    current_raw: pd.DataFrame,
    previous_period: str,
    current_period: str,
    *,
    atol: float = 1e-12,
) -> ReleaseComparison:
    previous_components = build_components(previous_raw)
    current_components = build_components(current_raw)
    if previous_components.empty:
        raise ValueError(f"A divulgação {previous_period} não produz componentes completos")

    previous_reference = previous_components.index[-1]
    if previous_reference not in current_components.index:
        raise ValueError(
            f"A competência-base {previous_reference:%Y-%m} da divulgação anterior "
            f"não está disponível em {current_period}"
        )

    previous_index = build_index(previous_components)
    current_index = build_index(current_components)

    idc_revisions: list[IDCRevision] = []
    overlapping_dates = previous_index.index.intersection(current_index.index)
    overlapping_dates = overlapping_dates[overlapping_dates >= IDC_PUBLICATION_START]
    for date in overlapping_dates:
        old_idc = previous_index.loc[date, "index"]
        new_idc = current_index.loc[date, "index"]
        if pd.isna(old_idc) or pd.isna(new_idc):
            continue
        if np.isclose(old_idc, new_idc, rtol=0.0, atol=atol):
            continue
        idc_revisions.append(IDCRevision(
            date=date.strftime("%Y-%m-%d"),
            previous=float(old_idc),
            current=float(new_idc),
            delta=float(new_idc - old_idc),
        ))

    revisions: list[RawRevision] = []
    all_dates = previous_raw.index.union(current_raw.index)
    for series in previous_raw.columns:
        if series not in current_raw.columns:
            raise ValueError(f"Série ausente na divulgação {current_period}: {series}")
        old = previous_raw[series].reindex(all_dates)
        new = current_raw[series].reindex(all_dates)
        both_present = old.notna() & new.notna()
        changed_value = both_present & ~np.isclose(
            old.fillna(0.0), new.fillna(0.0), rtol=0.0, atol=atol
        )
        removed_value = old.notna() & new.isna()
        previous_last_date = old.last_valid_index()
        backfilled_value = old.isna() & new.notna()
        if previous_last_date is not None:
            backfilled_value &= all_dates <= previous_last_date
        else:
            backfilled_value &= False
        for date in all_dates[changed_value | removed_value | backfilled_value]:
            old_value = _optional_float(old.loc[date])
            new_value = _optional_float(new.loc[date])
            delta = (
                None
                if old_value is None or new_value is None
                else new_value - old_value
            )
            revisions.append(RawRevision(
                series=series,
                date=date.strftime("%Y-%m-%d"),
                previous=old_value,
                current=new_value,
                delta=delta,
            ))

    component_rows = tuple(
        ComponentComparison(
            component=component,
            previous_raw=float(previous_components.loc[previous_reference, component]),
            current_raw=float(current_components.loc[previous_reference, component]),
            previous_normalized=float(previous_index.loc[previous_reference, f"{component}_norm"]),
            current_normalized=float(current_index.loc[previous_reference, f"{component}_norm"]),
        )
        for component in ("C", "I", "Q")
    )

    old_idc = float(previous_index.loc[previous_reference, "index"])
    new_idc = float(current_index.loc[previous_reference, "index"])
    values_to_validate = [old_idc, new_idc]
    for component in component_rows:
        values_to_validate.extend((
            component.previous_raw,
            component.current_raw,
            component.previous_normalized,
            component.current_normalized,
        ))
    if not np.isfinite(values_to_validate).all():
        raise ValueError(
            f"A competência-base {previous_reference:%Y-%m} não produz IDC e "
            "componentes normalizados finitos nas duas divulgações"
        )
    return ReleaseComparison(
        previous_period=previous_period,
        current_period=current_period,
        previous_reference_date=previous_reference.strftime("%Y-%m-%d"),
        previous_idc=old_idc,
        current_vintage_idc=new_idc,
        idc_revision=new_idc - old_idc,
        idc_revisions=tuple(idc_revisions),
        components=component_rows,
        revisions=tuple(revisions),
    )


def compare_releases(period: str, data_dir: Path = DATA_DIR) -> ReleaseComparison:
    previous_path, current_path = find_release_pair(period, data_dir)
    previous_period = _period_from_path(previous_path)
    current_period = _period_from_path(current_path)
    return compare_raw_vintages(
        load_raw_series(previous_path),
        load_raw_series(current_path),
        previous_period,
        current_period,
    )


def _format_number(value: Optional[float]) -> str:
    if value is None:
        return "ausente"
    return f"{value:.12g}"


def format_text(comparison: ReleaseComparison) -> str:
    lines = [
        f"Comparação de safras BCB: {comparison.previous_period} -> {comparison.current_period}",
        f"Alterações históricas entre safras: {'SIM' if comparison.has_revisions else 'NÃO'}",
        f"Competência-base da divulgação anterior: {comparison.previous_reference_date[:7]}",
        (
            "IDC da competência-base: "
            f"{comparison.previous_idc:.12f} -> {comparison.current_vintage_idc:.12f} "
            f"(revisão {comparison.idc_revision:+.12f})"
        ),
        "Componentes da competência-base:",
    ]
    for component in comparison.components:
        lines.append(
            f"  {component.component}: bruto {_format_number(component.previous_raw)} -> "
            f"{_format_number(component.current_raw)}; normalizado "
            f"{component.previous_normalized:.12f} -> {component.current_normalized:.12f}"
        )

    if comparison.revisions:
        lines.append(f"Observações históricas alteradas ({len(comparison.revisions)}):")
        for revision in comparison.revisions:
            label = SERIES_LABELS.get(revision.series, revision.series)
            lines.append(
                f"  {revision.date[:7]} | {label}: {_format_number(revision.previous)} -> "
                f"{_format_number(revision.current)} (delta {_format_number(revision.delta)})"
            )
    if comparison.idc_revisions:
        lines.append(f"Competências com IDC efetivamente alterado ({len(comparison.idc_revisions)}):")
        for revision in comparison.idc_revisions:
            lines.append(
                f"  {revision.date[:7]} | {revision.previous:.12f} -> "
                f"{revision.current:.12f} (revisão {revision.delta:+.12f})"
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compara a planilha do BCB com a divulgação imediatamente anterior."
    )
    parser.add_argument("period", help="Divulgação atual no formato YYYYMM")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--json", action="store_true", help="Emite JSON em vez do resumo textual")
    args = parser.parse_args()

    comparison = compare_releases(args.period, args.data_dir)
    if args.json:
        print(json.dumps(comparison.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_text(comparison))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
