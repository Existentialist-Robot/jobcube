# social-alts/

Candidate compositions for the social card. **None of these is the live asset** —
that is [`../social-preview.svg`](../social-preview.svg), which currently matches
`A-aligned`.

Regenerate with `python -B assets/build_social_alts.py`, then render the PNGs with a
browser. Delete this folder once a direction is settled; it exists so the choice gets
made by looking rather than by describing.

| | Composition | Where it wins | Where it loses |
|---|---|---|---|
| **A** | `aligned` — text left, triad right, both ink-centred | Balanced, name and diagram both legible at timeline width | Quiet space left of the diagram; the safest option rather than the striking one |
| **B** | `hero` — triad large and centred, name as a caption | The glyph detail actually resolves; most striking | Demotes the name on an asset whose job is recognition. Wordmark and tagline crowd each other and the bottom edge |
| **C** | `stacked` — one centred column | No axis competition; nothing to misalign | Diagram shrinks to where the leg detail stops resolving; voids open left and right |
| **D** | `mirrored` — triad left, text right | Puts the mark first for a left-to-right reader; as balanced as A | Right-aligned type is harder to scan, and the tagline's ragged left edge is loose |
| **E** | `banner` — legs abreast instead of radial | Uses the full width; the three legs read as a set | Loses the 120° radial that ties the diagram to the mark, which is the whole visual argument |
| **F** | `minimal` — the mark alone, no legs | Cleanest; scales to a favicon | Says nothing about the doctrine. A lone cube reads as generic tech |

## The one measurement that matters

The triad's ink centre is **not** its hub. The bomber label clears the hub by its leg
radius plus a gap, while the silo and patrol labels sit a shorter distance below, so the
ink centre sits about 38px above the hub at the shipping scale. Aligning hubs instead of
ink is what made the live card wrong twice — once at 55px out, then at 76px out after the
"fix". `triad_ink_dy()` in the generator computes it from the arm angles and the measured
radii, so no variant here carries an eyeballed offset.
