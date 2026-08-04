#!/usr/bin/env python3
"""Generate every brand asset from one copy of the geometry.

    python -B assets/build_assets.py

The mark and the three leg glyphs appear in the standalone icons, in triad.svg
and in social-preview.svg. SVG cannot reference a shape across files in a way
GitHub will render, so the geometry has to be duplicated in the output — which
is exactly how the silo drifted out of sync once already. It is defined once
here instead, and the duplication happens at build time.

After running this, re-render the PNG and LOOK at it:

    msedge --headless --disable-gpu --screenshot=assets/social-preview.png \\
           --window-size=1280,640 file:///<abs>/assets/social-preview.svg

Stdlib only.
"""

from __future__ import annotations

import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent

VIOLET, GREEN, DIM, PAPER, GROUND = "#b98cff", "#3fca7d", "#8d85a8", "#e9e6f5", "#0b0910"

# ── the mark ────────────────────────────────────────────────────────────────
TREFOIL = f"""\
  <polygon fill="{VIOLET}" points="32,8.8 51.8,19.5 32,30.3 12.2,19.5"/>
  <polygon fill="{VIOLET}" points="10.6,22.1 30.4,32.9 30.4,54.4 10.6,43.6"/>
  <polygon fill="{VIOLET}" points="53.4,22.1 33.6,32.9 33.6,54.4 53.4,43.6"/>
  <circle fill="{GREEN}" cx="32" cy="33.5" r="3.6"/>"""

# ── silo ────────────────────────────────────────────────────────────────────
# Blast doors belong at GROUND level, thrown open either side of the opening —
# not partway up the missile, where they read as handles. The hardened tube is
# what makes it a silo rather than a rocket on a launch pad.
#
# The doors hinge at their OUTER edge and lift, so each one is low where it meets
# the ground slab and high where it meets the opening. They sloped the other way
# for three commits, which read as two ramps running down into the hole rather
# than as a closure thrown open.
#
# Second pass: they were also too small and too shallow. A 19-degree incline on a
# thin bar reads as a shrug; a blast door thrown open is a heavy slab standing well
# clear of the opening. Now 42 degrees, ~22 units long and 7 thick — each one built
# as a thick bar from an outer hinge at (4,44) to an inner tip at (20,29.5), which
# is why the corner numbers look arbitrary. The inner corner clears the collar's
# top-left at (21,34) by design; check that if the collar ever moves.
SILO = f"""\
  <rect fill="{DIM}" opacity=".28" x="2" y="46" width="60" height="13" rx="2"/>
  <rect fill="{DIM}" opacity=".55" x="21" y="34" width="22" height="16" rx="2"/>
  <path fill="{DIM}" opacity=".85" d="M17.6,26.8 L22.4,32.2 L6.4,46.7 L1.6,41.3 Z"/>
  <path fill="{DIM}" opacity=".85" d="M46.4,26.8 L41.6,32.2 L57.6,46.7 L62.4,41.3 Z"/>
  <rect fill="{VIOLET}" x="26" y="8" width="12" height="34" rx="2.5"/>
  <path fill="{GREEN}" d="M26,16 L26,10.5 A2.5,2.5 0 0 1 28.5,8 L35.5,8 A2.5,2.5 0 0 1 38,10.5 L38,16 Z"/>"""

# ── patrol ──────────────────────────────────────────────────────────────────
# Three passes to get here. A wide flat ellipse with a thin stalk read as a
# frying pan; adding a tinted body of water behind it then read as an aquarium,
# because a faint filled rectangle is a box before it is anything else. So: the
# waterline is a single rule and nothing else, the hull is submerged beneath it
# with only the mast breaking through, and the stern plane is small enough to
# read as a fin rather than a blunt nose.
PATROL = f"""\
  <rect fill="{DIM}" opacity=".4" x="4" y="21" width="56" height="2" rx="1"/>
  <rect fill="{VIOLET}" x="6" y="41" width="9" height="4.5" rx="2.25"/>
  <rect fill="{VIOLET}" x="10" y="36" width="44" height="15" rx="7.5"/>
  <rect fill="{VIOLET}" x="26" y="25" width="12" height="12" rx="2"/>
  <rect fill="{VIOLET}" x="30.5" y="15" width="3" height="11" rx="1.5"/>
  <path fill="{GREEN}" d="M28.5,17 L28.5,12.5 A2,2 0 0 1 30.5,10.5 L33.5,10.5 A2,2 0 0 1 35.5,12.5 L35.5,17 Z"/>"""

