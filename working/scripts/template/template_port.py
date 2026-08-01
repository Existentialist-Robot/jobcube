# -*- coding: utf-8 -*-
"""template_port.py — generic, manifest-driven Canva port primitive.

Replaces per-sprint builder cloning. The layout is locked; slots are identified
by POSITION (stable across dups — only element IDs regenerate), and capacities
are derived from box GEOMETRY, calibrated by render-verified fits.

Commands:
  python template_port.py build-manifest <snapshot.json> --resume-page 1 --cover-page 2
      Fingerprint the template variant from a transaction snapshot and write
      manifest.json next to this script (preserves calibration overrides).

  python template_port.py port <snapshot.json> <copy.json> [--out ops.json]
      Fingerprint each pair's pages, match the variant, measure new copy
      against slot capacities (hard caps + fill floors + banned-phrase scan),
      and emit a flat ops list ready for perform-editing-operations.
      Prints CLEAN-MAP CHECK: PASS/FAIL and a measure table.

copy.json schema:
{
  "pairs": [
    {
      "resume_page": 1, "cover_page": 2,
      "slots": {
        "headline": "...", "section_header": "...", "divider": "...",
        "tagline": "...", "profile": "...",
        "skill_label_1": "...", "skill_desc_1": "...",   # 1 = TOP skill slot
        ... labels/descs 2-4 (4 = the tall 4-line bottom slot) ...
      },
      "ceo_bullets": ["b1", null, "b3", ...],   # null/omit = keep current bullet
      "cover_body": "Dear ...",                  # or "cover_body_file": "path"
      "cover_headline": "...",                   # defaults to slots.headline
      "normalize_work_box_italics": true,
      "run_replacements": {                      # REQUIRED for any mixed-style slot
        "slot_name": [{"find_text": "...", "replace_text": "..."}]
      },
      "cover_body_run_replacements": [           # REQUIRED if cover body has >1 run
        {"find_text": "...", "replace_text": "..."}
      ]
    }
  ]
}

Rules encoded: caps are hard (geometry × calibration); descs & profile warn
under 90% fill; covers must land inside the configured character band;
banned-phrase regex fails the run. After applying ops: verify every cover
sign-off and rich-text run from the perform response, commit within seconds
only if those gates pass, then render-verify with render_canva_page.py and
measure_cover_gap.py per cover.

FIRST-RUN SETUP
---------------
1. Fill in `port_config.json` (sign-off name, cover character band, ban list).
   `port` refuses to run while the sign-off name is still the placeholder.
2. Register YOUR layout:
       python template_port.py build-manifest <snapshot.json> --name v1
   The shipped manifest.json and the slot positions / VERIFIED_CAPS in this file
   were measured against one specific Canva design. They are a worked example,
   NOT universal — your design will have different positions and capacities.
3. Recalibrate: port one pair, render it, and tighten any slot that overflowed.
   Character counts are a drafting heuristic; pixels decide.
"""
import sys, os, re, json, hashlib, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(HERE, "manifest.json")
CONFIG_PATH = os.path.join(HERE, "port_config.json")

# ---------------------------------------------------------------------------
# Configuration (see port_config.json — SET IT UP BEFORE YOUR FIRST PORT)
# ---------------------------------------------------------------------------
PLACEHOLDER_NAME = "[YOUR_NAME]"


def load_config():
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            cfg = json.load(fh)
    # Env var wins, so CI and one-off runs can override without editing the file.
    name = os.environ.get("JOB_SEARCH_SIGNOFF_NAME") or cfg.get("signoff_name") or ""
    cfg["signoff_name"] = name.strip()
    band = cfg.get("cover_char_band") or [3050, 3387]
    cfg["cover_char_band"] = (int(band[0]), int(band[1]))
    return cfg


CONFIG = load_config()
SIGNOFF_NAME = CONFIG["signoff_name"]
COVER_MIN, COVER_MAX = CONFIG["cover_char_band"]

# ---------------------------------------------------------------------------
# Snapshot parsing (transaction JSON, tolerant of the ~106KB truncation)
# ---------------------------------------------------------------------------
ELEM_PAT = re.compile(
    r'\\"page_index\\":(\d+),\\"regions\\":\[(.*?)\],'
    r'\\"containerElement\\":\{\\"type\\":\\"TEXT\\",\\"position\\":\{\\"top\\":([\d.]+),\\"left\\":([\d.]+)\},'
    r'\\"dimension\\":\{\\"width\\":([\d.]+),\\"height\\":([\d.]+)\}\},\\"element_id\\":\\"(PB[^"\\\\]+)\\"')
