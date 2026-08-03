# Getting Started with jobcube

> **Start with [`README.md`](README.md)** for the short version — what this is, what you need, and
> the one command that sets it up. This file is the deep walkthrough: it takes you from a fresh
> clone to a filed, submission-ready application, and explains *why* each guard exists. Work
> through it once, in order.

## What this repo does

jobcube turns a coding agent — Claude Code or Codex — into your personal job application pipeline. It handles job discovery (searching confirmed-queryable job boards), fit evaluation (screening roles against your profile and realistic hiring probability, not just skills match), application drafting (résumé body + cover letter, length-matched to your Canva template), porting (editing your Canva design via MCP without you touching the tool), and filing (exporting PDFs, naming folders, updating your tracker).

The design principle is **one conversation = one sprint** — you open Claude Code, say `/pipeline`, and Claude handles search → evaluate → draft → port → export. You review drafts in your IDE, greenlight, and Claude does the Canva edits and PDF exports. The output is submission-ready PDFs filed in `working/exports/`, a running `job_search_tracker.csv`, and a searchable 3D visualization of your entire pipeline.

The system is built for a specific workflow: a **Canva resume template with multiple resume+cover pairs** (each pair = one application), edited programmatically via the Canva MCP. It produces consistently formatted applications at volume with almost no per-application layout work. If you don't want to use Canva, the repo still works with LaTeX templates (see `cv/` and `cover_letters/` as fallbacks), but the porting automation won't apply.

---

## Prerequisites

Before you start:

