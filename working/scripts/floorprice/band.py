#!/usr/bin/env python3
"""Produce a defensible salary band, or refuse to.

    python -B working/scripts/floorprice/band.py --role "director" [--location AB]

Reads observations.json and reports a band with the postings behind it, so what
you say in a negotiation has receipts attached.

The important behaviour is the refusal. Below MIN_POSTED observations it prints
what it has and declines to state a band. A number you invented and then
repeated in a salary conversation is worse than saying you don't know: you can
recover from "let me come back to you on that", and you cannot recover from a
figure the other side knows is wrong.

Estimates never count toward the sample. Only ranges an employer actually
published.

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STORE = Path(__file__).with_name("observations.json")

# Below this many posted ranges, no band is reported. Four is already thin; it
# is set here rather than at three so the refusal is the common case early on,
# which is the honest state of a search that has just started.
MIN_POSTED = 4


def load() -> list[dict]:
    if not STORE.exists():
        print(f"No observations file. Run collect.py first.", file=sys.stderr)
        raise SystemExit(2)
    return json.loads(STORE.read_text(encoding="utf-8")).get("observations", [])


def match(obs: dict, role: str | None, location: str | None) -> bool:
    if role and role.lower() not in obs.get("role", "").lower():
        return False
    if location and location.lower() not in obs.get("location", "").lower():
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Report a salary band with sources.")
    parser.add_argument("--role", help="substring match on the role title")
    parser.add_argument("--location", help="substring match on location")
    parser.add_argument("--all", action="store_true", help="include estimates (never for negotiation)")
    args = parser.parse_args()

    pool = [o for o in load() if match(o, args.role, args.location)]
    posted = [o for o in pool if o.get("posted")] if not args.all else pool

    label = f"role~{args.role!r}" if args.role else "all roles"
    if args.location:
        label += f", location~{args.location!r}"
    print(f"\nfloorprice — {label}")
    print(f"  {len(pool)} matching observation(s), {len(posted)} usable\n")

    if len(posted) < MIN_POSTED:
        print(f"  NO BAND. Need {MIN_POSTED} posted ranges, have {len(posted)}.")
        print("  Widen the filter, or run more sweeps. Do not quote a number yet.")
        for obs in pool:
            flag = "" if obs.get("posted") else "  (estimate)"
            print(f"    - {obs['low']}-{obs['high']}k  {obs['role']} @ {obs['org']}{flag}")
        return 1

    lows = sorted(o["low"] for o in posted)
    highs = sorted(o["high"] for o in posted)
    mids = sorted((o["low"] + o["high"]) / 2 for o in posted)

    print(f"  Floor      ${statistics.median(lows):.0f}k   (median of posted minimums)")
    print(f"  Midpoint   ${statistics.median(mids):.0f}k")
    print(f"  Ceiling    ${statistics.median(highs):.0f}k   (median of posted maximums)")
    print(f"  Observed   ${min(lows):.0f}k – ${max(highs):.0f}k across {len(posted)} postings\n")
    print("  Ask at or above the midpoint. The floor is what you can defend flatly;")
    print("  the ceiling is what somebody in this market is already being paid.\n")
    print("  Receipts:")
    for obs in sorted(posted, key=lambda o: -(o["low"] + o["high"])):
        where = f" · {obs['location']}" if obs["location"] else ""
        print(f"    ${obs['low']}-{obs['high']}k  {obs['role']} @ {obs['org']}{where}")
        print(f"        {obs['source']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
