# AI Job Search — Canva Edition

*Polished applications at volume, without opening a design tool.*

A job application framework built on [Claude Code](https://claude.com/claude-code). You keep one Canva file with a résumé/cover-letter pair per application; Claude searches job boards, screens roles against your real hiring odds, drafts length-matched copy, edits the Canva design over MCP, exports the PDFs, and files them.

> Derived from [MadsLorentzen/ai-job-search](https://github.com/MadsLorentzen/ai-job-search) (MIT). The LaTeX pipeline and profile-skill structure come from there; the Canva porting engine, sweep tooling, and 3D pipeline viz are additions. Not affiliated with or endorsed by Anthropic or Canva.

## What this is

Most résumé automation stops at "here's some LaTeX." The expensive part of a real job search isn't drafting — it's the loop after it: reformatting, checking nothing overflowed, exporting, filing, remembering which version went where. This repo automates that loop.

```
/pipeline
  |
  v
Search boards ──> Screen for hiring odds ──> JD-verify finalists
  |                    (not skills match)          |
  v                                                v
Sweep doc written to disk              You confirm which are still open
  |                                                |
  v                                                v
Draft length-matched packets ──> Review agents ──> You greenlight
  |                                                |
  v                                                v
Port to Canva over MCP ──> Render-verify the PNG ──> Export PDFs ──> File + track
```

The design constraint that makes it work: Canva text boxes are **absolutely positioned**, so the only way to break a layout is to overflow a box. Every draft is measured against that box's proven capacity before it's written. Nothing gets reformatted by hand.

## Prerequisites

- **[Claude Code](https://claude.com/claude-code)** — the CLI, desktop app, or IDE extension
- **Canva account** with the Canva MCP connector enabled
- **Python 3.11+** — helper scripts (`pip install plotly pymupdf`)
- **Optional: LaTeX** (`lualatex` + `xelatex`) — only if you use the `cv/` fallback instead of Canva
- **Optional: [Adzuna](https://developer.adzuna.com) / [Jooble](https://jooble.org/api/about) API keys** — free tiers, structured listings with salary data

## Quick start

### 1. Create your repo

Click **Use this template** on GitHub, then clone it. Or:

```bash
gh repo create my-job-search --template Existentialist-Robot/ai-job-search-template --private --clone
cd my-job-search
git submodule update --init --recursive   # optional: linkedin-cli for outreach
```

### 2. Drop in your career documents

```
documents/cv/            your master CV (PDF or .tex)
documents/linkedin/      LinkedIn profile export (Profile → More → Save to PDF)
documents/diplomas/      degrees and transcripts
documents/references/    reference letters
```

Anything you put here becomes source material for your profile. See [`documents/README.md`](documents/README.md). Skip it if you'd rather fill the profile in by hand.

### 3. Fill in your profile

[`CLAUDE.md`](CLAUDE.md) is what Claude reads before doing anything. Replace every `[YOUR_...]` placeholder — identity, experience, skills, behavioral profile, target sectors, deal-breakers, salary floor.

This is the single biggest lever on output quality. "Python, project management" produces generic applications. "Built ML pipelines for churn prediction in scikit-learn; ran a 12-person cross-functional program to ship it" produces tailored ones.

### 4. Set up the Canva design

Build one résumé page + one cover-letter page you're happy with, then duplicate the pair as many times as you want applications in flight. Pair *k* = page (2k−1) résumé + page (2k) cover.

Put the design ID and shortlink in `CLAUDE.md`. Full walkthrough — including which text boxes the porting engine expects — is in [`GETTING_STARTED.md`](GETTING_STARTED.md#step-2--set-up-the-canva-design).

### 5. Configure keys (optional)

```bash
cp .env.example .env
```

Nothing is required to start — web search works without keys. Add Adzuna/Jooble for structured results with salary data.

### 6. Run your first sweep

```
/pipeline
```

Claude searches the boards in [`.claude/skills/pipeline/boards.md`](.claude/skills/pipeline/boards.md), drops roles with no realistic path to hire, reads each finalist's actual job description before rating it, writes a sweep doc to `working/active/`, and *then* reports.

## Commands

| Command | What it does |
|---|---|
| **`/pipeline`** | The full loop: search → screen → draft → port → export |
| **`/deep-sweep`** | Dual-thread deep search across your configured search spaces |
| **`/apply <url>`** | Single role: evaluate fit, draft, review, output |
| **`/setup`** | Profile onboarding interview |

## File structure

```
.
├── CLAUDE.md                       # your profile + workflow rules (read first, every session)
├── README.md                       # this file
├── GETTING_STARTED.md              # the deep walkthrough
├── HANDOFF.md                      # sprint state: what's in flight, what's pending
├── job_search_tracker.csv          # canonical application index
├── .env.example
│
├── documents/                      # ← your career source material (input)
│   ├── cv/  linkedin/  diplomas/  references/
│   ├── postings/                   # paste JDs Claude can't fetch
│   └── applications/               # past application records
│
├── working/
│   ├── active/                     # live work only: current sweep + current interview doc
│   ├── templates/                  # ← fill-in-the-blank docs (sweep, packet, outreach log)
│   ├── exports/                    # ← finals archive: every submitted app, by month
│   │   └── YYYY-MM (Mon 'YY)/YY-MM-DD - Company - Role/
│   ├── archive/                    # superseded sweeps, sprints, packets
│   └── scripts/
│       ├── PORTING_RECIPE.md       # step-by-step Canva porting guide
│       ├── REVIEW_AGENTS.md        # reviewer personas + review log
│       ├── utils/                  # parse, read, audit, render-verify
│       ├── builders/               # per-role port scripts
│       ├── viz/                    # 3D pipeline visualizer
│       └── generated/              # ops JSON output
│
├── cv/                             # LaTeX CV fallback (moderncv)
├── cover_letters/                  # LaTeX cover fallback (cover.cls + fonts)
│
└── .claude/skills/
    ├── pipeline/                   # the full loop + board registry
    ├── deep-sweep/                 # deep search
    ├── job-scraper/                # search execution
    └── linkedin-outreach/          # pre-application outreach
```

## How the pipeline works

**Screening is about hiring odds, not keyword overlap.** A role passes only if there's a realistic path to an offer. Skills match is necessary and nowhere near sufficient — specialist-gated roles, near-certain internal competitions, and level mismatches get dropped before you ever see them.

**Every finalist's rating comes from its real job description.** Aggregator titles mislead constantly. The sweep fetches and reads each posting before assigning a fit rating, and bakes the hard gates — domain, level, salary, closed/filled — into the score. Rows that can't be verified are marked as such rather than guessed at.

**Copy is measured before it's written.** Each box in your Canva template has a proven character capacity. Drafts are measured against it: overflow breaks the layout, and under-fill reads as thin. Cover letters target a near-full page.

**Pixels decide, not character counts.** After every port, the edited page is exported, rendered to PNG, and visually checked for overflow and under-fill before anything is reported as done. Character counts are a drafting heuristic; they get wrapping wrong often enough to matter.

**Open status is confirmed by you before any porting.** Workday, ADP, and recruiter portals are JS-gated — aggregators show closed postings as live. Claude posts a link checklist; you verify; only confirmed-open roles get ported.

## Customization

| What | Where |
|---|---|
| Your profile | `CLAUDE.md` |
| Job boards to search | `.claude/skills/pipeline/boards.md` |
| Reviewer personas | `working/scripts/REVIEW_AGENTS.md` |
| Box capacity targets | `CLAUDE.md` → calibrated targets table |
| Banned words and phrases | `CLAUDE.md` → Never-Use list |
| Viz axes and search spaces | `working/scripts/viz/build_job_viz.py` |

### Calibrating your template

The capacity numbers shipped in `CLAUDE.md` are estimates from a specific layout. Yours will differ. After your first Canva transaction, run `working/scripts/utils/parse_transaction.py` to get real box dimensions, do two ports, and write your confirmed numbers into the table. That one-time calibration is what buys you zero-reformatting ports afterward.

### Not using Canva?

The LaTeX fallback in `cv/` and `cover_letters/` still works — `/apply` will draft into it. You lose the porting automation and keep everything else.

## Tips

**Profile depth beats prompt engineering.** Describe what you actually did, with numbers. Include what energized you and what drained you — it shapes which roles get surfaced, not just how they're written up.

**Searches are small and in the foreground.** Four to six calls, then a written doc. Large background research agents silently hit token limits and return nothing. Need more coverage? Run another small sweep.

**Write to disk before reporting.** A sweep that only exists in chat is gone when the session ends.

**Log outcomes.** The applied and rejected role logs are what stop the next sweep from re-surfacing roles you've already burned.

## Credits

- Forked from [MadsLorentzen/ai-job-search](https://github.com/MadsLorentzen/ai-job-search) — LaTeX templates, profile skill structure, drafter-reviewer `/apply` workflow
- Job search CLI skills originally by [Mikkel Krogholm](https://github.com/mikkelkrogsholm/skills)
- Built with [Claude Code](https://claude.com/claude-code)

## License

MIT — see [LICENSE](LICENSE).