# ── bomber ──────────────────────────────────────────────────────────────────
BOMBER = f"""\
  <path fill="{DIM}" opacity=".22" d="M4,50 C18,42 46,42 60,50 L60,56 L4,56 Z"/>
  <path fill="{VIOLET}" d="M32,9 L58,44 L38,39.5 L32,48 L26,39.5 L6,44 Z"/>
  <rect fill="{GREEN}" x="29" y="14" width="6" height="7" rx="1.5"/>"""

LEGS = {
    "silo": (SILO, "Silo — cold application"),
    "patrol": (PATROL, "Patrol — LinkedIn outreach"),
    "bomber": (BOMBER, "Bomber — referral"),
}

# ── measured geometry ───────────────────────────────────────────────────────
# Alpha-weighted centroid and enclosing ink radius of each glyph, in the 64-unit
# viewBox. Measured by rendering each at 512px and taking the centroid of the
# rendered alpha, so partial opacity counts the way the eye counts it.
#
# These are why the spokes looked wrong. Every glyph's ink sits BELOW its box
# centre -- patrol by 6.3 units, silo by 4.3 -- because the hull and the ground
# slab are the heavy parts. Centring the boxes therefore pointed each spoke
# above the thing it was supposed to connect to. Re-measure if a glyph changes.
METRICS = {
    "trefoil": {"cx": 31.94, "cy": 31.98, "r": 23.16},
    "silo":    {"cx": 31.94, "cy": 36.16, "r": 35.52},
    "patrol":  {"cx": 31.49, "cy": 38.34, "r": 31.33},
    "bomber":  {"cx": 31.94, "cy": 33.72, "r": 33.92},
}

# Layout, in the triad's own 360x310 coordinate space.
TW, TH = 360, 300
CX, CY = 180.0, 176.0
HUB_SCALE = 1.6      # the mark, deliberately larger than the legs
LEG_SCALE = 0.75
SPOKE = 120.0        # centroid-to-centroid distance
GAP = 14.0           # clear space at both ends of every spoke

# angle, glyph, label, which side the label sits on.
# Ordered by altitude: the aircraft flies, so it takes the top arm; the silo
# sits on the ground and the patrol boat runs beneath the surface, so both take the
# lower two. The arrangement is arbitrary geometrically and obvious visually,
# which is the good kind of arbitrary.
ARMS = [
    (-90.0, "bomber", "BOMBER", "above"),
    (30.0, "patrol", "PATROL", "below"),
    (150.0, "silo", "SILO", "below"),
]


def _place(name: str, px: float, py: float, scale: float) -> str:
    """Translate a glyph so its measured centroid lands exactly on (px, py)."""
    m = METRICS[name]
    return (
        f'<use href="#{name}" transform="translate('
        f'{px - m["cx"] * scale:.2f},{py - m["cy"] * scale:.2f}) scale({scale})"/>'
    )


