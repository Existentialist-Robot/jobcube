---
name: linkedin-outreach
description: >
  Pre-application LinkedIn outreach: scope the decision chain at a target org (hiring manager,
  their boss, adjacent leads), resolve LinkedIn handles, send connection requests, and message
  once connected — all BEFORE the application is submitted.
  Triggers on: outreach, hiring manager, decision chain, connection request, LinkedIn scoping,
  "who would I report to", warm intro, referral, linkedin-cli.
allowed-tools: Read, Write, Edit, Glob, Grep, WebFetch, WebSearch, Bash, PowerShell
framework_version: 1.0.0
---

# LinkedIn Outreach (Pre-Application)

---

## When this stage runs

**After** a role is confirmed open (open-status gate passed) and its packet is drafted; **BEFORE** the application is submitted. A connection request from a "prospective applicant researching the team" lands far better than one from "applicant #482 in the ATS." Ideal sequence per role:

```
role confirmed open → packet drafted → SCOPE → RESOLVE → CONNECT → (accepted) MESSAGE → submit application
```

If connections haven't been accepted within ~3–5 days, submit anyway — outreach is a booster, never a gate.

## Tooling

The CLI is vendored at `.agents/vendor/linkedin-cli` (submodule; see its `llms.txt` for the full verb/JSON contract). Windows exe: `.agents/vendor/linkedin-cli/.venv/Scripts/linkedin-cli.exe` (built by `.agents/vendor/setup_linkedin_cli.ps1`).

**Session model:** one long-lived owner process, short-lived verb clients.
- Terminal 1 (yours, stays open): `linkedin-cli.exe session open --session work` (blocks — owns the browser)
- Terminal 2: `linkedin-cli.exe login` once, then any verb: `linkedin-cli.exe --session work <verb> <handle> --json`

**HARD RULE — Claude never runs live LinkedIn commands unattended.** All `search`/`profile`/`status`/`connect`/`message` calls are run by **you**, or by Claude only with you watching and having explicitly approved that specific batch. Claude's default job is Stages 1 and 5 (research + logging) and preparing exact commands for you to paste.

The caution is load-bearing: an automated-looking session gets the account restricted, and a restricted LinkedIn account costs more than any single application gains.

---

## Stage 1 — Scope the decision chain (no LinkedIn needed)

Pure web research — do this for every queued role, it costs nothing and needs no session.

1. Read the JD for reporting lines ("reports to X", team/division names).
2. WebFetch the org's team/leadership/about page; cross-check with WebSearch (`"<org>" "<team name>" director OR manager site:linkedin.com` is fine for *names*, but handles get verified in Stage 2).
3. Name, in order: **probable direct supervisor** (the role's hiring manager), **their boss**, **1–2 peers/adjacent leads** (likely interview panel), and **recruiter/TA** if visible.

Output a target table in the outreach log (scaffold it with `python working/scripts/outreach/scope_targets.py "<Org>" "<Role>"`):

| Name | Title | Why in chain | Priority | Handle | Status |
|------|-------|--------------|----------|--------|--------|
| … | … | probable direct supervisor | 1 | *(Stage 2)* | — |

Priority: **1** = probable hiring manager · **2** = their boss / division head · **3** = adjacent leads, panel, recruiter.

## Stage 2 — Resolve handles

Per target (you run, or you watch):

1. `linkedin-cli.exe --session work search "<name> <org>" --json` → candidate `public_identifier`s.
2. `linkedin-cli.exe --session work profile <handle> --json` → **verify headline + current position match the target's name, title, and org.**
3. Record the confirmed `public_identifier` in the log's Handle column.

**Never connect to an unverified handle.** Common-name collisions are the norm, not the exception — a `search` hit alone is not confirmation. If `profile` doesn't clearly match, mark the row `unresolved` and move on.

## Stage 3 — Connect

In priority order (1 → 2 → 3):

1. `status <handle>` first. **Skip** if `Connected` or `Pending` (never double-fire).
2. `connect <handle>` — note: the CLI sends requests **without a note**; the pitch happens in Stage 4 after acceptance.
3. Log every action (timestamp, handle, verb, result, error type) in the outreach log.

**Pacing caps (hard):** ≤ **5 connects per org per day**, ≤ **10 connects per day total**, 30–60 s randomized gaps between any calls (the `run_outreach.ps1` wrapper enforces the gap and the error-stop). Keep search volume modest — a handful of searches per session, not dozens. LinkedIn tolerates roughly 10–15 requests/day on a normal account; stay well under.

## Stage 4 — Message when accepted

- Check `status <handle>` roughly daily (batch it: `run_outreach.ps1 -Handles a,b,c -Action status`).
- Once `Connected`, send **ONE** short message (templates below) via `message <handle> --text "..."` — then **stop**. No follow-up sequences, no nudges. If they reply, you take the thread over manually.
- Message goes out **before** the application is submitted whenever possible ("I'm about to apply / my application is going in this week").

## Stage 5 — Log + tracker

Every org gets a folder: `working/outreach/<YYYY-MM-DD> - <Org> - <Role>/outreach_log.md`, copied from [`working/templates/OUTREACH_LOG_TEMPLATE.md`](../../../working/templates/OUTREACH_LOG_TEMPLATE.md), containing:
- the Stage 1 target table (with handles + status columns kept current),
- a timestamped action log — one row per CLI action: `timestamp | action | handle | result | error type (if any)`,
- the drafted messages used.

Scaffold with `python working/scripts/outreach/scope_targets.py "<Org>" "<Role>"`. Update the log after every live batch. Cross-reference the outreach folder from the role's application folder / packet roster when it exists.

---

## Message templates (≤300 chars, one only, sent after acceptance)

Write in **your own** first person — plain and direct, no sycophancy. Always name the specific role and one concrete hook. **Respect the CLAUDE.md never-use list.** Adapt, don't pad.

Replace the bracketed parts with your own strongest proof point — the one credential or result most relevant to *that* org. One concrete number beats three adjectives.

**A — probable hiring manager (Priority 1):**
> Hi {first} — thanks for connecting. I'm about to apply for the {role} role on your team. [One sentence: what you built or ran, with a number.] The overlap with what you're building looks strong. Happy to share more if useful.

**B — their boss / division head (Priority 2):**
> Hi {first} — thanks for connecting. I'm applying for {role} in {division}. [One sentence: your track record at the scale their division operates at.] {org}'s mandate is where I want to point that next.

**C — adjacent lead / peer / recruiter (Priority 3):**
> Hi {first} — I'm applying for the {role} opening at {org} and wanted to get a real picture of the team first. Your work on {one specific thing} stood out. [One clause: who you are.] Would value being connected as my application goes in.

**Do not** send the same message to two people at the same org — they compare notes. Vary the hook per target.

## Safety rails (non-negotiable)

- **Stop immediately** on `checkpoint_challenge` or `connection_limit` (stderr error types) — alert the user, do **not** retry that day. A checkpoint means it must be cleared by hand in the bound browser before anything else runs.
- Other errors (`profile_inaccessible`, `skip_profile`) — log, skip that handle, continue.
- Never mass-connect; never exceed the Stage 3 caps; never message before `status` says `Connected`; never send more than one outbound message per target.
- All live commands run by the user, or with the user watching. Claude prepares; the user fires.
- If in doubt about account health, do nothing and flag it.
