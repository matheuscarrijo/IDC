from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "https://www.bcb.gov.br/content/estatisticas/hist_estatisticasmonetariascredito"
TABLE_SUFFIX = "Tabelas_de_estatisticas_monetarias_e_de_credito.xlsx"
REPORT_SUFFIX = "Texto_de_estatisticas_monetarias_e_de_credito.pdf"
USER_AGENT = "Mozilla/5.0 (compatible; IDC-data-downloader/1.0)"
MIN_FILE_SIZE = 10_000


def _validate_period(period: str) -> str:
    if not re.fullmatch(r"\d{6}", period):
        raise argparse.ArgumentTypeError("Use o formato YYYYMM, por exemplo: 202604.")

    month = int(period[4:6])
    if month < 1 or month > 12:
        raise argparse.ArgumentTypeError("O mes do periodo deve estar entre 01 e 12.")

    return period


def _release_files(period: str) -> dict[str, str]:
    return {
        "table": f"{period}_{TABLE_SUFFIX}",
        "report": f"{period}_{REPORT_SUFFIX}",
    }


def _validate_downloaded_file(path: Path, filename: str) -> None:
    """Reject truncated responses and HTML error pages before publishing a file."""
    if not path.is_file() or path.stat().st_size < MIN_FILE_SIZE:
        raise RuntimeError(f"Arquivo baixado ausente ou muito pequeno: {filename}")

    with path.open("rb") as downloaded_file:
        header = downloaded_file.read(5)
    if filename.endswith(".xlsx") and not header.startswith(b"PK\x03\x04"):
        raise RuntimeError(f"Conteudo invalido para XLSX: {filename}")
    if filename.endswith(".pdf") and header != b"%PDF-":
        raise RuntimeError(f"Conteudo invalido para PDF: {filename}")


def _download(url: str, destination: Path, overwrite: bool) -> None:
    if destination.exists() and not overwrite:
        print(f"Arquivo ja existe, pulando: {destination}")
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_destination = destination.with_name(f"{destination.name}.part")
    request = Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urlopen(request, timeout=60) as response, tmp_destination.open("wb") as output:
            shutil.copyfileobj(response, output)
        _validate_downloaded_file(tmp_destination, destination.name)
    except HTTPError as exc:
        tmp_destination.unlink(missing_ok=True)
        raise RuntimeError(f"Falha ao baixar {url}: HTTP {exc.code}") from exc
    except URLError as exc:
        tmp_destination.unlink(missing_ok=True)
        raise RuntimeError(f"Falha ao baixar {url}: {exc.reason}") from exc
    except OSError as exc:
        tmp_destination.unlink(missing_ok=True)
        raise RuntimeError(f"Falha ao salvar {destination}: {exc}") from exc
    except RuntimeError:
        tmp_destination.unlink(missing_ok=True)
        raise

    tmp_destination.replace(destination)
    print(f"Baixado: {destination}")


def download_release(period: str, output_dir: Path, overwrite: bool = False) -> None:
    files = _release_files(period)
    period_dir = output_dir / period

    for filename in files.values():
        url = f"{BASE_URL}/{filename}"
        _download(url, period_dir / filename, overwrite=overwrite)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Baixa a tabela XLSX e o PDF do relatorio mensal de Estatisticas "
            "Monetarias e de Credito do Banco Central."
        )
    )
    parser.add_argument("period", type=_validate_period, help="Periodo no formato YYYYMM.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw"),
        help="Diretorio base para salvar data/raw/YYYYMM/ (padrao: data/raw).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Sobrescreve arquivos ja existentes.",
    )
    args = parser.parse_args()

    download_release(args.period, args.output_dir, overwrite=args.overwrite)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
