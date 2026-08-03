#!/usr/bin/env python3
"""The one page you read before the call.

    python -B working/scripts/floorprice/brief.py --role "Dir"
    python -B working/scripts/floorprice/brief.py --role "Dir" --offer acme.offer.json

Step 4 of the skill says to rehearse, and to have three things ready: the number,
the two postings you would cite if pushed, and what you say when they ask for your
expectations first. This assembles exactly those from what the repo already knows,
so the rehearsal is against your own data rather than a feeling.

It composes rather than computes. The band comes from band.py's logic over
observations.json; the offer, if you pass one, from offer.py's. Nothing new is
estimated here.

  WITHOUT --offer   what to ask for, and the receipts to cite
  WITH --offer      the same, plus where the offer sits in the band, and whether
                    the gap is worth a counter

**It refuses on thin data, for the same reason band.py does.** A rehearsal built on
two postings teaches you to say a number you cannot defend, which is worse than
going in without one: you can recover from "let me come back to you on that" and
you cannot recover from a figure the other side knows is wrong.

Stdlib only. Exit 1 if there is not enough posted data to brief from.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from band import MIN_POSTED, load, match  # noqa: E402
from offer import load as load_offer, price  # noqa: E402


def money(thousands: float) -> str:
    return f"${thousands:,.0f}k"


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble a negotiation brief.")
    parser.add_argument("--role", help="substring match on the role title")
    parser.add_argument("--location", help="substring match on location")
    parser.add_argument("--offer", type=Path, help="an offer file to position against the band")
    args = parser.parse_args()

    pool = [o for o in load() if match(o, args.role, args.location)]
    posted = [o for o in pool if o.get("posted")]

    label = f"{args.role!r}" if args.role else "all roles"
    print(f"\nfloorprice brief — {label}")
    print(f"  {len(posted)} posted range(s) behind this\n")

    if len(posted) < MIN_POSTED:
        print(f"  NO BRIEF. Need {MIN_POSTED} posted ranges, have {len(posted)}.")
        print("  Rehearsing a number you cannot defend is worse than going in without one.")
        print("  Widen the filter, or run more sweeps. If the call is tomorrow, the line is")
        print('  "I would rather hear the band you have budgeted" — and then stop talking.\n')
        return 1

    lows = sorted(o["low"] for o in posted)
    highs = sorted(o["high"] for o in posted)
    mids = sorted((o["low"] + o["high"]) / 2 for o in posted)
    floor = statistics.median(lows)
    midpoint = statistics.median(mids)
    ceiling = statistics.median(highs)

    print("  THE NUMBER")
    print(f"    Ask at {money(midpoint)}. Defend down to {money(floor)}. Do not open at the floor.")
    print(f"    Observed across these postings: {money(min(lows))} to {money(max(highs))}.")
    print()

    # The two strongest receipts, because two is what you can hold in your head
    # and reciting five sounds rehearsed rather than informed.
    receipts = sorted(posted, key=lambda o: -(o["low"] + o["high"]))[:2]
    print("  THE TWO YOU CITE IF PUSHED")
    for obs in receipts:
        where = f", {obs['location']}" if obs.get("location") else ""
        print(f"    {obs['role']} at {obs['org']}{where} — posted {money(obs['low'])}"
              f"–{money(obs['high'])}")
        print(f"        {obs['source']}")
    print()

    print("  WHAT YOU SAY")
    print("    Asked for your expectations first:")
    print('      "I would rather hear the band you have budgeted for the role."')
    print("      If pressed, give the band and never a point:")
    print(f'      "Comparable roles in this market are posting {money(floor)} to'
          f' {money(ceiling)}."')
    print("    Asked what you make now: that is a fact about your last employer, not this")
    print("      one. Redirect to the band. In several jurisdictions they may not ask.")
    print("    After you state the number: stop talking. Silence is a tactic and it is free.")
    print()

    if args.offer:
        offer = load_offer(args.offer)
        priced, unpriced = price(offer)
        recurring = [p for p in priced if "one-time" not in p[2]]
        guaranteed = sum(p[1] for p in recurring if "AT TARGET" not in p[2])
        base_k = float(offer["base"]) / 1000
        total_k = guaranteed / 1000

        print("  THE OFFER, AGAINST THAT BAND")
        print(f"    Base {money(base_k)} · guaranteed total {money(total_k)}")
        if base_k < floor:
            print(f"    The base is below the posted floor of {money(floor)}. That is the")
            print("    strongest position you will get: you are not asking for more than the")
            print("    market, you are asking for the market.")
        elif base_k < midpoint:
            gap = midpoint - base_k
            print(f"    The base sits between the floor and the midpoint. {money(gap)} short of")
            print("    the midpoint is a normal counter and a cheap one for them to grant.")
        else:
            print("    The base is at or above the midpoint of what you have seen posted.")
            print("    A counter here is about the unpriced terms, not the salary.")

        if total_k >= midpoint > base_k:
            print(f"\n    Note: the guaranteed total already clears the midpoint even though the")
            print("    base does not. If you counter on base alone you may be arguing about")
            print("    less than you think — check what the pension and leave are worth first.")

        if unpriced:
            print(f"\n    {len(unpriced)} unpriced term(s) — these are where the movement usually")
            print("    is, because they cost a manager less than salary does:")
            for item, _ in unpriced:
                print(f"      · {item}")
        print()
        print("    An employer who will not give you two days to consider has told you how")
        print("    they will behave once you work there.")
        print()

    print("  This is the floor of what is defensible, not the ceiling of what is possible.")
    print("  It knows only the postings you have swept and the employers who publish ranges.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
