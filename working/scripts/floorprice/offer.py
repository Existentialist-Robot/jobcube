#!/usr/bin/env python3
"""Price an offer past the base salary, and refuse to price what it cannot.

    python -B working/scripts/floorprice/offer.py <offer.json>
    python -B working/scripts/floorprice/offer.py <a.json> <b.json>   # compare two

band.py tells you what the market posts. This tells you what an offer is actually
worth, which is a different question: the gap people leave a job over is routinely
smaller than the pension they leave behind.

Every component is either PRICED from a number in the offer file, or listed as
UNPRICED. Nothing is estimated and nothing is assumed to be zero, because those
are opposite errors and both get made. An offer with an unpriced defined-benefit
pension is not worth its base salary -- it is worth its base salary plus something
you have not established yet, and the report says so in those terms.

Equity is never priced. Not conservatively, not with a haircut, not at the last
round's valuation. A private-company share count times a number somebody said on
a call is not a figure, and putting it in a total makes the total wrong in the one
direction that costs you money.

What gets priced, and how:

  base                  as stated
  bonus_target_pct      base x pct, reported separately and labelled AT TARGET,
                        because a target bonus is a forecast about someone else's
                        discretion
  employer_pension_pct  base x pct. For a DC plan or RRSP match this is the
                        employer contribution. For a defined-benefit plan it is
                        the employer's normal cost, which is published in the
                        plan's own annual report -- if you have not looked it up,
                        leave it out and the report will tell you what you are
                        leaving on the table by not knowing.
  vacation_days         days above statutory, valued as base / working_days. This
                        is the value of time you are paid for and do not work.
  health_premium        employer's annual premium share, as stated
  pd_budget             professional development, as stated, if it is a real
                        entitlement rather than a line somebody mentioned
  other                 {label: annual dollars} for anything else you can price

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKING_DAYS = 260  # 52 x 5, before statutory holidays; the denominator for a day's pay


def load(path: Path) -> dict:
    if not path.exists():
        print(f"No offer file at {path}", file=sys.stderr)
        raise SystemExit(2)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def price(offer: dict) -> tuple[list[tuple[str, float, str]], list[tuple[str, str]]]:
    """Return (priced components, unpriced items)."""
    base = offer.get("base")
    if not base:
        print("An offer with no `base` cannot be priced.", file=sys.stderr)
        raise SystemExit(2)

    priced: list[tuple[str, float, str]] = [("base salary", float(base), "as stated")]
    unpriced: list[tuple[str, str]] = []

    bonus_pct = offer.get("bonus_target_pct")
    if bonus_pct:
        priced.append(
            (
                "bonus at target",
                base * bonus_pct / 100,
                f"{bonus_pct}% of base — AT TARGET, not guaranteed",
            )
        )
    elif offer.get("bonus_exists"):
        unpriced.append(("bonus", "exists but no target percentage recorded"))

    pension_pct = offer.get("employer_pension_pct")
    pension_kind = offer.get("pension_type", "")
    if pension_pct:
        label = f"pension ({pension_kind})" if pension_kind else "pension"
        priced.append((label, base * pension_pct / 100, f"employer contributes {pension_pct}% of base"))
    elif pension_kind:
        hint = (
            "look up the employer's normal cost in the plan's annual report — for a DB plan "
            "this is often 8-14% of base and it is the largest thing people fail to count"
            if pension_kind.lower().startswith("d") and "b" in pension_kind.lower()
            else "ask for the employer match percentage"
        )
        unpriced.append((f"pension ({pension_kind})", hint))

    days = offer.get("vacation_days")
    statutory = offer.get("statutory_vacation_days", 10)
    if days is not None:
        extra = days - statutory
        if extra > 0:
            priced.append(
                (
                    f"vacation above statutory ({extra}d)",
                    base * extra / WORKING_DAYS,
                    f"{days}d offered vs {statutory}d statutory, at base/{WORKING_DAYS}",
                )
            )
        elif extra < 0:
            priced.append(
                (
                    f"vacation BELOW statutory ({extra}d)",
                    base * extra / WORKING_DAYS,
                    "check this against your jurisdiction's minimum — it may not be lawful",
                )
            )

    for key, label in (
        ("health_premium", "employer health premium"),
        ("pd_budget", "professional development"),
        ("signing_bonus", "signing bonus (one-time)"),
    ):
        value = offer.get(key)
        if value:
            note = "one-time; not an annual figure" if key == "signing_bonus" else "as stated"
            priced.append((label, float(value), note))

    for label, value in (offer.get("other") or {}).items():
        priced.append((label, float(value), "as stated"))

    equity = str(offer.get("equity") or "").strip()
    # "none" is an answer, not an unpriced term. Listing it as one would put an
    # item with no value on the list of things worth negotiating over.
    if equity and equity.lower() not in {"none", "n/a", "na", "no", "0", "-"}:
        unpriced.append(
            ("equity", f"{equity} — never priced here; see the note in this script")
        )
    for item in offer.get("unpriced") or []:
        unpriced.append((item, "recorded as unpriced"))

    return priced, unpriced


def report(name: str, offer: dict) -> tuple[float, float, int]:
    priced, unpriced = price(offer)
    recurring = [p for p in priced if "one-time" not in p[2]]
    one_time = [p for p in priced if "one-time" in p[2]]
    guaranteed = [p for p in recurring if "AT TARGET" not in p[2]]

    print(f"\n{name}")
    if offer.get("org") or offer.get("role"):
        print(f"  {offer.get('role','?')} at {offer.get('org','?')}")
    print()
    width = max(len(p[0]) for p in priced)
    for label, value, note in priced:
        print(f"    {label:<{width}}  ${value:>10,.0f}   {note}")

    total_guaranteed = sum(p[1] for p in guaranteed)
    total_recurring = sum(p[1] for p in recurring)
    print()
    print(f"    {'ANNUAL, guaranteed':<{width}}  ${total_guaranteed:>10,.0f}")
    if abs(total_recurring - total_guaranteed) > 0.5:
        print(f"    {'ANNUAL, at target':<{width}}  ${total_recurring:>10,.0f}")
    for label, value, _ in one_time:
        print(f"    {'+ ' + label:<{width}}  ${value:>10,.0f}   first year only")

    base = float(offer["base"])
    uplift = (total_guaranteed - base) / base * 100
    print(f"\n    Guaranteed value is {uplift:+.1f}% against the base salary alone.")

    if unpriced:
        print("\n    UNPRICED — real value, no number established:")
        for label, why in unpriced:
            print(f"      · {label}: {why}")
        print("      These are not zero. Two offers are not comparable until you have")
        print("      either priced them or decided they do not matter to you.")
    return total_guaranteed, total_recurring, len(unpriced)


def main() -> int:
    parser = argparse.ArgumentParser(description="Price an offer, or compare two.")
    parser.add_argument("offers", nargs="+", type=Path, help="one or two offer JSON files")
    args = parser.parse_args()

    if len(args.offers) > 2:
        print("Two at a time. More than that is a spreadsheet, not a decision.", file=sys.stderr)
        return 2

    results = []
    for path in args.offers:
        offer = load(path)
        results.append((path, offer, report(path.stem, offer)))

    if len(results) == 2:
        (path_a, offer_a, (guar_a, targ_a, unp_a)) = results[0]
        (path_b, offer_b, (guar_b, targ_b, unp_b)) = results[1]
        print("\n" + "-" * 68)
        print(f"\n  {path_a.stem} vs {path_b.stem}\n")
        gap = guar_a - guar_b
        base_gap = float(offer_a["base"]) - float(offer_b["base"])
        ahead = path_a.stem if gap > 0 else path_b.stem
        print(f"    On base salary alone:   {abs(base_gap):>10,.0f} to "
              f"{path_a.stem if base_gap > 0 else path_b.stem}")
        print(f"    On guaranteed value:    {abs(gap):>10,.0f} to {ahead}")
        if (base_gap > 0) != (gap > 0) and base_gap and gap:
            print("\n    The base salary and the guaranteed value disagree about which offer")
            print("    is better. This is the ordinary case, not an unusual one, and it is")
            print("    the reason to run this before answering a recruiter.")
        if unp_a or unp_b:
            print(f"\n    Unpriced items: {unp_a} in {path_a.stem}, {unp_b} in {path_b.stem}.")
            print("    The comparison above is provisional until those are resolved.")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
