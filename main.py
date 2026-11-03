import os
from pathlib import Path
import shutil
import tempfile
from typing import Optional
from zipfile import ZipFile

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill

from src import low_income
from src.build_index import build_components, build_index
from src.load_data import find_latest_bcb_table, load_raw_series
from src.plot import plot_all

DATA_OUT = Path("data/processed")
README_PATH = Path("README.md")
README_LATEST_START = "<!-- IDC_LATEST_START -->"
README_LATEST_END = "<!-- IDC_LATEST_END -->"
README_STATS_START = "<!-- IDC_STATS_START -->"
README_STATS_END = "<!-- IDC_STATS_END -->"
README_LOW_INCOME_START = "<!-- IDC_LOW_INCOME_START -->"
README_LOW_INCOME_END = "<!-- IDC_LOW_INCOME_END -->"

PT_MONTH_ABBR = {
    1: "jan", 2: "fev", 3: "mar", 4: "abr",
    5: "mai", 6: "jun", 7: "jul", 8: "ago",
    9: "set", 10: "out", 11: "nov", 12: "dez",
}


def main() -> None:
    DATA_OUT.mkdir(parents=True, exist_ok=True)

    print("Carregando dados do BCB...")
    raw = load_raw_series()
    raw.to_csv(DATA_OUT / "series_raw.csv")

    print("Construindo componentes (C, I, Q)...")
    components = build_components(raw)
    components.to_csv(DATA_OUT / "components_raw.csv")
    start = components.index[0].strftime("%b-%Y")
    end   = components.index[-1].strftime("%b-%Y")
    print(f"  Período: {start} a {end} ({len(components)} observações)")

    print("Construindo índice — janela expansiva, normalização min-max...")
    index_df = build_index(components)
    index_df.loc[index_df.index < "2014-01-01"] = float("nan")
    index_df.to_csv(DATA_OUT / "index.csv")

    print("Calculando o IDC Baixa Renda (SCR.data)...")
    try:
        low = low_income.calcular(components, raw)
    except Exception as exc:  # noqa: BLE001 - the general IDC must never depend on the optional low-income step
        low = low_income.Resultado("sem_dados", f"erro inesperado ao calcular o índice ({exc!r})", t1=index_df.index[-1])
    low_income.gravar(low)
    print(f"  {_low_income_message(low)}")

    # Salva arquivo Excel consolidado: as séries do relatório, notas, e os dados brutos e normalizados
    excel_path = DATA_OUT / "idc_data.xlsx"
    print(f"Salvando planilha consolidada em {excel_path}...")
    
    # Criamos cópias para renomear os índices para exibição amigável no Excel
    components_excel = components.copy()
    components_excel.index.name = "Data"
    index_excel = index_df.copy()
    index_excel.index.name = "Data"
    
    # Formata datas como string 'YYYY-MM-DD' para facilitar visualização no Excel
    components_excel.index = components_excel.index.strftime("%Y-%m-%d")
    index_excel.index = index_excel.index.strftime("%Y-%m-%d")

    _write_excel_safely(index_excel, components_excel, excel_path,
                        report=_report_series(components, index_df, low), low=_low_income_sheet(low),
                        notes=_workbook_notes(find_latest_bcb_table().parent.name, low))

    _update_readme(components, index_df, low)
    plot_all(components, index_df, low_income=low.serie if low.disponivel else None)
    _print_summary(index_df, low)


REPORT_SHEET = "Séries do relatório"
NOTES_SHEET = "Notas"
LOW_INCOME_SHEET = "IDC Baixa Renda"


def _report_series(components: pd.DataFrame, index_df: pd.DataFrame, low) -> pd.DataFrame:
    """The monthly series shown in the report, with Portuguese headers and units (one row per month)."""
    table = pd.DataFrame({
        "IDC Geral": index_df["index"],
        "IDC Baixa Renda": float("nan"),
        "C — Comprometimento de renda (%)": components["C"],
        "I — Inadimplência 90+ dias (%)": components["I"],
        "Q — Crédito oneroso no crédito livre PF (%)": 100 * components["Q"],
        "I — Inadimplência 90+ dias, baixa renda (%)": float("nan"),
        "Q — Crédito oneroso, baixa renda (%)": float("nan"),
    }, index=components.index)
    if low.disponivel:
        serie = low.serie
        shown = serie["IDC"].loc[low_income.primeira_exibicao():]  # the warm-up months are not shown, as in the report
        table["IDC Baixa Renda"] = shown.reindex(table.index)
        table["I — Inadimplência 90+ dias, baixa renda (%)"] = serie["I"].reindex(table.index)
        table["Q — Crédito oneroso, baixa renda (%)"] = serie["Q"].reindex(table.index)
    table.index = table.index.strftime("%Y-%m-%d")
    table.index.name = "Data"
    return table


