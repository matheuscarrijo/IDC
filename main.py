from pathlib import Path

from src.build_index import build_components, build_index
from src.load_data import load_raw_series
from src.plot import plot_all

DATA_OUT = Path("outputs/data")


def main() -> None:
    Path("outputs/data").mkdir(parents=True, exist_ok=True)

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
    print("  outputs/data/     — series_raw.csv, components_raw.csv, index.csv")
    print("  outputs/figures/  — 6 figuras (PNG)")


if __name__ == "__main__":
    main()
