# -*- coding: utf-8 -*-
"""Render a Canva-exported PDF page to PNG(s) for visual overflow verification.

Part of the MANDATORY render-verify loop (see CLAUDE.md -> Formatting rules):
after any Canva edit commit, export the edited page as PDF (export-design,
size letter, pro), download it, run this, then Read the PNGs to visually
check wrapping. Char counts are a drafting heuristic only — pixels decide.

Usage:
  python render_canva_page.py <page.pdf> [outdir]

When ``outdir`` is omitted, verification images are written to the packet's
``archive/`` subfolder. This keeps the submit-ready packet root limited to the
PDFs and ``copy/``.

Outputs:
  <stem>_full.png    - whole page at 110 dpi
  <stem>_skills.png  - right skill column (x>60%, y>25%) at 200 dpi
  <stem>_left.png    - left column (x<62%) at 150 dpi (profile + work boxes)
"""
import sys, os
import fitz  # pymupdf

pdf = sys.argv[1]
pdf_dir = os.path.dirname(os.path.abspath(pdf))
outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(pdf_dir, "archive")
os.makedirs(outdir, exist_ok=True)
stem = os.path.splitext(os.path.basename(pdf))[0]
doc = fitz.open(pdf)
page = doc[0]
r = page.rect

jobs = [
    ("full", 110, None),
    ("skills", 200, fitz.Rect(r.width * 0.60, r.height * 0.25, r.width, r.height)),
    ("left", 150, fitz.Rect(0, 0, r.width * 0.62, r.height)),
]
for name, dpi, clip in jobs:
    pix = page.get_pixmap(dpi=dpi, clip=clip)
    out = os.path.join(outdir, f"{stem}_{name}.png")
    pix.save(out)
    print(out)
