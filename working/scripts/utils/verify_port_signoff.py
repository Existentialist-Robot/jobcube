# -*- coding: utf-8 -*-
"""Post-perform sign-off + integrity backstop for Canva ports.

Canva silently CLIPS trailing text when replace_text writes into a fixed-height
box smaller than the new content — this once shipped a cover letter with the
"Sincerely, / <name>" sign-off dropped and zero error raised. template_port now
emits a resize_element before each cover replace_text to prevent it, but ALWAYS
verify the stored result too: run this against the perform-editing-operations
RESPONSE file BEFORE you commit. If it FAILs, cancel the transaction, fix, and
re-perform — never commit.

Usage:
  python verify_port_signoff.py <perform_response.json> EID1 [EID2 ...]
  # EIDs = the cover_body element_ids you just wrote. Defaults to scanning every
  # element region for a sign-off if no EIDs given (coarser).
Exit 0 = all good; exit 1 = a cover is missing its sign-off (DO NOT COMMIT).

The sign-off name comes from working/scripts/template/port_config.json (or the
JOB_SEARCH_SIGNOFF_NAME env var) — the same source template_port.py uses.
"""
import json, os, re, sys

PLACEHOLDER_NAME = "[YOUR_NAME]"
CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "template", "port_config.json")


def signoff_name():
    name = os.environ.get("JOB_SEARCH_SIGNOFF_NAME", "").strip()
    if not name and os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            name = (json.load(fh).get("signoff_name") or "").strip()
    if not name or name == PLACEHOLDER_NAME:
        print(f"FAIL  signoff_name is unset (still {PLACEHOLDER_NAME!r}).")
        print(f"      Set it in {CONFIG_PATH} or export JOB_SEARCH_SIGNOFF_NAME.")
        raise SystemExit(2)
    return name


# Tolerates literal newlines AND single/double JSON-escaped newlines (perform
# responses double-escape: "Sincerely,\\n<name>"). Backslashes/n/whitespace
# between the two are all optional and repeatable.
SIGNOFF = re.compile(r"Sincerely,[\s\\n]*" + re.escape(signoff_name()))


def region_before(raw, eid, window=4500):
    i = raw.find(eid)
    if i < 0:
        return None
    return raw[max(0, i - window):i]


def main():
    if len(sys.argv) < 2:
        print("usage: verify_port_signoff.py <response.json> [cover_eid ...]")
        return 2
    raw = open(sys.argv[1], encoding="utf-8", errors="replace").read()
    eids = sys.argv[2:]
    ok = True
    if eids:
        for eid in eids:
            seg = region_before(raw, eid)
            if seg is None:
                print(f"FAIL  {eid[:24]}… : element not found in response"); ok = False; continue
            present = bool(SIGNOFF.search(seg))
            print(f"{'PASS' if present else 'FAIL'}  {eid[:24]}… : sign-off {'present' if present else 'MISSING (clipped?)'}")
            ok = ok and present
    else:
        n = len(SIGNOFF.findall(raw))
        print(f"found {n} sign-off block(s) across all regions (pass explicit cover EIDs for a precise check)")
        ok = n > 0
    print("VERDICT:", "PASS - safe to commit" if ok else "FAIL - CANCEL transaction, do NOT commit")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
