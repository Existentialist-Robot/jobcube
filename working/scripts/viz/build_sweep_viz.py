# -*- coding: utf-8 -*-
"""Sweep-coverage DATA SOURCE (SWEEPS + FUTURE) — NOT a standalone renderer.

⚠️ THIS FILE DOES NOT PRODUCE ITS OWN HTML. The coverage layer (explored purple +
future/prospective green spheres) is rendered *inside* the single job viz,
`working/active/job_search_viz.html`, by `build_job_viz_three.py`, which imports
`SWEEPS`/`FUTURE` from here. There is exactly ONE viz. Do not create a second one.

What this is for: a job search drifts toward the cells you have already mined.
Plotting where you have looked (purple) against where you have not (green) makes
the gaps visible, so the next sweep aims at new territory instead of re-mining
the same three orgs.

Model: every sweep is a sphere in a 3-D search space (sector × focus × seniority),
each axis 1..5.
  - PURPLE = sweeps already run, shaded by recency. Radius ≈ breadth.
  - GREEN  = planned / prospective regions (thin coverage). `new=True` marks the
    threads you intend to sweep next; they render bolder and prong-coloured, and
    the deep-sweep skill reads exactly those entries to decide what to search.

⚠️ THE DATA BELOW IS AN EXAMPLE, NOT A STARTING POSITION. `AXES`, `SWEEPS` and
`FUTURE` describe one hypothetical search so the viz has something to draw.
Replace all three with your own: rename the axis values to the dimensions your
search actually varies along, delete the example sweeps, and write FUTURE
entries for the gaps you care about. Nothing here is calibration you should
inherit.

Workflow: after each sweep, move the thread you just ran from FUTURE to SWEEPS
with the date and what it surfaced, then add a new FUTURE entry for the next
gap. Run this file (or build_job_viz_three.py directly) to rebuild the one viz.
"""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# Axis model — shared with build_job_viz_three.py, values 1..5 on each axis.
# EDIT THESE FIRST. They define what the cube means; every x/y/z below is read
# against them. The defaults suit a search that ranges across employer type,
# kind of work, and level — yours may vary along entirely different dimensions
# (industry, geography, company stage, IC vs management, ...).
AXES = {
    "x": ["Startup", "Innovation org", "Nonprofit", "Post-secondary", "Gov"],
    "y": ["Ops", "Change mgmt", "Strategy", "Programs/Partnerships", "Ecosystem/R&D"],
    "z": ["Specialist", "Officer/Advisor", "Manager", "Director/ED", "VP/C-suite"],
}

# ---------------------------------------------------------------------------
# SWEEPS — searches you have ALREADY run (purple).
#   id     stable slug
#   label  what you searched, in your own shorthand
#   date   YYYY-MM-DD, drives the recency shading and the timeline scrubber
#   prong  grouping key; must have an entry in PRONG_COLORS below
#   x/y/z  1..5 centroid of the region searched, read against AXES
#   r      breadth (visual radius) — a single-org check ≈0.6, a 25-board sweep ≈1.4
#   count  roles surfaced
#   notes  what it yielded, and whether the seam is worth returning to
#
# EXAMPLE DATA — delete these and log your own sweeps.
# ---------------------------------------------------------------------------
SWEEPS = [
    dict(id="ex-gov-spring", label="EXAMPLE — provincial ministries, policy/workforce",
         date="2026-04-19", prong="Gov", x=5.0, y=3.0, z=3.0, r=1.0, count=8,
         notes="Manager tier. Well mined by now; returns diminishing."),
    dict(id="ex-innovation", label="EXAMPLE — regional innovation orgs, partnerships",
         date="2026-06-27", prong="Innovation", x=2.0, y=4.0, z=3.0, r=1.0, count=6,
         notes="Programs/partnerships at Manager tier across four agencies."),
    dict(id="ex-startups-ats", label="EXAMPLE — startup ATS sweep (25 boards)",
         date="2026-07-17", prong="Startups", x=1.0, y=4.0, z=3.5, r=1.4, count=12,
         notes="Direct Greenhouse/Lever/Ashby JSON. Highest yield per call so far."),
    dict(id="ex-psi", label="EXAMPLE — post-secondary innovation offices",
         date="2026-07-02", prong="PSI", x=4.0, y=4.5, z=4.0, r=0.6, count=1,
         notes="Thin — most postings had closed or gone to executive search."),
]

