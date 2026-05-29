from __future__ import annotations

import argparse
import mimetypes
import os
import smtplib
import ssl
from dataclasses import dataclass
from datetime import date
from email.message import EmailMessage
from pathlib import Path

import pandas as pd


PT_MONTH_FULL = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}

PT_MONTH_ABBR = {
    1: "jan",
    2: "fev",
    3: "mar",
    4: "abr",
    5: "mai",
    6: "jun",
    7: "jul",
    8: "ago",
    9: "set",
    10: "out",
    11: "nov",
    12: "dez",
}


@dataclass(frozen=True)
class UpdateEmailData:
    period: str
    subject: str
    body: str
    pdf_path: Path
    pdf_size: int


def main() -> None:
    _load_dotenv(Path(".env"))
    args = _parse_args()
    recipients = _read_recipients(args.recipients)
    email_data = build_update_email(args.period, args.pdf)

    if args.dry_run:
        print("Dry run only; no e-mail was sent.")
        print(f"Recipients: {', '.join(recipients)}")
        print(f"Subject: {email_data.subject}")
        print(f"PDF attached: {email_data.pdf_path.name} ({_format_file_size(email_data.pdf_size)})")
        print("\nBody:\n")
        print(email_data.body)
        return

    smtp_config = _smtp_config_from_env()
    sender = os.environ.get("IDC_EMAIL_FROM", smtp_config["username"])
    sender_name = os.environ.get("IDC_EMAIL_SENDER_NAME", "FGVcemif / FGV-EAESP")
    sent_to = send_update_email(
        email_data=email_data,
        recipients=recipients,
        sender=sender,
        sender_name=sender_name,
        smtp_config=smtp_config,
    )

    print(f"E-mail sent to: {', '.join(sent_to)}")
    print(f"Subject: {email_data.subject}")
    print(f"PDF attached: {email_data.pdf_path.name} ({_format_file_size(email_data.pdf_size)})")


def build_update_email(period: str | None = None, pdf_path: Path | None = None) -> UpdateEmailData:
    period = period or date.today().strftime("%Y%m")
    pdf_path = pdf_path or Path("outputs/report") / f"update-{period}" / f"idc-update-{period}.pdf"
    pdf_path = pdf_path.expanduser()

    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if pdf_path.stat().st_size <= 50 * 1024:
        raise RuntimeError(f"PDF is unexpectedly small: {pdf_path} ({pdf_path.stat().st_size} bytes)")

    index_df = pd.read_csv("data/processed/index.csv", index_col=0, parse_dates=True)
    components_df = pd.read_csv("data/processed/components_raw.csv", index_col=0, parse_dates=True)

    index_df = index_df.dropna(subset=["index"])
    if len(index_df) < 2:
        raise RuntimeError("data/processed/index.csv must contain at least two IDC observations.")

    current_date = index_df.index[-1]
    previous_date = index_df.index[-2]
    current_index = index_df.iloc[-1]
    previous_index = index_df.iloc[-2]
    current_components = components_df.loc[current_date]

    mesref = _format_period_abbr(current_date)
    mesanterior = _format_period_abbr(previous_date)
    mes_referencia = _format_period_full(current_date)
    idc_atual = _format_decimal(current_index["index"])
    idc_anterior = _format_decimal(previous_index["index"])

    subject = f"IDC — Atualização {mesref}: índice alcança {idc_atual}"
    body = f"""Prezados,

Segue a atualização mensal do Índice de Desconforto de Crédito (IDC),
competência {period} (dados de {mes_referencia}).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IDC — {mesref}: {idc_atual}  (anterior {mesanterior}: {idc_anterior})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Componentes:
  C – Comprometimento de renda: {_format_percent(current_components["C"])}  (normalizado: {_format_decimal(current_index["C_norm"])})
  I – Inadimplência 90+ dias:   {_format_percent(current_components["I"])}  (normalizado: {_format_decimal(current_index["I_norm"])})
  Q – Modalidades onerosas:     {_format_percent(current_components["Q"] * 100)}  (normalizado: {_format_decimal(current_index["Q_norm"])})

Nota: 1,000 = pior valor histórico; 0,000 = melhor valor histórico.

O relatório completo com análise e gráficos está em anexo (PDF).

Atenciosamente,
FGVcemif / FGV-EAESP
"""

    return UpdateEmailData(
        period=period,
        subject=subject,
        body=body,
        pdf_path=pdf_path,
        pdf_size=pdf_path.stat().st_size,
    )


