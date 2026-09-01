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
from typing import Mapping, Optional

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

# This is an editorial disclosure threshold, not an audit tolerance.  The audit
# above and below continues to use ``atol`` to retain every effective revision.
PUBLIC_REVISION_MATERIALITY_THRESHOLD = 0.010


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


@dataclass(frozen=True)
class RevisionMagnitudeFacts:
    """Quantitative facts used by the public-disclosure decision.

    ``largest_current_absolute_delta`` describes the consecutive-vintage audit.
    ``largest_cumulative_absolute_delta`` describes net changes measured from the
    last vintage whose revisions were publicly disclosed.  Keeping the two
    values separate prevents the editorial rule from weakening the audit.
    """

    threshold: float
    largest_current_absolute_delta: float
    largest_cumulative_absolute_delta: float
    effective_absolute_delta: float
    meets_threshold: bool


@dataclass(frozen=True)
class RevisionEditorialContext:
    """Editorial facts that cannot be inferred from two BCB workbooks alone.

    A routine revision requires both the quantitative threshold and
    ``affects_relevant_element``.  The remaining fields are explicit qualitative
    overrides: any one of them makes disclosure material independently of the
    numeric threshold.
    """

    affects_relevant_element: bool = False
    reverses_sign: bool = False
    changes_record: bool = False
    invalidates_published_statement: bool = False
    changes_idc_methodology: bool = False
    changes_source_or_coverage: bool = False
    corrects_relevant_error: bool = False

    @property
    def qualitative_overrides(self) -> tuple[str, ...]:
        candidates = (
            ("reverses_sign", self.reverses_sign),
            ("changes_record", self.changes_record),
            (
                "invalidates_published_statement",
                self.invalidates_published_statement,
            ),
            ("changes_idc_methodology", self.changes_idc_methodology),
            ("changes_source_or_coverage", self.changes_source_or_coverage),
            ("corrects_relevant_error", self.corrects_relevant_error),
        )
        return tuple(name for name, active in candidates if active)


@dataclass(frozen=True)
class RevisionMaterialityDecision:
    """Result of applying the editorial policy to quantitative audit facts."""

    quantitative: RevisionMagnitudeFacts
    editorial: RevisionEditorialContext
    routine_rule_met: bool
    qualitative_overrides: tuple[str, ...]
    is_publicly_material: bool


def quantify_revision_magnitude(
    comparison: ReleaseComparison,
    *,
    cumulative_idc_deltas_since_last_disclosure: Optional[Mapping[str, float]] = None,
    threshold: float = PUBLIC_REVISION_MATERIALITY_THRESHOLD,
) -> RevisionMagnitudeFacts:
    """Measure revision magnitude without making an editorial judgment.

    ``cumulative_idc_deltas_since_last_disclosure`` maps each affected IDC date
    to its *net* delta between the last publicly disclosed vintage and the
    current vintage.  Callers should therefore pass accumulated totals, rather
    than individual monthly increments.  The current consecutive-vintage audit
    remains part of the calculation even when no cumulative mapping is supplied.
    """

    if not np.isfinite(threshold) or threshold <= 0:
        raise ValueError("O limiar de materialidade deve ser finito e positivo")

    current_deltas = [comparison.idc_revision]
    current_deltas.extend(revision.delta for revision in comparison.idc_revisions)
    if not np.isfinite(current_deltas).all():
        raise ValueError("As revisões correntes do IDC devem ser finitas")
    largest_current = max((abs(delta) for delta in current_deltas), default=0.0)

    cumulative_deltas = tuple(
        (cumulative_idc_deltas_since_last_disclosure or {}).values()
    )
    if not np.isfinite(cumulative_deltas).all():
        raise ValueError("As revisões acumuladas do IDC devem ser finitas")
    largest_cumulative = max(
        (abs(delta) for delta in cumulative_deltas),
        default=0.0,
    )

    effective_delta = max(largest_current, largest_cumulative)
    return RevisionMagnitudeFacts(
        threshold=float(threshold),
        largest_current_absolute_delta=float(largest_current),
        largest_cumulative_absolute_delta=float(largest_cumulative),
        effective_absolute_delta=float(effective_delta),
        meets_threshold=effective_delta >= threshold,
    )


def assess_revision_materiality(
    quantitative: RevisionMagnitudeFacts,
    editorial: Optional[RevisionEditorialContext] = None,
) -> RevisionMaterialityDecision:
    """Apply the strict public-disclosure rule to precomputed audit facts."""

    editorial = editorial or RevisionEditorialContext()
    routine_rule_met = (
        quantitative.meets_threshold and editorial.affects_relevant_element
    )
    qualitative_overrides = editorial.qualitative_overrides
    return RevisionMaterialityDecision(
        quantitative=quantitative,
        editorial=editorial,
        routine_rule_met=routine_rule_met,
        qualitative_overrides=qualitative_overrides,
        is_publicly_material=routine_rule_met or bool(qualitative_overrides),
    )


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


def compare_release_vintages(
    baseline_period: str,
    current_period: str,
    data_dir: Path = DATA_DIR,
) -> ReleaseComparison:
    """Compare two explicitly selected vintages instead of consecutive ones.

    This is the operational path for measuring net revisions since the last
    public revision disclosure: use that disclosed vintage as ``baseline_period``
    and the release being prepared as ``current_period``.
    """

    if baseline_period >= current_period:
        raise ValueError("A safra-base deve ser anterior à safra atual")

    tables = _release_tables(data_dir)
    paths_by_period: dict[str, Path] = {}
    for period, path in tables:
        paths_by_period[period] = path

    missing_periods = [
        period
        for period in (baseline_period, current_period)
        if period not in paths_by_period
    ]
    if missing_periods:
        missing = ", ".join(missing_periods)
        raise FileNotFoundError(
            f"Planilha do BCB não encontrada para {missing} em {data_dir}"
        )

    return compare_raw_vintages(
        load_raw_series(paths_by_period[baseline_period]),
        load_raw_series(paths_by_period[current_period]),
        baseline_period,
        current_period,
    )


def idc_revision_deltas_by_date(
    comparison: ReleaseComparison,
) -> dict[str, float]:
    """Return net IDC deltas keyed by competence for materiality accumulation.

    When ``comparison`` comes from :func:`compare_release_vintages`, the result
    can be passed directly to ``cumulative_idc_deltas_since_last_disclosure`` in
    :func:`quantify_revision_magnitude`.
    """

    return {
        revision.date: revision.delta
        for revision in comparison.idc_revisions
    }


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
