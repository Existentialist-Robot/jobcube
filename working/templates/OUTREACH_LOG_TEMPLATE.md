# Outreach Log — [Org] — [Role]

- **Date opened:** YYYY-MM-DD
- **Org:** [Org] ([City, Region])
- **Role:** [Role Title] ([division/team])
- **Posting:** [link] — verified live YYYY-MM-DD
- **Application status:** not yet submitted (outreach runs BEFORE submission)
- **Decision chain source:** [URL you found the names on] — verified YYYY-MM-DD
- **Skill reference:** `.claude/skills/linkedin-outreach/SKILL.md`

Outreach precedes the application, but never blocks it. If connections haven't landed in 3–5 days, submit anyway.

## Stage 1 — decision chain

Priority: 1 = probable hiring manager · 2 = their boss / division head · 3 = adjacent lead or likely panel.
Leave **Handle** blank until Stage 2 verifies it against a real profile.

| # | Name | Title | Why in chain | Priority | Handle | Connected | Messaged |
|---|---|---|---|---|---|---|---|
| 1 | | | Probable direct supervisor for this role | 1 | | | |
| 2 | | | Heads the division the role sits in | 2 | | | |
| 3 | | | Adjacent lead, likely panel | 3 | | | |

## Stage 2 — resolve and verify handles

Search each target, then **verify before recording** — headline and current org must both match. Same-name profiles are common and a wrong connection is unrecoverable.

```
search "<Name> <Org>" --json
profile <handle> --json
```

## Stage 3 — connect

Priority order, and **respect the caps**: ≤5 per org per day, ≤10 per day total. Batches go through the paced wrapper (30–60s gaps).

**Hard stop:** if you hit `connection_limit` or `checkpoint_challenge`, stop for the day. Do not retry — retrying is what escalates a soft limit into a restricted account.

| # | Sent | Accepted | Notes |
|---|---|---|---|
| 1 | | | |

## Stage 4 — message

One message per accepted connection, **≤300 characters**, only after they accept. Specific to the role and to them; no template smell.

| # | Date | Message | Reply |
|---|---|---|---|
| 1 | | | |

## Stage 5 — submit

- [ ] Outreach sent, or 3–5 days elapsed
- [ ] Posting re-confirmed open
- [ ] Application submitted YYYY-MM-DD
- [ ] Tracker and applied-roles log updated
