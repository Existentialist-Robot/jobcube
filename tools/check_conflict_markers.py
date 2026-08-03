#!/usr/bin/env python3
"""Fail if any tracked text file carries an unresolved merge-conflict marker.

    python -B tools/check_conflict_markers.py

This exists because it happened. A rebase conflict was `git add`-ed after the
script meant to resolve it had already failed, and the markers went into a commit
in DOCTRINE.md. Nothing else would have caught it: the file still parses as
Markdown, the links still resolve, and every other gate passed.

Markers are matched at the start of a line with the length git actually emits, so
a `====` rule inside a docstring and a diff pasted into prose do not trip it.

Stdlib only. Exit 1 on any finding.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Exactly seven characters, at the start of a line — git's own marker width.
MARKER = re.compile(r"^(<{7}|={7}|>{7})(\s|$)")

BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ttf", ".otf", ".woff", ".woff2",
    ".ico", ".zip", ".gz", ".webp",
}


def tracked() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        print("check_conflict_markers: not a git repository", file=sys.stderr)
        raise SystemExit(2)
    return [ROOT / line for line in result.stdout.splitlines() if line]


def main() -> int:
    findings: list[str] = []
    scanned = 0
    for path in tracked():
        if path.suffix.lower() in BINARY_SUFFIXES or not path.is_file():
            continue
        # A vendored bundle is not ours to police, and three.min.js is 654KB of
        # one line.
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(("assets/vendor/", ".agents/vendor/")):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        scanned += 1
        for number, line in enumerate(text.splitlines(), 1):
            if MARKER.match(line):
                findings.append(f"{rel}:{number}: {line[:60]}")

    if findings:
        print(f"check_conflict_markers: {len(findings)} unresolved marker(s)\n")
        for item in findings:
            print(f"  {item}")
        print("\nResolve the conflict and commit again.")
        return 1
    print(f"check_conflict_markers: OK ({scanned} text file(s) scanned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
