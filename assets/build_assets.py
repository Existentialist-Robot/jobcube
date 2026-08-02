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
SILO = f"""\
  <rect fill="{DIM}" opacity=".28" x="2" y="46" width="60" height="13" rx="2"/>
  <rect fill="{DIM}" opacity=".55" x="21" y="34" width="22" height="16" rx="2"/>
  <path fill="{DIM}" opacity=".85" d="M19,38 L4,32 L2,38 L18,44 Z"/>
  <path fill="{DIM}" opacity=".85" d="M45,38 L60,32 L62,38 L46,44 Z"/>
  <rect fill="{VIOLET}" x="26" y="8" width="12" height="34" rx="2.5"/>
  <path fill="{GREEN}" d="M26,16 L26,10.5 A2.5,2.5 0 0 1 28.5,8 L35.5,8 A2.5,2.5 0 0 1 38,10.5 L38,16 Z"/>"""

# ── boomer ──────────────────────────────────────────────────────────────────
# Three passes to get here. A wide flat ellipse with a thin stalk read as a
# frying pan; adding a tinted body of water behind it then read as an aquarium,
# because a faint filled rectangle is a box before it is anything else. So: the
# waterline is a single rule and nothing else, the hull is submerged beneath it
# with only the mast breaking through, and the stern plane is small enough to
# read as a fin rather than a blunt nose.
BOOMER = f"""\
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
    "silo": (SILO, "Silo — portal submission"),
    "boomer": (BOOMER, "Boomer — LinkedIn outreach"),
    "bomber": (BOMBER, "Bomber — warm intro"),
}


def icon(frag: str, label: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64"\n'
        f'     role="img" aria-label="{label}">\n  <title>{label}</title>\n{frag}\n</svg>\n'
    )


def triad() -> str:
    defs = "\n".join(
        f'    <g id="{name}">\n{frag}\n    </g>' for name, (frag, _) in LEGS.items()
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 460 300" width="460" height="300"
     role="img" aria-label="The three delivery legs on the mark's blade axes">
  <title>The jobcube triad — silo, boomer, bomber</title>
  <defs>
    <g id="trefoil">
{TREFOIL}
    </g>
{defs}
  </defs>

  <g stroke="{DIM}" stroke-width="1.6" opacity=".5" stroke-linecap="round" fill="none">
    <path d="M230,150 L230,74"/><path d="M230,150 L296,188"/><path d="M230,150 L164,188"/>
  </g>

  <use href="#trefoil" transform="translate(198,118)"/>
  <use href="#silo"    transform="translate(206,26) scale(0.75)"/>
  <use href="#boomer"  transform="translate(272,190) scale(0.75)"/>
  <use href="#bomber"  transform="translate(140,190) scale(0.75)"/>

  <g font-family="ui-monospace, SFMono-Regular, Consolas, monospace" font-size="10.5"
     letter-spacing="1.5" fill="{DIM}" text-anchor="middle">
    <text x="230" y="18">SILO</text>
    <text x="296" y="256">BOOMER</text>
    <text x="164" y="256">BOMBER</text>
  </g>
</svg>
"""


def social() -> str:
    defs = "\n".join(
        f'    <g id="{name}">\n{frag}\n    </g>' for name, (frag, _) in LEGS.items()
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 640" width="1280" height="640"
     role="img" aria-label="jobcube — second-strike capability for job applications">
  <title>jobcube</title>
  <defs>
    <pattern id="grid" width="64" height="64" patternUnits="userSpaceOnUse">
      <path d="M64,0 L0,0 0,64" fill="none" stroke="{VIOLET}" stroke-opacity="0.055" stroke-width="1"/>
    </pattern>
    <g id="trefoil">
{TREFOIL}
    </g>
{defs}
  </defs>

  <rect width="1280" height="640" fill="{GROUND}"/>
  <rect width="1280" height="640" fill="url(#grid)"/>

  <!-- Weight comes from a matched stroke rather than font-weight, so the mark
       renders identically wherever Consolas Bold is absent. -->
  <text x="96" y="322" font-family="Consolas, 'Cascadia Mono', 'JetBrains Mono', monospace"
        font-size="108" letter-spacing="-2" paint-order="stroke fill" stroke-linejoin="round">
    <tspan fill="{PAPER}" stroke="{PAPER}" stroke-width="4">job</tspan><tspan fill="{VIOLET}" stroke="{VIOLET}" stroke-width="4">cube</tspan>
  </text>

  <rect x="99" y="360" width="104" height="5" rx="2.5" fill="{VIOLET}"/>

  <text x="99" y="424" font-family="'Segoe UI',system-ui,Helvetica,Arial,sans-serif"
        font-size="34" fill="#a49cbe">Second-strike capability for job applications.</text>

  <g transform="translate(792,138)">
    <g stroke="{DIM}" stroke-width="2" opacity=".45" stroke-linecap="round" fill="none">
      <path d="M182,182 L182,88"/><path d="M182,182 L263,229"/><path d="M182,182 L101,229"/>
    </g>
    <use href="#trefoil" transform="translate(142,142) scale(1.25)"/>
    <use href="#silo"    transform="translate(150,26)"/>
    <use href="#boomer"  transform="translate(231,226)"/>
    <use href="#bomber"  transform="translate(69,226)"/>
    <g font-family="'Cascadia Mono',Consolas,monospace" font-size="14"
       letter-spacing="2.4" fill="{DIM}" text-anchor="middle">
      <text x="182" y="14">PORTAL</text>
      <text x="263" y="316">OUTREACH</text>
      <text x="101" y="316">WARM INTRO</text>
    </g>
  </g>
</svg>
"""


def main() -> int:
    written = []
    (OUT / "logo.svg").write_text(icon(TREFOIL, "jobcube"), encoding="utf-8")
    written.append("logo.svg")
    for name, (frag, label) in LEGS.items():
        (OUT / f"icon-{name}.svg").write_text(icon(frag, label), encoding="utf-8")
        written.append(f"icon-{name}.svg")
    (OUT / "triad.svg").write_text(triad(), encoding="utf-8")
    (OUT / "social-preview.svg").write_text(social(), encoding="utf-8")
    written += ["triad.svg", "social-preview.svg"]

    for name in written:
        print(f"  wrote assets/{name}")
    print("\nNow re-render the PNG and look at it — geometry that reads at 420px")
    print("does not always read at 64px, and only a render tells you.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
