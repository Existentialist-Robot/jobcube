# Canva Porting Toolkit (reusable — don't re-derive)

The résumé/cover template is identical across every dup pair. **Element IDs regenerate per duplicated page** (the one thing that changes), so a quick parse is always needed — but the layout, mapping, and recipe below never change.

## First-run setup (once)
1. Fill in `template/port_config.json` — sign-off name, cover character band, ban list. **`port` refuses to run while the name is the `[YOUR_NAME]` placeholder.**
2. `python template/template_port.py build-manifest <snapshot.json> --name v1` — register YOUR layout. The shipped `manifest.json` and the capacities in `template_port.py` are a **worked example measured against one specific design**, not universal values.

## Fast path (any number of pairs, one batch)
1. `start-editing-transaction` → note the persisted snapshot file path + transaction_id.
2. Write a `copy.json` — slots + lead-role bullets + cover body per pair (schema in the `template_port.py` docstring; drafting tables in [`../templates/PACKET_TEMPLATE.md`](../templates/PACKET_TEMPLATE.md)).
3. `python template/template_port.py port <snapshot.json> copy.json` → measures every slot against its manifest cap, flags `UNDER-FILL`, scans the ban list, prints `SLOP-WARN` per cover, checks each cover ends with the sign-off, prints **`CLEAN-MAP CHECK: PASS`**, and writes the ops JSON. **Never proceed on FAIL.**
4. `python validate_canva_ops.py <snapshot.json> <ops.json>` must pass.
5. `perform-editing-operations` with **all** ops in one call, immediately after `start-editing-transaction` (transactions expire — a stale one silently drops the edits).
6. `python utils/verify_port_signoff.py <perform_response.json> <cover_eid...>` — **before** committing. On FAIL, **cancel** the transaction; never commit a clipped cover.
7. `commit-editing-transaction` — within seconds. **Changes are lost if not committed.**
8. Render-verify (see below) — this is not optional.

`template_port.py` handles the `format_text {font_style: normal}` on work boxes (clears the baked italic first bullet) and the width-only `resize_element` on each cover box before its text is written, so the frame grows before Canva can clip the sign-off.

## Stable template layout (logical box → how to find it)
- **headline** (×2, resume+cover): your positioning title (top of page).
- **tagline**: short phrase below headline.
- **profile**: the wide summary paragraph.
- **divider**: the standalone section-break phrase.
- **work boxes** (Role1/Role2/Role3/Role4): match by title prefix (your exact title text). Each = bold title-run + date/org-run + **italic first-bullet run** + normal-rest run.
- **skill labels/descriptions**: 4 skill areas with label + description paragraph.
- **cover**: the big box on the even page.

## Rules (why it ports clean)
- Boxes are absolutely positioned → **overflow is the only failure**. Keep every box **≤ current length**; under is safe.
- **Single-run boxes** → whole-box `replace_text`.
- **Work boxes** → `find_and_replace_text` on the **bullets-block only** (everything after the first `\n\n`), preserving the bold title; then **`format_text {font_style: normal}`** to clear the baked italic first bullet (verify the title stays its own run).
- Never set italic. Length-match by character count; expect a 1-line trim pass.

## Render-verify loop (MANDATORY — always run after commit)
Character count is an imprecise proxy: proportional fonts render wide words wider regardless of char count, so a box that held 184 chars of one wording overflows at 184 of another. **Pixels decide.**

1. `export-design` the edited page(s) to PDF (`size:letter`, `export_quality:pro`, `pages:[N]`) and download them.
2. `python utils/render_canva_page.py <page.pdf>` — writes full-page, skill-column, and left-column PNGs.
3. **Read the PNGs.** Check every edited box for **overflow** (text crowding the next label) and **under-fill** (short last line / stranded empty line). Confirm the cover's sign-off is visibly present.
4. Covers: `python utils/measure_cover_gap.py <cover.pdf>` — target signature gap **7–12pt** (sweet spot ~10).
5. Iterate trims and fills autonomously until the render is clean, then re-export.

Skipping this is expensive — see [`GETTING_STARTED.md`](../../GETTING_STARTED.md) for what it costs.

**Per-bullet rule:** matching the *box total* to ceiling is not sufficient — a single over-long bullet wraps to an extra line and overflows even when the box total is under. Match each bullet to its proven-good equivalent length (or shorter), not just the box total.