TEXT_PAT = re.compile(r'\\"text\\":\\"((?:[^"\\\\]|\\\\.)*?)\\"')


def _unescape(s):
    try:
        return json.loads('"' + s.replace('\\\\', '\\') + '"')
    except Exception:
        return s.replace("\\\\n", "\n").replace('\\\\"', '"')


def parse_snapshot(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    try:
        payload = json.loads(raw)
        richtexts = payload.get("richtexts") if isinstance(payload, dict) else None
        if isinstance(richtexts, list):
            elems = []
            for item in richtexts:
                container = item.get("containerElement") or {}
                position = container.get("position") or {}
                dimension = container.get("dimension") or {}
                regions = item.get("regions") or []
                texts = [region.get("text", "") for region in regions]
                elems.append(dict(
                    page=int(item["page_index"]),
                    top=float(position["top"]),
                    left=float(position["left"]),
                    w=float(dimension["width"]),
                    h=float(dimension["height"]),
                    eid=item["element_id"],
                    runs=len(texts),
                    run_texts=texts,
                    text="".join(texts),
                ))
            return elems
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass
    elems = []
    for m in ELEM_PAT.finditer(raw):
        texts = [_unescape(t) for t in TEXT_PAT.findall(m.group(2))]
        elems.append(dict(
            page=int(m.group(1)), top=float(m.group(3)), left=float(m.group(4)),
            w=float(m.group(5)), h=float(m.group(6)), eid=m.group(7),
            runs=len(texts), run_texts=texts, text="".join(texts)))
    return elems


# ---------------------------------------------------------------------------
# Slot naming by position (locked layout, positions rounded to nearest 2px)
# ---------------------------------------------------------------------------
def key(top, left):
    return f"{round(top/2)*2},{round(left/2)*2}"


# EXAMPLE POSITION MAP — measured against one specific Canva design. Replace the
# coordinates with your own (read them from a transaction snapshot), keeping the
# slot NAMES, which the rest of the pipeline and PACKET_TEMPLATE.md refer to.
# "ceo" is the lead-role work box (your most recent / most important role); the
# other work boxes are role-neutral and usually left untouched between ports.
RESUME_SLOTS = {  # (top,left) -> (name, kind)
    key(70.6, 25.7):  ("headline", "single"),
    key(144.7, 25.7): ("section_header", "single"),
    key(177.0, 25.7): ("profile", "single"),
    key(290.3, 25.7): ("divider", "single"),
    key(604.1, 27.0): ("tagline", "single"),
    key(318.3, 27.0): ("ceo", "bullets"),
    key(505.9, 27.0): ("cto", "bullets"),        # role-neutral; usually untouched
    key(632.2, 25.7): ("research", "bullets"),   # role-neutral
    key(730.4, 25.7): ("program_creator", "bullets"),  # role-neutral
    key(290.3, 542.3): ("skill_label_1", "single"),
    key(314.1, 542.3): ("skill_desc_1", "single"),
    key(372.9, 542.3): ("skill_label_2", "single"),
    key(396.7, 542.3): ("skill_desc_2", "single"),
    key(455.6, 542.3): ("skill_label_3", "single"),
    key(479.4, 542.3): ("skill_desc_3", "single"),
    key(538.3, 542.3): ("skill_label_4", "single"),
    key(562.1, 542.3): ("skill_desc_4", "single"),
}
COVER_SLOTS = {
    key(167.7, 52.3): ("cover_body", "cover"),
    key(70.6, 25.7):  ("cover_headline", "single"),
}

# Geometry -> capacity calibration (render-verified constants, 2026-07-02):
# chars/line ~= width / 5.2 ; lines = round(height / 15.8); safety 0.97.
CPL_DIVISOR = 5.2
LINE_H = 15.8
SAFETY = 0.97
# Hard verified overrides (slot name -> cap) — trump geometry when tighter.
#
# RECALIBRATE THESE AGAINST YOUR OWN LAYOUT. Every number below was measured
# against one specific Canva design; they are a worked example, not universal.
# Character count predicts fit only roughly — wrapping depends on WORD lengths,
# so a box that held 184 chars of one wording overflows at 184 of another. The
# way to calibrate: port a pair, render it, and tighten any slot that overflowed
# to the longest length you have actually seen fit.
VERIFIED_CAPS = {"headline": 44, "section_header": 30, "divider": 31,
                 "tagline": 37, "profile": 719, "skill_desc_1": 141,
                 "skill_desc_2": 146, "skill_desc_3": 141,
                 "skill_desc_4": 194,
                 "skill_label_1": 25, "skill_label_2": 25,
                 "skill_label_3": 25, "skill_label_4": 25}
FILL_FLOOR = 0.90   # descs + profile should reach 90% of cap
# Per-bullet caps for the lead-role work box (b1..b5) — the most recent/most
# important role, keyed as "ceo" in the slot map below. Matching the BOX TOTAL
# is not sufficient: one over-long bullet wraps to an extra line and overflows
# even when the total is under cap. Validate against these proven per-bullet
# lengths, NOT the current dup text — dups may be a shorter template variant.
CEO_BULLET_CAPS = [232, 178, 165, 150, 123]

# Ban list — loaded from port_config.json. Add a phrase every time you catch one
# that isn't yours, so you never have to correct it twice.
_banned = CONFIG.get("banned_phrases") or []
_banned_allow = CONFIG.get("banned_allow") or []
BANNED = re.compile("|".join(_banned), re.I) if _banned else None
BANNED_ALLOW = re.compile("|".join(_banned_allow)) if _banned_allow else None


def banned_hits(text):
    """Phrases from the ban list present in `text`, minus allow-listed matches."""
    if BANNED is None:
        return []
    return [m.group(0) for m in BANNED.finditer(text)
            if not (BANNED_ALLOW and BANNED_ALLOW.fullmatch(m.group(0)))]

# AI-slop tells — printed as SLOP warnings in the measure table (soft gate).
# Applies mainly to cover_body; keep covers human. See [[feedback-anti-slop]].
SLOP_PATTERNS = [
    (r"I would welcome the chance to discuss how", "formulaic closer"),
    (r"[Hh]ere is how I would approach", "'here is how' opener"),
    (r"not just a\b|, not (?:a |an |just )", "antithesis cliche"),
    (r"I am not adjacent", "antithesis cliche"),
    (r"\bOn the [a-z]+:\s", "parallel label scaffold"),
    (r"\bI am both\.", "punchy fragment"),
    (r"reads like a summary", "AI flourish"),
    (r"\b(genuinely|precisely|exactly|truly)\b", "hollow intensifier"),
]


def slop_scan(text):
    hits = []
    for pat, label in SLOP_PATTERNS:
        n = len(re.findall(pat, text))
        if n:
            hits.append(f"{label}(x{n})")
    em = text.count("—")
    if em > 3:
        hits.append(f"em-dash x{em} (>3)")
    return hits


def geometry_cap(w, h):
    lines = max(1, round(h / LINE_H))
    cpl = w / CPL_DIVISOR
    return int(lines * cpl * SAFETY)


def fingerprint(elems_on_page):
    # Positions only: box width/height auto-size with content, positions are
    # the stable skeleton of a locked layout.
    sig = sorted(key(e["top"], e["left"]) for e in elems_on_page)
    return hashlib.sha1(json.dumps(sig).encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
def build_manifest(snapshot, resume_page, cover_page, name="v1"):
    elems = parse_snapshot(snapshot)
    manifest = {"variants": {}}
    if os.path.exists(MANIFEST_PATH):
        manifest = json.load(open(MANIFEST_PATH, encoding="utf-8"))
    for page, slotmap, vname in ((resume_page, RESUME_SLOTS, f"resume-{name}"),
                                 (cover_page, COVER_SLOTS, f"cover-{name}")):
        page_elems = [e for e in elems if e["page"] == page]
        fp = fingerprint(page_elems)
        slots = {}
        for e in page_elems:
            k = key(e["top"], e["left"])
            if k in slotmap:
                sname, kind = slotmap[k]
                cap = VERIFIED_CAPS.get(sname) or geometry_cap(e["w"], e["h"])
                slots[sname] = dict(pos=k, kind=kind, w=e["w"], h=e["h"], cap=cap)
        manifest["variants"][vname] = dict(fingerprint=fp, page_kind=vname.split("-")[0],
                                           slots=slots)
        print(f"{vname}: fingerprint={fp}, {len(slots)} slots mapped")
    json.dump(manifest, open(MANIFEST_PATH, "w", encoding="utf-8"), indent=1)
    print(f"manifest -> {MANIFEST_PATH}")


# ---------------------------------------------------------------------------
def match_variant(manifest, page_elems, page_kind):
    fp = fingerprint(page_elems)
    for vname, v in manifest["variants"].items():
        if v["fingerprint"] == fp and v["page_kind"] == page_kind:
            return vname, v
    # Persisted MCP responses can be truncated. When the full-page fingerprint
    # is unavailable, accept exactly one variant whose complete calibrated slot
    # skeleton is present. Text box widths can auto-size with content, so they
    # are intentionally excluded; uniqueness across registered variants keeps
    # this fallback fail-closed.
    by_pos = {key(e["top"], e["left"]): e for e in page_elems}
    candidates = []
    for vname, variant in manifest["variants"].items():
        if variant["page_kind"] != page_kind:
            continue
        slots = variant.get("slots") or {}
        if all(slot["pos"] in by_pos for slot in slots.values()):
            candidates.append((vname, variant))
    if len(candidates) == 1:
        print(
            f"  NOTE: {page_kind} matched {candidates[0][0]} by complete "
            "slot skeleton because the full-page fingerprint was unavailable"
        )
        return candidates[0]
    print(
        f"  FAIL: {page_kind} fingerprint {fp} is unknown; register and "
        "render-calibrate a new manifest variant"
    )
    return None, None


def bind(page_elems, variant):
    """slot name -> element dict, by position."""
    by_pos = {key(e["top"], e["left"]): e for e in page_elems}
    out = {}
    for sname, s in variant["slots"].items():
        e = by_pos.get(s["pos"])
        if e:
            out[sname] = e
    return out


def split_bullets(text):
    """CEO-box text -> (title_lines, bullets). Title = first 2 non-empty lines."""
    lines = [l for l in text.split("\n") if l.strip()]
    return lines[:2], lines[2:]


def run_preserving_ops(element, replacements, label, fails):
    """Emit exact-run replacements and refuse anchors that could cross styles."""
    if not replacements:
        fails.append(
            f"{label}: mixed-style box has {element['runs']} runs; provide "
            "run_replacements instead of whole-box replace_text"
        )
        return []
    initial_fail_count = len(fails)
    ops = []
    simulated = element["text"]
    for item in replacements:
        find_text = item.get("find_text")
        replace_text = item.get("replace_text")
        if not find_text or replace_text is None:
            fails.append(f"{label}: invalid run replacement {item!r}")
            continue
        if find_text not in element["run_texts"]:
            fails.append(
                f"{label}: anchor is not one complete snapshot text run: {find_text!r}"
            )
            continue
        if simulated.count(find_text) != 1:
            fails.append(
                f"{label}: run anchor must be unique in the element: {find_text!r}"
            )
            continue
        simulated = simulated.replace(find_text, replace_text, 1)
        ops.append(
            dict(
                type="find_and_replace_text",
                element_id=element["eid"],
                find_text=find_text,
                replace_text=replace_text,
            )
        )
    if len(fails) != initial_fail_count:
        return None
    return ops, simulated


def port(snapshot, copy_path, out_path):
    # Fail closed: without a real sign-off name the guard below cannot tell a
    # signed cover from an unsigned one, and Canva clips trailing text silently.
    if not SIGNOFF_NAME or SIGNOFF_NAME == PLACEHOLDER_NAME:
        print("CLEAN-MAP CHECK: FAIL")
        print(f"  - signoff_name is unset (still {PLACEHOLDER_NAME!r}). Set it in")
        print(f"    {CONFIG_PATH}")
        print("    or export JOB_SEARCH_SIGNOFF_NAME. This guard is what stops an")
        print("    unsigned cover letter from shipping.")
        sys.exit(1)
    manifest = json.load(open(MANIFEST_PATH, encoding="utf-8"))
    elems = parse_snapshot(snapshot)
    spec = json.load(open(copy_path, encoding="utf-8"))
    ops, fails, report = [], [], []

    for pair in spec["pairs"]:
        rp, cp = pair["resume_page"], pair.get("cover_page")
        if not isinstance(rp, int):
            fails.append(f"{pair.get('role', 'pair')}: resume_page is unassigned")
            continue
        r_elems = [e for e in elems if e["page"] == rp]
        if not r_elems:
            fails.append(f"resume page {rp} not in snapshot (truncated)"); continue
        vname, variant = match_variant(manifest, r_elems, "resume")
        if not variant:
            fails.append(f"p{rp}: no resume variant matched"); continue
        bound = bind(r_elems, variant)

        for sname, new in (pair.get("slots") or {}).items():
            if new is None: continue
            if sname not in bound:
                fails.append(f"p{rp}/{sname}: slot not bound"); continue
            e, cap = bound[sname], variant["slots"][sname]["cap"]
            hits = banned_hits(new)
            if hits: fails.append(f"p{rp}/{sname}: banned {hits}")
            status = "PASS" if len(new) <= cap else "OVER"
            if status == "OVER": fails.append(f"p{rp}/{sname}: {len(new)} > cap {cap}")
            fill = ""
            if sname.startswith("skill_desc") or sname == "profile":
                if len(new) < cap * FILL_FLOOR: fill = "  UNDER-FILL"
            report.append(f"  p{rp} {sname:16s} {len(new):4d}/{cap:4d}  {status}{fill}")
            if e["runs"] > 1:
                repl = (pair.get("run_replacements") or {}).get(sname)
                result = run_preserving_ops(e, repl, f"p{rp}/{sname}", fails)
                if result:
                    slot_ops, simulated = result
                    if simulated != new:
                        fails.append(
                            f"p{rp}/{sname}: run replacements do not reconstruct final slot text"
                        )
                    else:
                        ops.extend(slot_ops)
            else:
                ops.append(dict(type="replace_text", element_id=e["eid"], text=new))

        cb = pair.get("ceo_bullets")
        if cb:
            if "ceo" not in bound:
                fails.append(f"p{rp}/ceo: slot not bound")
            else:
                e = bound["ceo"]
                _, cur = split_bullets(e["text"])
                bullet_changes = []
                for i, new in enumerate(cb):
                    if new is None or i >= len(cur): continue
                    old = cur[i].strip()
                    cap = CEO_BULLET_CAPS[i] if i < len(CEO_BULLET_CAPS) else len(old)
                    if len(new) > cap:
                        fails.append(f"p{rp}/ceo_b{i+1}: {len(new)} > cap {cap}")
                    report.append(f"  p{rp} ceo_b{i+1:<14d} {len(new):4d}/{cap:4d}  "
                                  + ("PASS" if len(new) <= cap else "OVER"))
                    bullet_changes.append((old, new))
                if e["runs"] > 1 and bullet_changes:
                    matching_runs = [
                        run for run in e["run_texts"]
                        if all(old in run for old, _ in bullet_changes)
                    ]
                    if len(matching_runs) == 1:
                        old_run = matching_runs[0]
                        new_run = old_run
                        for old, new in bullet_changes:
                            new_run = new_run.replace(old, new, 1)
                        ops.append(dict(
                            type="find_and_replace_text",
                            element_id=e["eid"],
                            find_text=old_run,
                            replace_text=new_run,
                        ))
                    elif all(old in e["run_texts"] for old, _ in bullet_changes):
                        for old, new in bullet_changes:
                            ops.append(dict(
                                type="find_and_replace_text",
                                element_id=e["eid"],
                                find_text=old,
                                replace_text=new,
                            ))
                    else:
                        fails.append(
                            f"p{rp}/ceo: bullet anchors do not align to complete "
                            "snapshot rich-text runs"
                        )
                else:
                    for old, new in bullet_changes:
                        ops.append(dict(
                            type="find_and_replace_text",
                            element_id=e["eid"],
                            find_text=old,
                            replace_text=new,
                        ))
                if pair.get("normalize_work_box_italics") is True:
                    ops.append(dict(type="format_text", element_id=e["eid"],
                                    formatting=dict(font_style="normal")))
                else:
                    report.append(
                        f"  p{rp} ceo formatting     PRESERVED "
                        "(set normalize_work_box_italics=true only for known template artifact)"
                    )

        if cp:
            c_elems = [e for e in elems if e["page"] == cp]
            if not c_elems:
                fails.append(f"cover page {cp} not in snapshot"); continue
            _, cvar = match_variant(manifest, c_elems, "cover")
            cbound = bind(c_elems, cvar) if cvar else {}
            # An explicit file is the final copy source when both a long-form
            # working draft and a length-matched file are retained in JSON.
            if pair.get("cover_body_file"):
                body = open(pair["cover_body_file"], encoding="utf-8").read().strip()
            else:
                body = pair.get("cover_body")
            if body:
                body = body.replace("'", "’")
                n = len(body)
                st = "PASS" if COVER_MIN <= n <= COVER_MAX else ("LIGHT" if n < COVER_MIN else "OVER")
                if st != "PASS": fails.append(f"p{cp}/cover_body: {n} chars ({st})")
                report.append(f"  p{cp} cover_body       {n:4d}  band {COVER_MIN}-{COVER_MAX}  {st}")
                sl = slop_scan(body)
                if sl: report.append(f"  p{cp} cover SLOP-WARN: " + ", ".join(sl))
                # SIGN-OFF INTEGRITY (draft-side): the body MUST carry the sign-off,
                # else the letter ships unsigned. Canva ALSO silently clips trailing
                # lines when replace_text writes into a fixed-height box smaller than
                # the new text — this shipped a cover with the sign-off missing and
                # no error at all. Name comes from port_config.json.
                signoff_re = re.compile(
                    r"Sincerely,\s*\n\s*" + re.escape(SIGNOFF_NAME) + r"\s*$")
                if not signoff_re.search(body):
                    fails.append(
                        f"p{cp}/cover_body: missing/!=trailing "
                        f"'Sincerely,\\n{SIGNOFF_NAME}' sign-off")
                if "cover_body" in cbound:
                    cbe = cbound["cover_body"]
                    # ROOT FIX: resize the box first (width-only -> Canva auto-recomputes
                    # height) so the frame grows to fit the full text BEFORE it is stored.
                    ops.append(dict(type="resize_element", element_id=cbe["eid"], width=cbe["w"]))
                    if cbe["runs"] > 1:
                        result = run_preserving_ops(
                            cbe,
                            pair.get("cover_body_run_replacements"),
                            f"p{cp}/cover_body",
                            fails,
                        )
                        if result:
                            cover_ops, simulated = result
                            if simulated != body:
                                fails.append(
                                    f"p{cp}/cover_body: run replacements do not reconstruct "
                                    "the final cover body"
                                )
                            else:
                                ops.extend(cover_ops)
                    else:
                        ops.append(dict(type="replace_text", element_id=cbe["eid"], text=body))
                else:
                    fails.append(f"p{cp}: cover_body slot not bound")
            ch = pair.get("cover_headline") or (pair.get("slots") or {}).get("headline")
            if ch and "cover_headline" in cbound:
                che = cbound["cover_headline"]
                if che["runs"] > 1:
                    repl = (pair.get("run_replacements") or {}).get("cover_headline")
                    result = run_preserving_ops(
                        che, repl, f"p{cp}/cover_headline", fails
                    )
                    if result:
                        headline_ops, simulated = result
                        if simulated != ch:
                            fails.append(
                                f"p{cp}/cover_headline: run replacements do not reconstruct "
                                "final text"
                            )
                        else:
                            ops.extend(headline_ops)
                else:
                    ops.append(dict(type="replace_text",
                                    element_id=che["eid"], text=ch))

    print("MEASURE:"); print("\n".join(report))
    print()
    if fails:
        print("CLEAN-MAP CHECK: FAIL")
        for f in fails: print("  -", f)
        sys.exit(1)
    print("CLEAN-MAP CHECK: PASS")
    json.dump(ops, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(ops)} ops -> {out_path}")
    print("NEXT: start-editing-transaction -> perform (all ops, page_index=first) "
          "-> commit IMMEDIATELY -> render-verify (render_canva_page.py + "
          "measure_cover_gap.py per cover).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    bm = sub.add_parser("build-manifest")
    bm.add_argument("snapshot"); bm.add_argument("--resume-page", type=int, default=1)
    bm.add_argument("--cover-page", type=int, default=2); bm.add_argument("--name", default="v1")
    pt = sub.add_parser("port")
    pt.add_argument("snapshot"); pt.add_argument("copy")
    pt.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.cmd == "build-manifest":
        build_manifest(a.snapshot, a.resume_page, a.cover_page, a.name)
    else:
        port(a.snapshot, a.copy, a.out or a.copy + ".ops.json")