def send_update_email(
    *,
    email_data: UpdateEmailData,
    recipients: list[str],
    sender: str,
    sender_name: str,
    smtp_config: dict[str, str | int | bool],
) -> list[str]:
    sent_to: list[str] = []
    context = ssl.create_default_context()

    timeout = int(os.environ.get("IDC_SMTP_TIMEOUT", "15"))
    if smtp_config["ssl"]:
        server_context = smtplib.SMTP_SSL(
            str(smtp_config["host"]),
            int(smtp_config["port"]),
            context=context,
            timeout=timeout,
        )
    else:
        server_context = smtplib.SMTP(str(smtp_config["host"]), int(smtp_config["port"]), timeout=timeout)

    with server_context as server:
        if smtp_config["starttls"]:
            server.starttls(context=context)
        server.login(str(smtp_config["username"]), str(smtp_config["password"]))

        for recipient in recipients:
            message = _build_message(
                email_data=email_data,
                sender=sender,
                sender_name=sender_name,
                recipient=recipient,
            )
            server.send_message(message)
            sent_to.append(recipient)

    return sent_to


def _build_message(
    *,
    email_data: UpdateEmailData,
    sender: str,
    sender_name: str,
    recipient: str,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = f"{sender_name} <{sender}>"
    message["To"] = recipient
    message["Subject"] = email_data.subject

    reply_to = os.environ.get("IDC_EMAIL_REPLY_TO")
    if reply_to:
        message["Reply-To"] = reply_to

    message.set_content(email_data.body)

    content_type, _ = mimetypes.guess_type(email_data.pdf_path.name)
    maintype, subtype = (content_type or "application/pdf").split("/", 1)
    message.add_attachment(
        email_data.pdf_path.read_bytes(),
        maintype=maintype,
        subtype=subtype,
        filename=email_data.pdf_path.name,
    )
    return message


def _read_recipients(path: Path) -> list[str]:
    recipients = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not recipients:
        raise RuntimeError(f"No recipients found in {path}")
    return recipients


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _smtp_config_from_env() -> dict[str, str | int | bool]:
    username = os.environ.get("IDC_SMTP_USERNAME") or os.environ.get("SMTP_USERNAME")
    password = os.environ.get("IDC_SMTP_PASSWORD") or os.environ.get("SMTP_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "Missing SMTP credentials. Set IDC_SMTP_USERNAME and IDC_SMTP_PASSWORD "
            "(for Gmail, use an app password, not the account password)."
        )

    use_ssl = _env_bool("IDC_SMTP_SSL", default=True)
    use_starttls = _env_bool("IDC_SMTP_STARTTLS", default=not use_ssl)
    default_port = 465 if use_ssl else 587

    return {
        "host": os.environ.get("IDC_SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.environ.get("IDC_SMTP_PORT", default_port)),
        "username": username,
        "password": password,
        "ssl": use_ssl,
        "starttls": use_starttls,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send the monthly IDC update e-mail with the PDF report attached."
    )
    parser.add_argument(
        "period",
        nargs="?",
        default=date.today().strftime("%Y%m"),
        help="BCB release period in YYYYMM format. Defaults to the current month.",
    )
    parser.add_argument(
        "--recipients",
        type=Path,
        default=Path("mailing_list.txt"),
        help="Plain-text file with one recipient e-mail per line.",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help="Path to the PDF report. Defaults to outputs/report/update-PERIOD/idc-update-PERIOD.pdf.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print recipients, subject, body, and attachment info without sending.",
    )
    return parser.parse_args()


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _format_decimal(value: float) -> str:
    return f"{value:.3f}".replace(".", ",")


def _format_percent(value: float) -> str:
    return f"{value:.1f}%".replace(".", ",")


def _format_period_abbr(timestamp: pd.Timestamp) -> str:
    return f"{PT_MONTH_ABBR[timestamp.month]}-{timestamp.year}"


def _format_period_full(timestamp: pd.Timestamp) -> str:
    return f"{PT_MONTH_FULL[timestamp.month]} de {timestamp.year}"


def _format_file_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / 1024:.0f} KB"


if __name__ == "__main__":
    main()