def triad_group(label_size: float = 10.5, label_fill: str = DIM) -> str:
    """Spokes and glyphs, aligned centroid-to-centroid with uniform gaps.

    Labels on the same side share one baseline. Offsetting each from its own ink
    radius looked correct in the code and wrong on the page: silo's radius is
    35.5 and patrol's is 31.3, so the two lower labels landed 4px apart and read
    as a misalignment rather than a pair.
    """
    import math

    hub_r = METRICS["trefoil"]["r"] * HUB_SCALE
    spokes, glyphs = [], []
    placed: list[tuple[float, float, float, str, str]] = []

    for deg, name, text, side in ARMS:
        rad = math.radians(deg)
        ux, uy = math.cos(rad), math.sin(rad)
        leg_r = METRICS[name]["r"] * LEG_SCALE

        # The spoke runs between the two ink edges, inset by GAP at each end,
        # so the visible gap is identical on every arm even though the glyphs
        # are different sizes.
        r0, r1 = hub_r + GAP, SPOKE - leg_r - GAP
        spokes.append(
            f'<path d="M{CX + ux * r0:.2f},{CY + uy * r0:.2f} '
            f'L{CX + ux * r1:.2f},{CY + uy * r1:.2f}"/>'
        )

        px, py = CX + ux * SPOKE, CY + uy * SPOKE
        glyphs.append("  " + _place(name, px, py, LEG_SCALE))
        placed.append((px, py, leg_r, text, side))

    # One baseline per side: the outermost ink edge on that side, plus the gap.
    below = [py + leg_r for px, py, leg_r, _, side in placed if side == "below"]
    above = [py - leg_r for px, py, leg_r, _, side in placed if side == "above"]
    below_y = max(below) + GAP * 1.15 + label_size * 0.55 if below else 0.0
    above_y = min(above) - GAP * 0.8 if above else 0.0

    labels = [
        f'<text x="{px:.2f}" y="{(below_y if side == "below" else above_y):.2f}">{text}</text>'
        for px, py, leg_r, text, side in placed
    ]

    nl = "\n    "
    return f"""  <g stroke="{DIM}" stroke-width="1.6" opacity=".5" stroke-linecap="round" fill="none">
    {nl.join(spokes)}
  </g>
{chr(10).join(glyphs)}
  {_place("trefoil", CX, CY, HUB_SCALE)}
  <g font-family="ui-monospace, SFMono-Regular, Consolas, monospace" font-size="{label_size}"
     letter-spacing="1.5" fill="{label_fill}" text-anchor="middle">
    {nl.join(labels)}
  </g>"""


def icon(frag: str, label: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64"\n'
        f'     role="img" aria-label="{label}">\n  <title>{label}</title>\n{frag}\n</svg>\n'
    )


def _defs() -> str:
    out = [f'    <g id="trefoil">\n{TREFOIL}\n    </g>']
    out += [f'    <g id="{name}">\n{frag}\n    </g>' for name, (frag, _) in LEGS.items()]
    return "\n".join(out)


def triad() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {TW} {TH}" width="{TW}" height="{TH}"
     role="img" aria-label="The three delivery legs on the mark's blade axes">
  <title>The jobcube triad — silo, patrol, bomber</title>
  <defs>
{_defs()}
  </defs>