# ---------------------------------------------------------------------------
# FUTURE — regions you have NOT yet swept (green). Place these in cells that
# are genuinely FAR from every SWEEPS centroid above; a future sphere sitting on
# top of an explored one is a coverage illusion, which defeats the point.
#
# `new=True` = queued for the next sweep. The deep-sweep skill reads ONLY those
# entries, so this list is the steering wheel: edit it to re-aim the search.
#
# EXAMPLE DATA — delete these and write the gaps you actually want covered.
# ---------------------------------------------------------------------------
FUTURE = [
    dict(id="f-ex-senior-startup", new=True,
         label="EXAMPLE THREAD 1 — senior startup leadership (Head/VP of partnerships or programs)",
         prong="Startups", x=1.3, y=4.3, z=5.0, r=0.95,
         notes="The tier ABOVE the manager-level startup roles already swept. "
               "Name the 8-12 target orgs here — the deep-sweep skill searches them by name."),
    dict(id="f-ex-corp-innovation", new=True,
         label="EXAMPLE THREAD 2 — corporate innovation & strategy leadership",
         prong="Industry", x=2.1, y=4.2, z=4.9, r=0.95,
         notes="Distinct from the light client-facing industry roles already seen. "
               "Geo, level, and salary floor go in this note so the sweep can gate on them."),
    dict(id="f-ex-nonprofit-exec", label="EXAMPLE — nonprofit at senior-executive (ED/VP) tier",
         prong="Nonprofit", x=3.2, y=4.5, z=5.0, r=0.85,
         notes="No `new=True`, so this is a standing gap the next sweep will skip."),
    dict(id="f-ex-municipal", label="EXAMPLE — regional & municipal economic development",
         prong="Municipal", x=3.7, y=3.4, z=4.6, r=0.9,
         notes="Sits in the gap between the innovation-org and government lanes."),
]

# Outline tint per prong. Add a colour whenever you add a prong — a prong with no
# entry falls back to plain green and stops being distinguishable in the legend.
PRONG_COLORS = {
    "Gov": "#d98cff", "Innovation": "#b98cff", "Nonprofit": "#9a8cff",
    "PSI": "#c8a0ff", "Industry": "#8f9cff", "Startups": "#e0a0ff",
    "Municipal": "#a0b0ff", "Cross-cut": "#cfa8ff",
}

DATA = {"axes": AXES, "sweeps": SWEEPS, "future": FUTURE, "prong_colors": PRONG_COLORS}


def main():
    # This file is data-only. It deliberately does NOT write its own HTML —
    # a second, competing viz is worse than no viz. Running it rebuilds the ONE
    # integrated viz, working/active/job_search_viz.html.
    import subprocess
    import sys

    queued = sum(1 for f in FUTURE if f.get("new"))
    print(f"build_sweep_viz.py = DATA ONLY  (sweeps={len(SWEEPS)}, future={len(FUTURE)}, "
          f"queued threads={queued}).")
    if queued == 0:
        print("  note: no FUTURE entry has new=True — `deep sweep` has nothing to aim at.")
    if any(s["id"].startswith(("ex-", "f-ex-")) for s in SWEEPS + FUTURE):
        print("  note: still carrying the EXAMPLE dataset — replace SWEEPS/FUTURE with your own.")

    print("Rebuilding the integrated viz (working/active/job_search_viz.html) ...")
    three = Path(__file__).with_name("build_job_viz_three.py")
    if not three.exists():
        print(f"!! {three.name} not found next to this file — nothing to rebuild.")
        return 1
    result = subprocess.run([sys.executable, str(three)])
    if result.returncode != 0:
        print("!! integrated rebuild failed — run build_job_viz_three.py directly.")
        return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
