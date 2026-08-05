from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

from src.download_bcb_release import (
    _release_files,
    _validate_downloaded_file,
    _validate_period,
)


WORKFLOW_FILE = "fetch-bcb-release.yml"
RUN_TITLE_PREFIX = "BCB release"
ARTIFACT_PREFIX = "bcb-release-"


def _run_gh(
    args: Sequence[str],
    *,
    check: bool = True,
    timeout: float = 60,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["gh", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("GitHub CLI (gh) nao encontrado.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Tempo esgotado ao executar gh {' '.join(args)}") from exc

    if check and result.returncode != 0:
        details = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        raise RuntimeError(f"Falha ao executar gh {' '.join(args)}:\n{details}")
    return result


def _parse_github_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _select_run(
    runs: Sequence[dict[str, Any]],
    *,
    period: str,
    ref: str,
    not_before: datetime,
) -> Optional[dict[str, Any]]:
    title = f"{RUN_TITLE_PREFIX} {period}"
    matches = [
        run
        for run in runs
        if run.get("displayTitle") == title
        and run.get("headBranch") == ref
        and _parse_github_datetime(run["createdAt"]) >= not_before
    ]
    if not matches:
        return None
    return max(matches, key=lambda run: _parse_github_datetime(run["createdAt"]))


def _wait_for_run(period: str, ref: str, not_before: datetime, timeout: float) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = _run_gh(
            [
                "run",
                "list",
                "--workflow",
                WORKFLOW_FILE,
                "--event",
                "workflow_dispatch",
                "--limit",
                "20",
                "--json",
                "databaseId,displayTitle,createdAt,status,conclusion,headBranch",
            ]
        )
        run = _select_run(
            json.loads(result.stdout),
            period=period,
            ref=ref,
            not_before=not_before,
        )
        if run is not None:
            return int(run["databaseId"])
        time.sleep(3)
    raise RuntimeError("Tempo esgotado aguardando o workflow aparecer no GitHub Actions.")


def _copy_artifact_files(
    artifact_dir: Path,
    output_dir: Path,
    period: str,
    overwrite: bool,
) -> None:
    period_dir = output_dir / period
    period_dir.mkdir(parents=True, exist_ok=True)

    for filename in _release_files(period).values():
        matches = list(artifact_dir.rglob(filename))
        if len(matches) != 1:
            raise RuntimeError(
                f"Artefato deveria conter exatamente um arquivo {filename}; "
                f"encontrados: {len(matches)}"
            )

        destination = period_dir / filename
        if destination.exists() and not overwrite:
            print(f"Arquivo ja existe, pulando: {destination}")
            continue

        part = destination.with_name(f"{destination.name}.part")
        try:
            shutil.copyfile(matches[0], part)
            _validate_downloaded_file(part, filename)
            part.replace(destination)
        finally:
            part.unlink(missing_ok=True)
        print(f"Baixado via GitHub Actions: {destination}")


def download_release_via_github(
    period: str,
    output_dir: Path,
    *,
    ref: str = "main",
    timeout: float = 900,
    overwrite: bool = False,
) -> int:
    _run_gh(["auth", "status"])

    not_before = datetime.now(timezone.utc) - timedelta(minutes=1)
    _run_gh(
        [
            "workflow",
            "run",
            WORKFLOW_FILE,
            "--ref",
            ref,
            "-f",
            f"period={period}",
        ]
    )
    run_id = _wait_for_run(period, ref, not_before, timeout)
    print(f"GitHub Actions run: {run_id}")

    watch = _run_gh(
        ["run", "watch", str(run_id), "--exit-status"],
        check=False,
        timeout=timeout,
    )
    if watch.returncode != 0:
        logs = _run_gh(
            ["run", "view", str(run_id), "--log-failed"],
            check=False,
            timeout=120,
        )
        details = "\n".join(
            part
            for part in (watch.stdout, watch.stderr, logs.stdout, logs.stderr)
            if part
        ).strip()
        raise RuntimeError(f"Workflow {run_id} falhou:\n{details}")

    artifact_name = f"{ARTIFACT_PREFIX}{period}"
    with tempfile.TemporaryDirectory(prefix=f"idc-{artifact_name}-") as temp_dir:
        _run_gh(
            [
                "run",
                "download",
                str(run_id),
                "--name",
                artifact_name,
                "--dir",
                temp_dir,
            ],
            timeout=180,
        )
        _copy_artifact_files(
            Path(temp_dir),
            output_dir,
            period,
            overwrite=overwrite,
        )
    return run_id


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Aciona um runner do GitHub Actions para baixar a divulgacao mensal "
            "do BCB e copia o artefato validado para data/raw/YYYYMM/."
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
        "--ref",
        default="main",
        help="Ref que contem o workflow no GitHub (padrao: main).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=900,
        help="Tempo maximo total de espera, em segundos (padrao: 900).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Sobrescreve arquivos ja existentes.",
    )
    args = parser.parse_args()

    download_release_via_github(
        args.period,
        args.output_dir,
        ref=args.ref,
        timeout=args.timeout,
        overwrite=args.overwrite,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