{triad_group()}
</svg>
"""


# ── the social card's shared centre line ────────────────────────────────────
# 1280x640 is GitHub's recommended size, so the ink of both halves is centred on
# y=320. Everything here is derived, not nudged, because this card has been
# re-cut several times and each eyeballed offset was a fresh guess.
SOCIAL_AXIS = 320.0
SOCIAL_TRIAD_SCALE = 1.38          # up from 1.2: at 1.2 the leg detail did not resolve
SOCIAL_TRIAD_HUB_X = 1000.0
SOCIAL_LABEL_SIZE = 19.0           # rendered size, before the scale is divided out
SOCIAL_WORDMARK_SIZE = 112
# Cap top to tagline descender, for a 112px mono wordmark with the tagline 102px
# below it: the block's ink centre sits ~14.7px below the wordmark baseline.
SOCIAL_WORDMARK_BASELINE = SOCIAL_AXIS - 14.7


def _social_triad_ink_dy() -> float:
    """How far the triad's ink centre sits above its hub, in final pixels.

    The bomber label clears the hub by its leg radius plus a gap; the silo and
    patrol labels sit a shorter distance below. The asymmetry is why matching
    hubs does not match ink.
    """
    import math

    internal_label = SOCIAL_LABEL_SIZE / SOCIAL_TRIAD_SCALE
    tops, bottoms = [], []
    for deg, name, _text, side in ARMS:
        py = CY + math.sin(math.radians(deg)) * SPOKE
        leg_r = METRICS[name]["r"] * LEG_SCALE
        if side == "above":
            tops.append(py - leg_r - GAP * 0.8 - internal_label * 0.8)
        else:
            bottoms.append(py + leg_r)
    bottom = max(bottoms) + GAP * 1.15 + internal_label * 0.75
    ink_centre = (min(tops) + bottom) / 2
    return (CY - ink_centre) * SOCIAL_TRIAD_SCALE


SOCIAL_TRIAD_INK_DY = _social_triad_ink_dy()
SOCIAL_TRIAD_HUB_Y = SOCIAL_AXIS + SOCIAL_TRIAD_INK_DY


def social() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 640" width="1280" height="640"
     role="img" aria-label="jobcube — second-strike capability for job applications">
  <title>jobcube</title>
  <defs>
    <pattern id="grid" width="64" height="64" patternUnits="userSpaceOnUse">
      <path d="M64,0 L0,0 0,64" fill="none" stroke="{VIOLET}" stroke-opacity="0.055" stroke-width="1"/>
    </pattern>
{_defs()}
  </defs>

  <rect width="1280" height="640" fill="{GROUND}"/>
  <rect width="1280" height="640" fill="url(#grid)"/>

  <!-- Weight comes from a matched stroke rather than font-weight, so the mark
       renders identically wherever Consolas Bold is absent. -->
  <!-- Both halves centre their INK on y=320, the canvas centre.

       Aligning the triad's hub to a shared axis is the obvious move and it is
       wrong: the bomber label sits far above the hub while the silo and patrol
       labels sit close below it, so the diagram's ink centre is {SOCIAL_TRIAD_INK_DY:.0f}px above
       its hub. Matching hubs to text left the two halves {76}px apart, which is
       worse than the {55}px offset it was meant to fix. Both numbers below are
       derived from the glyph metrics rather than nudged by eye. -->
  <text x="96" y="{SOCIAL_WORDMARK_BASELINE:.0f}" font-family="Consolas, 'Cascadia Mono', 'JetBrains Mono', monospace"
        font-size="{SOCIAL_WORDMARK_SIZE}" letter-spacing="-2" paint-order="stroke fill" stroke-linejoin="round">
    <tspan fill="{PAPER}" stroke="{PAPER}" stroke-width="4.1">job</tspan><tspan fill="{VIOLET}" stroke="{VIOLET}" stroke-width="4.1">cube</tspan>
  </text>

  <rect x="99" y="{SOCIAL_WORDMARK_BASELINE + 38:.0f}" width="112" height="5" rx="2.5" fill="{VIOLET}"/>

  <text x="99" y="{SOCIAL_WORDMARK_BASELINE + 102:.0f}" font-family="'Segoe UI',system-ui,Helvetica,Arial,sans-serif"
        font-size="34" fill="#a49cbe">Second-strike capability for job applications.</text>

  <!-- Same triad geometry as triad.svg, scaled, and the same labels. It used to
       substitute COLD APPLY / OUTREACH / REFERRAL on the theory that a shared
       link has no table to explain the leg names. Wrong call: the leg names ARE
       the identity, the card is where someone meets them first, and a card that
       teaches different words from the docs teaches the wrong ones.

       Label size is 19, not the 13 this used to carry. A social card is read at
       roughly 500px wide in a timeline, so 13px on a 1280px canvas arrives at
       about five pixels and the labels were decoration rather than information.
       The fill is lifted off DIM for the same reason: at that scale the dim
       violet-grey disappeared into the ground.

       No double hyphen anywhere in this string. XML forbids it inside a comment,
       and emitting one here silently dropped the whole triad group from the
       rendered card while the SVG still looked fine as source. -->
  <!-- label_size is divided by the scale so the rendered size stays at 19.

       The card labels the three legs by their REGISTER, not their nickname. It has
       tried both nicknames (SILO / PATROL / BOMBER) and component names (COLD APPLY
       / OUTREACH / REFERRAL); neither works cold. The nicknames need DOCTRINE.md to
       mean anything, and the component names read as a feature list. Scripted /
       paced / crewed is still the doctrine's own vocabulary — it is the italic
       register word on each leg in DOCTRINE.md and in the network diagram — but it
       describes what the route *is like* rather than naming a weapon, so it carries
       meaning to someone who has never opened the repo. -->
  <g transform="translate({SOCIAL_TRIAD_HUB_X - CX * SOCIAL_TRIAD_SCALE:.1f},{SOCIAL_TRIAD_HUB_Y - CY * SOCIAL_TRIAD_SCALE:.1f}) scale({SOCIAL_TRIAD_SCALE})">
{triad_group(label_size=SOCIAL_LABEL_SIZE / SOCIAL_TRIAD_SCALE, label_fill="#c3bcd8").replace("SILO", "SCRIPTED").replace("PATROL", "PACED").replace("BOMBER", "CREWED")}
  </g>
</svg>
"""