**Wide-word text** (long words like "government", "post-secondary", "institutional") renders wider than char count suggests — aim 10–15 chars UNDER the cap when the copy is wide-word-heavy.

**Under-fill is a flag too.** Skill descriptions should reach ~95–100% of proven capacity; `template_port.py` prints `UNDER-FILL` below 90%.

## Files

### The port primitive (`template/`) — this is the one you use
| File | Purpose |
|------|---------|
| `template_port.py` | **The only current op generator.** `build-manifest` registers a layout variant; `port` measures copy against caps, scans the ban list and slop tells, guards the sign-off, and emits validated ops. |
| `manifest.json` | Slot map keyed by box position + per-slot capacities, per template variant. Pages auto-match by position fingerprint. **Worked example — recalibrate.** |
| `port_config.json` | Sign-off name, cover character band, ban list. Shared with `utils/verify_port_signoff.py`. |

### Validation + verification
| Script | Purpose |
|--------|---------|
| `validate_canva_ops.py` | Independent check that every op targets a real element in the snapshot. Run between `port` and `perform`. |
| `utils/verify_port_signoff.py` | **Pre-commit gate.** Confirms each cover's sign-off survived into the stored text. FAIL → cancel the transaction. |
| `utils/render_canva_page.py` | Renders an exported page to full / skill-column / left-column PNGs for the visual overflow check. |
| `utils/measure_cover_gap.py` | Measures cover text-bottom to signature-top; target 7–12pt. |

### Utilities (`utils/`) — occasional, for manual inspection
| Script | Purpose |
|--------|---------|
| `parse_transaction.py` | Parse a truncated Canva transaction JSON into element IDs, positions, dimensions, run counts, and text. `template_port.py` does this internally; use it standalone when inspecting a layout by hand. |
| `read_work_boxes.py` | Read current text from multi-run work boxes by element_id lookup. |
| `read_bullets_full.py` | Get the full untruncated bullet block for a work box. |
| `read_bullets_unicode.py` | Get exact Unicode codepoints for bullet text — critical when bullets contain em-dashes (—) that must match exactly in `find_text`. |
| `height_audit.py` | Compare box heights across pairs. Superseded by the render loop for overflow detection; still handy for a quick numeric cross-check. |

### Builders (`builders/`) — HISTORICAL, do not clone
Kept only as evidence of how the layout was originally derived. **The builder-cloning workflow is retired** — `template_port.py` replaces it. Do not start a new packet from these.

### Generated (`generated/`)
`template_port.py` writes ops JSON here. These are ephemeral — commit them if you want a record, but they're always rebuildable from the snapshot plus `copy.json`.

### Viz (`viz/`)
- `build_job_viz.py` — generates `working/active/job_search_viz.html`: 3D job search pipeline visualization

## Export & filing convention

Export each application as **separate résumé + cover PDFs** (portals usually want them apart), **PRO** quality.

- **Export call:** `export-design` → `{type:"pdf", size:"letter", export_quality:"pro", pages:[N]}`, one page per call (résumé = first page of the pair, cover = second). The `pages` param exports a single page and skips hidden/stale pages. Each call returns a download URL; fetch with PowerShell `Invoke-WebRequest` (not Bash — spaces/parentheses in paths cause failures).
- **Re-export whenever Canva changes** — URLs reflect a point-in-time render.

**Folder structure** (under `working/exports/`):
```
working/exports/
└── <YYYY-MM (Mon 'YY)>/                      ← monthly only. e.g. "2025-06 (Jun '25)"
    └── <YY-MM-DD - Company - Role>/          ← per application; date-FIRST so it auto-sorts
          ├── [YOUR_NAME]_Resume.pdf
          ├── [YOUR_NAME]_Cover_Letter.pdf
          └── copy/
              ├── packet_<slug>_<date>.md      ← draft packet (written here at draft time)
              └── review_agents_<date>.md      ← reviewer agent findings
```
- Month folder: `YYYY-MM (Mon 'YY)`. App folder: `YY-MM-DD - <Company> - <Role>`. Date = export/submit date.
- **`working/exports/` is the finals archive — the source of truth for every submitted application.**
- **File working docs WITH the application.** A doc that maps 1:1 to one application (draft, interview prep) goes in that app's folder. Only **multi-app sprint notes and intermediate pair-reviews** stay in `working/archive/`.
- **`working/active/` holds live work only** — the current interview doc, plus (optionally) one current sweep doc. Everything else is filed.
