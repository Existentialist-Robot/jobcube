#!/usr/bin/env python3
"""Scaffold a LinkedIn outreach log for a target org + role.

Creates working/outreach/<YYYY-MM-DD> - <Org> - <Role>/outreach_log.md from
working/templates/OUTREACH_LOG_TEMPLATE.md, filling in the title and the
date/org/role header fields. Everything else in the template is left as
placeholders for you to complete. Does NOT call linkedin-cli -- scaffolding
only, so it is safe to run unattended.

The log format lives in OUTREACH_LOG_TEMPLATE.md and nowhere else: edit that
file to change the shape of every future log.

Usage:
    python working/scripts/outreach/scope_targets.py "Acme Institute" "Manager, Programs"
    python working/scripts/outreach/scope_targets.py "Org" "Role" --date 2026-08-01 --force

Stdlib only.
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

# working/scripts/outreach/scope_targets.py -> repo root is parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]
OUTREACH_DIR = REPO_ROOT / "working" / "outreach"
LOG_TEMPLATE = REPO_ROOT / "working" / "templates" / "OUTREACH_LOG_TEMPLATE.md"

# Lines rewritten in the copied template, matched by prefix. Each entry is
# (prefix, builder) -- builder receives (org, role, date) and returns the whole
# replacement line. A prefix that never matches is reported as a warning rather
# than a failure, so an edited template still scaffolds.
SUBSTITUTIONS = [
    ("# Outreach Log", lambda org, role, date: f"# Outreach Log — {org} — {role}"),
    ("- **Date opened:**", lambda org, role, date: f"- **Date opened:** {date}"),
    ("- **Org:**", lambda org, role, date: f"- **Org:** {org} ([City, Prov])"),
    ("- **Role:**", lambda org, role, date: f"- **Role:** {role} ([division/team])"),
]

# The "how to use / copy this file" preamble is stale once the copy exists.
COPY_INSTRUCTION_MARKERS = ("**How to use:**", "`working/outreach/<YYYY-MM-DD>")


def sanitize(name: str) -> str:
    """Make a string safe for a Windows folder name."""
    cleaned = re.sub(r'[<>:"/\\|?*]', "", name).strip().rstrip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def build_log(template_text: str, org: str, role: str, date: str) -> tuple[str, list[str]]:
    """Fill the template's header fields. Returns (text, unmatched prefixes)."""
    lines = template_text.splitlines()
    matched = set()
    out = []

    for line in lines:
        stripped = line.lstrip("> ").rstrip()
        if any(marker in line for marker in COPY_INSTRUCTION_MARKERS):
            continue  # drop the "copy this file to ..." preamble
        for prefix, builder in SUBSTITUTIONS:
            if stripped.startswith(prefix):
                line = builder(org, role, date)
                matched.add(prefix)
                break
        out.append(line)

    unmatched = [prefix for prefix, _ in SUBSTITUTIONS if prefix not in matched]
    text = "\n".join(out).rstrip() + "\n"
    # Collapse the blank quote line the dropped preamble may leave behind.
    text = re.sub(r"(?m)^>\s*\n(?=>\s*\n)", "", text)
    return text, unmatched


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a LinkedIn outreach log.")
    parser.add_argument("org", help='Target organization, e.g. "Acme Institute"')
    parser.add_argument("role", help='Role title, e.g. "Manager, Programs"')
    parser.add_argument(
        "--date",
        default=datetime.date.today().isoformat(),
        help="Log date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Overwrite an existing outreach_log.md"
    )
    args = parser.parse_args()

    if not LOG_TEMPLATE.exists():
        print(f"Log template not found: {LOG_TEMPLATE}", file=sys.stderr)
        print(
            "This script copies working/templates/OUTREACH_LOG_TEMPLATE.md; restore it first.",
            file=sys.stderr,
        )
        return 1

    folder = OUTREACH_DIR / f"{args.date} - {sanitize(args.org)} - {sanitize(args.role)}"
    log_path = folder / "outreach_log.md"

    if log_path.exists() and not args.force:
        print(f"Refusing to overwrite existing log: {log_path}", file=sys.stderr)
        print("Pass --force to overwrite.", file=sys.stderr)
        return 1

    text, unmatched = build_log(
        LOG_TEMPLATE.read_text(encoding="utf-8"), args.org, args.role, args.date
    )

    folder.mkdir(parents=True, exist_ok=True)
    log_path.write_text(text, encoding="utf-8")
    print(f"Scaffolded: {log_path}")

    if unmatched:
        print(
            "WARNING: these header lines were not found in the template and were "
            "left unfilled: " + ", ".join(unmatched),
            file=sys.stderr,
        )
    print("Next: Stage 1 web research -> fill the target table, then resolve handles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