def _low_income_sheet(low) -> Optional[pd.DataFrame]:
    """The full series of the IDC Baixa Renda (from jul-2012, warm-up included), or ``None`` when unavailable."""
    if not low.disponivel:
        return None
    sheet = low.serie.rename(columns={
        "I": "I — Inadimplência 90+ dias (%)", "Q": "Q — Crédito oneroso (%)", "I_norm": "I normalizado",
        "Q_norm": "Q normalizado", "C_norm": "C normalizado (nacional)", "IDC": "IDC Baixa Renda",
    })
    sheet.index = sheet.index.strftime("%Y-%m-%d")
    sheet.index.name = "Data"
    return sheet


def _workbook_notes(release: str, low) -> pd.DataFrame:
    """A few lines on what each sheet holds, for readers of the workbook."""
    linhas = [
        ("Divulgação do BCB", f"{release} (Estatísticas Monetárias e de Crédito)"),
        (REPORT_SHEET, "Séries mostradas no relatório, uma linha por mês: IDC Geral (desde jan-2014), IDC Baixa Renda "
                       "(desde mai-2015) e componentes brutos C, I e Q, em % (I e Q também para a baixa renda, desde jul-2012)."),
        ("IDC e Normalizados", "IDC Geral (coluna index) e componentes normalizados C, I e Q, de 0 (melhor) a 1 (pior) "
                               "no histórico observado; min-max com janela expansiva desde mar-2011, exibidos desde jan-2014."),
        ("Componentes Brutos", "C e I em %; Q como fração do crédito livre PF (0,245 = 24,5%)."),
        (LOW_INCOME_SHEET, "Série completa do IDC Baixa Renda (renda até 2 salários mínimos, incluindo sem rendimento): "
                           "I e Q do SCR.data, normalizados desde jul-2012; C nacional. O índice é exibido desde mai-2015."
                           if low.disponivel else f"Não atualizado nesta edição: {low.motivo}."),
        ("Fontes", "BCB: SGS 29034 (C), 21112 (I), 20570, 20573, 20574, 20587 e 20588 (Q); SCR.data (baixa renda)."),
    ]
    return pd.DataFrame(linhas, columns=["Item", "Descrição"]).set_index("Item")


def _write_excel_safely(index_excel, components_excel, excel_path: Path, *, report: Optional[pd.DataFrame] = None,
                        low: Optional[pd.DataFrame] = None, notes: Optional[pd.DataFrame] = None) -> None:
    """Build the ZIP-based workbook off-volume, then replace it atomically."""
    excel_path.parent.mkdir(parents=True, exist_ok=True)
    staged_path = excel_path.with_suffix(f"{excel_path.suffix}.tmp")
    with tempfile.NamedTemporaryFile(prefix="idc-data-", suffix=".xlsx", delete=False) as tmp:
        temp_path = Path(tmp.name)

    try:
        with pd.ExcelWriter(temp_path, engine="openpyxl") as writer:
            if report is not None:
                report.to_excel(writer, sheet_name=REPORT_SHEET)
                _format_excel_sheet(
                    writer.sheets[REPORT_SHEET],
                    column_widths={"A": 13, **{c: 18 for c in "BCDEFGH"}},
                    number_formats={"B": "0.000", "C": "0.000", "D": "0.0", "E": "0.0", "F": "0.0", "G": "0.00", "H": "0.00"},
                    header_height=48,
                )
            if notes is not None:
                notes.to_excel(writer, sheet_name=NOTES_SHEET)
                sheet = writer.sheets[NOTES_SHEET]
                _format_excel_sheet(sheet, column_widths={"A": 22, "B": 110}, number_formats={})
                for row in sheet.iter_rows(min_row=2):
                    for cell in row:
                        cell.alignment = Alignment(wrap_text=True, vertical="top")
            index_excel.to_excel(writer, sheet_name="IDC e Normalizados")
            components_excel.to_excel(writer, sheet_name="Componentes Brutos")
            _format_excel_sheet(
                writer.sheets["IDC e Normalizados"],
                column_widths={"A": 13, "B": 16, "C": 16, "D": 16, "E": 16},
                number_formats={"B": "0.000000", "C": "0.000000", "D": "0.000000", "E": "0.000000"},
            )
            _format_excel_sheet(
                writer.sheets["Componentes Brutos"],
                column_widths={"A": 13, "B": 14, "C": 14, "D": 16},
                number_formats={"B": "0.0", "C": "0.0", "D": "0.000000"},
            )
            if low is not None:
                low.to_excel(writer, sheet_name=LOW_INCOME_SHEET)
                _format_excel_sheet(
                    writer.sheets[LOW_INCOME_SHEET],
                    column_widths={"A": 13, **{c: 18 for c in "BCDEFG"}},
                    number_formats={"B": "0.00", "C": "0.00", "D": "0.000000", "E": "0.000000", "F": "0.000000", "G": "0.000000"},
                    header_height=48,
                )

        with ZipFile(temp_path) as workbook:
            corrupt_member = workbook.testzip()
        if corrupt_member is not None:
            raise RuntimeError(f"Planilha consolidada inválida: {corrupt_member}")

        shutil.copyfile(temp_path, staged_path)
        os.replace(staged_path, excel_path)
    finally:
        temp_path.unlink(missing_ok=True)
        staged_path.unlink(missing_ok=True)


