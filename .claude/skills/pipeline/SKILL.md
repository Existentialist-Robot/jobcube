---
name: pipeline
description: >
  End-to-end job application pipeline: discover, evaluate, optional confirm gate, draft, review,
  port to Canva, export PDFs, file the application folder. Runs from a confirmed list of
  queryable job boards.
  Triggers on: run the pipeline, apply to, full application, draft and port, /pipeline
allowed-tools: Read, Write, Edit, Glob, Grep, WebFetch, WebSearch, Agent, Bash, TodoWrite, mcp__claude_ai_Canva__*
framework_version: 1.0.0
---

# Full Application Pipeline

---

## Invocation

```
/pipeline                     # asks about confirmation gate, then runs full pipeline
/pipeline --confirm           # always pauses at shortlist for you to approve before drafting
/pipeline --auto              # no gate — drafts and ports everything above threshold automatically
/pipeline --search-only       # just run discovery + evaluation; stop before drafting
/pipeline --sectors=gov,eco   # limit to specific sectors (gov | eco | nonprofit | postsec | all)
/pipeline --min-stars=4       # override minimum fit threshold (default: 3)
```

---

## Step 0: Configure

**Before doing anything else**, check for search focus parameters — in priority order:
1. **Inline in prompt**: If the prompt contains a `SEARCH_FOCUS={"cx":...}` JSON line (pasted from the "Copy Focus" button in the viz), parse and use those values directly. Also write them to `working/active/search_focus.json` for future runs.
2. **From file**: Read `working/active/search_focus.json` if it exists.
3. **Default**: cx=3, cy=3.5, cz=3.5, radius=1.0, boundary=5.

If the file exists, use it to:
1. Bias keyword selection toward sectors/seniority matching the focus
2. Set the minimum fit threshold dynamically: boundary ≤3 → raise min-stars to 4; boundary ≥7 → accept 3-star
3. Tell the user the current focus before starting the sweep

**Then ask one question:**

> "Do you want to review the shortlist and confirm which roles to apply for before I start drafting? (Or pass `--confirm` / `--auto` next time to skip this.)"

If `--confirm` was passed: set `GATE=true`. If `--auto` was passed: set `GATE=false`. Otherwise wait for answer.

Then read these files:
- `.claude/skills/pipeline/boards.md` — confirmed queryable boards + keyword strategy
- `working/scripts/PORTING_RECIPE.md` — Canva porting rules
- `working/scripts/REVIEW_AGENTS.md` — review agent personas

---

## Step 1: Discover

**Search the confirmed boards** using the keyword strategy in `boards.md`. Run in **two parallel waves of 5 boards** (not all at once — stay under 6 WebFetch/WebSearch calls per wave per CLAUDE.md Search Execution rule).

For each board:
1. Fetch the search results page using the URL patterns in `boards.md`
2. Extract: title, org, location, salary (if shown), close date, URL
3. **Immediately verify open status** — fetch the posting if close date is unclear. Discard anything showing "application period has closed" or past close date.
4. **Verify the posting URL resolves to the actual job posting** — not a homepage redirect or 404. Check by fetching the URL and confirming the page title / posting content matches the role.

**Anti-signal filter** (mandatory before presenting any role):
- Cross-check every result against any previously-applied roles log
- Silently drop any role where title + org matches an applied entry
- Never present already-applied roles

---

## Step 2: Evaluate

For each verified-open role that passes the anti-signal filter:

1. Run a quick fit assessment against the candidate profile in `CLAUDE.md`
2. Assign a **star rating (1–5)** and estimate **P(interview)** and **P(hire|interview)**
3. Apply **minimum threshold**: only continue with roles rated **≥ 3 stars** (unless `--min-stars` overrides)

**Probability anchors:**
- Screener PASS + no major gaps → P(interview) 30–50%
- HOLD-FOR-HM (conditional) → 15–35%
- BORDERLINE / stretch → 10–20%
- Strong sector recognition (relevant awards, grants, relationships) → +5pp

**Hard filters** — always drop regardless of star rating:
- Requires specialist credential the candidate doesn't have (P.Eng, CPA, legal, clinical license, etc.)
- Salary below floor confirmed in posting
- Another CEO/ED role (if candidate has concurrent org — check CLAUDE.md Deal-breakers)
- APS internal-only posting (explicitly states preference for current employees)

---

## Step 3: Compile Shortlist

**MANDATORY — write the sweep to disk IMMEDIATELY.** The sweep document is written to `working/active/job_sweep_{YYYY-MM-DD}_{slug}.md` as the **first action after discovery+evaluation, before presenting anything in chat**. Never produce a shortlist only in the chat reply — a chat-only sweep is lost the moment the session ends. Draft the doc, then summarize from it in chat.

