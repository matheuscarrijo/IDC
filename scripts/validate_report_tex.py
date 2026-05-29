#!/usr/bin/env python3
"""Validate IDC monthly report LaTeX after it has been filled.

The checks are intentionally narrow: they enforce the local writing/style rules
that are easy to regress during the monthly automation.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


TEXTBF_RE = re.compile(r"\\textbf\{((?:[^{}]|\{[^{}]*\})*)\}", re.DOTALL)
MONTH_YEAR_RE = re.compile(
    r"^(?:jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)-\d{4}$",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(
    r"""^
    [+-]?
    (?:
        \d+(?:[,.]\d+)?
        |
        \d+(?:[,.]\d+)?\\%
        |
        \d+(?:[,.]\d+)?~(?:ponto|pontos|p\.p\.)
        |
        \\placeholder\{(?:X|x|[,.~%\\$+\-ponto\s])+[^{}]*\}
        |
        \\mesref|\\mesanterior|\\mesproximo
    )
    $""",
    re.VERBOSE,
)


def active_lines(text: str) -> list[str]:
    return [
        line
        for line in text.splitlines()
        if not line.lstrip().startswith("%")
        and r"\newcommand{\placeholder}" not in line
    ]


def strip_latex_spacing(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip())
    return value.replace(r"\,", "").strip()


def validate_textbf(text: str) -> list[str]:
    errors: list[str] = []
    for match in TEXTBF_RE.finditer(text):
        content = strip_latex_spacing(match.group(1))
        if NUMBER_RE.match(content) or MONTH_YEAR_RE.match(content):
            continue
        line = text.count("\n", 0, match.start()) + 1
        errors.append(
            f"line {line}: \\textbf{{...}} is only allowed for numbers, deltas, "
            f"percentages, and abbreviated month-year values; found {content!r}"
        )
    return errors


def validate_placeholders(text: str) -> list[str]:
    errors: list[str] = []
    for i, line in enumerate(active_lines(text), start=1):
        if r"\placeholder{" in line:
            errors.append(f"line {i}: active placeholder remains")
    return errors


def validate_sources(text: str) -> list[str]:
    errors: list[str] = []
    if re.search(
        r"\\end\{figure\}\s*\\fonte\{BCB, elaboração própria\.\}",
        text,
        re.DOTALL,
    ):
        errors.append(
            r"\fonte{BCB, elaboração própria.} must stay inside the figure environment"
        )
    if re.search(
        r"Fonte:\s*BCB,\s*elaboração própria\.\s*Fonte:\s*BCB,\s*elaboração própria\.",
        text,
        re.DOTALL,
    ):
        errors.append("duplicate BCB source note detected")
    figure_blocks = re.findall(r"\\begin\{figure\}.*?\\end\{figure\}", text, re.DOTALL)
    for n, block in enumerate(figure_blocks, start=1):
        if r"\caption{" in block and r"\fonte{" not in block:
            errors.append(f"figure {n}: missing source note inside figure environment")
    return errors


def validate_log(log_file: Path | None) -> list[str]:
    if log_file is None:
        return []
    if not log_file.exists():
        return [f"LaTeX log not found: {log_file}"]
    text = log_file.read_text(encoding="utf-8", errors="replace")
    errors: list[str] = []
    if "! LaTeX Error" in text:
        errors.append("LaTeX log contains an error")
    overfull = re.findall(r"Overfull \\hbox[^\n]*", text)
    if overfull:
        errors.append("LaTeX log contains overfull hbox warnings: " + "; ".join(overfull))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tex_file", type=Path)
    parser.add_argument(
        "--log",
        type=Path,
        help="Optional LaTeX .log file to check for errors and overfull hbox warnings.",
    )
    args = parser.parse_args()

    text = args.tex_file.read_text(encoding="utf-8")
    active = "\n".join(active_lines(text))
    errors = []
    errors.extend(validate_textbf(active))
    errors.extend(validate_placeholders(text))
    errors.extend(validate_sources(active))
    errors.extend(validate_log(args.log))

    if errors:
        print("Report validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Report validation OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