# ── the network: what nests under each leg ──────────────────────────────────
# The triad diagram says there are three routes. It does not say what runs them,
# which is the question anyone reading DOCTRINE.md asks next. This is that
# answer as a picture: three tiers, the middle one holding the legs, and every
# leg's actual machinery hanging off it by filename.
#
# Left-to-right rather than radial. A radial layout with fourteen leaf labels
# collides with itself no matter how the angles are chosen; the tree reads.
#
# Leaves stack UNDER their leg's description rather than beside it. Side by side
# was the first attempt and it overlapped: a description runs about 340px and the
# longest leaf line about 500px, which does not fit in 1160 next to a glyph
# column. Stacking removes the constraint instead of negotiating with it.
# Width is set by the longest leaf line (verify_port_signoff.py plus its gloss,
# about 460px from the leaf column) rather than by a round number. At 1240 the
# right 400px was empty.
NW = 920
BAND_W = 840

TIER1 = (
    "TIER 1 · TARGETING",
    "Decides what to pursue. Once per role, upstream of all three legs.",
    ["deep-sweep", "build_sweep_viz.py", "open-status gate", "JD-verify", "validate_job_sweep.py"],
)
TIER3 = (
    "TIER 3 · COMMAND AND CONTROL",
    "Governs all of it. Not a leg, and not per-role: every gate fails closed.",
    ["security_guards.py", "lint_skills.py", "check_upstream_updates.py", "the greenlight"],
)

# name, register, y centre, description lines, leaves
NET_LEGS = [
    (
        "silo", "SILO", "Scripted", 312,
        ["Fixed infrastructure, automated up to the firing",
         "order. A human still sends."],
        [("pipeline", "discover → draft → port → export → file"),
         ("template_port.py", "the port primitive, measured against manifest.json"),
         ("validate_canva_ops.py", "no live call without a passing op check"),
         ("verify_port_signoff.py", "cancel the transaction rather than ship a clipped cover"),
         ("render_canva_page.py", "pixels decide; character counts are a drafting heuristic"),
         ("working/exports/", "PDFs filed beside the copy that made them")],
    ),
    (
        "patrol", "PATROL", "Paced", 566,
        ["Patrols under emission discipline. Contact with a",
         "checkpoint means silent for the day, no exceptions."],
        [("linkedin-outreach", "scope the chain, verify the handle, connect, one message"),
         ("scope_targets.py", "the decision chain, before any contact"),
         ("run_outreach.ps1", "5 per org per day, 30–60s gaps, hard-stop on a checkpoint"),
         ("working/outreach/", "gitignored — the logs name real people")],
    ),
    (
        "bomber", "BOMBER", "Crewed", 742,
        ["The leg valued because there is judgment on board. Empty here,",
         "because the judgment is asking a person for a favour."],
        [],
    ),
]

# Two lines, because one ran past the container at this width.
BOMBER_NOTE = [
    "nothing, on purpose. The row stays on the diagram because",
    "dropping it would imply two routes are all there are.",
]


def _band(x: float, y: float, w: float, h: float, title: str, sub: str, items: list[str]) -> str:
    """A tier that wraps the triad rather than sitting inside it."""
    chips, cx_ = [], x + 28
    for item in items:
        width = len(item) * 7.4 + 22
        chips.append(
            f'<rect x="{cx_:.1f}" y="{y + h - 40:.1f}" width="{width:.1f}" height="25" rx="12.5"'
            f' fill="{VIOLET}" fill-opacity=".085" stroke="{VIOLET}" stroke-opacity=".22"/>'
            f'<text x="{cx_ + width / 2:.1f}" y="{y + h - 22.5:.1f}" text-anchor="middle"'
            f' font-family="ui-monospace, SFMono-Regular, Consolas, monospace" font-size="12.5"'
            f' fill="#a79fc0">{item}</text>'
        )
        cx_ += width + 10
    nl = "\n    "
    return f"""  <g>
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{VIOLET}" fill-opacity=".035"
          stroke="{DIM}" stroke-opacity=".28" stroke-dasharray="5 4"/>
    <text x="{x + 28}" y="{y + 30}" font-family="ui-monospace, SFMono-Regular, Consolas, monospace"
          font-size="13" letter-spacing="1.6" fill="{VIOLET}">{title}</text>
    <text x="{x + 28}" y="{y + 52}" font-family="'Segoe UI',system-ui,Helvetica,Arial,sans-serif"
          font-size="14.5" fill="#8d85a8">{sub}</text>
    {nl.join(chips)}
  </g>"""