### Canonical sweep doc format

```markdown
# Job Sweep — {YYYY-MM-DD} — {Focus Label}

## Search focus
{scope description or search_focus JSON block}

## Confirmed Open — Shortlist

| # | Role | Org | Location | Salary | Posted | Closes | Fit | P(int) | P(hire\|int) | Status |
|---|------|-----|----------|--------|--------|--------|-----|--------|-------------|--------|
| 1 | [Title](url) | Org | City, Province (remote/hybrid) | $X–Y or Not listed (~$X–Y est.) | Mon DD | Mon DD ⚠️ VERIFY / URGENT | ★★★★☆ | 30% | 25% | Queue |

**Probability rationale:** 1–2 sentences on why the P(int) estimates are what they are.
(After running review agents: update P(int) — PASS=50%+, HOLD-FOR-HM=25–40%, AUTO-REJECT=<10%)

## Role Summaries

### {N}. {Org} — {Title} ({Location})
**Why it fits:** …  
**Gap / risk:** …  
**Recommendation:** Apply / Strong apply / Monitor / Skip

## Strong but not in shortlist

| Role | Org | Reason |
|------|-----|--------|

## Boards checked / blocked / no usable target

| Board | Result |
|-------|--------|
```

**Column rules:**
- **Role** — hyperlink the title to the live posting URL (Adzuna mirror URL is fine if that has the full text)
- **Salary** — posted range if available; otherwise `Not listed (~$X–Y est.)` with a calibrated estimate
- **Posted / Closes** — actual dates; `⚠️ VERIFY` if close date absent; `⚠️ URGENT` if ≤3 days out
- **Fit** — ★★★★★ scale: 5★=80–100%, 4★=65–79%, 3★=50–64%; minimum to include is 3★ (or `--min-stars` override)
- **P(int) / P(hire\|int)** — conservative calibrated estimates; NEVER omit these columns
- **Status** — `Queue`, `Verified open`, `⚠️ Closes {date}`, or `Skip`

**Markdown table rule:** escape any `|` inside headers/cells as `\|` or the column breaks.

---

## Step 4: Confirmation Gate (if GATE=true)

Present the sprint document and ask:

> "Here's the shortlist from today's sweep. Which numbers do you want to proceed with? (Enter numbers, e.g. `1 3 5`, or `all`, or `none`.)"

Wait for response. Proceed only with the confirmed numbers.

If `GATE=false`: proceed with all roles above threshold automatically. Log which were auto-approved.

---

## Step 5: Pre-Port Check

Before drafting any application, ask (once for the whole batch):

> "I'll need one Canva pair per application — pages (2k−1) and (2k). How many pairs have you duplicated in the design? I'll work through them in order."

If pairs haven't been duplicated yet, wait. Once confirmed, assign pairs in order (lowest unused page numbers first).

Verify pair availability by calling `mcp__claude_ai_Canva__get-design` on design `[YOUR_CANVA_DESIGN_ID]` (from CLAUDE.md) to check live `page_count`.

---

## Step 6: Apply (per role)

Process **one role at a time** — never draft or port multiple roles simultaneously.

### 6a. Draft Packet

1. Read the full job posting via WebFetch
2. **Create the application folder + `copy/` subfolder FIRST** (PowerShell), then draft the packet **directly into it**:
   `working/exports/{YYYY-MM (Mon 'YY)}/{YY-MM-DD - Company - Role}/copy/packet_{slug}_{date}.md`
   - Packets are NOT written to `working/active/`
   - Use calibrated box targets from `CLAUDE.md`
   - Cover letter: 3,050–3,387 chars (the band in `port_config.json`)

### 6b. Review

Run review agents from `working/scripts/review-agent-library.json` (personas also documented in `working/scripts/REVIEW_AGENTS.md`):
- For 5-star: run 3 agents (Hiring Manager + Screener + Holistic)
- For 4-star or below: run 2 agents (Hiring Manager + Screener)
- **Every cover draft, regardless of rating:** Anti-AI-Slop Reviewer

Pick agents by tag overlap and **state the match score before running one**: reuse needs ≥8.5/10, or ≥9.0/10 for a 5-star application. Below threshold, clone the closest agent into a new specialized entry rather than running a bad match. Append each outcome to that agent's `used_for`.

Incorporate fixes before porting.

### 6c. Port to Canva

