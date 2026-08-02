#!/usr/bin/env python3
"""Harvest salary observations from the postings this repo has already seen.

    python -B working/scripts/floorprice/collect.py [--out <path>]

The point of floorprice is that you are not guessing. Every number it reports
traces to a specific posting you actually looked at, with a date and a source.
This script builds that evidence file.

Two sources, both already in the repo:

  1. build_job_viz.py JOBS  — the structured record: sal / sal_min / sal_max,
     level, location, date. Read via ast, never executed.
  2. working/active/*.md sweeps — the Salary column of the canonical shortlist
     table. Coarser, and marked as such: a posting that said "Not listed
     (~$95-110k est.)" is an ESTIMATE, not an observation, and is stored with
     `posted: false` so band.py can exclude it.

An estimate you made and then later quote back to yourself is circular. Keeping
the two apart is most of the value here.

Stdlib only. Writes JSON to working/scripts/floorprice/observations.json.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEGACY = ROOT / "working" / "scripts" / "viz" / "build_job_viz.py"
SWEEPS = ROOT / "working" / "active"
DEFAULT_OUT = Path(__file__).with_name("observations.json")

# "$95,000-$110,000", "95-110k", "Not listed (~$95–110k est.)"
MONEY = re.compile(
    r"\$?\s*(\d{2,3}(?:[,\d]{3})?)\s*(?:k|K)?\s*(?:[-–—]|to)\s*\$?\s*(\d{2,3}(?:[,\d]{3})?)\s*(?:k|K)?"
)
EST_HINT = re.compile(r"\best\.?\b|~|approx|not listed", re.IGNORECASE)


def to_thousands(raw: str) -> int | None:
    """Normalize '95', '95,000' and '95000' to 95 (thousands of dollars)."""
    digits = raw.replace(",", "")
    if not digits.isdigit():
        return None
    value = int(digits)
    if value >= 1000:
        value = round(value / 1000)
    return value if 20 <= value <= 900 else None


def from_jobs() -> list[dict]:
    """Structured observations from the viz dataset."""
    if not LEGACY.exists():
        return []
    tree = ast.parse(LEGACY.read_text(encoding="utf-8"))
    node = None
    for item in tree.body:
        if isinstance(item, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "JOBS" for t in item.targets
        ):
            node = item.value
            break
    if node is None:
        return []
    jobs = eval(  # noqa: S307 - literal dict list, no builtins exposed
        compile(ast.Expression(node), str(LEGACY), "eval"),
        {"__builtins__": {}, "dict": dict},
        {},
    )

    out = []
    for job in jobs:
        low, high = job.get("sal_min"), job.get("sal_max")
        if not low or not high:
            continue
        out.append(
            {
                "role": job.get("label", ""),
                "org": job.get("org", ""),
                "location": job.get("loc", ""),
                "low": int(low),
                "high": int(high),
                "seniority": job.get("z"),
                "date": job.get("date", ""),
                "posted": True,  # from a real range in the record
                "source": "build_job_viz.py:JOBS",
            }
        )
    return out


def from_sweeps() -> list[dict]:
    """Looser observations from the Salary column of sweep shortlists."""
    out = []
    if not SWEEPS.is_dir():
        return out
    for doc in sorted(SWEEPS.glob("*.md")):
        for line_no, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
            if not line.lstrip().startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 6:
                continue
            role_cell, org_cell, loc_cell, sal_cell = cells[1], cells[2], cells[3], cells[4]
            match = MONEY.search(sal_cell)
            if not match:
                continue
            low, high = to_thousands(match.group(1)), to_thousands(match.group(2))
            if not low or not high or low > high:
                continue
            out.append(
                {
                    "role": re.sub(r"\[([^\]]*)\].*", r"\1", role_cell),
                    "org": org_cell,
                    "location": loc_cell,
                    "low": low,
                    "high": high,
                    "seniority": None,
                    "date": "",
                    # An estimate is not evidence. Mark it and let band.py drop it.
                    "posted": not bool(EST_HINT.search(sal_cell)),
                    "source": f"{doc.relative_to(ROOT).as_posix()}:{line_no}",
                }
            )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect salary observations.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    observations = from_jobs() + from_sweeps()

    # Same role at the same org twice is one data point, not two.
    seen, deduped = set(), []
    for obs in observations:
        key = (obs["role"].lower(), obs["org"].lower(), obs["low"], obs["high"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(obs)

    posted = sum(1 for o in deduped if o["posted"])
    args.out.write_text(
        json.dumps({"observations": deduped}, indent=2) + "\n", encoding="utf-8"
    )

    print(f"collected {len(deduped)} observation(s) -> {args.out.relative_to(ROOT).as_posix()}")
    print(f"  {posted} posted, {len(deduped) - posted} estimated (excluded from bands)")
    if posted == 0:
        print("  note: no posted ranges yet — run some sweeps before asking for a band.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
