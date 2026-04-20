from pathlib import Path

from src.build_index import NORM_METHODS, build_components, build_index
from src.load_data import load_raw_series
from src.plot import plot_all

DATA_OUT = Path("outputs/data")


def main() -> None:
    Path("outputs/data").mkdir(parents=True, exist_ok=True)
    Path("outputs/figures").mkdir(parents=True, exist_ok=True)

    print("Carregando dados do BCB...")
    raw = load_raw_series()
    raw.to_csv(DATA_OUT / "series_raw.csv")

    print("Construindo componentes (C, I, Q)...")
    components = build_components(raw)
    components.to_csv(DATA_OUT / "components_raw.csv")
    start = components.index[0].strftime("%b-%Y")
    end   = components.index[-1].strftime("%b-%Y")
    print(f"  Período: {start} a {end} ({len(components)} observações)")

    print("Construindo índice (3 normalizações)...")
    index_df = build_index(components)
    index_df.to_csv(DATA_OUT / "index_full.csv")

    plot_all(components, index_df)
    _print_summary(index_df)


def _print_summary(index_df) -> None:
    labels = {
        "minmax":     "Min-Max",
        "robust":     "Min-Max Robusto",
        "percentile": "Rank Percentil",
    }
    last_date = index_df.index[-1].strftime("%b-%Y")
    print(f"\nEstatísticas descritivas — Índice agregado (último dado: {last_date}):")
    print(f"  {'Método':<22} {'Atual':>8} {'Média':>8} {'Desvpad':>8} {'Mín':>8} {'Máx':>8}")
    print("  " + "-" * 62)
    for method, label in labels.items():
        s = index_df[f"index_{method}"]
        print(
            f"  {label:<22} {s.iloc[-1]:8.3f} {s.mean():8.3f}"
            f" {s.std():8.3f} {s.min():8.3f} {s.max():8.3f}"
        )
    print("\nOutputs salvos em:")
    print("  outputs/data/    — series_raw.csv, components_raw.csv, index_full.csv")
    print("  outputs/figures/ — 01 a 08 (PNG)")


if __name__ == "__main__":
    main()
