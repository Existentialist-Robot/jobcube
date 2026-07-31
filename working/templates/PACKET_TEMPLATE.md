# Application Packet — [Org] — [Role Title]

> **How to use:** copy this file to
> `working/exports/<YYYY-MM (Mon 'YY)>/<YY-MM-DD - Company - Role>/copy/packet_<slug>_<YYYY-MM-DD>.md`
> **at draft time** — packets live with their application from the first draft, not in `working/active/`.
> Fill every `[bracket]`. Delete these quote blocks as you go.

## Roster

> One row per role in this batch. The **Pair** cell links to the Canva page; the **Role** cell links to the live posting. Never hardcode page numbers without checking the live `page_count` first.

| Pair | Role | Org | Location | Level vs. bar | Salary | Apply via | Porting status |
|------|------|-----|----------|---------------|--------|-----------|----------------|
| [Pages N-M](https://www.canva.com/design/[DESIGN_ID]) | [Role Title](https://posting-url) | [Org] | [City, Prov (hybrid/remote)] | [clears / door-opener] | [Not listed (~$X–Y est.)] | [Portal name] | [Queued / Ported / Exported / Submitted] |

## Packet status

| Field | Value |
|-------|-------|
| Role | [Role Title](https://posting-url) |
| Organization | [Org] |
| Fit | [N] stars |
| Copy | [Drafted / Reviewed / Validated] [YYYY-MM-DD] |
| Canva pages | [Pages N-M](https://www.canva.com/design/[DESIGN_ID]) |
| PDF | [Exported / Not yet exported] |
| Application form | [Questions and drafted response](application_form_questions_[YYYY-MM-DD].md) |
| Submission | [Not submitted / Submitted YYYY-MM-DD] |

## Resume copy slots

> Character counts are a **drafting heuristic only — pixels decide.** Measure against
> `working/scripts/template/manifest.json` caps, then run the render-verify loop.
> Fill each box to ~95–100% of its proven capacity: under-fill reads sparse, overflow overlaps the box below.

| Slot | Final copy | Characters |
|------|-----------|------------|
| `headline` | [text] | [n] |
| `section_header` | [text] | [n] |
| `divider` | [text] | [n] |
| `tagline` | [text] | [n] |
| `profile` | [text] | [n] |
| `skill_label_1` | [text] | [n] |
| `skill_desc_1` | [text] | [n] |
| `skill_label_2` | [text] | [n] |
| `skill_desc_2` | [text] | [n] |
| `skill_label_3` | [text] | [n] |
| `skill_desc_3` | [text] | [n] |
| `skill_label_4` | [text] | [n] |
| `skill_desc_4` | [text] | [n] |

## Lead-role experience bullets

> Multi-run box: the title/org line stays **byte-identical** and each changed bullet is edited with a
> per-line `find_and_replace_text`. Never whole-replace a multi-run box — it flattens the bold title.
> Match **each bullet** to its proven-length equivalent, not just the box total: one over-long bullet
> wraps to an extra line and overflows even when the box total is under cap.

| # | Final bullet | Characters |
|---|-------------|------------|
| 1 | [bullet] | [n] |
| 2 | [bullet] | [n] |
| 3 | [bullet] | [n] |
| 4 | [bullet] | [n] |
| 5 | [bullet] | [n] |

## Cover letter body

> **Must fill a full page** — target the proven character band for your cover box (roughly 3,050–3,400
> in the reference layout). Substance, never filler: concrete examples, a how-I'd-approach-the-role
> paragraph, a second proof point.
>
> **Must end with the sign-off** exactly as configured in `template_port.py` — `Sincerely,` then your
> name on the next line. Canva silently clips trailing text out of a too-small box, so the sign-off is
> guarded at draft, op-gen, and pre-commit.

```
[Cover letter body — ending with:]

Sincerely,
[YOUR_NAME]
```

Characters: [n]

## Pre-port checklist

- [ ] Live posting confirmed **open** (open-status gate — verified in the real portal, not an aggregator)
- [ ] Fit rating derived from the **actual JD**, not the title + snippet
- [ ] Every claim traceable to `CLAUDE.md`; nothing fabricated
- [ ] Banned words/phrases scan clean (see `CLAUDE.md` → Never-Use Words & Phrases)
- [ ] Anti-AI-slop pass run on the cover
- [ ] Reviewer personas run on the draft (`working/scripts/REVIEW_AGENTS.md`)
- [ ] Every box ≤ its manifest cap, and ≥ ~95% of capacity
- [ ] Cover body ends with the sign-off
- [ ] `template_port.py port` prints `CLEAN-MAP CHECK: PASS`
- [ ] `validate_canva_ops.py` passes

## Post-port checklist

- [ ] Sign-offs verified from the perform response **before** commit (`verify_port_signoff.py`)
- [ ] Committed within seconds of perform (stale transactions silently drop edits)
- [ ] Render-verified every edited page (`render_canva_page.py`) — no overflow, no under-fill
- [ ] Cover-to-signature gap 7–12pt (`measure_cover_gap.py`)
- [ ] Exported as separate résumé + cover PDFs (`size:letter`, `export_quality:pro`)
- [ ] Filed to `working/exports/<YYYY-MM (Mon 'YY)>/<YY-MM-DD - Company - Role>/`
