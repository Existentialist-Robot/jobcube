#!/usr/bin/env python3
"""Validate the repository's canonical Markdown job-sweep format."""

from __future__ import annotations

import re
import sys
from pathlib import Path


EXPECTED = [
    "#",
    "Role",
    "Org",
    "Location",
    "Salary",
    "Posted",
    "Closes",
    "Fit",
    "P(int)",
    r"P(hire\|int)",
    "Status",
]
REQUIRED_HEADINGS = [
    "## Search focus",
    "## Confirmed Open",
    "## Role Summaries",
    "## Strong but not in shortlist",
    "## Boards checked",
]
ROLE_LINK = re.compile(r"^\[[^\]]+\]\(https?://[^)]+\)")
PERCENT = re.compile(r"^\d{1,3}(?:\.\d+)?%$")


def split_row(line: str) -> list[str]:
    """Split a Markdown row while preserving escaped pipes."""
    marker = "\0PIPE\0"
    protected = line.strip().strip("|").replace(r"\|", marker)
    return [cell.strip().replace(marker, r"\|") for cell in protected.split("|")]


def table_at(lines: list[str], start: int) -> tuple[list[str], list[list[str]]]:
    for index in range(start, len(lines) - 1):
        if lines[index].lstrip().startswith("|") and lines[index + 1].lstrip().startswith("|"):
            header = split_row(lines[index])
            separator = split_row(lines[index + 1])
            if len(header) != len(separator):
                return header, []
            rows: list[list[str]] = []
            for line in lines[index + 2 :]:
                if not line.lstrip().startswith("|"):
                    break
                rows.append(split_row(line))
            return header, rows
    return [], []


def find_heading(lines: list[str], prefix: str) -> int:
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            return index
    return -1


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if not re.match(
        r"^# Job Sweep — (?:\d{4}-\d{2}-\d{2}|YYYY-MM-DD) — .+",
        lines[0] if lines else "",
    ):
        errors.append("title must be '# Job Sweep — YYYY-MM-DD — Focus Label'")

    for heading in REQUIRED_HEADINGS:
        if find_heading(lines, heading) < 0:
            errors.append(f"missing required section beginning '{heading}'")

    shortlist_index = find_heading(lines, "## Confirmed Open")
    if shortlist_index >= 0:
        header, rows = table_at(lines, shortlist_index)
        if header != EXPECTED:
            errors.append(
                "shortlist columns must exactly equal: " + " | ".join(EXPECTED)
            )
        if not rows:
            errors.append("shortlist table has no data rows")
        for row_number, row in enumerate(rows, 1):
            if len(row) != len(EXPECTED):
                errors.append(
                    f"shortlist row {row_number} has {len(row)} cells; expected {len(EXPECTED)}"
                )
                continue
            role = row[1]
            if not ROLE_LINK.match(role):
                errors.append(f"shortlist row {row_number} role is not a direct hyperlink")
            if not row[5]:
                errors.append(f"shortlist row {row_number} is missing Posted")
            if not row[6]:
                errors.append(f"shortlist row {row_number} is missing Closes")
            if "★" not in row[7]:
                errors.append(f"shortlist row {row_number} has no star rating")
            if not PERCENT.match(row[8]):
                errors.append(f"shortlist row {row_number} has invalid P(int)")
            if not PERCENT.match(row[9]):
                errors.append(f"shortlist row {row_number} has invalid P(hire|int)")
            if not row[10]:
                errors.append(f"shortlist row {row_number} is missing Status")

    if "**Probability rationale:**" not in text:
        errors.append("missing '**Probability rationale:**' after shortlist")

    # Harden the user's hyperlink requirement across every Markdown table with
    # a Role column, not only the canonical shortlist.
    index = 0
    while index < len(lines) - 1:
        if lines[index].lstrip().startswith("|") and lines[index + 1].lstrip().startswith("|"):
            header = split_row(lines[index])
            if "Role" in header:
                role_index = header.index("Role")
                _, rows = table_at(lines, index)
                for row_number, row in enumerate(rows, 1):
                    if len(row) > role_index and not ROLE_LINK.match(row[role_index]):
                        errors.append(
                            f"table near line {index + 1}, row {row_number}: Role must be hyperlinked"
                        )
                index += len(rows) + 2
                continue
        index += 1

    return errors


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: python -B working/scripts/validate_job_sweep.py <sweep.md> [...]")
        return 2

    failed = False
    for value in argv[1:]:
        path = Path(value)
        if not path.is_file():
            print(f"FAIL {path}: file not found")
            failed = True
            continue
        errors = validate(path)
        if errors:
            print(f"FAIL {path}")
            for error in errors:
                print(f"  - {error}")
            failed = True
        else:
            print(f"PASS {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