def network() -> str:
    hub_x, hub_s = 108.0, 1.35
    leg_x, leg_s = 232.0, 0.62
    text_x = 300.0
    spine_x = 318.0
    leaf_x = 348.0
    leaf_step = 25.0
    block_gap = 30.0
    y = 300.0

    spokes, glyphs, blocks, leaves = [], [], [], []
    centres: list[tuple[str, float, float]] = []

    for name, label, register, _unused_cy, desc, items in NET_LEGS:
        head = 40.0 + len(desc) * 19.0
        rows = max(len(items), len(BOMBER_NOTE))
        height = head + rows * leaf_step

        # The glyph aligns with its leg's NAME, not the centre of the whole block.
        # Centred, it sat level with the leaves instead of the thing it labels, so
        # the spokes appeared to point at a list rather than at a leg.
        cy = y + 14
        glyphs.append("  " + _place(name, leg_x, cy, leg_s))
        centres.append((name, cy, METRICS[name]["r"] * leg_s))

        blocks.append(
            f'    <text x="{text_x}" y="{y + 20:.1f}"'
            f' font-family="ui-monospace, SFMono-Regular, Consolas, monospace" font-size="19"'
            f' letter-spacing="2.2" fill="{PAPER}">{label}'
            f'<tspan font-size="13" letter-spacing="1.4" fill="{VIOLET}"'
            f' font-style="italic">   {register}</tspan></text>'
        )
        for i, line in enumerate(desc):
            blocks.append(
                f'    <text x="{text_x}" y="{y + 42 + i * 19:.1f}"'
                f' font-family="\'Segoe UI\',system-ui,Helvetica,Arial,sans-serif"'
                f' font-size="13.5" fill="#8d85a8">{line}</text>'
            )

        first = y + head + 2
        if not items:
            for i, line in enumerate(BOMBER_NOTE):
                leaves.append(
                    f'    <text x="{leaf_x}" y="{first + 6 + i * 19:.1f}"'
                    f' font-family="\'Segoe UI\',system-ui,Helvetica,Arial,sans-serif" font-size="13.5"'
                    f' font-style="italic" fill="#6f6885">{line}</text>'
                )
        else:
            last = first + (len(items) - 1) * leaf_step
            leaves.append(
                f'    <path d="M{spine_x:.1f},{y + head - 12:.1f} L{spine_x:.1f},{last:.1f}"'
                f' stroke="{VIOLET}" stroke-opacity=".38" stroke-width="1.4" fill="none"/>'
            )
            for i, (item, gloss) in enumerate(items):
                ly = first + i * leaf_step
                leaves.append(
                    f'    <path d="M{spine_x:.1f},{ly:.1f} L{leaf_x - 12:.1f},{ly:.1f}"'
                    f' stroke="{VIOLET}" stroke-opacity=".38" stroke-width="1.4" fill="none"/>'
                    f'<circle cx="{leaf_x - 10:.1f}" cy="{ly:.1f}" r="2.6" fill="{GREEN}"'
                    f' fill-opacity=".8"/>'
                    f'<text x="{leaf_x:.1f}" y="{ly + 4.5:.1f}"'
                    f' font-family="ui-monospace, SFMono-Regular, Consolas, monospace" font-size="13"'
                    f' fill="{PAPER}">{item}'
                    f'<tspan font-family="\'Segoe UI\',system-ui,Helvetica,Arial,sans-serif"'
                    f' font-size="12.5" fill="#7d7595">   {gloss}</tspan></text>'
                )

        y += height + block_gap

    # The hub sits on the mean of the three leg centres, so no spoke has to bend
    # further than the others to reach it.
    hub_y = sum(cy for _, cy, _ in centres) / len(centres)
    hr = METRICS["trefoil"]["r"] * hub_s + 11
    for name, cy, lr in centres:
        x0, x1 = hub_x + hr, leg_x - lr - 11
        mid = (x0 + x1) / 2
        spokes.append(
            f'<path d="M{x0:.1f},{hub_y:.1f} C{mid:.1f},{hub_y:.1f} {mid:.1f},{cy:.1f}'
            f' {x1:.1f},{cy:.1f}"/>'
        )

    tier2_h = y - block_gap - 212 + 28
    height = 212 + tier2_h + 28 + 104 + 40
    nl = "\n    "
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {NW} {height:.0f}" width="{NW}" height="{height:.0f}"
     role="img" aria-label="The three tiers, the triad's three legs, and the machinery under each">
  <title>jobcube — what nests under each leg of the triad</title>
  <defs>
    <pattern id="ngrid" width="64" height="64" patternUnits="userSpaceOnUse">
      <path d="M64,0 L0,0 0,64" fill="none" stroke="{VIOLET}" stroke-opacity="0.05" stroke-width="1"/>
    </pattern>
{_defs()}
  </defs>

  <rect width="{NW}" height="{height:.0f}" fill="{GROUND}"/>
  <rect width="{NW}" height="{height:.0f}" fill="url(#ngrid)"/>

  <text x="40" y="52" font-family="Consolas, 'Cascadia Mono', 'JetBrains Mono', monospace"
        font-size="30" letter-spacing="-0.5" paint-order="stroke fill" stroke-linejoin="round">
    <tspan fill="{PAPER}" stroke="{PAPER}" stroke-width="1.1">job</tspan><tspan fill="{VIOLET}" stroke="{VIOLET}" stroke-width="1.1">cube</tspan><tspan
      font-size="17" letter-spacing="0" fill="#8d85a8" font-family="'Segoe UI',system-ui,sans-serif">   doctrine, and what runs it</tspan>
  </text>

