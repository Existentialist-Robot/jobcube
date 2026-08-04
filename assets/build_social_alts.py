#!/usr/bin/env python3
"""Render every social-card composition that has been considered, side by side.

    python -B assets/build_social_alts.py

Writes assets/social-alts/<name>.svg. One of them is what social-preview.svg
currently ships; the rest are candidates. Delete the folder once a direction is
settled — it exists so the choice is made by looking rather than by describing.

Geometry, glyphs and measured centroids all come from build_assets, so a change
to the mark propagates here and the comparison stays honest. Only layout differs
between variants.

Every variant centres what it can on real numbers rather than eyeballed offsets:
the triad's ink centre sits above its hub by an amount that depends on the arm
angles and the measured leg radii, so hub-alignment and ink-alignment are not the
same thing. That distinction is what made the shipped card wrong twice.

Stdlib only. Rendering to PNG needs a browser and is a separate step:
    python -B assets/build_social_alts.py --list      # print the file list
"""

from __future__ import annotations

import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_assets as ba  # noqa: E402

OUT = Path(__file__).resolve().parent / "social-alts"
W, H = 1280, 640
MONO = "Consolas, 'Cascadia Mono', 'JetBrains Mono', monospace"
SANS = "'Segoe UI',system-ui,Helvetica,Arial,sans-serif"
TAGLINE = "Second-strike capability for job applications."


def head(title: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}"
     role="img" aria-label="jobcube — {title}">
  <title>jobcube — {title}</title>
  <defs>
    <pattern id="grid" width="64" height="64" patternUnits="userSpaceOnUse">
      <path d="M64,0 L0,0 0,64" fill="none" stroke="{ba.VIOLET}" stroke-opacity="0.055" stroke-width="1"/>
    </pattern>
{ba._defs()}
  </defs>
  <rect width="{W}" height="{H}" fill="{ba.GROUND}"/>
  <rect width="{W}" height="{H}" fill="url(#grid)"/>"""


def wordmark(x: float, baseline: float, size: float, anchor: str = "start") -> str:
    sw = size / 27.3
    return f"""  <text x="{x:.0f}" y="{baseline:.0f}" font-family="{MONO}" text-anchor="{anchor}"
        font-size="{size:.0f}" letter-spacing="{-size / 56:.1f}" paint-order="stroke fill" stroke-linejoin="round">
    <tspan fill="{ba.PAPER}" stroke="{ba.PAPER}" stroke-width="{sw:.1f}">job</tspan><tspan fill="{ba.VIOLET}" stroke="{ba.VIOLET}" stroke-width="{sw:.1f}">cube</tspan>
  </text>"""


def rule(x: float, y: float, w: float) -> str:
    return f'  <rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="5" rx="2.5" fill="{ba.VIOLET}"/>'


def tagline(x: float, y: float, size: float, anchor: str = "start") -> str:
    return (f'  <text x="{x:.0f}" y="{y:.0f}" font-family="{SANS}" font-size="{size:.0f}"'
            f' text-anchor="{anchor}" fill="#a49cbe">{TAGLINE}</text>')


def triad_ink_dy(scale: float, label_px: float) -> float:
    """Pixels between the triad's hub and the centre of its ink, at this scale."""
    internal = label_px / scale
    tops, bottoms = [], []
    for deg, name, _t, side in ba.ARMS:
        py = ba.CY + math.sin(math.radians(deg)) * ba.SPOKE
        leg_r = ba.METRICS[name]["r"] * ba.LEG_SCALE
        (tops if side == "above" else bottoms).append(
            py - leg_r - ba.GAP * 0.8 - internal * 0.8 if side == "above" else py + leg_r
        )
    bottom = max(bottoms) + ba.GAP * 1.15 + internal * 0.75
    return (ba.CY - (min(tops) + bottom) / 2) * scale


def triad(cx: float, ink_cy: float, scale: float, label_px: float = 19.0) -> str:
    """Place the triad so the centre of its INK lands on (cx, ink_cy)."""
    hub_y = ink_cy + triad_ink_dy(scale, label_px)
    tx = cx - ba.CX * scale
    ty = hub_y - ba.CY * scale
    body = ba.triad_group(label_size=label_px / scale, label_fill="#c3bcd8")
    return f'  <g transform="translate({tx:.1f},{ty:.1f}) scale({scale})">\n{body}\n  </g>'


