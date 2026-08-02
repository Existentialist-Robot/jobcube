# working/outreach/

One folder per org you run pre-application LinkedIn outreach against:

```
working/outreach/<YYYY-MM-DD> - <Org> - <Role>/outreach_log.md
```

Scaffold one with:

```powershell
python working/scripts/outreach/scope_targets.py "<Org>" "<Role>"
```

That copies [`../templates/OUTREACH_LOG_TEMPLATE.md`](../templates/OUTREACH_LOG_TEMPLATE.md)
and fills in the date/org/role header. The log format lives in that template —
edit it there, not here.

Process: [`.claude/skills/linkedin-outreach/SKILL.md`](../../.claude/skills/linkedin-outreach/SKILL.md).
Batches run through the paced wrapper
[`../scripts/outreach/run_outreach.ps1`](../scripts/outreach/run_outreach.ps1).

**These logs are gitignored, deliberately.** They name real people — hiring
managers, their bosses, likely panellists — gathered from public profiles for
your own job search. That is fine to hold locally and not fine to publish in a
repo you may fork, share, or make public. This README and the folder itself are
the only tracked things here. Don't add an exception for the logs.
