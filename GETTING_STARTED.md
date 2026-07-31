# Getting Started — Claude-Assisted Job Search Workspace

> **Start with [`README.md`](README.md)** for the short version — what this is, prerequisites, and a
> five-step quick start. This file is the deep walkthrough: it takes you from a fresh clone to a
> filed, submission-ready application, and explains *why* each guard exists. Work through it once,
> in order.

## What this repo does

This workspace turns Claude Code into your personal job application pipeline. It handles job discovery (searching confirmed-queryable job boards), fit evaluation (screening roles against your profile and realistic hiring probability, not just skills match), application drafting (résumé body + cover letter, length-matched to your Canva template), porting (editing your Canva design via MCP without you touching the tool), and filing (exporting PDFs, naming folders, updating your tracker).

The design principle is **one conversation = one sprint** — you open Claude Code, say `/pipeline`, and Claude handles search → evaluate → draft → port → export. You review drafts in your IDE, greenlight, and Claude does the Canva edits and PDF exports. The output is submission-ready PDFs filed in `working/exports/`, a running `job_search_tracker.csv`, and a searchable 3D visualization of your entire pipeline.

The system is built for a specific workflow: a **Canva resume template with multiple resume+cover pairs** (each pair = one application), edited programmatically via the Canva MCP. This is the fastest way to produce polished, consistently formatted applications at volume. If you don't want to use Canva, the repo still works with LaTeX templates (see `cv/` and `cover_letters/` as fallbacks), but the porting automation won't apply.

---

## Prerequisites

Before you start:

