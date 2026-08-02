# HANDOFF — [YOUR_NAME] Job Search

**Last updated:** [DATE]
**Working directory:** `[PATH_TO_THIS_REPO]`
**Owner:** [YOUR_NAME] ([profile in CLAUDE.md](CLAUDE.md))

`job_search_tracker.csv` is the unified application index, and `working/exports/` is the canonical packet/PDF archive. This file is narrative handoff context, not the canonical application index. Start here, then read the current files in `working/active/`.

---

## Quick Start

When resuming:

1. Read this file end to end.
2. Read everything in [`working/active/`](working/active/).
3. Use [`CLAUDE.md`](CLAUDE.md) for candidate profile, Canva workflow, and verification rules.
4. Confirm with [YOUR_NAME] if anything in Current Sprint looks stale.

Before stopping:

1. Update this file's Current Sprint, Active Documents, and Pending Items.
2. Move stale active docs to [`working/archive/`](working/archive/).
3. Keep helper scripts in [`working/scripts/`](working/scripts/) and generated JSON in [`working/scripts/generated/`](working/scripts/generated/).
4. Update `job_search_tracker.csv` when applications are submitted or closed without submission.

---

## Current Sprint

**Window:** [START_DATE] to [END_DATE]

**Active effort:** [DESCRIPTION — e.g. "3 applications in progress from June sweep; pair 1 ported, pairs 2–3 pending."]

| Priority | Workstream | Artifact | Next action |
|----------|------------|----------|-------------|
| 1 | [e.g. Interview prep — Role at Org] | `working/active/interview_prep_role.md` | [e.g. Rehearse answer bank] |
| 2 | [e.g. Fresh apply-list search] | _pending_ | [e.g. Run /pipeline sweep] |

**Level reminder:** [YOUR acceptance target — e.g. Senior Manager / Director scope and roughly $100K+. Sub-level roles only worth pursuing when salary/scope clearly clears the bar.]

---

## Application Finals Archive (`working/exports/`)

**Every application — past and present — is filed under `working/exports/` as the single source of truth.** Structure:

```
working/exports/<YYYY-MM (Mon 'YY)>/<YY-MM-DD - Company - Role>/
    [YOUR_NAME]_Resume.pdf
    [YOUR_NAME]_Cover_Letter.pdf
    copy/
        packet_slug_date.md       # per-app draft/review record
        review_agents_date.md     # agent review findings
    <Interview Research>.md       # any per-app interview artifacts
```

- Month folders sort chronologically; app folders are date-first for autosort.
- Working/record docs and interview prep live WITH their application (not in generic archive) whenever they map 1:1 to one role. Only multi-app sprint notes and intermediate pair-reviews stay in `working/archive/`.

---

## Active Documents

`working/active/` is cleaned to live work only:

- _[List current active docs here — e.g. job sweep doc, current interview prep]_

---

## Interview Prep

The live answer bank stays in `working/active/`; everything else is filed with the
application under `working/exports/<month>/<date - company - role>/`.

- **Role:** _[title, org, competition number if any]_
- **Panel:** _[names and titles from the invite — research each before the interview]_
- **Process contact:** _[recruiter/coordinator]_
- **Constraints from the invite:** _[e.g. no AI tools, search engines, outside help, or
  recording during the interview — in which case prep is advance-study only]_
- **Docs:** _[link the live answer bank, plus the filed prep and any HR/red-flag pass]_

---

## Outreach In Flight

One row per org where connection requests are out but the application hasn't gone in yet.
Full process in [`.claude/skills/linkedin-outreach/SKILL.md`](.claude/skills/linkedin-outreach/SKILL.md);
the per-org logs live in `working/outreach/` and are gitignored.

| Org | Role | Targets contacted | Accepted | Messaged | Submit by |
|-----|------|-------------------|----------|----------|-----------|
| [Org] | [Role] | 0/3 | 0 | 0 | [date — 3–5 days out; submit regardless] |

---

## Repo Structure

