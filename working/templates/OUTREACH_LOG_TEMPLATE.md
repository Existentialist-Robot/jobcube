# Outreach Log — [Org] — [Role Title]

> **How to use:** copy this file to
> `working/outreach/<YYYY-MM-DD> - <Org> - <Role>/outreach_log.md`.
> Outreach runs **before** you submit the application. Don't block on it: if connections
> haven't landed in 3–5 days, submit anyway.
>
> All live LinkedIn commands are run by **you**, not the AI. The AI scaffolds this log,
> preps the exact commands, and records results.

- **Date opened:** [YYYY-MM-DD]
- **Org:** [Org] ([City, Prov])
- **Role:** [Role Title] ([division/team])
- **Posting:** [Careers page](url) → [direct apply link](url) — verified live [YYYY-MM-DD]
- **Application status:** not yet submitted (outreach runs BEFORE submission)
- **Decision chain source:** [url] — verified [YYYY-MM-DD]
- **Skill reference:** `.claude/skills/linkedin-outreach/SKILL.md`

## Targets (Stage 1 — decision chain, verified)

Priority: 1 = probable hiring manager · 2 = their boss / division head · 3 = adjacent lead / panel.
The Handle column is filled in Stage 2 **only** after `profile <handle>` confirms name + title + org.

| # | Name | Title | Why in chain | Priority | Handle | Status | Connected | Messaged |
|---|------|-------|--------------|----------|--------|--------|-----------|----------|
| 1 | [Name] | [Title] | [Probable direct supervisor / hiring manager] | 1 |  |  |  |  |
| 2 | [Name] | [Title] | [Heads the division the role sits in] | 2 |  |  |  |  |
| 3 | [Name] | [Title] | [Adjacent lead, likely interview panel] | 3 |  |  |  |  |

## Command checklist (you run these)

Set `$CLI` once per terminal:

```powershell
$CLI = ".agents\vendor\linkedin-cli\.venv\Scripts\linkedin-cli.exe"
```

Session owner (Terminal 1 — blocks, leave it running):

```powershell
& $CLI session open --session work
```

Login (Terminal 2, once):

```powershell
& $CLI --session work login
```

### Stage 2 — resolve + verify handles (one target at a time)

```powershell
& $CLI --session work search "[Name] [Org]" --json
```

Then verify EACH candidate handle before recording it in the table above
(headline + current org must match):

```powershell
& $CLI --session work profile <handle> --json
```

### Stage 3 — connect (priority order; ≤5/org/day, ≤10/day total)

Check status first (skip anyone already Connected/Pending), then connect:

```powershell
& $CLI --session work status <handle> --json
& $CLI --session work connect <handle> --json
```

Or batch via the paced wrapper (30–60s gaps, hard-stops on limit/checkpoint):

```powershell
.\working\scripts\outreach\run_outreach.ps1 -Handles <h1>,<h2>,<h3> -Action status
.\working\scripts\outreach\run_outreach.ps1 -Handles <h1>,<h2>,<h3> -Action connect
```

### Stage 4 — daily-ish status check, then ONE message per accepted connection

```powershell
.\working\scripts\outreach\run_outreach.ps1 -Handles <h1>,<h2>,<h3> -Action status
& $CLI --session work message <handle> --text "<M1 or M2 below>"
```

Submit the application after messages land — or after 3–5 days regardless.

## Drafted messages (Stage 4 — send only once Connected; one per target, no follow-ups)

> One short message, **≤300 characters**. Lead with the specific role, then your single
> strongest relevant proof point. No follow-ups.

**M1 — [Name] (Priority 1, probable hiring manager) — [n] chars:**

> [Message text]

**M2 — Priority 2–3 targets — [n] chars:**

> [Message text, with {first} for the first name]

## Action log (Stage 5 — one row per CLI action, append as you go)

| Timestamp | Action | Handle | Result | Error type |
|-----------|--------|--------|--------|------------|
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |

## Status-check checklist

- [ ] Live JD link confirmed open and pasted above
- [ ] All handles resolved and verified via `profile`
- [ ] Connect requests sent in priority order (1 → 2 → 3)
- [ ] `status` re-checked daily-ish
- [ ] One message sent per Connected target (M1/M2, adapted per person)
- [ ] Application submitted (after messages, or after 3–5 days regardless)
- [ ] This folder cross-referenced from the application packet folder

## Safety rails

- **STOP for the day** on `connection_limit` or `checkpoint_challenge` — no retries; clear
  checkpoints by hand in the bound browser.
- `profile_inaccessible` / `skip_profile` — log it, skip the handle, continue.
- Never connect to an unverified handle; never message before Connected; one message max per target.