{_band(40, 84, BAND_W, 104, *TIER1)}

  <g>
    <rect x="40" y="212" width="{BAND_W}" height="{tier2_h:.0f}" rx="14" fill="{VIOLET}" fill-opacity=".05"
          stroke="{VIOLET}" stroke-opacity=".3"/>
    <text x="68" y="248" font-family="ui-monospace, SFMono-Regular, Consolas, monospace"
          font-size="13" letter-spacing="1.6" fill="{VIOLET}">TIER 2 · THE TRIAD</text>
    <text x="68" y="272" font-family="'Segoe UI',system-ui,Helvetica,Arial,sans-serif"
          font-size="14.5" fill="#8d85a8">Three independent routes to a human, so that no single defence stops everything.</text>
  </g>

  <g stroke="{DIM}" stroke-width="1.6" stroke-opacity=".5" stroke-linecap="round" fill="none">
    {nl.join(spokes)}
  </g>
{chr(10).join(glyphs)}
  {_place("trefoil", hub_x, hub_y, hub_s)}

  <g>
{chr(10).join(blocks)}
  </g>

  <g>
{chr(10).join(leaves)}
  </g>

{_band(40, 212 + tier2_h + 28, BAND_W, 104, *TIER3)}
</svg>
"""


def _wellformed(path: Path) -> None:
    """Parse what we just wrote. A malformed SVG still looks fine as source.

    A `--` inside an XML comment is illegal and shipped once: the browser dropped
    everything after it, which silently removed the whole triad group from the
    social card. Parsing here turns that into a build failure.
    """
    import xml.etree.ElementTree as ET

    try:
        ET.parse(path)
    except ET.ParseError as exc:
        raise SystemExit(f"  {path.name} is not well-formed XML: {exc}") from exc


def main() -> int:
    written = []
    (OUT / "logo.svg").write_text(icon(TREFOIL, "jobcube"), encoding="utf-8")
    written.append("logo.svg")
    for name, (frag, label) in LEGS.items():
        (OUT / f"icon-{name}.svg").write_text(icon(frag, label), encoding="utf-8")
        written.append(f"icon-{name}.svg")
    (OUT / "triad.svg").write_text(triad(), encoding="utf-8")
    (OUT / "social-preview.svg").write_text(social(), encoding="utf-8")
    (OUT / "triad-network.svg").write_text(network(), encoding="utf-8")
    written += ["triad.svg", "social-preview.svg", "triad-network.svg"]

    for name in written:
        _wellformed(OUT / name)
        print(f"  wrote assets/{name}")
    print("\nNow re-render the PNG and look at it — geometry that reads at 420px")
    print("does not always read at 64px, and only a render tells you.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