def _format_excel_sheet(worksheet, column_widths: dict[str, int], number_formats: dict[str, str], header_height: int = 22) -> None:
    """Apply readable, stable formatting to a generated data worksheet."""
    header_fill = PatternFill(fill_type="solid", fgColor="1F4E78")
    header_font = Font(color="FFFFFF", bold=True)
    for cell in worksheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    worksheet.row_dimensions[1].height = header_height
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions

    for column, width in column_widths.items():
        worksheet.column_dimensions[column].width = width
    for column, number_format in number_formats.items():
        for cell in worksheet[column][1:]:
            cell.number_format = number_format


def _low_income_message(low) -> str:
    if low.disponivel:
        status = "ok" if low.conciliacao.get("status") == "ok" and low.conciliacao.get("status_Q") == "ok" else "ok, com alerta de conciliação"
        return f"Status: {status} — último dado {low.t1:%b-%Y}, IDC Baixa Renda {low.serie['IDC'].iloc[-1]:.3f}"
    return f"Status: {low.status} — IDC Baixa Renda não atualizado nesta edição ({low.motivo})"


def _print_summary(index_df, low=None) -> None:
    s = index_df["index"].dropna()
    last_date = s.index[-1].strftime("%b-%Y")
    print(f"\nÍndice de Desconforto de Crédito — último dado: {last_date}")
    print(f"  {'Atual':>8} {'Média':>8} {'Desvpad':>8} {'Mín':>8} {'Máx':>8}")
    print("  " + "-" * 44)
    print(
        f"  {s.iloc[-1]:8.3f} {s.mean():8.3f}"
        f" {s.std():8.3f} {s.min():8.3f} {s.max():8.3f}"
    )
    if low is not None and low.disponivel:
        b = low.serie["IDC"].dropna()
        print(f"\nIDC Baixa Renda (até 2 SM) — último dado: {b.index[-1].strftime('%b-%Y')}")
        print(
            f"  {b.iloc[-1]:8.3f} {b.mean():8.3f}"
            f" {b.std():8.3f} {b.min():8.3f} {b.max():8.3f}"
        )
    elif low is not None:
        print(f"\nIDC Baixa Renda não atualizado: {low.motivo}")
    print("\nOutputs salvos em:")
    print("  data/processed/   — series_raw.csv, components_raw.csv, index.csv, idc_data.xlsx,")
    print("                      low_income_idc.csv, low_income_status.json")
    print("  outputs/figures/  — 8 figuras (PNG)")


def _format_pt_decimal(value: float) -> str:
    return f"{value:.3f}".replace(".", ",")


def _format_pt_percent(value: float) -> str:
    return f"{value:.1f}%".replace(".", ",")


def _format_pt_period(timestamp) -> str:
    return f"{PT_MONTH_ABBR[timestamp.month]}-{timestamp.year}"


