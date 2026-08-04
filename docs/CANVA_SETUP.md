# Connecting Canva

*Last checked: 2026-08-03. Connector UIs move; if a menu name below is wrong, the
**verification probe** at the bottom is still the definitive test and does not depend
on any menu.*

This is the repo's hardest prerequisite, and until now it was one clause in
`GETTING_STARTED.md` — "with the MCP connector enabled in your agent's settings" —
with no steps behind it. Everything in Tier A is downstream of this page.

**You do not need Canva to use this repo.** If any of this stalls, read
[Tier B](../README.md#which-path-am-i-on) and come back later. Search, screening,
JD-verification, drafting, the review personas and the anti-slop pass all work
without it. Only the automatic layout does not.

---

## 1. What you are connecting, and why

The agent needs to *edit your Canva design directly* — read the live page count,
replace text in specific boxes, and export PDFs. It does that through a Canva
**connector** (an MCP server), not by driving a browser. No connector means no
automatic layout.

A connector is a permission grant: you are letting the agent read and modify
designs in your Canva account. It cannot see anything else.

---

## 2. Enable it

**Claude Code (terminal, desktop, or IDE):**

1. Run `/mcp` in a session. It lists the connectors available to you and their
   connection state.
2. Find Canva in the list and connect it. You will be sent to a Canva
   authorization page in your browser; approve it, then return to the terminal.
3. Re-run `/mcp` and confirm Canva now reads as connected.

**Claude on the web or desktop app:** Settings → Connectors → find Canva → Connect,
then approve the Canva authorization page.

**Codex:** Canva is not available as a Codex connector as of the date above. Use
Tier B or Tier C under Codex, or run the porting step in Claude Code. `AGENTS.md`
says which parts are portable.

If Canva does not appear in your list at all, it is not enabled for your plan or
your organization. That is an account question, not a repo question — and it is a
legitimate reason to stay on Tier B indefinitely.

---

## 3. Verify it — this is the part that matters

Menus change. This test does not. In a fresh session, paste:

> Resolve this Canva shortlink and tell me the page count: `<your shortlink>`

**A working connector answers with a number** — "20 pages, which is 10
résumé/cover pairs." Anything else means it is not working:

| What you get back | What it means |
|---|---|
| A page count | Working. Continue to `GETTING_STARTED.md` Step 2. |
| "I don't have a tool for that" | Connector not enabled. Redo section 2. |
| An authorization or permission error | Connected but not authorized. Reconnect and approve the Canva page. |
| "I can't access that design" | Connected to a different Canva account than the one that owns the design. |

If the probe answers with a number, Tier A is ready. For a broader check that
nothing personal is tracked and the skill files are intact, run:

```bash
python -B tools/security_guards.py
python -B tools/lint_skills.py
```

*A `/doctor` command that audits the whole setup in one pass — including this probe
— is planned and does not exist yet. This page pointed at it before it was written;
that was the same phantom-artifact mistake this repo exists to avoid, caught by
review.*

---

## 4. What the design itself has to look like

**No reference design ships with this repo.** You build your own, and
`GETTING_STARTED.md` Step 2 describes the structural contract it has to satisfy —
résumé/cover pairs on consecutive pages, absolutely-positioned text boxes, N
identical duplicates as clean starting points.

The capacities in `working/scripts/template/manifest.json` were measured against
one specific design and **will be wrong for yours.** That is expected.
`template_port.py build-manifest` re-measures against yours, and the render-verify
loop corrects the rest on your first real port.

---

## 5. If it stops working later

Connectors expire and get revoked. The symptom is a porting run that fails at the
first `get-design` call. Re-run the probe in section 3 before debugging anything
else in the pipeline — an expired connector looks exactly like a broken script from
the inside.
