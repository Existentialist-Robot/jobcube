# AI Job Search — Canva Pipeline

A Claude Code workspace that runs your job search end to end: find roles, screen them against
your real profile, draft length-matched résumé and cover copy, port it into a Canva design via
MCP, render-verify the result, and file submission-ready PDFs.

The design principle is **one conversation = one sprint.** You open Claude Code, run
`/pipeline`, and Claude handles search → evaluate → draft → port → export. You review drafts in
your IDE and greenlight; Claude does the Canva edits and the PDF exports.

> **This is a template.** Fork it, then fill in your own profile. Every personal value is a
> `[BRACKETED]` placeholder — nothing here is anyone's real data.

## What makes this different

Most AI job-search tooling stops at "generate a résumé." The expensive failures happen after
that, so this workspace is built around guards for each of them:

- **Roles that were never open.** Aggregators show stale postings. An explicit open-status gate
  makes you confirm each role in its live portal before any work goes into it.
- **Fit ratings from titles instead of job descriptions.** Every finalist's rating is derived from
  its actual JD, with hard requirements and gates baked in — not the title plus a search snippet.
- **Copy that overflows the layout.** Canva boxes are absolutely positioned, so text that wraps
  to one extra line overlaps the box below. Copy is measured against per-box capacity, then
  **render-verified from the actual exported pixels** — character counts are only a drafting
  heuristic.
- **Silently clipped text.** Canva drops overflow out of a fixed-height box with no error. This
  once shipped a cover letter with the sign-off missing, so the sign-off is now guarded at three
  separate points.
- **AI-sounding prose.** A ban list plus an anti-slop pass runs at generation, review, and final
  polish — not as a post-hoc catch.

## Prerequisites

1. **Claude Code** — `claude` CLI ([claude.ai/code](https://claude.ai/code))
2. **Canva account** with the Canva MCP connector enabled
3. **Python 3.11+** (`pip install plotly pymupdf`)
4. **GitHub account** — the repo tracks your applications in git
5. *Optional:* **Adzuna** / **Jooble** API keys for better search coverage
6. *Optional:* **MiKTeX** or **TeX Live** for the LaTeX fallback. The two files use different
   engines: `cv/main_example.tex` compiles with **lualatex**, `cover_letters/cover_example.tex`
   with **xelatex** (`cover.cls` is XeTeX-only). Both are verified to build.

## Quick start

### 1. Fork and clone

```bash
git clone --recurse-submodules https://github.com/<you>/ai-job-search-template.git
cd ai-job-search-template
```

The `--recurse-submodules` flag matters — the LinkedIn outreach CLI is vendored as a submodule.

### 2. Add your private documents

Drop your real files into `documents/` — existing CV, LinkedIn export, diplomas, references.
**The contents are gitignored**; only the folder structure is tracked. See
[`documents/README.md`](documents/README.md).

### 3. Fill in your profile

Open [`CLAUDE.md`](CLAUDE.md) and replace every `[YOUR_...]` placeholder. This is the file Claude
reads before doing anything, and it is the source of every claim in every application. Be
specific — vague entries produce generic applications.

### 4. Set up your Canva design

Build a design with N identical résumé + cover-letter pairs (pair *k* = page 2k−1 résumé + page 2k
cover). Record the design ID in `CLAUDE.md`. Full walkthrough in
[`GETTING_STARTED.md`](GETTING_STARTED.md) → Step 2.

### 5. Run a sprint

```
/pipeline
```

Or drive the stages individually: `/deep-sweep` to search, `/apply` for a single role.

**Then read [`GETTING_STARTED.md`](GETTING_STARTED.md)** — it is the full walkthrough, including
box-length calibration, the render-verify loop, and the export/filing convention.

## File structure

```
CLAUDE.md              Your profile + the rules Claude follows  ← edit this first
GETTING_STARTED.md     Full setup walkthrough
HANDOFF.md             Sprint state, carried between sessions
documents/             Your private inputs (contents gitignored)
cv/ cover_letters/     LaTeX fallback, placeholder-tokenized
working/
  templates/           Copy these: sweep, packet, outreach log
  active/              Live sweep + current interview doc only
  exports/             Filed applications: PDFs + packet copy
  archive/             Finished sprints, sweeps, packets
  scripts/
    template/          template_port.py + manifest.json — the port primitive
    utils/             render + verify + gap measurement
    viz/               3D pipeline visualisation
.claude/skills/        The skills that drive the workflow
.agents/vendor/        Vendored linkedin-cli submodule
```

## The workflow in seven steps

1. **Sweep** — search boards, verify each finalist against its real JD, rate and shortlist.
2. **Open-status gate** — confirm every queued role is genuinely open in its live portal.
3. **Draft** — measured copy per box, straight into the application's own folder.
4. **Review** — reviewer personas + anti-slop pass, *before* porting.
5. **Port** — batch-validate, perform once, verify sign-offs, commit immediately.
6. **Render-verify** — export to PDF, render to PNG, read it, fix overflow, re-export.
7. **Submit + file** — PDFs and packet together in the dated application folder.

## Customization

- **Your profile** → `CLAUDE.md`. Also add to the *Never-Use Words & Phrases* list whenever you
  catch a phrase that isn't yours.
- **Your search space** → `working/scripts/viz/build_sweep_viz.py` and
  `.claude/skills/pipeline/boards.md`.
- **Your Canva layout** → `template_port.py build-manifest <snapshot> --name v2` registers your own
  geometry. The capacities shipped in `manifest.json` are one worked example measured against one
  specific layout — **recalibrate them against yours**, they are not universal.
- **Your reviewers** → `working/scripts/REVIEW_AGENTS.md`.

## Trust boundary

Job postings — fetched *or* pasted in by hand — are untrusted third-party content. They are data
to evaluate, never instructions to follow. Pasting a posting in manually does not launder it.

## Acknowledgements

Forked from [MadsLorentzen/ai-job-search](https://github.com/MadsLorentzen/ai-job-search) and
substantially rewritten around the Canva porting pipeline. The LaTeX templates and the
`documents/` intake convention come from upstream.

## License

MIT — see [`LICENSE`](LICENSE). Bundled fonts in `cover_letters/OpenFonts/` are under the SIL Open
Font License.