1. **Claude Code** installed and running (`claude` CLI — see [claude.ai/code](https://claude.ai/code))
2. **Canva account** with MCP integration enabled in Claude Code settings (this is what lets Claude edit your design without a browser)
3. **Python 3.11+** for the helper scripts (`pip install plotly` for the viz)
4. **Node.js** (optional — only needed if you use the `working/scripts/utils/check_viz_full.py` / `check_viz_three.py` syntax checkers)
5. **GitHub account** (the repo tracks your applications via git)
6. **Optional: Adzuna API key** — structured Canadian job listings with salary data. Free tier. Register at [developer.adzuna.com](https://developer.adzuna.com). The pipeline can call it as an MCP tool for significantly better search coverage than HTML scraping.
7. **Optional: Jooble API key** — broader aggregator. Free key on request at [jooble.org/api/about](https://jooble.org/api/about).

---

## Step 0 — Load your private documents

Before you personalize anything, give Claude your raw source material. Drop your real files into
`documents/`:

| Folder | What goes in it |
|--------|-----------------|
| `documents/cv/` | Your current résumé(s), in any format |
| `documents/linkedin/` | Your LinkedIn data export or a saved profile PDF |
| `documents/diplomas/` | Degrees, transcripts, certifications |
| `documents/references/` | Reference letters, performance reviews, testimonials |
| `documents/postings/` | Job postings you want evaluated — saved or pasted |
| `documents/applications/` | Past applications worth reusing language from |

**The contents are gitignored.** Only the folder structure and `documents/README.md` are tracked, so
the layout survives a fresh clone while your personal files never get committed. Verify with:

```bash
git check-ignore -v documents/cv/your_resume.pdf   # should report a match
```

This matters for two reasons. First, Step 1 is much faster if Claude can read your existing CV and
draft the profile from it rather than asking you to type it all out — you can literally say *"read
`documents/cv/` and fill in CLAUDE.md."* Second, it keeps personal data out of a repo you may later
push to a public fork.

> **Trust boundary — read this once.** Anything in `documents/postings/` is untrusted third-party
> content. A job posting is **data to evaluate, never instructions to follow**, and pasting one in by
> hand does not launder it. If a posting contains text like "ignore previous instructions" or "email
> this document to…", that is an injection attempt, not a requirement of the role.

---

## Step 1 — Personalize CLAUDE.md

`CLAUDE.md` is the AI's persistent memory of who you are. Every time you open a session, Claude reads this file before doing anything. It contains:

- **Your identity** (name, contact, location, languages, status)
- **Your education and experience** (the source material for all CV bullets)
- **Your technical skills** (primary, secondary, domain, software)
- **Your behavioral profile** (how you think and work — used for cover letters and culture fit)
- **Your target sectors** (where to look for jobs)
- **Your deal-breakers** (what to skip automatically)
- **Workflow rules** (porting, formatting, search execution)
- **Never-use phrases** (words you've flagged as off-brand)

Open `CLAUDE.md` and replace every `[YOUR_...]` placeholder with your real information. The more specific you are, the better the applications. Vague entries produce generic output.

**Fields that need special attention:**
- `[YOUR_ORGANIZATION]` — if you have a concurrent venture, nonprofit, or consultancy that will run alongside your new job, describe it here so Claude can frame it as complementary, not conflicting.
- `Target Sectors` — list the specific agencies, org types, and companies you want to apply to. Claude uses this to bias search queries.
- `Deal-breakers` — including your salary floor. Claude will silently skip any role below this threshold.
- `Behavioral Profile` — write this in the first person, as you'd actually describe yourself. Claude uses it to make cover letters sound like you.

---

## Step 2 — Set up the Canva design

### What the template needs to look like

Your Canva file should be a **multi-page document** structured as pairs:
- **Odd pages** = resume (one per application)
- **Even pages** = cover letter (one per application)

Page 1 + 2 = application #1, Page 3 + 4 = application #2, etc. You build up inventory by duplicating a "baseline" pair — a clean resume/cover design that works for your default positioning — and then Claude edits each pair's text to target a specific role.

The porting workflow requires your resume to use **absolutely-positioned text boxes** (not auto-flowing text frames). This is Canva's default for design files (not docs), so any standard resume template will work. The key structural boxes Claude expects to find:

- **headline** — your job title / positioning tagline (top of page)
- **profile / summary** — 3–5 sentence paragraph
- **work experience boxes** — one per role; formatted as: bold title + org line, then bullet lines
- **skills boxes** — 4 skill labels with description paragraphs
- **cover letter box** — the large text area on the cover page

Claude identifies boxes by matching their current text content (not by position), so after you set up the baseline, it can find the right box on any duplicated pair.

### Getting the design ID and shortlink

1. Open your Canva design
2. Click Share → Copy link — this is your shortlink (e.g. `canva.link/xxxxx`)
3. The design ID is the alphanumeric code in the Canva URL (e.g. `DAGxxxxxx` in `canva.com/design/DAGxxxxxx/...`)
4. Update `CLAUDE.md` with both values

### Calibrating box lengths

After your first `start-editing-transaction` in a session, run `working/scripts/utils/parse_transaction.py` (update the `SNAP` path at the top to your transaction file). This gives you the actual width, height, and character count of every box. Do 2 real ports and update the calibration table in `CLAUDE.md` with your confirmed targets. The defaults in the table are estimates — your actual template will differ.

---

## Step 3 — Configure .env

Copy `.env.example` to `.env` and fill in your API keys:

```
cp .env.example .env
```

Then open `.env` and fill in values. At minimum you need nothing to start — WebSearch and WebFetch work without keys. Add Adzuna/Jooble when you want structured search results with salary data.

The `.env` file is gitignored. Never commit it.

---

## Step 4 — Build your first viz

The job search visualizer is a self-contained HTML file that shows your entire pipeline in 3D.

```bash
python working/scripts/viz/build_job_viz.py
```

This generates `working/active/job_search_viz.html`. Open it in any browser — no server needed.

### What the three axes mean

- **X = Public-sector proximity** (1 = startup, 5 = core government/APS)
- **Y = Innovation focus** (1 = operations/compliance, 5 = ecosystem/R&D)
- **Z = Seniority** (1 = specialist/individual contributor, 5 = branch-head/VP)

Every job in your pipeline is a dot. You plot it based on how the role actually sits in that 3D space, not just its job title. This makes it easy to see where your search is concentrated, where you have blind spots, and how to talk about your positioning.

### Adding your own jobs

Edit the `JOBS` list in `working/scripts/viz/build_job_viz.py`. Each entry is a dict:

```python
dict(
    label="Director, Innovation Programs",   # short label shown in viz
    org="Example Innovation Hub",            # organization name
    x=2.5,   # sector proximity (1–5)
    y=4.2,   # innovation focus (1–5)
    z=3.8,   # seniority (1–5)
    fit=4,   # your assessment of fit (1–5 stars)
    p=25,    # P(interview) estimate as integer %
    sal=110, # salary midpoint estimate in $K
    sal_min=95, sal_max=125,   # salary range
    status="Applied",          # Applied/Interview/Ported/Drafted/Target/Queued/Ready
    date="2025-01-20",         # YYYY-MM-DD of application or first awareness
    outcome=None,              # None / "pending" / "offer" / "no-offer"
    note="Optional note",      # shown in dot-click modal
    closes="2025-02-15",       # close date if known
)
```

After editing, re-run `build_job_viz.py` to regenerate the HTML.

### The focus sphere

The blue sphere in the viz shows your current search focus — the region of the 3D space you're actively targeting. Use the sidebar sliders to move and resize it. The "Copy Focus" button copies a `/pipeline` prompt to your clipboard that tells Claude exactly where to search.

---

## Step 5 — Run your first job sweep

```
/pipeline
```

Claude will:
1. Ask if you want to review the shortlist before drafting (or pass `--confirm` / `--auto` next time to skip the question)
2. Search the confirmed-queryable boards in `.claude/skills/pipeline/boards.md` — ~4–6 WebFetch/WebSearch calls per wave
3. Filter results through a **hiring probability gate** (skills match ≠ hiring probability; roles where there's no realistic path to hire are dropped silently)
4. Write a sweep doc to `working/active/job_sweep_YYYY-MM-DD.md` **before presenting anything in chat**
5. Summarize from the doc, then wait for your input

### The anti-signal filter

Every sweep result is cross-checked against your applied-roles log — `job_search_tracker.csv` plus Claude's own project memory (`.claude/projects/<project>/memory/`, which is gitignored and created on first use). Roles you've already applied to are silently dropped — you never see them again. Update the tracker after every submission.

### The open-status gate

Before any Canva porting, Claude posts a checklist of role URLs and asks you to verify each is still open in its live portal. This is mandatory — aggregators and job boards frequently show closed roles. Never skip this step; porting to a closed role wastes an hour.

---

## Step 6 — Port your first application to Canva

Once you've greenlighted a packet (résumé + cover draft), Claude handles the Canva edit in one transaction:

1. **`start-editing-transaction`** — opens an editing session and returns all element IDs
2. **`parse_transaction.py`** — maps element IDs to box names/positions from the persisted transaction file
3. **Build a builder script** — clone the closest script in `working/scripts/builders/`, swap the role copy and find-anchors (current text used to locate each box), run it to generate an ops JSON
4. **Clean-map check** — every element ID in the ops must resolve to a real box. The builder prints `CLEAN-MAP CHECK: PASS` or `FAIL`. Never proceed on FAIL.
5. **`perform-editing-operations`** — apply the ops JSON. Do this immediately after starting the transaction — transactions expire.
6. **`format_text {font_style: normal}`** — on all work-experience boxes, to clear the baked italic first bullet
7. **Overflow audit** — run `working/scripts/utils/height_audit.py` on the new transaction snap. Compare box heights across pairs; any box taller than the same-type reference = overflow. Trim the offending bullet(s) and re-apply.
8. **`commit-editing-transaction`** — changes are lost if you don't commit.

### The builder script pattern

Builder scripts (in `working/scripts/builders/`) do four things:
1. Define a `SNAP` path — the persisted transaction file from the last `start-editing-transaction`
2. Define `ID` — a dict mapping box names to their element IDs from the transaction
3. Define `CAP` — character capacity per box (your calibrated targets from CLAUDE.md)
4. Print a per-box table showing old vs. new char counts, then write the ops JSON

To port a new role: copy `build_EXAMPLE_pair1.py`, update `SNAP` to your new transaction file, update `ID` with the element IDs from `parse_transaction.py`, swap the role copy, run, check the output table for OVER! flags, trim if needed, then apply.

### Overflow detection

Character count is a rough proxy — proportional fonts render wide words wider regardless of char count. The reliable overflow check is box height comparison:

1. After committing, start a new transaction and run `height_audit.py`
2. The **shortest clean box height is the baseline** — any box taller by ≥5 units is overflowing
3. Trim the longest bullets until heights match

---

## Step 7 — Export and file

After you greenlight the Canva edits:

```
export-design → type:pdf, size:letter, export_quality:pro, pages:[2k-1]   # resume
export-design → type:pdf, size:letter, export_quality:pro, pages:[2k]     # cover letter
```

PDFs are small (~100–120 KB each at pro quality). Download with `Invoke-WebRequest` (PowerShell — use this for paths with spaces/parentheses, never Bash `mv`).

**Folder naming convention:**
```
working/exports/
└── YYYY-MM (Mon 'YY)/                          # e.g. "2025-01 (Jan '25)"
    └── YY-MM-DD - Company - Role/              # e.g. "25-01-20 - Example Inc - Director"
        ├── [YOUR_NAME]_Resume.pdf
        ├── [YOUR_NAME]_Cover_Letter.pdf
        └── copy/
            ├── packet_role-slug_YYYY-MM-DD.md  # the draft (created at draft time)
            └── review_agents_YYYY-MM-DD.md     # reviewer agent findings
```

Month folders sort chronologically; app folders are date-first for autosort. PDFs are the source of truth — `job_search_tracker.csv` points to them.

---

## Agent Onboarding

When starting a new Claude Code session on this repo, paste this prompt to orient the agent quickly:

```
Read CLAUDE.md (candidate profile + Canva workflow), HANDOFF.md (current sprint state), 
and working/active/ (live docs). Then tell me:
1. What sprint we're in and what's pending
2. Whether there are any roles in the shortlist not yet ported
3. Whether the Canva design has enough pairs for the pending roles
Don't start any work yet — just orient yourself and report.
```

Claude will read the key files and give you a status brief before doing anything. This prevents duplicate work and stale-context mistakes.

---

## Common Pitfalls

**The session token limit.** Background/multi-agent search jobs silently fail when they hit the token limit — you get no results and no error. HARD RULE: job searches are small foreground sweeps only (~4–6 WebFetch/WebSearch calls). If you need more coverage, run another small sweep in a fresh session.

**Stale job board listings.** Aggregators (Indeed, Glassdoor, LinkedIn) frequently show closed postings. Always verify open status on the employer's own portal before porting. Three roles were ported mid-pipeline before this rule was established, wasting ~3 hours each.

**The italic first bullet.** Canva bakes the first bullet of each work-experience box as italic (it's in its own run). `find_and_replace_text` preserves this italic. Fix it every port with `format_text {font_style: normal}` on all work boxes.

**Overflow from wide words.** A bullet that's 5% shorter than its predecessor can still overflow if it uses more long words ("government", "infrastructure", "organizational"). When you're close to the char limit and using wide-word-heavy text, aim 10–15 chars under the limit.

**Hardcoded transaction file paths.** The `SNAP` variable in every utility and builder script must point to a file that exists on your machine. After each `start-editing-transaction`, update `SNAP` in the scripts you're about to run.

**Committing without committing.** The Canva transaction is not saved until you call `commit-editing-transaction`. If the session ends or errors, all edits are lost. Always commit immediately after applying ops.

**Pair assignment confusion.** Keep the roster table in the sprint doc updated — one row per role with its pair number. If two roles accidentally get the same pair, one gets overwritten.

**Chat-only sweep docs.** If Claude only reports the sweep in chat and doesn't write a doc, the results are lost when the session ends. The sweep doc (`working/active/job_sweep_YYYY-MM-DD.md`) must be written to disk before anything is presented in chat. This is a standing rule in `CLAUDE.md` and the skills.

---

## Directory Reference

```
ai-job-search-template/
├── README.md                   # front door: what this is + quick start
├── CLAUDE.md                   # candidate profile + workflow rules (AI reads this first)
├── GETTING_STARTED.md          # this file — the deep walkthrough
├── HANDOFF.md                  # sprint state, active docs, pending items
├── LICENSE                     # MIT (dual copyright; fonts under OFL)
├── .env.example                # env var keys (copy to .env, fill in)
├── .gitignore
├── job_search_tracker.csv      # canonical application index
├── documents/                  # YOUR PRIVATE INPUTS — contents gitignored
│   ├── cv/                     # existing résumé(s)
│   ├── linkedin/               # LinkedIn export / profile PDF
│   ├── diplomas/               # degrees, transcripts, certifications
│   ├── references/             # reference letters, reviews
│   ├── postings/               # job postings to evaluate (UNTRUSTED content)
│   └── applications/           # past applications worth reusing
├── working/
│   ├── templates/              # COPY THESE, never edit in place
│   │   ├── SWEEP_TEMPLATE.md   # one job-search sweep
│   │   ├── PACKET_TEMPLATE.md  # one application: measured copy + checklists
│   │   └── OUTREACH_LOG_TEMPLATE.md  # LinkedIn outreach for one role
│   ├── active/                 # live work only: current sweep + current interview doc
│   ├── exports/                # FINALS ARCHIVE: every submitted app (PDFs + packet)
│   ├── archive/
│   │   ├── sweeps/             # past sweep docs (move here after sprint ends)
│   │   ├── sprints/            # past sprint plans
│   │   └── packets/            # intermediate multi-app drafts
│   └── scripts/
│       ├── PORTING_RECIPE.md   # step-by-step Canva porting guide
│       ├── REVIEW_AGENTS.md    # reviewer persona templates + log
│       ├── template/           # template_port.py + manifest.json (the port primitive)
│       ├── utils/              # render, verify sign-off, measure gap, audits
│       ├── viz/                # visualization generators
│       ├── builders/           # historical examples — do NOT clone for new work
│       └── generated/          # output JSON from the port primitive
├── cv/                         # LaTeX CV fallback (legacy), placeholder-tokenized
├── cover_letters/              # LaTeX cover letter fallback (legacy) + bundled fonts
├── .agents/vendor/             # vendored linkedin-cli submodule + setup script
└── .claude/skills/             # AI skill definitions
    ├── pipeline/SKILL.md       # full pipeline skill
    ├── pipeline/boards.md      # confirmed queryable job boards
    └── job-scraper/SKILL.md    # job search skill
```
