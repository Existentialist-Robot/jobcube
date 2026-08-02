---
name: deep-sweep
description: >
  Run a multi-thread deep job-search sweep over the search spaces currently queued in
  working/scripts/viz/build_sweep_viz.py. Trigger on the two-word command "deep sweep" (or /deep-sweep).
  Small, direct, FOREGROUND sweeps only — never background/multi-agent jobs. JD-verify + dedup before presenting.
  Triggers on: "deep sweep", "init sweep", "run the sweep", "next sweep".
---

# deep-sweep — two-word sweep initializer

**Invocation:** the two-word command **`deep sweep`** (also `/deep-sweep`, "init sweep", "next sweep").

The *threads* are deliberately not hardcoded here. They are read live from the `FUTURE`
entries marked `new=True` in
[`working/scripts/viz/build_sweep_viz.py`](../../../working/scripts/viz/build_sweep_viz.py).
That file is the steering wheel: edit those entries to re-aim the command. If nothing is
marked `new=True`, this skill has nothing to search — say so and stop rather than
inventing threads.

## HARD RULES

- **Foreground only.** Roughly 4–6 direct `WebSearch`/`WebFetch` calls per thread, made by
  the main agent. **Never** launch background or long-running multi-agent search jobs. They
  burn tokens and fail silently — one such job has hit a token limit mid-run and returned
  nothing at all.
- **Fail-proof over exhaustive.** Need more coverage? Run another small sweep, not a bigger
  agent.
- **JD-verify before presenting.** Read each finalist's real posting and bake the hard gates
  — level, salary floor, close date, domain/specialist requirements, work authorization,
  on-site expectations — into the rating *before* writing the shortlist. Titles and
  aggregator snippets mislead constantly; a title-only rating makes you the JD reader
  instead of the assistant.
- **Dedup** against `job_scraper/seen_jobs.json`, your applied-roles tracker, and project
  memory before listing anything. A role you already applied to or already rejected should
  never surface twice.
- **Level bar.** Apply the floor set in `CLAUDE.md` (level and salary). Anything below it is
  a door-opener at best and must be labelled as such, not listed as a match.
- **Rating format.** Every row gets a 5-star fit rating plus P(interview) and
  P(hire | interview). Estimates, clearly, but written down so they can be checked against
  outcomes later.

## Procedure

1. **Read** the `new=True` `FUTURE` entries in `build_sweep_viz.py`. Those entries carry the
   target org list, geography, and level for each thread — treat them as the search brief.
2. **Per thread**, run one small foreground batch: `WebSearch` the named orgs and role
   archetypes, hitting ATS JSON endpoints directly where you can (see
   [`../pipeline/sources.json`](../pipeline/sources.json) for the endpoint patterns), then
   `WebFetch` the live postings for the top hits.
3. **Dedup**, then **JD-verify** each survivor and assign ★ + P(int) + P(hire | int) from
   what the posting actually says.
4. **Output ONE consolidated sweep doc** in `working/active/`, copied from
   [`../../../working/templates/SWEEP_TEMPLATE.md`](../../../working/templates/SWEEP_TEMPLATE.md).
   Every Role cell in every table is a direct hyperlink to the posting. JD verdicts go in
   `Role Summaries` — do not add a verdict column to the roster.
5. **Run the gate:** `python -B working/scripts/validate_job_sweep.py <sweep-path>`. Do not
   present the sweep unless it prints `PASS`.
6. **Do not port or apply.** This command proposes. You greenlight, and the open-status gate
   runs, before any application work starts.
7. **Update the coverage data** once a thread has actually been swept: move it from `FUTURE`
   to `SWEEPS` in `build_sweep_viz.py` with today's date and what it yielded, then add a new
   `FUTURE` entry for the next gap. Rebuild the viz when you want to look at it — not
   automatically on every data touch.

## Re-aiming the sweep

Edit the `new=True` entries in `FUTURE`: new cube cell, new org list, new geo/level note.
Then run `deep sweep` again. Aim at cells far from every `SWEEPS` centroid — the whole point
is to stop re-mining the same seam.

## ONE VIZ ONLY

There is a single viz: **`working/active/job_search_viz.html`**, built by
`build_job_viz_three.py`. The coverage layer — explored plus prospective spheres — renders
*inside* it. `build_sweep_viz.py` is **data-only**; running it just rebuilds that one file.
Never generate a separate coverage viz; two visualizations of the same data disagree within
a week.
