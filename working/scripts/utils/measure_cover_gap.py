# -*- coding: utf-8 -*-
"""Measure the gap between cover-letter body text and the signature image.

Part of the render-verify loop. The signature is an IMAGE element with NO
element ID exposed via the Canva editing API (transaction maps are TEXT-only,
verified 2026-07-02), so the pipeline controls the gap from the TEXT side:
tune cover length so text-bottom lands a set distance above the fixed
signature. Target band: signature top 7-12pt below text bottom.

Usage: python measure_cover_gap.py <cover.pdf> [page_index]

Output: text_bottom, sig_top, gap (pt + canva-px), verdict, and the
approximate character delta needed to hit the middle of the target band
(~95 chars/line at cover width, ~13.4pt line height).
"""
import sys
import fitz

TARGET_MIN, TARGET_MAX = 7.0, 12.0   # pt; sweet spot ~9.5
TARGET_MID = (TARGET_MIN + TARGET_MAX) / 2
CHARS_PER_LINE = 95
LINE_H = 13.4

pdf = sys.argv[1]
idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
page = fitz.open(pdf)[idx]

blocks = [b for b in page.get_text("dict")["blocks"] if b["type"] == 0]
text_bottom = max(l["bbox"][3] for b in blocks for l in b["lines"])

rects = []
for img in page.get_images(full=True):
    try:
        rects += page.get_image_rects(img[0])
    except Exception:
        pass
sig = [r for r in rects if r.y0 > page.rect.height * 0.5]
if not sig:
    print(f"text_bottom={text_bottom:.0f}pt | NO signature image found in lower half")
    sys.exit(1)

s = sig[0]
gap = s.y0 - text_bottom
k = 1056 / 792  # pt -> canva px
if gap < TARGET_MIN:
    verdict = "OVERLAP/TIGHT - shrink inter-paragraph blank lines (font 10->6), else trim cover"
    delta_lines = (TARGET_MID - gap) / LINE_H
    action = f"trim ~{int(delta_lines * CHARS_PER_LINE)} chars (~{delta_lines:.1f} lines)"
elif gap > TARGET_MAX:
    verdict = "SIGNATURE TOO FAR DOWN - lengthen cover or drag signature up"
    delta_lines = (gap - TARGET_MID) / LINE_H
    action = f"add ~{int(delta_lines * CHARS_PER_LINE)} chars (~{delta_lines:.1f} lines) OR drag signature up {gap - TARGET_MID:.0f}pt ({(gap - TARGET_MID) * k:.0f} canva-px)"
else:
    verdict = "IN BAND"
    action = "none"

print(f"text_bottom={text_bottom:.0f}pt  sig_top={s.y0:.0f}pt  gap={gap:.0f}pt "
      f"({gap * k:.0f} canva-px)")
print(f"verdict: {verdict}")
print(f"action:  {action}")
