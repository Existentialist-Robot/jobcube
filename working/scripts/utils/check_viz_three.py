"""
Static checks for the Three.js job search visualizer.

This intentionally checks architecture-level invariants that failed in the
Plotly version: no Plotly restyle loop, no inline event handlers, one JSON data
island, delegated controls, and parseable generated JavaScript.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "active" / "job_search_viz.html"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def ok(message: str) -> None:
    print(f"OK: {message}")


def main() -> None:
    if not HTML.exists():
        fail(f"Missing generated HTML: {HTML}")

    text = HTML.read_text(encoding="utf-8")

    if "Plotly." in text or "Plotly.newPlot" in text:
        fail("Generated viz still contains Plotly calls")
    ok("no Plotly runtime calls")

    for needle in [
        "three.min.js",
        "id=\"scene3d\"",
        "id=\"location-map\"",
        "data-action=\"color\" data-mode=\"location\"",
        "function syncSceneState",
        "function raycastHover",
        "function renderMapState",
        "addEventListener(\"pointerdown\"",
        "ResizeObserver",
    ]:
        if needle not in text:
            fail(f"Missing expected Three.js viz marker: {needle}")
    ok("Three.js architecture markers present")

    if re.search(r"\son[a-z]+=", text):
        fail("Inline event handler found; controls should use delegated listeners")
    ok("no inline event handlers")

    data_match = re.search(
        r"<script id=\"job-data\" type=\"application/json\">(.*?)</script>",
        text,
        flags=re.S,
    )
    if not data_match:
        fail("Missing job-data JSON script")
    payload = json.loads(data_match.group(1))
    jobs = payload.get("jobs", [])
    # The invariant is that the payload rendered at all, not that it is large.
    # This used to require 10+, which failed on a fresh clone: the shipped JOBS
    # list is a handful of examples.
    if not jobs:
        fail("Job payload is empty — build_job_viz_three.py rendered no jobs")
    if not all({"id", "label", "org", "x", "y", "z", "province"} <= set(j) for j in jobs):
        fail("At least one job is missing required rendered fields")
    ok(f"job payload valid: {len(jobs)} jobs")

    scripts = []
    for match in re.finditer(r"<script(?![^>]*\bsrc=)(?![^>]*application/json)[^>]*>(.*?)</script>", text, flags=re.S):
        scripts.append(match.group(1))
    if not scripts:
        fail("No inline application script found")

    combined = "\n\n".join(scripts)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tmp:
        tmp.write(combined)
        tmp_path = Path(tmp.name)

    try:
        result = subprocess.run(["node", "--check", str(tmp_path)], capture_output=True, text=True)
    except FileNotFoundError:
        fail("Node is not available for JavaScript syntax check")
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass

    if result.returncode != 0:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        fail("Generated JavaScript failed node --check")
    ok("generated JavaScript parses")

    print("All Three.js viz checks passed.")


if __name__ == "__main__":
    main()
