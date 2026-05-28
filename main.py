from pathlib import Path
import pandas as pd

from src.build_index import build_components, build_index
from src.load_data import load_raw_series
from src.plot import plot_all

DATA_OUT = Path("data/processed")
README_PATH = Path("README.md")
README_LATEST_START = "<!-- IDC_LATEST_START -->"
README_LATEST_END = "<!-- IDC_LATEST_END -->"
README_STATS_START = "<!-- IDC_STATS_START -->"
README_STATS_END = "<!-- IDC_STATS_END -->"

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

    # Salva arquivo Excel consolidado com dados brutos e normalizados
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

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        index_excel.to_excel(writer, sheet_name="IDC e Normalizados")
        components_excel.to_excel(writer, sheet_name="Componentes Brutos")

    _update_readme(components, index_df)
    plot_all(components, index_df)
    _print_summary(index_df)


def _print_summary(index_df) -> None:
    s = index_df["index"].dropna()
    last_date = s.index[-1].strftime("%b-%Y")
    print(f"\nÍndice de Desconforto de Crédito — último dado: {last_date}")
    print(f"  {'Atual':>8} {'Média':>8} {'Desvpad':>8} {'Mín':>8} {'Máx':>8}")
    print("  " + "-" * 44)
    print(
        f"  {s.iloc[-1]:8.3f} {s.mean():8.3f}"
        f" {s.std():8.3f} {s.min():8.3f} {s.max():8.3f}"
    )
    print("\nOutputs salvos em:")
    print("  data/processed/   — series_raw.csv, components_raw.csv, index.csv, idc_data.xlsx")
    print("  outputs/figures/  — 6 figuras (PNG)")


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


def _update_readme(components, index_df, readme_path: Path = README_PATH) -> None:
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
    readme_path.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
