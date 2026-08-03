---
name: floorprice
description: >
  Work out what a role should pay and how to argue it, using only salary ranges from postings
  this repo has actually seen. Builds a band with the postings cited underneath it, normalizes
  total compensation, and rehearses the negotiation. Refuses to state a number on thin data.
  Triggers on: "what should I ask for", "salary", "comp", "negotiate", "counter", "what's this
  role worth", "floorprice".
allowed-tools: Read, Write, Edit, Glob, Grep, WebFetch, WebSearch, Bash
framework_version: 1.0.0
---

# floorprice — what you should be paid, with receipts

Most people negotiate blind. Levels.fyi covers tech and nowhere else, Glassdoor is noisy and
gated, and government wage bands are too coarse to argue with. Meanwhile this repo has been
quietly collecting posted salary ranges for every role it has swept.

That is a comp dataset. It is small, it is specific to the roles you actually want, and — unlike
anything you can look up — **you know where every number came from.**

## The rule

**No number without postings behind it.** Below four posted ranges,
[`band.py`](../../../working/scripts/floorprice/band.py) refuses and exits 1. Do not talk
around it. A figure you invented and then repeated in a salary conversation is worse than
saying "let me come back to you on that" — you can recover from the second and not from the
first.

Estimates never count. A sweep row reading `Not listed (~$95–110k est.)` is *your own guess*,
stored with `posted: false` and excluded from every band. Quoting your own estimate back to
yourself is circular, and it is the single easiest way to walk into a room confidently wrong.

## Procedure

1. **Collect** — `python -B working/scripts/floorprice/collect.py`. Harvests from the `JOBS`
   record in `build_job_viz.py` and the Salary column of sweep shortlists in `working/active/`.
   Re-run after every sweep.
2. **Band** — `python -B working/scripts/floorprice/band.py --role "<substring>" [--location XX]`.
   Reports floor, midpoint, ceiling and the postings underneath. If it refuses, widen the
   filter or run more sweeps.
3. **Normalize the offer** — `cp offer.example.json <org>.offer.json`, fill in what you were
   actually told, then `python -B working/scripts/floorprice/offer.py <org>.offer.json`. Pass
   two files to compare them. Salary is one term: the tool prices the employer's pension
   contribution, vacation above the statutory minimum, the health premium and any PD budget,
   and reports a guaranteed annual figure separately from an at-target one.

   **Leave a field out rather than guessing it.** Anything missing is reported `UNPRICED`,
   which is the state that prompts you to go and ask. A guessed field silently becomes part of
   a total you then rely on in a conversation. Equity is never priced — a private share count
   times a number somebody said on a call is not a figure.

   Expect the base salary and the guaranteed value to disagree about which of two offers is
   better. That is the ordinary case, and it is the reason to run this before you answer.
4. **Rehearse** before the call. Have ready: the number, the two postings you would cite if
   pushed, and what you say when asked for your expectations first.

## Talking points that hold up

- **Anchor on the midpoint, not the floor.** The floor is what you can defend flatly; asking
  there guarantees you get it.
- **Never answer "what are your expectations?" first.** "I'd rather hear the band you have
  budgeted — I'm sure it's reasonable." If pressed, give the band, not a point.
- **Cite the market, not your needs.** "Comparable director roles in this market posted at
  $115–148k" is a fact about the world. What you need to cover rent is a fact about you, and
  it belongs nowhere in this conversation.
- **Silence is a tactic and it is free.** State the number and stop talking.
- **An exploding offer is information.** An employer who will not give you two days to consider
  has told you how they will behave once you work there.

## What this cannot do

It knows only the postings you have seen, so it is biased toward the roles you already search
for and the employers who publish ranges at all. It cannot tell you what an individual is paid,
and it cannot price equity. Treat the band as the floor of what is defensible, not the ceiling
of what is possible.

`--role` is a plain substring match, so it will miss what the posting abbreviated. The shipped
example data says `Dir, Economic Development`, and `--role director` finds nothing at all. Try
the abbreviation, or a shorter fragment, before concluding you have no data.