**Pair selection — ASK, never probe.** Do NOT spend tokens calling `get-design-content` / starting transactions to hunt for a free pair. Just ask "[which pair?]" (one line) and port there.

Follow [`working/scripts/PORTING_RECIPE.md`](../../../working/scripts/PORTING_RECIPE.md) exactly:

1. `start-editing-transaction` → the snapshot persists to a file; element IDs come from there and nowhere else
2. Write the `copy.json` for the pair (slots + lead-role bullets + cover body)
3. `python -B working/scripts/template/template_port.py port <snapshot> <copy.json> --out <ops.json>` → measures against the manifest, scans banned phrases, prints **CLEAN-MAP CHECK**
4. `python -B working/scripts/validate_canva_ops.py <snapshot> <ops.json>` → must pass
5. One `perform-editing-operations` with all ops
6. `format_text {font_style: normal}` on every work-experience box (clears the baked italic first bullet)
7. **Sign-off check, before committing:** `python -B working/scripts/utils/verify_port_signoff.py <perform_response.json> <cover_eid…>`. On FAIL, **cancel** the transaction — never commit a clipped cover.
8. `commit-editing-transaction` — immediately. A transaction left sitting expires and drops the edits silently.
9. **Render-verify (MANDATORY):** export each edited page, `render_canva_page.py` it, and *look* at the PNG. `measure_cover_gap.py` each cover; target 7–12pt.

> Do not clone a per-role builder. `working/scripts/builders/` is historical evidence only —
> `template_port.py` is the current and only op generator. Character counts are a drafting
> heuristic; the render is what decides.

### 6d. Export

The packet greenlight already covers this. Do not ask again: it is standing authorization
through porting, render-verify and export for the pages it named, including text-only
corrections found during those checks. Ask again only if a correction changes meaning,
expands scope, or alters layout geometry.

```
export-design → type:pdf, size:letter, export_quality:pro, pages:[2k-1]  → resume
export-design → type:pdf, size:letter, export_quality:pro, pages:[2k]    → cover letter
```

Download to application folder via PowerShell `Invoke-WebRequest` (never Bash mv — path quoting failures).

### 6e. File

```
working/exports/{YYYY-MM (Mon 'YY)}/{YY-MM-DD - Company - Role}/
├── [YOUR_NAME]_Resume.pdf
├── [YOUR_NAME]_Cover_Letter.pdf
└── copy/
    ├── packet_{slug}_{date}.md
    └── review_agents_{date}.md
```

### 6f. Update viz JOBS status

After each state change, update the corresponding `dict(...)` entry in `working/scripts/viz/build_job_viz.py` and rebuild the viz:

| Transition | `status=` value |
|---|---|
| Packet drafted, not ported | `"Drafted"` |
| Ported to Canva, not exported | `"Ported"` |
| PDFs exported and filed | `"Ready"` |
| Submitted to portal/email | `"Applied"` |
| Interview scheduled or completed | `"Interview"` |

Run `python working/scripts/viz/build_job_viz.py` after every update. It delegates to
`build_job_viz_three.py`, which also pulls the sweep-coverage layer from
`build_sweep_viz.py`. Set `loc` on each job ("Toronto, ON" / "Remote") or it plots as
Remote.

---

## Step 7: Update Logs

After each successfully filed application:
1. Add to any applied roles log
2. Add/update row in `job_search_tracker.csv`
3. Mark the role applied in `job_scraper/seen_jobs.json` so future sweeps drop it

---

## Standing Rules

1. **Never port without greenlight** on the packet content (unless `--auto` mode)
2. **CLEAN-MAP check before every port** — every element_id must resolve; FAIL = stop, don't touch Canva
3. **One role at a time** — draft, review, port, export, file; then next role
4. **Check overflow after every port** — trim and re-apply before committing if overflow detected
5. **Anti-signal filter is mandatory** — never present or draft for already-applied roles
6. **Use PowerShell for all file moves/downloads** — never Bash for paths with spaces/parentheses
7. **Transaction expires** — start transaction and apply ops in the same turn; never let it sit idle

---

## Porting Pair Assignment Reference

Fresh duplicate pairs in your Canva design all start from the same baseline, so porting a
role means transforming that baseline rather than filling a blank.

- Read the live `page_count` from `get-design` **before every session**. It grows each time
  you seed more pairs — never hardcode it.
- Pair *k* = page (2k−1) résumé + page (2k) cover letter. "The first pair" is pages 1–2.
- Work from the lowest unoccupied pair upward.
- Record which pair went to which role in the sprint doc's roster table, with the pair cell
  linking to the Canva page and the role cell linking to the live posting.
