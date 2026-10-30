"""SCR.data (Banco Central do Brasil): download, validation and PF aggregation.

The SCR.data is the BCB's open dataset of aggregated credit operations of the Sistema de Informações de
Crédito (SCR), published as one ZIP per year with one CSV per month (license: ODbL).  The IDC uses it to
measure the delinquency (I) and the share of costly credit (Q) of household borrowers by income class, by
lender type, by occupation and by state.

Design rules:

* Only household (PF) rows are used.
* Universe = crédito livre PF ("Sem destinação específica") excluding rural, housing and export/import
  credit.  It matches the SGS 20570 balance within about 0.1-4% (see ``lenses.conciliar``).
* The BCB regenerates the monthly files continuously and the current-year ZIP is sometimes rewritten while
  it is being downloaded, so every download is validated (the body must match its own ``Content-Length``,
  the central directory must open and the CRC of every month is checked when it is read) and retried.
* Raw files are never kept: only small aggregates plus vintage metadata (ZIP ``Last-Modified`` and each
  month's generation timestamp) are stored in ``data/processed/scr/``.
* ``refresh`` is incremental: a yearly ZIP is downloaded again only when its ``Last-Modified`` changed.

Command line (from the repository root)::

    python3 -m src.scr_data refresh            # download the years whose ZIP changed
    python3 -m src.scr_data refresh --full     # download every year again
    python3 -m src.scr_data refresh --years 2025 2026
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

BASE_URL = "https://www.bcb.gov.br/pda/desig/scrdata_{year}.zip"
USER_AGENT = "Mozilla/5.0"
FIRST_YEAR = 2012  # the SCR.data starts in jul-2012
OUT_DIR = Path("data/processed/scr")
WORK_DIR = Path("data/raw/scr_zip")  # temporary ZIPs, deleted after each year (data/raw/ is ignored by Git)
LIVRE = "Sem destinação específica"

USECOLS = [
    "data_base", "uf", "segmento", "cliente", "cnae_ocupacao", "porte",
    "modalidade", "submodalidade", "origem",
    "a_vencer_ate_90_dias", "vencido_de_15_ate_90_dias",
    "carteira_ativa", "carteira_inadimplencia", "ativo_problematico",
]
NUM_COLS = [
    "a_vencer_ate_90_dias", "vencido_de_15_ate_90_dias",
    "carteira_ativa", "carteira_inadimplencia", "ativo_problematico",
]
# Lens name -> SCR.data column.
LENS_FIELDS = {
    "uf": "uf",
    "credor": "segmento",
    "ocupacao": "cnae_ocupacao",
    "faixa": "porte",
}
# Product categories counted as "crédito oneroso" (numerator of Q).  Same definition as the IDC: cheque
# especial (the SGS series also includes conta garantida), crédito pessoal não consignado, cartão rotativo
# (the SGS rotativo includes the SCR "não migrado" submodality) and cartão parcelado.
ONEROSAS = (
    "cartao_rotativo",
    "cartao_parcelado",
    "cartao_nao_migrado",
    "cheque_especial_cg",
    "pessoal_nao_consignado",
)
# Categories excluded from the lens universe.
FORA_DO_UNIVERSO = ("rural", "habitacional", "export_import")


def classify_categoria(modalidade: pd.Series, submodalidade: pd.Series) -> pd.Series:
    """Map SCR modality/submodality strings to the IDC product categories.

    Strings are stripped first: some submodality labels carry a trailing space ("... lojista "), which
    silently breaks equality tests.
    """
    mod = modalidade.fillna("").str.strip()
    sub = submodalidade.fillna("").str.strip()
    conditions = [
        mod.str.contains("rurais", regex=False),
        mod.str.contains("imobili", regex=False),
        mod.str.contains("exporta|importa", regex=True),
        sub.str.contains("compra à vista e parcelado lojista", regex=False),
        sub.eq("Crédito rotativo vinculado a cartão de crédito"),
        sub.str.startswith("Cartão de crédito - compra") & ~sub.str.contains("vista", regex=False),
        sub.eq("Cartão de crédito - não migrado"),
        sub.isin(["Cheque especial", "Cheque especial e conta garantida", "Conta Garantida"]),
        sub.eq("Crédito pessoal - sem consignação em folha de pagam."),
        sub.eq("Crédito pessoal - com consignação em folha de pagam."),
        sub.str.contains("veículos automotores", regex=False),
    ]
    choices = [
        "rural", "habitacional", "export_import",
        "cartao_vista_lojista", "cartao_rotativo", "cartao_parcelado",
        "cartao_nao_migrado", "cheque_especial_cg", "pessoal_nao_consignado",
        "consignado", "veiculos",
    ]
    return pd.Series(np.select(conditions, choices, default="outros"), index=modalidade.index)


def _read_month(zip_path: str, member: str) -> tuple[str, dict[str, pd.DataFrame], tuple]:
    """Read one monthly CSV from a local ZIP and return the PF aggregates of every lens."""
    with zipfile.ZipFile(zip_path) as zf:
        info = zf.getinfo(member)
        with zf.open(member) as fh:  # the CRC is verified when the member is fully read
            df = pd.read_csv(fh, sep=";", encoding="utf-8-sig", dtype=str, usecols=USECOLS)
    df = df[df["cliente"] == "PF"].copy()
    for col in NUM_COLS:
        df[col] = pd.to_numeric(df[col].str.replace(",", ".", regex=False), errors="coerce")
    df["categoria"] = classify_categoria(df["modalidade"], df["submodalidade"])
    df["oneroso"] = df["categoria"].isin(ONEROSAS)
    df["livre"] = df["origem"] == LIVRE
    month = pd.Timestamp(df["data_base"].iloc[0]).to_period("M").to_timestamp()

    measures = {
        "carteira": ("carteira_ativa", "sum"),
        "inad": ("carteira_inadimplencia", "sum"),
        "ap": ("ativo_problematico", "sum"),
        "v1590": ("vencido_de_15_ate_90_dias", "sum"),
        "a90": ("a_vencer_ate_90_dias", "sum"),
    }
    universe = df[df["livre"] & ~df["categoria"].isin(FORA_DO_UNIVERSO)]
    out = {}
    for lens, column in LENS_FIELDS.items():
        g = universe.groupby([column, "oneroso"], as_index=False).agg(**measures)
        g = g.rename(columns={column: "unidade"})
        g.insert(0, "data_base", month)
        out[lens] = g
    return member, out, info.date_time


def last_modified(year: int, retries: int = 3) -> str | None:
    """``Last-Modified`` header of a yearly ZIP (HEAD request); ``None`` if the year is not published (HTTP 404)."""
    request = urllib.request.Request(BASE_URL.format(year=year), method="HEAD", headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.headers.get("Last-Modified", "")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            last_error = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        time.sleep(3 * attempt)
    raise RuntimeError(f"SCR.data {year}: não foi possível consultar o arquivo ({last_error})")


def download_year(year: int, dest: Path, retries: int = 4) -> dict:
    """Download one yearly ZIP with validation; returns vintage metadata.

    The server sometimes answers consecutive requests with different versions of the same ZIP (for example
    with and without the newest month), so the size of a previous HEAD request is *not* used for validation.
    ``curl`` already fails on a body shorter than the Content-Length of its own response, the central
    directory must open, and the CRC of every member is checked when it is read.
    """
    url = BASE_URL.format(year=year)
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers_path = Path(str(dest) + ".headers")
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            subprocess.run(
                ["curl", "-sL", "--fail", "-m", "1500", "-D", str(headers_path), "-o", str(dest), url],
                check=True,
            )
            headers = headers_path.read_text(errors="ignore")
            modified = next((ln.split(":", 1)[1].strip() for ln in headers.splitlines()
                             if ln.lower().startswith("last-modified:")), "")
            with zipfile.ZipFile(dest) as zf:  # the central directory must be readable
                members = sorted(n for n in zf.namelist() if n.startswith("scrdata_") and n.endswith(".csv"))
            if not members:
                raise OSError("empty ZIP")
            return {"year": year, "size": dest.stat().st_size, "last_modified": modified, "members": members}
        except Exception as exc:  # noqa: BLE001 - retry on any failure
            last_error = exc
            time.sleep(10 * attempt)
    raise RuntimeError(f"SCR.data {year}: download falhou ({last_error})")


def _extract_year(year: int, workdir: Path, workers: int, log) -> tuple[list[tuple], dict]:
    """Download one year, aggregate every month in parallel and delete the raw ZIP."""
    zip_path = workdir / f"scrdata_{year}.zip"
    meta = download_year(year, zip_path)
    try:
        for attempt in range(3):
            try:
                with ProcessPoolExecutor(max_workers=workers) as pool:
                    futures = [pool.submit(_read_month, str(zip_path), m) for m in meta["members"]]
                    return [f.result() for f in futures], meta
            except Exception as exc:  # noqa: BLE001 - e.g. a CRC error on a ZIP rewritten during the download
                log(f"{year}: leitura falhou ({exc!r}); baixando de novo (tentativa {attempt + 1})")
                meta = download_year(year, zip_path)
        raise RuntimeError(f"SCR.data {year}: não foi possível ler o arquivo")
    finally:
        zip_path.unlink(missing_ok=True)
        Path(str(zip_path) + ".headers").unlink(missing_ok=True)


def load_vintage(outdir: Path = OUT_DIR) -> pd.DataFrame:
    """Vintage table: one row per monthly file (member, zip_year, zip_last_modified, generated)."""
    path = outdir / "scr_vintage.csv"
    if not path.exists():
        return pd.DataFrame(columns=["member", "zip_year", "zip_last_modified", "generated"])
    return pd.read_csv(path)


def load_aggregates(outdir: Path = OUT_DIR) -> dict[str, pd.DataFrame]:
    """Raw lens aggregates (one frame per lens) as stored by :func:`refresh`."""
    return {lens: pd.read_csv(outdir / f"scr_{lens}.csv") for lens in LENS_FIELDS}


def years_to_refresh(vintage: pd.DataFrame, published: dict[int, str | None], full: bool = False) -> list[int]:
    """Years whose ZIP must be downloaded: missing locally, changed on the server, or all of them with ``full``."""
    stored = vintage.groupby("zip_year")["zip_last_modified"].first().to_dict() if len(vintage) else {}
    todo = []
    for year, modified in sorted(published.items()):
        if modified is None:  # not published (yet)
            continue
        if full or year not in stored or str(stored[year]) != modified:
            todo.append(year)
    return todo


def _write_atomic(frame: pd.DataFrame, path: Path) -> None:
    staged = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(staged, index=False)
    os.replace(staged, path)


def refresh(outdir: Path = OUT_DIR, workdir: Path = WORK_DIR, years: list[int] | None = None, full: bool = False,
            workers: int = 3, log=print, today: dt.date | None = None) -> pd.DataFrame:
    """Update the stored aggregates, downloading only the yearly ZIPs that changed.

    ``years`` limits the check to some years (default: every year from 2012 to the current one).  Returns the
    vintage table after the update.  Raises ``RuntimeError`` when a needed ZIP cannot be downloaded.
    """
    today = today or dt.date.today()
    outdir.mkdir(parents=True, exist_ok=True)
    vintage = load_vintage(outdir)
    candidates = years or list(range(FIRST_YEAR, today.year + 1))
    published: dict[int, str | None] = {}
    for year in candidates:
        try:
            published[year] = last_modified(year)
        except RuntimeError as exc:
            if year in set(vintage["zip_year"].astype(int)) and not full:
                log(f"{year}: {exc}; mantendo os agregados já gravados")
                continue
            raise
    todo = years_to_refresh(vintage, published, full)
    if not todo:
        log("SCR.data: agregados atualizados; nenhum ZIP mudou.")
        return vintage
    log(f"SCR.data: baixando {', '.join(map(str, todo))}")
    frames = {lens: (pd.read_csv(outdir / f"scr_{lens}.csv", parse_dates=["data_base"]) if (outdir / f"scr_{lens}.csv").exists()
                     else pd.DataFrame()) for lens in LENS_FIELDS}
    rows = vintage.to_dict("records")
    for year in todo:
        results, meta = _extract_year(year, workdir, workers, log)
        for lens in LENS_FIELDS:
            old = frames[lens]
            if len(old):
                old = old[old["data_base"].dt.year != year]
            frames[lens] = pd.concat([old] + [out[lens] for _, out, _ in results], ignore_index=True)
        rows = [r for r in rows if int(r["zip_year"]) != year]
        for member, _, date_time in results:
            rows.append({"member": member, "zip_year": year, "zip_last_modified": meta["last_modified"],
                         "generated": "%d-%02d-%02d %02d:%02d:%02d" % date_time})
        log(f"SCR.data {year}: {len(results)} meses agregados")
    for lens, frame in frames.items():
        _write_atomic(frame.sort_values(["data_base", "unidade", "oneroso"]).reset_index(drop=True), outdir / f"scr_{lens}.csv")
    vintage = pd.DataFrame(rows).sort_values("member").reset_index(drop=True)
    _write_atomic(vintage, outdir / "scr_vintage.csv")
    return vintage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Atualiza os agregados do SCR.data em data/processed/scr/.")
    sub = parser.add_subparsers(dest="command", required=True)
    refresh_parser = sub.add_parser("refresh", help="baixa os ZIPs anuais que mudaram e atualiza os agregados")
    refresh_parser.add_argument("--full", action="store_true", help="baixa todos os anos de novo")
    refresh_parser.add_argument("--years", type=int, nargs="+", help="restringe a atualização a estes anos")
    refresh_parser.add_argument("--workers", type=int, default=3, help="processos para ler os meses de cada ZIP")
    args = parser.parse_args(argv)
    t0 = time.time()
    try:
        vintage = refresh(years=args.years, full=args.full, workers=args.workers,
                          log=lambda m: print(f"[{time.time() - t0:5.0f}s] {m}", flush=True))
    except RuntimeError as exc:
        print(f"Falha: {exc}", file=sys.stderr)
        return 1
    print(f"SCR.data: {len(vintage)} meses nos agregados (de {vintage['member'].min()} a {vintage['member'].max()}).")
    return 0


if __name__ == "__main__":  # the guard is required: the monthly files are read in worker processes
    raise SystemExit(main())