1. **A coding agent** — [Claude Code](https://claude.ai/code) (`claude` CLI) or [Codex](https://openai.com/codex). The scripts and gates run under either; only the slash-command layer is Claude Code-specific. Codex users start from [`AGENTS.md`](AGENTS.md).
2. **Canva account** with the MCP connector enabled in your agent's settings (this is what lets the agent edit your design without a browser)
3. **Python 3.11+** for the helper scripts — `pip install -r requirements.txt`. That is `pymupdf` (required: the render-verify loop rasterizes exported PDFs), `plotly` (only for the legacy renderer) and `pyyaml` (optional; the linter has a fallback). Skip this entirely if you use the container.
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
- `Deal-breakers` — including your salary floor. Claude will silently skip any role below this threshold. The floor is yours to set, but once you have swept a few dozen roles `floorprice` can tell you what the market actually posts for them — see [Step 8](#step-8--what-to-ask-for).
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

Boxes are identified by **position**, not by their current text. Element IDs regenerate on every duplicated page, but the geometry does not, so `manifest.json` keys each slot by where it sits and pages match a variant by position fingerprint. That is why duplicating the pair is enough setup: the copy in the boxes can change freely and the slot map still resolves.

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

The visualizer plots your whole pipeline in a 3D coordinate space and doubles as the record of where you have already searched.

```bash
python -B tools/serve.py          # rebuilds, then serves at http://localhost:8000
```

Or in a container, if you would rather not set up Python locally:

```bash
docker compose up                 # same thing, same address
```

Either way it regenerates `working/active/job_search_viz.html` and serves it with caching off, so a refresh always shows the current build. **Don't open the file directly** — that was the old workflow, and it gives you no way to tell whether what you are looking at is stale. `build_job_viz_three.py` is the builder; `build_job_viz.py` now delegates to it and only renders the legacy Plotly version under `JOB_VIZ_LEGACY=1`.

### What the three axes mean

The shipped defaults describe one particular search:

- **X = employer type** (1 = startup, 5 = government)
- **Y = kind of work** (1 = operations/compliance, 5 = ecosystem/R&D)
- **Z = seniority** (1 = specialist, 5 = VP/C-suite)

**Rename them.** They are `AXES` in `working/scripts/viz/build_sweep_viz.py`, and your search may vary along entirely different dimensions — industry, company stage, geography, IC versus management. `/setup` asks you about this.

Every role is a dot, placed by where it actually sits rather than by its title. What that buys you is visible blind spots: `build_sweep_viz.py` also records which cells you have swept, so the map shows where you have not looked. `deep sweep` searches exactly the cells flagged `new=True`, which is what stops a search quietly re-mining one seam for a month.

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
4. Write a sweep doc to `working/active/job_sweep_<YYYY-MM-DD>_<slug>.md` **before presenting anything in chat**
5. Summarize from the doc, then wait for your input

### The anti-signal filter

Every sweep result is cross-checked against your applied-roles log — `job_search_tracker.csv` plus Claude's own project memory (`.claude/projects/<project>/memory/`, which is gitignored and created on first use). Roles you've already applied to are silently dropped — you never see them again. Update the tracker after every submission.

### The open-status gate

Before any Canva porting, Claude posts a checklist of role URLs and asks you to verify each is still open in its live portal. This is mandatory — aggregators and job boards frequently show closed roles. Never skip this step; porting to a closed role wastes an hour.

---

## Step 6 — Port your first application to Canva

### First-run setup (once)

Before your first port, do two things:

1. **Fill in `working/scripts/template/port_config.json`** — your sign-off name, the cover
   character band, and your ban list. `template_port.py port` **refuses to run** while the
   sign-off name is still `[YOUR_NAME]`. That guard is deliberate: Canva silently clips trailing
   text out of a too-small box, and without a real name the pipeline can't tell a signed cover
   from an unsigned one.
2. **Register your layout:**
   ```bash
   python working/scripts/template/template_port.py build-manifest <snapshot.json> --name v1
   ```
   where `<snapshot.json>` is a saved `start-editing-transaction` response. The shipped
   `manifest.json` and the capacities inside `template_port.py` were measured against one
   specific design — they are a **worked example, not universal**.

### The port loop

Once you've greenlighted a packet (résumé + cover draft), Claude handles the Canva edit in one
transaction:

1. **`start-editing-transaction`** — opens an editing session; the response persists to a file and
   is the only source of element IDs.
2. **Write `copy.json`** — slots, lead-role bullets, and cover body per pair (schema is in the
   `template_port.py` docstring; the drafting tables are in
   [`working/templates/PACKET_TEMPLATE.md`](working/templates/PACKET_TEMPLATE.md)).
3. **Generate ops:**
   ```bash
   python working/scripts/template/template_port.py port <snapshot.json> copy.json
   ```
   This measures every slot against its manifest cap, flags `UNDER-FILL` on sparse descriptions,
   scans the ban list, prints `SLOP-WARN` per cover, checks each cover ends with the sign-off, and
   prints **`CLEAN-MAP CHECK: PASS`** or `FAIL`. **Never proceed on FAIL.**
4. **Validate:** `python working/scripts/validate_canva_ops.py <snapshot.json> <ops.json>`
5. **`perform-editing-operations`** — apply all ops in one call, immediately (transactions expire
   and silently drop edits if they sit).
6. **Verify sign-offs BEFORE committing:**
   ```bash
   python working/scripts/utils/verify_port_signoff.py <perform_response.json> <cover_eid...>
   ```
   On FAIL, **cancel** the transaction. Never commit a clipped cover.
7. **`commit-editing-transaction`** — within seconds of the perform. Changes are lost if you don't
   commit.

`template_port.py` also emits `format_text {font_style: normal}` on work-experience boxes (to clear
a baked italic first bullet) and a width-only `resize_element` on each cover box before its text is
written, so the frame grows to fit before Canva can clip it.

### Overflow detection — render, don't count

Character count is a **drafting heuristic only**. Proportional fonts render wide words wider
regardless of char count, so a box that held 184 characters of one wording overflows at 184 of
another. **Pixels decide.** After every commit:

1. `export-design` the edited page(s) to PDF and download them
2. ```bash
   python working/scripts/utils/render_canva_page.py <page.pdf>
   ```
   renders the full page plus zoomed skill-column and left-column PNGs
3. **Read the PNGs.** Check every edited box for overflow (text crowding the next label) and
   under-fill (a short last line or a stranded empty line). Confirm the cover's sign-off is
   visibly present.
4. For covers, also run `python working/scripts/utils/measure_cover_gap.py <cover.pdf>` — target a
   signature gap of **7–12pt**
5. Iterate trims and fills until the render is clean, then re-export

Skipping this is expensive: one skill description once took **five** rounds of human correction
(151→184→164→159→146 chars) that a single render would have caught on the first pass.

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

## Step 8 — What to ask for

This one is not part of the application loop. It runs on the exhaust from it.

Every sweep records a Salary column, and after a few dozen roles that is a small comp dataset
with two properties nothing you can look up has: it is specific to the roles you actually want,
and you know where every number came from.

```bash
python -B working/scripts/floorprice/collect.py            # after every sweep
python -B working/scripts/floorprice/band.py --role "Dir"  # floor, midpoint, and the receipts
```

`--role` is a plain substring match, so try the abbreviation the postings use. The shipped
example says `Dir, Economic Development`, and `--role director` finds nothing.

**It refuses below four posted ranges, and that refusal is the feature.** Early in a search it
will refuse most of the time, which is the honest state of a search that has just started. A
figure you invented and then repeated in a salary conversation is worse than saying you will
come back to them on it — you can recover from the second and not from the first.

Estimates never count. A sweep row reading `Not listed (~$95–110k est.)` is your own guess,
stored with `posted: false` and excluded from every band. Keep that wording when you write
sweeps; the marker is what keeps your guess from becoming your evidence.

### When an offer arrives

```bash
cp working/scripts/floorprice/offer.example.json acme.offer.json   # *.offer.json is gitignored
python -B working/scripts/floorprice/offer.py acme.offer.json      # what it is actually worth
python -B working/scripts/floorprice/brief.py --role "Dir" --offer acme.offer.json
```

`offer.py` prices the pension, the leave above statutory, the employer premium and the PD budget,
and reports a guaranteed annual figure apart from an at-target one. Leave a field out rather than
guessing it — a missing term is reported `UNPRICED`, which is the state that sends you back to
ask, whereas a guess quietly becomes part of a total you then quote out loud. Equity is never
priced.

Expect base salary and total value to disagree about which of two offers is better. That is the
ordinary case: a public-sector offer $12k behind on base can be $13k ahead once the pension and
the leave are counted. `brief.py` is the page you read before the call — the number, the two
postings to cite if pushed, and the prepared answers to "what are your expectations" and "what
do you make now".

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

**Stale transaction snapshots.** `template_port.py` takes the snapshot path as an argument, so pass the file from the `start-editing-transaction` you *just* ran. Porting against an older snapshot means porting against stale element IDs — the clean-map check will fail, which is the point. The older `utils/` inspection scripts still use a hardcoded `SNAP` variable; update it before running one of those by hand.

**Committing without committing.** The Canva transaction is not saved until you call `commit-editing-transaction`. If the session ends or errors, all edits are lost. Always commit immediately after applying ops.

**Pair assignment confusion.** Keep the roster table in the sprint doc updated — one row per role with its pair number. If two roles accidentally get the same pair, one gets overwritten.

**Chat-only sweep docs.** If Claude only reports the sweep in chat and doesn't write a doc, the results are lost when the session ends. The sweep doc (`working/active/job_sweep_<YYYY-MM-DD>_<slug>.md`) must be written to disk before anything is presented in chat. This is a standing rule in `CLAUDE.md` and the skills.

---

## Directory Reference

```
jobcube/
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
│   ├── outreach/               # one folder per org — GITIGNORED, names real people
│   └── scripts/
│       ├── PORTING_RECIPE.md   # step-by-step Canva porting guide
│       ├── REVIEW_AGENTS.md    # reviewer persona reference + your review log
│       ├── review-agent-library.json  # same personas, machine-readable + reuse thresholds
│       ├── validate_job_sweep.py      # gates every sweep doc
│       ├── validate_canva_ops.py      # gates every batch of Canva ops
│       ├── template/           # template_port.py + manifest.json (the port primitive)
│       ├── utils/              # render, verify sign-off, measure gap, audits
│       ├── viz/                # visualization generators + sweep-coverage data
│       ├── outreach/           # log scaffolder + paced LinkedIn wrapper
│       ├── floorprice/         # salary band, offer pricing, negotiation brief
│       ├── builders/           # historical examples — do NOT clone for new work
│       └── generated/          # output JSON from the port primitive
├── cv/                         # LaTeX CV fallback (legacy), placeholder-tokenized
├── cover_letters/              # LaTeX cover letter fallback (legacy) + bundled fonts
├── tools/                      # lint, security guards, upstream drift, serve.py
├── assets/                     # logo, leg icons, triad emblem, vendored three.js
├── AGENTS.md                   # entry point for Codex; points back at CLAUDE.md
├── DOCTRINE.md                 # the vocabulary, and which tier each capability sits in
├── requirements.txt            # plotly · pymupdf · pyyaml — everything else stdlib
├── Dockerfile                  # runs the tooling and serves the viz
├── docker-compose.yml          # `up` to serve, `run --rm checks` for the gates
├── .agents/vendor/             # vendored linkedin-cli submodule + setup script
├── .claude/commands/           # /setup · /add-portal
└── .claude/skills/             # AI skill definitions
    ├── pipeline/SKILL.md       # full pipeline skill
    ├── pipeline/boards.md      # confirmed queryable job boards
    ├── pipeline/sources.json   # which job APIs are worth calling, with trust levels
    ├── job-scraper/SKILL.md    # discovery on its own
    ├── deep-sweep/SKILL.md     # the `deep sweep` command
    ├── linkedin-outreach/SKILL.md   # pre-application outreach
    └── floorprice/SKILL.md     # what to ask for, and what an offer is worth
```