def _readme_latest_table(components, index_df) -> str:
    s = index_df["index"].dropna()
    last_date = s.index[-1]
    latest_components = components.loc[last_date]
    latest_index = index_df.loc[last_date]
    rows = [
        ("IDC", "—", f"**{_format_pt_decimal(latest_index['index'])}**"),
        (
            "C — comprometimento de renda",
            _format_pt_percent(latest_components["C"]),
            _format_pt_decimal(latest_index["C_norm"]),
        ),
        (
            "I — inadimplência 90+ dias",
            _format_pt_percent(latest_components["I"]),
            _format_pt_decimal(latest_index["I_norm"]),
        ),
        (
            "Q — crédito oneroso no crédito livre PF",
            _format_pt_percent(latest_components["Q"] * 100),
            _format_pt_decimal(latest_index["Q_norm"]),
        ),
    ]
    table = ["| Indicador | Valor bruto | Valor normalizado |", "|---|---:|---:|"]
    table.extend(f"| {label} | {raw} | {norm} |" for label, raw, norm in rows)
    return "\n".join(table)


def _readme_low_income_table(low) -> str:
    """Latest values of the low-income IDC, or the reason why it was not updated in this edition."""
    if not low.disponivel:
        return f"IDC Baixa Renda não atualizado nesta edição: {low.motivo}."
    serie = low.serie
    last = serie.index[-1]
    row = serie.loc[last]
    shown = serie["IDC"].loc[low_income.primeira_exibicao():].dropna()
    table = [
        "| Indicador | Valor bruto | Valor normalizado |", "|---|---:|---:|",
        f"| IDC Baixa Renda | — | **{_format_pt_decimal(row['IDC'])}** |",
        f"| C — comprometimento de renda (nacional) | — | {_format_pt_decimal(row['C_norm'])} |",
        f"| I — inadimplência 90+ dias (até 2 SM) | {_format_pt_percent(row['I'])} | {_format_pt_decimal(row['I_norm'])} |",
        f"| Q — crédito oneroso (até 2 SM) | {_format_pt_percent(row['Q'])} | {_format_pt_decimal(row['Q_norm'])} |",
        "",
        f"Último dado: {_format_pt_period(last)}; série exibida desde {_format_pt_period(shown.index[0])} "
        f"(média {_format_pt_decimal(shown.mean())}, mínimo {_format_pt_decimal(shown.min())}, máximo {_format_pt_decimal(shown.max())}).",
    ]
    return "\n".join(table)


def _readme_stats_table(index_df) -> str:
    s = index_df["index"].dropna()
    last_date = _format_pt_period(s.index[-1])
    rows = [
        ("Último dado", last_date),
        ("Atual", _format_pt_decimal(s.iloc[-1])),
        ("Média", _format_pt_decimal(s.mean())),
        ("Desvio padrão", _format_pt_decimal(s.std())),
        ("Mínimo", _format_pt_decimal(s.min())),
        ("Máximo", _format_pt_decimal(s.max())),
    ]
    table = ["| Estatística | Valor |", "|---|---:|"]
    table.extend(f"| {label} | {value} |" for label, value in rows)
    return "\n".join(table)


def _replace_readme_block(readme: str, start_marker: str, end_marker: str, content: str) -> str:
    start = readme.find(start_marker)
    end = readme.find(end_marker)
    if start == -1 or end == -1 or end < start:
        raise RuntimeError(
            "Bloco automático do IDC não encontrado no README.md. "
            f"Use os marcadores {start_marker} e {end_marker}."
        )

    replacement = (
        f"{start_marker}\n"
        f"{content}\n"
        f"{end_marker}"
    )
    return readme[:start] + replacement + readme[end + len(end_marker):]


def _update_readme(components, index_df, low, readme_path: Path = README_PATH) -> None:
    readme = readme_path.read_text(encoding="utf-8")
    updated = _replace_readme_block(
        readme,
        README_LATEST_START,
        README_LATEST_END,
        _readme_latest_table(components, index_df),
    )
    updated = _replace_readme_block(
        updated,
        README_STATS_START,
        README_STATS_END,
        _readme_stats_table(index_df),
    )
    updated = _replace_readme_block(
        updated,
        README_LOW_INCOME_START,
        README_LOW_INCOME_END,
        _readme_low_income_table(low),
    )
    readme_path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