def legs_in_a_row(y: float, xs: list[float], scale: float, label_px: float) -> str:
    """The three legs abreast instead of radial, labels on a shared baseline."""
    order = ["silo", "patrol", "bomber"]
    names = {"silo": "SILO", "patrol": "PATROL", "bomber": "BOMBER"}
    glyphs, labels = [], []
    baseline = y + max(ba.METRICS[n]["r"] * scale for n in order) + 16 + label_px * 0.55
    for name, x in zip(order, xs):
        glyphs.append("  " + ba._place(name, x, y, scale))
        labels.append(f'<text x="{x:.0f}" y="{baseline:.0f}">{names[name]}</text>')
    nl = "\n    "
    return (
        "\n".join(glyphs)
        + f'\n  <g font-family="ui-monospace, SFMono-Regular, Consolas, monospace"'
        f' font-size="{label_px:.0f}" letter-spacing="1.5" fill="#c3bcd8" text-anchor="middle">'
        f"\n    {nl.join(labels)}\n  </g>"
    )


# ── the variants ────────────────────────────────────────────────────────────

def v_aligned() -> str:
    """A — what ships. Text left, triad right, both ink-centred on the canvas."""
    axis, base = 320.0, 305.0
    return "\n".join([head("aligned"), wordmark(96, base + 61, 112), rule(99, base + 99, 112),
                      tagline(99, base + 163, 34), triad(1000, axis, 1.38), "</svg>", ""])


def v_hero() -> str:
    """B — the diagram is the identity, so it takes the frame. Name becomes a caption."""
    return "\n".join([head("hero"), triad(640, 250, 1.62, 21), wordmark(96, 566, 72),
                      tagline(99, 600, 24), "</svg>", ""])


def v_stacked() -> str:
    """C — one centred column. Nothing competes for the axis; the diagram shrinks."""
    mid = W / 2
    return "\n".join([head("stacked"), wordmark(mid, 168, 104, "middle"), rule(mid - 56, 204, 112),
                      tagline(mid, 258, 31, "middle"), triad(mid, 452, 1.02), "</svg>", ""])


def v_mirrored() -> str:
    """D — A, flipped. Puts the mark first for a left-to-right reader."""
    return "\n".join([head("mirrored"), triad(300, 320, 1.38),
                      wordmark(1184, 366, 112, "end"), rule(1072, 404, 112),
                      tagline(1184, 468, 34, "end"), "</svg>", ""])


def v_banner() -> str:
    """E — legs abreast rather than radial. Fills the canvas; loses the 120 degree mark."""
    return "\n".join([
        head("banner"), wordmark(96, 168, 96), rule(99, 202, 112), tagline(99, 250, 30),
        f'  <path d="M96,318 L1184,318" stroke="{ba.DIM}" stroke-opacity=".22" stroke-width="1.5"/>',
        legs_in_a_row(430, [320.0, 640.0, 960.0], 1.15, 19),
        "</svg>", ""])


def v_minimal() -> str:
    """F — the mark alone, no legs. Cleanest, and says least about the doctrine."""
    mid = W / 2
    return "\n".join([
        head("minimal"),
        f'  {ba._place("trefoil", mid, 214, 1.5)}',
        wordmark(mid, 388, 116, "middle"), rule(mid - 60, 426, 120),
        tagline(mid, 486, 33, "middle"), "</svg>", ""])


VARIANTS = {
    "A-aligned": v_aligned,
    "B-hero": v_hero,
    "C-stacked": v_stacked,
    "D-mirrored": v_mirrored,
    "E-banner": v_banner,
    "F-minimal": v_minimal,
}


def main() -> int:
    if "--list" in sys.argv:
        for name in VARIANTS:
            print(f"assets/social-alts/{name}.svg")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in VARIANTS.items():
        path = OUT / f"{name}.svg"
        path.write_text(fn(), encoding="utf-8")
        try:
            ET.parse(path)
        except ET.ParseError as exc:
            raise SystemExit(f"  {name} is not well-formed XML: {exc}") from exc
        print(f"  wrote assets/social-alts/{name}.svg")
    print(f"\n{len(VARIANTS)} variant(s). A-aligned is what social-preview.svg ships.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