```text
jobcube/
|-- HANDOFF.md                  # this file: state + workflow + rules
|-- CLAUDE.md                   # candidate profile, Canva workflow, verification checklist
|-- GETTING_STARTED.md          # setup guide + agent onboarding
|-- job_search_tracker.csv
|-- working/
|   |-- active/                 # live work only (current interview doc + fresh search)
|   |-- outreach/               # per-org LinkedIn outreach logs (gitignored — real names)
|   |-- exports/                # FINALS ARCHIVE: every submitted app (PDFs + drafts), by month/date
|   |-- archive/                # superseded multi-app sprint notes + intermediate reviews
|   |-- templates/              # SWEEP / PACKET / OUTREACH_LOG starting points
|   `-- scripts/                # Canva port primitive, validators, viz, outreach
|       |-- template/           # template_port.py + manifest + port_config
|       |-- utils/              # render, sign-off verify, cover-gap measure
|       |-- viz/                # 3D pipeline viz + sweep-coverage data
|       |-- outreach/           # log scaffolder + paced linkedin-cli wrapper
|       `-- generated/          # generated operation/copy JSON
|-- cv/
|-- cover_letters/
`-- .claude/skills/             # job-scraper, pipeline, deep-sweep, linkedin-outreach
```

---

## Submitted This Calendar Quarter

Tracker file: [`job_search_tracker.csv`](job_search_tracker.csv)

_[Update this list as you submit applications. Example format:]_

- [Role] — [Org] — [Date]

---

## Hiring Probability Filter

Do not add a role to the apply list unless there is a minimum low-medium realistic chance you actually get hired. Skills match is not enough.

Passes:

- Generalist mandates: policy, strategy, program design, stakeholder engagement, ecosystem/innovation/economic development
- Manager, Senior Manager, or Director level where outsider perspective could plausibly be valued
- Roles aligned to your target sectors (see CLAUDE.md)

Fails despite skills match:

- Specialist domains where you lack the credential or track record
- Executive/VP-level without a strong identity-match reason
- Near-certain internal-only competitions

Your bridge into target sectors:

[DESCRIBE YOUR BRIDGE — e.g. grant relationships, awards, stakeholder recognition, relevant past roles]

---

## Job Search Infrastructure

### Search Execution

**HARD RULE — small direct sweeps only.** Run job searches as a handful of **foreground `WebSearch`/`WebFetch` calls the main agent makes itself**, then write one consolidated doc. **NEVER launch background or long-running multi-agent search jobs** — they burn tokens and silently fail. Keep each sweep to ~4–6 targeted queries against known employer portals; if more coverage is needed, run another small sweep, not a bigger agent. Fail-proof beats exhaustive.

**Canonical sweep doc format** (full template in `.claude/skills/pipeline/SKILL.md` → Step 3):
- File: `working/active/job_sweep_{YYYY-MM-DD}_{slug}.md` — written to disk FIRST, before presenting in chat
- Table columns (in order): `# | Role | Org | Location | Salary | Posted | Closes | Fit | P(int) | P(hire\|int) | Status`
- **Role** cell = hyperlinked title (no separate Links section at bottom)
- **Salary** = posted range, or `Not listed (~$X–Y est.)` with a calibrated estimate
- **Closes** = actual date; `⚠️ VERIFY` if absent; `⚠️ URGENT` if ≤3 days
- **Fit** = ★★★★★ stars; **P(int)** and **P(hire\|int)** = conservative estimates — NEVER omit
- After the table: 1–2 sentence **Probability rationale**
- Sections below the table: Role Summaries · Strong-but-not-included · Boards checked/blocked

Copy [`working/templates/SWEEP_TEMPLATE.md`](working/templates/SWEEP_TEMPLATE.md) rather than
rebuilding that shape by hand, and gate it before presenting:

```powershell
python -B working/scripts/validate_job_sweep.py working/active/<sweep>.md
```

It must print `PASS`. It checks the column set, that every Role cell in every table is a
real hyperlink, star ratings, and well-formed probabilities.

**Aiming the next sweep.** `deep sweep` (the [`deep-sweep`](.claude/skills/deep-sweep/SKILL.md)
skill) reads its threads from the `new=True` entries in
[`working/scripts/viz/build_sweep_viz.py`](working/scripts/viz/build_sweep_viz.py). That file
also records where you have already looked, so edit it as you go — a thread that stays in
`FUTURE` after being swept makes the coverage map lie.

### Job Boards to Search

See `.claude/skills/pipeline/boards.md` for the full registry of confirmed queryable boards.

Quick reference — highest-signal sources:
1. [Your government portal, e.g. jobpostings.alberta.ca]
2. [LinkedIn Jobs — saved search for your target roles + location]
3. [Your target org career pages]
4. CharityVillage (if non-profit sector)
5. GC Jobs / regional development agencies (if federal)

### Last Sweeps

| Source | Last checked | Notes |
|--------|--------------|-------|
| [Board name] | [Date] | [Notes] |

### Portals Requiring Manual Browser Check

| Portal | URL | Cadence |
|--------|-----|---------|
| [Org name] | [URL] | [e.g. Weekly] |

---

## Application Workflow

1. Evaluate fit first: skills, experience, behavior/culture, career alignment, and realistic hiring probability.
2. Do not draft for roles below the threshold.
3. Manual-open gate before Canva work: you must confirm live portal status before porting.
4. Draft edits as active docs only when they are current. Archive stale drafts promptly.
5. Use Canva design `[YOUR_CANVA_DESIGN_ID]` and the workflow in [`CLAUDE.md`](CLAUDE.md).
6. Run verification before presenting or porting.
7. Track submissions and non-submissions in `job_search_tracker.csv`.

---

## Hard Rules

- Never fabricate job postings.
- Salary floor: $[YOUR_FLOOR]. Real target: $[YOUR_TARGET_RANGE].
- No specialist-domain applications unless there is a clear, realistic bridge.
- Keep outputs direct and tight.

---

## Pending Items

_[List outstanding to-dos here. Example:]_

1. Verify open status on [Role A], [Role B] before porting.
2. Update `job_search_tracker.csv` with [recent submission].
3. Run next broad sweep after [Date].

---

## Reference

- Candidate profile, Canva workflow, verification checklist: [`CLAUDE.md`](CLAUDE.md)
- Setup guide: [`GETTING_STARTED.md`](GETTING_STARTED.md)
- Current active docs: [`working/active/`](working/active/)
- Archived prior work: [`working/archive/`](working/archive/)
- Canva helper scripts: [`working/scripts/`](working/scripts/)
