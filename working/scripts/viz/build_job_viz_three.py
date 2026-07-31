"""
Three.js job search visualizer.

This builder deliberately avoids Plotly. The old Plotly version coupled UI events
directly to trace indexes and frequent restyle calls; this version keeps one small
state object, a stable Three.js scene, delegated UI events, and synced map/list/3D
hover state.

Regenerate:
  python working/scripts/viz/build_job_viz_three.py

Output:
  working/active/job_search_viz.html
"""

from __future__ import annotations

import ast
import json
import math
import re
import shutil
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKING = ROOT / "working"
LEGACY = Path(__file__).with_name("build_job_viz.py")
OUT = WORKING / "active" / "job_search_viz.html"
NEXT = WORKING / "active" / "job_search_viz_next.html"
ARCHIVE = WORKING / "archive" / "viz"

STATUS_ALIAS = {"File-ready": "Ready", "Canva-ported": "Ported"}
STATUS_COLORS = {
    "Applied": "#4f8fd8",
    "Interview": "#f0a13a",
    "Ready": "#a887ff",
    "Ported": "#44c7e8",
    "Queued": "#73c985",
    "Drafted": "#f47f55",
    "Target": "#27c6d8",
    "Declined": "#7f8795",
}

FIT_COLORS = ["#d85a4a", "#f28b58", "#e7c85d", "#73b4d4", "#3978bd"]

AXIS_LABELS = {
    "x": ["", "Startup", "Innovation org", "Nonprofit", "Post-secondary", "Gov"],
    "y": ["", "Ops", "Change mgmt", "Strategy", "Programs/Partnerships", "Ecosystem/R&D"],
    "z": ["", "Specialist", "Officer/Advisor", "Manager", "Director/ED", "VP/C-suite"],
}


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "job"


def load_legacy_jobs() -> list[dict]:
    """Read JOBS from the legacy builder without executing that builder."""
    tree = ast.parse(LEGACY.read_text(encoding="utf-8"))
    jobs_node = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "JOBS":
                    jobs_node = node.value
                    break
        if jobs_node is not None:
            break
    if jobs_node is None:
        raise RuntimeError(f"Could not find JOBS assignment in {LEGACY}")

    code = compile(ast.Expression(jobs_node), str(LEGACY), "eval")
    jobs = eval(code, {"__builtins__": {}, "dict": dict}, {})
    if not isinstance(jobs, list):
        raise TypeError("JOBS did not evaluate to a list")
    return jobs


def infer_location(job: dict) -> tuple[str, str]:
    text = f"{job.get('label','')} {job.get('org','')} {job.get('note','')}".lower()
    org = job.get("org", "")
    org_l = org.lower().strip()

    if "communitech" in text or "kitchener" in text:
        return "ON", "Kitchener, ON"
    if "cohere" in text:
        return "ON", "Toronto/Ottawa, ON"
    if org_l == "oci" or "ontario centre of innovation" in text:
        return "ON", "Toronto/Ottawa, ON"
    if "nrc" in text:
        return "ON", "Ottawa, ON"
    if "platform calgary" in text or "calgary" in text:
        return "AB", "Calgary, AB"
    if "city of edmonton" in text or "edmonton" in text:
        return "AB", "Edmonton, AB"
    if "goa" in text or "alberta" in text or "radiance" in text:
        return "AB", "Alberta"
    if "post-sec" in text or "regional development" in text or "social innovation" in text:
        return "AB", "Alberta"
    if "ai/tech" in text or "series a" in text:
        return "Remote", "Remote/Canada"
    return "Remote", org or "Remote/Canada"


def enrich_jobs(jobs: list[dict]) -> list[dict]:
    enriched: list[dict] = []
    province_counts: dict[str, int] = {}
    for index, source in enumerate(jobs):
        job = dict(source)
        job["status"] = STATUS_ALIAS.get(job.get("status"), job.get("status", "Applied"))
        job["id"] = f"{slugify(job.get('label','job'))}-{index:02d}"
        job["index"] = index
        job["fit"] = int(job.get("fit", 1))
        job["p"] = int(job.get("p", 0))
        job["sal"] = int(job.get("sal", 0))
        job["sal_min"] = int(job.get("sal_min", job["sal"]))
        job["sal_max"] = int(job.get("sal_max", job["sal"]))
        province, place = infer_location(job)
        province_counts[province] = province_counts.get(province, 0) + 1
        job["province"] = province
        job["place"] = place
        job["provinceOrdinal"] = province_counts[province]
        enriched.append(job)
    return enriched


def backup_existing() -> None:
    if not OUT.exists():
        return
    text = OUT.read_text(encoding="utf-8", errors="ignore")
    if "Plotly.newPlot" not in text:
        return
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    target = ARCHIVE / f"job_search_viz_plotly_backup_{stamp}.html"
    if not target.exists():
        shutil.copy2(OUT, target)


def job_center(jobs: list[dict]) -> dict:
    return {
        "x": round(sum(j["x"] for j in jobs) / len(jobs), 3),
        "y": round(sum(j["y"] for j in jobs) / len(jobs), 3),
        "z": round(sum(j["z"] for j in jobs) / len(jobs), 3),
    }


def build_html(jobs: list[dict]) -> str:
    data = {
        "jobs": jobs,
        "center": job_center(jobs),
        "statusColors": STATUS_COLORS,
        "fitColors": FIT_COLORS,
        "axisLabels": AXIS_LABELS,
        "today": date.today().isoformat(),
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    html = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Job Search Space</title>
  <script src="https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js"></script>
  <style>
    :root {
      color-scheme: dark;
      --bg: #090c12;
      --panel: #111723;
      --panel-2: #151d2a;
      --line: rgba(220, 230, 255, 0.13);
      --text: #eff4ff;
      --muted: #9aa7bd;
      --soft: #c2ccdf;
      --accent: #60a5fa;
      --accent-2: #41d7c8;
      --danger: #f87171;
      --radius: 8px;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; margin: 0; background: var(--bg); color: var(--text); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { overflow: hidden; }
    button, input { font: inherit; }
    button { color: inherit; }
    .app {
      height: 100vh;
      display: grid;
      grid-template-columns: 220px minmax(0, 1fr);
      grid-template-rows: minmax(0, 100vh);
      background:
        linear-gradient(120deg, rgba(38, 83, 129, 0.12), transparent 28%),
        linear-gradient(180deg, #0b1018, #070a0f 56%, #080b11);
    }
    .sidebar {
      min-height: 0;
      overflow: auto;
      border-right: 1px solid var(--line);
      background: rgba(12, 17, 26, 0.96);
      padding: 14px 12px 16px;
    }
    .brand {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }
    h1 { margin: 0; font-size: 15px; letter-spacing: 0; }
    .count { color: var(--muted); font-size: 11px; white-space: nowrap; }
    details {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: rgba(16, 23, 35, 0.74);
      margin-bottom: 9px;
      overflow: hidden;
    }
    summary {
      cursor: pointer;
      user-select: none;
      list-style: none;
      padding: 9px 10px;
      font-size: 11px;
      font-weight: 700;
      color: var(--soft);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    summary::-webkit-details-marker { display: none; }
    summary:after { content: "+"; color: #748099; font-size: 13px; }
    details[open] summary:after { content: "-"; }
    .section { padding: 0 10px 11px; display: grid; gap: 9px; }
    .row { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
    .btn {
      border: 1px solid rgba(150, 170, 210, 0.18);
      background: #171f30;
      border-radius: 6px;
      padding: 6px 9px;
      font-size: 12px;
      cursor: pointer;
      min-height: 30px;
    }
    .btn:hover { border-color: rgba(150, 190, 255, 0.38); background: #1d273a; }
    .btn.active { background: #223a60; border-color: rgba(108, 166, 255, 0.68); color: #ddebff; }
    .btn.compact { min-height: 25px; padding: 3px 7px; font-size: 11px; }
    .pill {
      border: 1px solid rgba(150, 170, 210, 0.18);
      border-radius: 999px;
      padding: 5px 8px;
      font-size: 11px;
      cursor: pointer;
      background: rgba(255,255,255,0.04);
      white-space: nowrap;
    }
    .pill.off { opacity: 0.36; filter: grayscale(0.7); }
    .preset-tag {
      display: inline-flex;
      align-items: stretch;
      border: 1px solid rgba(150, 170, 210, 0.18);
      border-radius: 6px;
      overflow: hidden;
      background: #171f30;
    }
    .preset-tag:hover { border-color: rgba(150, 190, 255, 0.38); }
    .preset-load {
      border: 0;
      background: transparent;
      padding: 3px 7px;
      font-size: 11px;
      cursor: pointer;
      color: inherit;
    }
    .preset-del {
      border: 0;
      border-left: 1px solid rgba(150, 170, 210, 0.18);
      background: transparent;
      padding: 3px 7px;
      font-size: 11px;
      cursor: pointer;
      color: var(--danger);
    }
    .preset-del:hover { background: rgba(248, 113, 113, 0.18); }
    .field { display: grid; gap: 5px; }
    .field label { display: flex; justify-content: space-between; gap: 8px; color: var(--muted); font-size: 11px; }
    .field input[type="range"] { width: 100%; accent-color: #5fa8ff; cursor: pointer; }
    .field input[type="text"] {
      width: 100%;
      border: 1px solid rgba(150, 170, 210, 0.22);
      border-radius: 6px;
      padding: 7px 8px;
      background: #0d1320;
      color: var(--text);
      outline: none;
    }
    .field input[type="text"]:focus { border-color: rgba(96,165,250,0.72); }
    .main {
      min-width: 0;
      min-height: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
    }
    .topbar {
      min-height: 48px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 10px 14px;
      border-bottom: 1px solid var(--line);
      background: rgba(9, 13, 20, 0.78);
    }
    .title { font-weight: 700; font-size: 14px; }
    .axis-readout { color: var(--muted); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .workspace {
      min-height: 0;
      min-width: 0;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 260px;
    }
    .scene-wrap {
      position: relative;
      min-width: 0;
      min-height: 0;
      overflow: hidden;
      background:
        radial-gradient(circle at 50% 45%, rgba(66, 125, 190, 0.16), transparent 34%),
        linear-gradient(180deg, #0a0f18, #070a0f);
    }
    #scene3d {
      position: absolute;
      inset: 0;
      touch-action: none;
      cursor: grab;
    }
    #scene3d.dragging { cursor: grabbing; }
    .label-layer, .pulse-layer {
      position: absolute;
      inset: 0;
      pointer-events: none;
    }
    .job-label {
      position: absolute;
      padding: 2px 5px;
      border-radius: 4px;
      background: rgba(9, 13, 20, 0.78);
      border: 1px solid rgba(255,255,255,0.1);
      color: #dce8ff;
      font-size: 10px;
      white-space: nowrap;
      max-width: 170px;
      overflow: hidden;
      text-overflow: ellipsis;
      opacity: 0;
      transition: opacity 120ms ease;
    }
    .job-label.visible { opacity: 0.92; }
    .axis-label {
      position: absolute;
      top: 0;
      left: 0;
      pointer-events: none;
      white-space: nowrap;
      color: rgba(255,255,255,0.82);
      text-shadow: 0 1px 3px rgba(0,0,0,0.85);
    }
    .axis-label.axis-tick { font-size: 10px; color: rgba(255,255,255,0.7); }
    .axis-label.axis-title {
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.04em;
      color: #cfe0ff;
    }
    .tooltip {
      position: absolute;
      pointer-events: none;
      min-width: 220px;
      max-width: 310px;
      padding: 9px 10px;
      border: 1px solid rgba(220,230,255,0.16);
      border-radius: var(--radius);
      background: rgba(10, 14, 22, 0.94);
      color: #e7eefc;
      font-size: 12px;
      line-height: 1.45;
      box-shadow: 0 12px 32px rgba(0,0,0,0.36);
      display: none;
      z-index: 7;
    }
    .tooltip strong { display: block; font-size: 13px; margin-bottom: 2px; }
    .map-overlay {
      position: absolute;
      left: 14px;
      bottom: 14px;
      width: min(390px, calc(100% - 28px));
      border: 1px solid rgba(220,230,255,0.16);
      border-radius: var(--radius);
      background: rgba(10, 15, 23, 0.94);
      box-shadow: 0 18px 44px rgba(0,0,0,0.42);
      display: none;
      z-index: 6;
    }
    .map-overlay.open { display: block; }
    .map-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      padding: 8px 10px;
      border-bottom: 1px solid var(--line);
      color: var(--soft);
      font-size: 12px;
      font-weight: 700;
    }
    #location-map { display: block; width: 100%; height: 240px; }
    .province { fill: #182235; stroke: rgba(230,240,255,0.24); stroke-width: 1; }
    .province-label { fill: #8ea0bd; font-size: 10px; pointer-events: none; }
    .map-dot { cursor: pointer; stroke: rgba(5,8,12,0.82); stroke-width: 1.5; transition: r 140ms ease, opacity 140ms ease; }
    .map-dot.dim { opacity: 0.18; }
    .map-dot.hot { r: 7; stroke: white; stroke-width: 2.2; }
    .side-panel {
      min-width: 0;
      min-height: 0;
      border-left: 1px solid var(--line);
      background: rgba(12, 17, 26, 0.86);
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
    }
    .detail {
      padding: 13px 13px 11px;
      border-bottom: 1px solid var(--line);
      min-height: 174px;
    }
    .detail h2 { margin: 0 0 3px; font-size: 16px; line-height: 1.2; }
    .detail .org { color: var(--muted); font-size: 12px; margin-bottom: 10px; }
    .chips { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 9px; }
    .chip { border: 1px solid var(--line); border-radius: 5px; padding: 4px 6px; color: var(--soft); font-size: 11px; background: rgba(255,255,255,0.04); }
    .note { color: #c5cfdf; font-size: 12px; line-height: 1.48; }
    .role-list {
      overflow: auto;
      padding: 8px;
      display: grid;
      align-content: start;
      gap: 5px;
    }
    .role-row {
      border: 1px solid transparent;
      border-radius: 6px;
      padding: 8px;
      cursor: pointer;
      background: rgba(255,255,255,0.025);
      display: grid;
      gap: 3px;
    }
    .role-row:hover, .role-row.hot {
      border-color: rgba(118, 181, 255, 0.54);
      background: rgba(74, 130, 200, 0.16);
    }
    .role-row.selected {
      border-color: rgba(65, 215, 200, 0.74);
      background: rgba(65, 215, 200, 0.13);
    }
    .role-line { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; }
    .role-line span:first-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .role-meta { color: var(--muted); font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .timeline {
      border-top: 1px solid var(--line);
      background: rgba(9, 13, 20, 0.88);
      padding: 8px 14px 10px;
      display: grid;
      gap: 5px;
    }
    .timeline-row { display: grid; grid-template-columns: 74px minmax(0, 1fr) 74px auto; align-items: center; gap: 9px; }
    .timeline-row span { color: var(--muted); font-size: 11px; }
    .range-wrap { position: relative; height: 24px; display: flex; align-items: center; }
    .range-track, .range-fill { position: absolute; left: 0; right: 0; height: 4px; border-radius: 3px; pointer-events: none; }
    .range-track { background: rgba(255,255,255,0.10); }
    .range-fill { background: linear-gradient(90deg, #558ee8, #39c6bd); }
    .range-wrap input[type="range"] { position: absolute; width: 100%; margin: 0; appearance: none; background: transparent; pointer-events: none; }
    .range-wrap input[type="range"]::-webkit-slider-thumb { appearance: none; pointer-events: auto; cursor: pointer; width: 14px; height: 14px; border-radius: 50%; background: #e6f0ff; border: 3px solid #4285d8; }
    .range-wrap input[type="range"]::-moz-range-thumb { pointer-events: auto; cursor: pointer; width: 14px; height: 14px; border-radius: 50%; background: #e6f0ff; border: 3px solid #4285d8; }
    .today { color: var(--accent-2); }
    .tl-ticks { position: relative; height: 17px; margin: 0 2px; }
    .tl-ticks .tm {
      position: absolute;
      transform: translateX(-50%);
      font-size: 10px;
      color: #7da0e0;
      white-space: nowrap;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .tl-ticks .tm .tmk { width: 1px; height: 5px; background: rgba(120,160,220,0.45); margin-bottom: 1px; }
    .tl-ticks .tm.today { color: var(--accent-2); }
    .tl-ticks .tm.today .tmk { background: rgba(65,215,200,0.7); }
    @media (max-width: 720px) {
      body { overflow: auto; }
      .app { height: auto; min-height: 100vh; grid-template-columns: 1fr; grid-template-rows: minmax(500px, 70vh) auto; }
      .sidebar { max-height: none; border-right: 0; border-top: 1px solid var(--line); }
      .workspace { grid-template-columns: 1fr; grid-template-rows: minmax(460px, 1fr) 360px; }
      .side-panel { border-left: 0; border-top: 1px solid var(--line); }
    }
  </style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="brand">
      <h1>Job Search Space</h1>
      <span class="count" id="job-count">0 roles</span>
    </div>

    <details>
      <summary>Colour</summary>
      <div class="section">
        <div class="row" data-group="color">
          <button class="btn active" data-action="color" data-mode="fit">Fit</button>
          <button class="btn" data-action="color" data-mode="probability">P(int)</button>
          <button class="btn" data-action="color" data-mode="salary">Salary</button>
          <button class="btn" data-action="color" data-mode="status">Status</button>
          <button class="btn" data-action="color" data-mode="location">Location</button>
        </div>
      </div>
    </details>

    <details open>
      <summary>Filter</summary>
      <div class="section">
        <div class="field">
          <label for="filter-text"><span>Search text</span><span id="visible-count">0 visible</span></label>
          <input id="filter-text" type="text" placeholder="director, GoA, Calgary">
        </div>
        <div class="field">
          <label for="fit-floor"><span>Fit floor</span><span id="fit-floor-value">1/5</span></label>
          <input id="fit-floor" type="range" min="1" max="5" step="1" value="1">
        </div>
        <div class="field">
          <label><span>Salary</span><span id="salary-range-value">$55K – $220K</span></label>
          <div class="range-wrap">
            <div class="range-track"></div>
            <div class="range-fill" id="salary-fill"></div>
            <input id="salary-min" type="range" min="55" max="220" step="5" value="55">
            <input id="salary-max" type="range" min="55" max="220" step="5" value="220">
          </div>
        </div>
        <div class="row" id="status-pills"></div>
        <div class="row">
          <button class="btn compact" data-action="clear-status">Clear status</button>
          <button class="btn compact" data-action="reset-filters">Reset filters</button>
        </div>
      </div>
    </details>

    <details open>
      <summary>Focus</summary>
      <div class="section">
        <div class="field">
          <label for="sx"><span>X sector</span><span id="sx-value"></span></label>
          <input id="sx" data-focus="sx" type="range" min="1" max="5" step="0.1">
        </div>
        <div class="field">
          <label for="sy"><span>Y innovation</span><span id="sy-value"></span></label>
          <input id="sy" data-focus="sy" type="range" min="1" max="5" step="0.1">
        </div>
        <div class="field">
          <label for="sz"><span>Z seniority</span><span id="sz-value"></span></label>
          <input id="sz" data-focus="sz" type="range" min="1" max="5" step="0.1">
        </div>
        <div class="field">
          <label for="radius"><span>Radius</span><span id="radius-value"></span></label>
          <input id="radius" data-focus="radius" type="range" min="0.3" max="2.0" step="0.1" value="1">
        </div>
        <div class="field">
          <label for="boundary"><span>Boundary cloud</span><span id="boundary-value"></span></label>
          <input id="boundary" data-focus="boundary" type="range" min="1" max="10" step="1" value="5">
        </div>
        <div class="row">
          <button class="btn compact" data-action="copy-focus">Copy focus</button>
          <button class="btn compact" data-action="save-preset">Save preset</button>
        </div>
        <div class="field">
          <input id="preset-name" type="text" placeholder="Preset name">
        </div>
        <div class="row" id="preset-list"></div>
      </div>
    </details>

    <details open>
      <summary>View</summary>
      <div class="section">
        <div class="row">
          <button class="btn active" data-action="toggle-labels">Labels</button>
          <button class="btn" data-action="toggle-connections">Connections</button>
          <button class="btn" data-action="toggle-salary-rings">Salary rings</button>
          <button class="btn" data-action="toggle-map">Map</button>
        </div>
        <div class="row">
          <button class="btn compact" data-action="reset-camera">Reset camera</button>
          <button class="btn compact" data-action="screenshot">Screenshot</button>
        </div>
      </div>
    </details>
  </aside>

  <main class="main">
    <header class="topbar">
      <div>
        <div class="title">Sector x Innovation x Seniority</div>
        <div class="axis-readout" id="axis-readout"></div>
      </div>
      <div class="axis-readout" id="health-readout">Three.js renderer ready</div>
    </header>

    <section class="workspace">
      <div class="scene-wrap" id="scene-wrap">
        <div id="scene3d" aria-label="3D job search cloud"></div>
        <div class="label-layer" id="label-layer"></div>
        <div class="tooltip" id="tooltip"></div>
        <div class="map-overlay" id="map-overlay">
          <div class="map-head">
            <span>Location map - west to east</span>
            <button class="btn compact" data-action="toggle-map">Close</button>
          </div>
          <svg id="location-map" viewBox="0 0 1608.4 644" role="img" aria-label="Canada province map"></svg>
        </div>
      </div>

      <aside class="side-panel">
        <div class="detail" id="detail"></div>
        <div class="role-list" id="role-list"></div>
      </aside>
    </section>

    <footer class="timeline">
      <div class="timeline-row">
        <span id="tl-start-label"></span>
        <div class="range-wrap">
          <div class="range-track"></div>
          <div class="range-fill" id="timeline-fill"></div>
          <input id="tl-start" type="range" min="0" max="100" value="0">
          <input id="tl-end" type="range" min="0" max="100" value="100">
        </div>
        <span id="tl-end-label"></span>
        <button class="btn compact" data-action="reset-timeline">Reset</button>
      </div>
      <div class="timeline-row">
        <span></span>
        <div class="tl-ticks" id="tl-ticks"></div>
        <span></span>
        <span></span>
      </div>
    </footer>
  </main>
</div>

<script id="job-data" type="application/json">__PAYLOAD__</script>
<script>
(function () {
  "use strict";

  const DATA = JSON.parse(document.getElementById("job-data").textContent);
  const JOBS = DATA.jobs;
  const STATUS_COLORS = DATA.statusColors;
  const FIT_COLORS = DATA.fitColors;
  const AXIS_LABELS = DATA.axisLabels;
  const BOUNDARY_LABELS = ["", "Very strict", "Strict", "Fairly strict", "Moderate", "Medium", "Fairly loose", "Loose", "Very loose", "Very loose", "Fuzzy"];
  const LOCATION_COLORS = { AB: "#44c7e8", BC: "#7dd3a8", SK: "#e7c85d", MB: "#f59e0b", ON: "#a887ff", QC: "#f472b6", Remote: "#d1d5db" };
  const OUTCOMES = ["pending", "offer", "no-offer", "waitlisted"];
  const OUTCOME_COLORS = { pending: "#e0b15b", offer: "#46c08a", "no-offer": "#d73027", waitlisted: "#a78bfa" };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
  const lerp = (a, b, t) => a + (b - a) * t;
  const dateMs = (iso) => new Date(iso + "T00:00:00").getTime();
  const fmtDate = (iso) => iso ? iso.slice(2) : "-";

  const state = {
    colorMode: "fit",
    filters: { text: "", fitFloor: 1, salaryMin: 55, salaryMax: 220, statuses: new Set(Object.keys(STATUS_COLORS)), province: null },
    focus: { sx: DATA.center.x, sy: DATA.center.y, sz: DATA.center.z, radius: 1, boundary: 5 },
    timeline: { startPct: 0, endPct: 100, startDate: null, endDate: null },
    showLabels: true,
    showConnections: false,
    showSalaryRings: false,
    showMap: false,
    hoveredId: null,
    selectedId: JOBS[0] ? JOBS[0].id : null,
  };

  let renderer, scene, camera;
  let jobGroup, ringGroup, lineGroup, focusPoints, focusOutline;
  let raycaster, pointer, sceneWrap, sceneEl, labelLayer, tooltip;
  let width = 1, height = 1;
  let dirtyScene = true;
  let dirtyFilter = true;
  let dirtyFocus = true;
  let dirtyMap = true;
  let dirtyList = true;
  let dragging = false;
  let dragStart = { x: 0, y: 0, theta: 0, phi: 0 };
  let orbit = { theta: Math.PI * 0.25, phi: Math.PI * 0.34, radius: 9.2 };
  const jobObjects = new Map();
  const labelEls = new Map();
  const axisLabels = [];
  const jobById = new Map(JOBS.map((j) => [j.id, j]));
  const visibleIds = new Set();
  // Interview outcomes — seeded from data, mutable during session (not persisted).
  const jobOutcomes = new Map();
  JOBS.forEach((j) => { if (j.outcome !== null && j.outcome !== undefined) jobOutcomes.set(j.id, j.outcome || "pending"); });

  function cycleOutcome(id) {
    const cur = jobOutcomes.get(id) || "pending";
    const next = OUTCOMES[(OUTCOMES.indexOf(cur) + 1) % OUTCOMES.length];
    jobOutcomes.set(id, next);
    renderDetail();
  }

  const allDates = [...new Set(JOBS.map((j) => j.date).filter(Boolean))].sort();
  const minDate = allDates[0] || "2026-01-01";
  const maxDate = allDates[allDates.length - 1] || minDate;

  function worldFromJob(job) {
    return new THREE.Vector3((job.x - 3) * -1.82, (job.z - 3) * 1.58, (job.y - 3) * -1.82);
  }

  function colorFor(job) {
    if (state.colorMode === "fit") return FIT_COLORS[clamp(job.fit, 1, 5) - 1];
    if (state.colorMode === "probability") {
      const t = clamp(job.p / 35, 0, 1);
      return rgbToHex(lerp(190, 70, t), lerp(84, 204, t), lerp(84, 128, t));
    }
    if (state.colorMode === "salary") {
      const t = clamp((job.sal - 55) / 165, 0, 1);
      return rgbToHex(lerp(92, 250, t), lerp(170, 204, t), lerp(255, 90, t));
    }
    if (state.colorMode === "location") return LOCATION_COLORS[job.province] || "#d1d5db";
    return STATUS_COLORS[job.status] || "#9aa7bd";
  }

  function rgbToHex(r, g, b) {
    return "#" + [r, g, b].map((v) => clamp(Math.round(v), 0, 255).toString(16).padStart(2, "0")).join("");
  }

  function baseScale(job) {
    if (job.status === "Interview") return 0.18;
    if (job.status === "Target") return 0.12;
    return 0.135;
  }

  function jobVisible(job) {
    const f = state.filters;
    if (!f.statuses.has(job.status)) return false;
    if (job.fit < f.fitFloor) return false;
    if (job.sal < f.salaryMin || job.sal > f.salaryMax) return false;
    if (state.timeline.startDate && job.date < state.timeline.startDate) return false;
    if (state.timeline.endDate && job.date > state.timeline.endDate) return false;
    if (f.province && job.province !== f.province) return false;
    if (f.text) {
      const hay = (job.label + " " + job.org + " " + job.status + " " + job.place + " " + (job.note || "")).toLowerCase();
      if (!hay.includes(f.text)) return false;
    }
    return true;
  }

  function initThree() {
    if (!window.THREE) {
      $("#health-readout").textContent = "Three.js failed to load";
      return;
    }
    sceneWrap = $("#scene-wrap");
    sceneEl = $("#scene3d");
    labelLayer = $("#label-layer");
    tooltip = $("#tooltip");
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x080c12);

    camera = new THREE.PerspectiveCamera(48, 1, 0.1, 100);
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    sceneEl.appendChild(renderer.domElement);

    raycaster = new THREE.Raycaster();
    raycaster.params.Points.threshold = 0.08;
    pointer = new THREE.Vector2();

    const amb = new THREE.AmbientLight(0xffffff, 0.68);
    scene.add(amb);
    const key = new THREE.DirectionalLight(0xdcebff, 1.1);
    key.position.set(3, 6, 5);
    scene.add(key);

    jobGroup = new THREE.Group();
    ringGroup = new THREE.Group();
    lineGroup = new THREE.Group();
    scene.add(jobGroup, ringGroup, lineGroup);

    buildGrid();
    buildJobs();
    rebuildFocusCloud();
    resizeScene();
    resetCamera();

    const ro = new ResizeObserver(resizeScene);
    ro.observe(sceneWrap);
    window.addEventListener("resize", resizeScene);
    sceneEl.addEventListener("pointerdown", onPointerDown);
    sceneEl.addEventListener("pointermove", onPointerMove);
    sceneEl.addEventListener("pointerup", onPointerUp);
    sceneEl.addEventListener("pointercancel", onPointerUp);
    sceneEl.addEventListener("mouseleave", () => { if (!dragging) setHover(null); });
    sceneEl.addEventListener("wheel", onWheel, { passive: false });
    sceneEl.addEventListener("click", onSceneClick);

    requestAnimationFrame(animate);
  }

  function buildGrid() {
    const matGrid = new THREE.LineBasicMaterial({ color: 0x334057, transparent: true, opacity: 0.55 });
    const matAxis = new THREE.LineBasicMaterial({ color: 0x7898c8, transparent: true, opacity: 0.9 });
    const lines = [];
    for (let i = 1; i <= 5; i++) {
      const a = worldFromJob({ x: i, y: 1, z: 1 });
      const b = worldFromJob({ x: i, y: 5, z: 1 });
      const c = worldFromJob({ x: 1, y: i, z: 1 });
      const d = worldFromJob({ x: 5, y: i, z: 1 });
      lines.push(a, b, c, d);
    }
    const geo = new THREE.BufferGeometry().setFromPoints(lines);
    scene.add(new THREE.LineSegments(geo, matGrid));

    const axisPts = [
      worldFromJob({ x: 1, y: 1, z: 1 }), worldFromJob({ x: 5.35, y: 1, z: 1 }),
      worldFromJob({ x: 1, y: 1, z: 1 }), worldFromJob({ x: 1, y: 5.35, z: 1 }),
      worldFromJob({ x: 1, y: 1, z: 1 }), worldFromJob({ x: 1, y: 1, z: 5.35 }),
    ];
    scene.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(axisPts), matAxis));

    buildAxisDecor();
  }

  // Axis tick marks (3D line segments) + HTML tick/title labels projected each frame.
  function buildAxisDecor() {
    const tickMat = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.4 });
    const tickPts = [];
    const tick = 0.16; // tick half-length in scene units

    for (let i = 1; i <= 5; i++) {
      // Store the TICK world position (not an offset) — screen-space offset applied in updateAxisLabels
      let p = worldFromJob({ x: i, y: 1, z: 1 });
      tickPts.push(new THREE.Vector3(p.x, p.y - tick, p.z), new THREE.Vector3(p.x, p.y + tick, p.z));
      addAxisLabel(new THREE.Vector3(p.x, p.y, p.z), AXIS_LABELS.x[i], "axis-tick axis-tick-x");

      p = worldFromJob({ x: 1, y: i, z: 1 });
      tickPts.push(new THREE.Vector3(p.x, p.y, p.z - tick), new THREE.Vector3(p.x, p.y, p.z + tick));
      addAxisLabel(new THREE.Vector3(p.x, p.y, p.z), AXIS_LABELS.y[i], "axis-tick axis-tick-y");

      p = worldFromJob({ x: 1, y: 1, z: i });
      tickPts.push(new THREE.Vector3(p.x - tick, p.y, p.z), new THREE.Vector3(p.x + tick, p.y, p.z));
      addAxisLabel(new THREE.Vector3(p.x, p.y, p.z), AXIS_LABELS.z[i], "axis-tick axis-tick-z");
    }
    scene.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(tickPts), tickMat));

    // Axis titles — positioned just past the end of each axis line (5.35), not far beyond
    addAxisLabel(worldFromJob({ x: 5.5, y: 1, z: 1 }), "X · Sector", "axis-title");
    addAxisLabel(worldFromJob({ x: 1, y: 5.5, z: 1 }), "Y · Innovation", "axis-title");
    addAxisLabel(worldFromJob({ x: 1, y: 1, z: 5.5 }), "Z · Seniority", "axis-title");
  }

  function addAxisLabel(worldPos, text, cls) {
    const el = document.createElement("div");
    el.className = "axis-label " + cls;
    el.textContent = text;
    labelLayer.appendChild(el);
    axisLabels.push({ el, pos: worldPos });
  }

  function updateAxisLabels() {
    if (!camera || !axisLabels.length) return;
    for (const a of axisLabels) {
      const v = a.pos.clone().project(camera);
      if (v.z > 1) { a.el.style.display = "none"; continue; }
      a.el.style.display = "";
      const sx = (v.x * 0.5 + 0.5) * width;
      const sy = (-v.y * 0.5 + 0.5) * height;
      // Screen-space offset: Y and Z ticks always go LEFT of the projected tick (right-aligned, -16px gap)
      // X ticks hang 10px below (centered). Titles stay centered.
      if (a.el.classList.contains("axis-tick-z") || a.el.classList.contains("axis-tick-y")) {
        a.el.style.left = (sx - 16).toFixed(1) + "px";
        a.el.style.top  = sy.toFixed(1) + "px";
        a.el.style.transform = "translate(-100%, -50%)";
        a.el.style.textAlign = "right";
      } else if (a.el.classList.contains("axis-tick-x")) {
        a.el.style.left = sx.toFixed(1) + "px";
        a.el.style.top  = (sy + 16).toFixed(1) + "px";
        a.el.style.transform = "translate(-50%, 0)";
        a.el.style.textAlign = "center";
      } else {
        a.el.style.left = sx.toFixed(1) + "px";
        a.el.style.top  = sy.toFixed(1) + "px";
        a.el.style.transform = "translate(-50%, -50%)";
        a.el.style.textAlign = "center";
      }
    }
  }

  function buildJobs() {
    const sphere = new THREE.SphereGeometry(1, 24, 18);
    const diamond = new THREE.OctahedronGeometry(1, 0);
    const target = new THREE.TetrahedronGeometry(1, 0);
    JOBS.forEach((job) => {
      const geom = job.status === "Interview" ? diamond : job.status === "Target" ? target : sphere;
      const mat = new THREE.MeshStandardMaterial({
        color: colorFor(job),
        roughness: 0.48,
        metalness: 0.08,
        emissive: 0x000000,
      });
      const mesh = new THREE.Mesh(geom, mat);
      mesh.position.copy(worldFromJob(job));
      mesh.scale.setScalar(baseScale(job));
      mesh.userData.jobId = job.id;
      jobGroup.add(mesh);
      jobObjects.set(job.id, mesh);

      const label = document.createElement("div");
      label.className = "job-label";
      label.textContent = job.label;
      labelLayer.appendChild(label);
      labelEls.set(job.id, label);
    });
  }

  function spherePointCloud(cx, cy, cz, radius, boundary) {
    const strict = 11 - boundary;
    const n = Math.round(260 + strict * 32);
    const disp = Math.max(0, (10 - strict) / 10 * 1.4); // more scatter at fuzzy end
    const pts = new Float32Array(n * 3);
    const gr = (1 + Math.sqrt(5)) / 2;
    for (let i = 0; i < n; i++) {
      const theta = Math.acos(1 - 2 * (i + 0.5) / n);
      const phi = 2 * Math.PI * i / gr;
      const jitter = 1 + disp * (Math.cos(i * 7.389 + theta) * 0.6 + Math.sin(i * 2.718 + phi) * 0.4);
      const x = cx + radius * jitter * Math.sin(theta) * Math.cos(phi);
      const y = cy + radius * jitter * Math.sin(theta) * Math.sin(phi);
      const z = cz + radius * 0.8 * jitter * Math.cos(theta);
      const v = worldFromJob({ x, y, z });
      pts[i * 3] = v.x;
      pts[i * 3 + 1] = v.y;
      pts[i * 3 + 2] = v.z;
    }
    return pts;
  }

  function rebuildFocusCloud() {
    const f = state.focus;
    const positions = spherePointCloud(f.sx, f.sy, f.sz, f.radius, f.boundary);
    if (focusPoints) scene.remove(focusPoints);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const alpha = 0.32 + f.boundary * 0.028; // brighter dots
    const mat = new THREE.PointsMaterial({
      color: 0x74b8ff,
      size: 0.085, // larger dots — were barely visible at 0.045
      transparent: true,
      opacity: alpha,
      depthWrite: false,
    });
    focusPoints = new THREE.Points(geo, mat);
    scene.add(focusPoints);
    rebuildFocusOutline();
    dirtyFocus = false;
  }

  function rebuildFocusOutline() {
    if (focusOutline) scene.remove(focusOutline);
    const f = state.focus;
    const pts = [];
    const lat = 6, lon = 12;
    for (let a = 1; a < lat; a++) {
      const theta = Math.PI * a / lat;
      for (let b = 0; b < lon; b++) {
        const p1 = sphereSurface(f, theta, 2 * Math.PI * b / lon);
        const p2 = sphereSurface(f, theta, 2 * Math.PI * (b + 1) / lon);
        pts.push(p1, p2);
      }
    }
    for (let b = 0; b < lon; b++) {
      const phi = 2 * Math.PI * b / lon;
      for (let a = 0; a < lat; a++) {
        pts.push(sphereSurface(f, Math.PI * a / lat, phi), sphereSurface(f, Math.PI * (a + 1) / lat, phi));
      }
    }
    const mat = new THREE.LineBasicMaterial({ color: 0x79b8ff, transparent: true, opacity: 0.07 }); // lighter frame
    focusOutline = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), mat);
    scene.add(focusOutline);
  }

  function sphereSurface(f, theta, phi) {
    return worldFromJob({
      x: f.sx + f.radius * Math.sin(theta) * Math.cos(phi),
      y: f.sy + f.radius * Math.sin(theta) * Math.sin(phi),
      z: f.sz + f.radius * 0.8 * Math.cos(theta),
    });
  }

  function updateCamera() {
    const eps = 0.05;
    orbit.phi = clamp(orbit.phi, eps, Math.PI - eps);
    camera.position.set(
      orbit.radius * Math.sin(orbit.phi) * Math.cos(orbit.theta),
      orbit.radius * Math.cos(orbit.phi),
      orbit.radius * Math.sin(orbit.phi) * Math.sin(orbit.theta)
    );
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();
  }

  function resetCamera() {
    orbit = { theta: Math.PI * 0.25, phi: Math.PI * 0.34, radius: 9.2 };
    updateCamera();
  }

  function resizeScene() {
    if (!renderer || !sceneWrap) return;
    const rect = sceneWrap.getBoundingClientRect();
    width = Math.max(1, Math.floor(rect.width));
    height = Math.max(1, Math.floor(rect.height));
    renderer.setSize(width, height, true);  // true = also update canvas CSS style so HiDPI doesn't misalign labels
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }

  function onPointerDown(ev) {
    if (ev.button !== 0) return;
    dragging = true;
    sceneEl.classList.add("dragging");
    sceneEl.setPointerCapture(ev.pointerId);
    dragStart = { x: ev.clientX, y: ev.clientY, theta: orbit.theta, phi: orbit.phi };
  }

  function onPointerMove(ev) {
    const rect = sceneEl.getBoundingClientRect();
    pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -(((ev.clientY - rect.top) / rect.height) * 2 - 1);

    if (dragging) {
      const dx = ev.clientX - dragStart.x;
      const dy = ev.clientY - dragStart.y;
      orbit.theta = dragStart.theta + dx * 0.008;
      orbit.phi = dragStart.phi - dy * 0.008;
      updateCamera();
      return;
    }
    raycastHover(ev);
  }

  function onPointerUp(ev) {
    dragging = false;
    sceneEl.classList.remove("dragging");
    try { sceneEl.releasePointerCapture(ev.pointerId); } catch (err) {}
  }

  function onWheel(ev) {
    ev.preventDefault();
    orbit.radius = clamp(orbit.radius + ev.deltaY * 0.007, 4.5, 26);
    updateCamera();
  }

  function raycastHover(ev) {
    if (!raycaster || !camera) return;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(Array.from(jobObjects.values()).filter((mesh) => mesh.visible), false);
    const id = hits.length ? hits[0].object.userData.jobId : null;
    setHover(id, ev);
  }

  function onSceneClick(ev) {
    if (dragging) return;
    if (state.hoveredId) selectJob(state.hoveredId);
  }

  function setHover(id, ev) {
    if (state.hoveredId === id) {
      if (id && ev) moveTooltip(ev);
      return;
    }
    state.hoveredId = id;
    dirtyMap = true;
    dirtyList = true;
    if (id && ev) showTooltip(id, ev);
    else tooltip.style.display = "none";
  }

  function selectJob(id) {
    if (!id) return;
    state.selectedId = id;
    dirtyList = true;
    dirtyMap = true;
    renderDetail();
  }

  function showTooltip(id, ev) {
    const job = jobById.get(id);
    if (!job) return;
    tooltip.innerHTML =
      "<strong>" + escapeHtml(job.label) + "</strong>" +
      escapeHtml(job.org) + "<br>" +
      "Fit " + job.fit + "/5 | P(int) " + job.p + "% | $" + job.sal + "K<br>" +
      escapeHtml(job.status + " | " + job.place);
    tooltip.style.display = "block";
    moveTooltip(ev);
  }

  function moveTooltip(ev) {
    const rect = sceneWrap.getBoundingClientRect();
    const left = clamp(ev.clientX - rect.left + 14, 8, rect.width - 328);
    const top = clamp(ev.clientY - rect.top + 14, 8, rect.height - 132);
    tooltip.style.left = left + "px";
    tooltip.style.top = top + "px";
  }

  function escapeHtml(text) {
    return String(text || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function applyFilters() {
    visibleIds.clear();
    JOBS.forEach((job) => { if (jobVisible(job)) visibleIds.add(job.id); });
    dirtyFilter = false;
    dirtyScene = true;
    dirtyMap = true;
    dirtyList = true;
    $("#visible-count").textContent = visibleIds.size + " visible";
  }

  function syncSceneState(time) {
    if (dirtyFilter) applyFilters();
    if (dirtyFocus) rebuildFocusCloud();
    const rebuildOverlays = dirtyScene;

    JOBS.forEach((job) => {
      const mesh = jobObjects.get(job.id);
      const visible = visibleIds.has(job.id);
      const hot = job.id === state.hoveredId || job.id === state.selectedId;
      const pulse = hot ? 1 + Math.sin(time * 0.006) * 0.08 + 0.18 : 1;
      mesh.visible = visible;
      mesh.material.color.set(colorFor(job));
      mesh.material.emissive.set(hot ? 0x17395f : 0x000000);
      mesh.scale.setScalar(baseScale(job) * pulse);

      const label = labelEls.get(job.id);
      if (label) {
        label.classList.toggle("visible", visible && (state.showLabels || hot));
      }
    });
    if (rebuildOverlays) {
      renderConnections();
      renderSalaryRings();
      dirtyScene = false;
    }
  }

  function renderConnections() {
    lineGroup.clear();
    if (!state.showConnections) return;
    const interviews = JOBS.filter((j) => j.status === "Interview" && visibleIds.has(j.id));
    const targets = JOBS.filter((j) => j.status !== "Interview" && visibleIds.has(j.id));
    const pts = [];
    interviews.forEach((iv) => {
      let best = null, bestD = Infinity;
      targets.forEach((t) => {
        const d = Math.hypot(iv.x - t.x, iv.y - t.y, iv.z - t.z);
        if (d < bestD) { best = t; bestD = d; }
      });
      if (best) pts.push(worldFromJob(iv), worldFromJob(best));
    });
    if (!pts.length) return;
    const mat = new THREE.LineBasicMaterial({ color: 0xffcf6b, transparent: true, opacity: 0.5 });
    lineGroup.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), mat));
  }

  function renderSalaryRings() {
    ringGroup.clear();
    if (!state.showSalaryRings) return;
    JOBS.forEach((job) => {
      if (!visibleIds.has(job.id)) return;
      const r = 0.18 + clamp((job.sal - 55) / 170, 0, 1) * 0.26;
      const geom = new THREE.RingGeometry(r, r + 0.018, 36);
      const mat = new THREE.MeshBasicMaterial({ color: colorFor(job), transparent: true, opacity: 0.26, side: THREE.DoubleSide });
      const ring = new THREE.Mesh(geom, mat);
      ring.position.copy(worldFromJob(job));
      ring.userData.billboard = true;
      ringGroup.add(ring);
    });
  }

  function updateLabels() {
    if (!camera) return;
    const zoomOpacity = Math.max(0, Math.min(1, (18 - orbit.radius) / 9));

    // When hovering, find the 5 nearest visible jobs in screen space
    const nearbyIds = new Set();
    if (state.hoveredId) {
      const hj = jobById.get(state.hoveredId);
      if (hj) {
        const hv = worldFromJob(hj).clone().project(camera);
        const hsx = (hv.x * 0.5 + 0.5) * width;
        const hsy = (-hv.y * 0.5 + 0.5) * height;
        const dists = [];
        JOBS.forEach((j) => {
          if (j.id === state.hoveredId || !visibleIds.has(j.id)) return;
          const v = worldFromJob(j).clone().project(camera);
          if (v.z > 1) return;
          const sx = (v.x * 0.5 + 0.5) * width;
          const sy = (-v.y * 0.5 + 0.5) * height;
          dists.push({ id: j.id, d: (sx - hsx) ** 2 + (sy - hsy) ** 2 });
        });
        dists.sort((a, b) => a.d - b.d);
        dists.slice(0, 5).forEach((e) => nearbyIds.add(e.id));
      }
    }

    JOBS.forEach((job) => {
      const label = labelEls.get(job.id);
      if (!label) return;
      const isHot    = job.id === state.hoveredId || job.id === state.selectedId;
      const isNearby = nearbyIds.has(job.id);
      const isGlobal = label.classList.contains("visible"); // Labels-toggle is on

      // Decide whether to show this label at all
      if (!isHot && !isNearby && !isGlobal) { label.style.opacity = "0"; return; }
      if (!isHot && !isNearby && zoomOpacity <= 0) { label.style.opacity = "0"; return; }

      const v = worldFromJob(job).clone().project(camera);
      if (v.z > 1) { label.style.opacity = "0"; return; }
      const sx = (v.x * 0.5 + 0.5) * width;
      const sy = (-v.y * 0.5 + 0.5) * height;
      label.style.left = sx.toFixed(1) + "px";
      label.style.top  = (sy + (isHot ? 18 : 12)).toFixed(1) + "px";
      label.style.transform = "translate(-50%, -100%)";

      if (isHot) {
        label.style.opacity = "0.97";
        label.style.background   = "rgba(30,50,90,0.92)";
        label.style.borderColor  = "rgba(100,180,255,0.40)";
      } else if (isNearby) {
        label.style.opacity = "0.70";
        label.style.background   = "rgba(18,28,50,0.82)";
        label.style.borderColor  = "rgba(80,150,220,0.22)";
      } else {
        label.style.opacity = (zoomOpacity * 0.88).toFixed(2);
        label.style.background   = "rgba(9,13,20,0.78)";
        label.style.borderColor  = "rgba(255,255,255,0.10)";
      }
    });
  }

  function animate(time) {
    requestAnimationFrame(animate);
    syncSceneState(time || 0);
    ringGroup.children.forEach((ring) => { if (ring.userData.billboard) ring.lookAt(camera.position); });
    updateLabels();
    updateAxisLabels();
    if (dirtyMap) renderMapState();
    if (dirtyList) renderListState();
    renderer.render(scene, camera);
  }

  function renderDetail() {
    const job = jobById.get(state.selectedId) || JOBS[0];
    const el = $("#detail");
    if (!job) {
      el.innerHTML = "<h2>No role selected</h2>";
      return;
    }
    const stars = "★".repeat(job.fit) + "☆".repeat(5 - job.fit);
    const salRange = (job.sal_min && job.sal_max && job.sal_min !== job.sal_max)
      ? "$" + job.sal_min + "K - $" + job.sal_max + "K"
      : "$" + job.sal + "K";
    const submitted = job.date ? fmtDate(job.date) : "-";
    const hasOutcome = jobOutcomes.has(job.id);
    const outcome = jobOutcomes.get(job.id) || "pending";
    el.innerHTML =
      "<h2>" + escapeHtml(job.label) + "</h2>" +
      "<div class=\"org\">" + escapeHtml(job.org) + " | " + escapeHtml(job.place) + "</div>" +
      "<div class=\"chips\">" +
      "<span class=\"chip\">Status: " + escapeHtml(job.status) + "</span>" +
      "<span class=\"chip\">Fit: " + stars + " (" + job.fit + "/5)</span>" +
      "<span class=\"chip\">P(int): " + job.p + "%</span>" +
      "<span class=\"chip\">Salary: $" + job.sal + "K</span>" +
      "<span class=\"chip\">Range: " + salRange + "</span>" +
      "<span class=\"chip\">Submitted: " + escapeHtml(submitted) + "</span>" +
      (hasOutcome
        ? "<button class=\"chip outcome-chip\" data-action=\"cycle-outcome\" data-job-id=\"" + job.id +
          "\" title=\"Click to cycle outcome\" style=\"color:" + OUTCOME_COLORS[outcome] + ";cursor:pointer\">Outcome: " + escapeHtml(outcome) + "</button>"
        : "") +
      "</div>" +
      "<div class=\"note\">" + escapeHtml(job.note || "No note recorded.") + "</div>";
  }

  function renderRoleList() {
    const list = $("#role-list");
    list.innerHTML = "";
    JOBS.forEach((job) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "role-row";
      row.dataset.jobId = job.id;
      row.innerHTML =
        "<div class=\"role-line\"><span>" + escapeHtml(job.label) + "</span><span>" + job.fit + "/5</span></div>" +
        "<div class=\"role-meta\">" + escapeHtml(job.org) + " | " + escapeHtml(job.status) + " | " + escapeHtml(job.place) + "</div>";
      row.addEventListener("mouseenter", () => setHover(job.id));
      row.addEventListener("mouseleave", () => setHover(null));
      row.addEventListener("click", () => selectJob(job.id));
      list.appendChild(row);
    });
  }

  function renderListState() {
    $$(".role-row").forEach((row) => {
      const id = row.dataset.jobId;
      row.style.display = visibleIds.has(id) ? "" : "none";
      row.classList.toggle("hot", id === state.hoveredId);
      row.classList.toggle("selected", id === state.selectedId);
    });
    dirtyList = false;
  }

  // Real province SVG paths from EHT/canadaGeo.ts (viewBox 1608.4 × 644)
  const CANADA_PROVINCE_PATHS = [
    {name:"Quebec",abr:"QC",d:"M1396.8,394.3L1426.5,409.2L1429.7,416.8L1419.7,417.7L1395.1,407.9L1378.1,393.6L1388.8,393ZM1514.1,347.2L1486.1,351.3L1479.2,359.1L1479,367.1L1477.4,363.2L1458.4,383.4L1342.7,381.5L1329.6,395.3L1325.3,409.9L1305.9,413.8L1283.2,445.4L1257.7,436.3L1282.3,446.2L1253.5,487.2L1267.4,479.4L1299,438.6L1339,415.9L1358.3,411.7L1376.7,416.2L1384.6,426.8L1377.3,423.1L1384.5,430.8L1381.7,436.9L1364.2,449.1L1352.7,442.9L1325.7,454.3L1307.2,451.8L1307.1,462.7L1295,470.6L1291.5,465.9L1277.6,488.7L1265.7,527.7L1250.8,532.4L1249.7,539.1L1190.4,539.7L1198,533.4L1196.7,522.5L1161,525.8L1138.7,504.9L1117.6,499.4L1104,476.2L1102.3,360.8L1106.1,366.8L1102.3,360.1L1102,343L1107.8,340.5L1115,354.7L1114.2,347.7L1117.9,345L1111.6,336.3L1123.1,322.4L1116.5,312.7L1117.9,303.2L1112.5,298.9L1114.1,291.6L1110.1,284.5L1113.7,282.8L1109.4,278.5L1114,275.1L1106.9,267.1L1111.3,264.1L1105.2,263.8L1102.6,252L1098.2,249.9L1134.9,231L1157.3,200.7L1157.5,176.5L1152.4,159.6L1140.7,144L1120.1,131.3L1120,120.9L1124.3,122.3L1136.3,107.9L1132.1,107.2L1134.7,98.4L1143.1,102.8L1138.9,99L1143.5,95.9L1141,92.3L1153.3,84.9L1137.3,87.8L1141.4,85.8L1135.3,77L1141.3,73.4L1133.6,70.5L1139.5,64.6L1127,66.1L1136.1,53.7L1134.3,46.1L1140.2,43.5L1130.4,37.8L1127.7,21.4L1141.2,12.1L1173.7,21L1169.2,25L1179.7,20.4L1193.7,26.6L1190.6,22.4L1209.8,15.4L1229.1,26.3L1226.1,34.7L1236.9,33.8L1240.8,39.5L1235.1,42.7L1248.5,41.6L1242.7,46.8L1248.3,47.5L1243.9,48.6L1248.4,55.1L1274.7,57.2L1278.7,65.5L1286.3,57.6L1288.9,65.4L1280.5,74L1284.2,87.7L1258.4,87.9L1285.4,93.7L1281.8,110.1L1291.4,112.5L1285.8,114.7L1289.4,117L1285.7,125.5L1279.8,118.1L1281.1,124.8L1272.8,126.6L1280.8,132L1293.3,122.6L1307.5,126.5L1310.5,133.5L1307.7,145.9L1288.9,156.7L1306.6,148.5L1314,132.4L1316.7,140.2L1311.7,147.5L1319,135.8L1319.4,152L1323.6,141.5L1339.4,135.1L1342.2,125.1L1352,131.5L1349.6,140.1L1353.9,132.5L1348.9,126.5L1354.5,124.3L1350.9,122.7L1353,119.4L1363.3,118.5L1356,115.2L1358.7,108.4L1362.6,111.4L1359.2,105L1369.4,108.4L1359.2,97.6L1369.4,96.8L1364.9,93.1L1370,82L1377.7,80.6L1371.8,81.9L1376.5,86.4L1370.8,88.3L1375.5,91.8L1372.3,103.8L1381.2,104.8L1377.7,113.8L1382.1,119.2L1371.4,121.9L1397,127.2L1386.5,129.4L1390.8,135.5L1379.6,147.1L1386.4,156.6L1394.9,157.6L1389.8,183.3L1385.1,188.3L1389.8,196.5L1385,200.5L1389.7,203.1L1387.1,207.4L1397.7,209L1392.7,213.9L1404.1,229.1L1396.3,234.1L1393.6,251.3L1356.5,248.2L1336.5,229.5L1338,247.4L1324.6,237.5L1331.8,251L1321.4,252.6L1323.5,262.6L1318.1,267.7L1324.5,276.3L1323.4,281.5L1334.1,289.4L1331.2,308.6L1338.5,307.8L1342,298.6L1345.8,303.3L1342.7,323.6L1345.7,320.2L1354.4,328.3L1367.1,324.5L1376.7,334.7L1376.8,342.8L1385.4,325L1384.3,304.1L1393.1,296.2L1398.9,310.1L1386,315.5L1393.8,325.8L1392.1,329.6L1514.1,329.6Z",cx:1300,cy:330},
    {name:"Newfoundland and Labrador",abr:"NL",d:"M1377.7,80.6L1373.5,82.8L1380.6,84.9L1372.3,90.1L1384.3,88.9L1382.8,97L1388.9,100.1L1385.2,104.1L1392.6,104.3L1386.3,108.2L1398.9,111.2L1386.6,119.1L1403.5,118L1399.9,124L1408.3,128.3L1395,140.7L1414,135.3L1407.6,143.4L1413.5,143.2L1399.6,150.3L1415.9,144.4L1418.5,148.8L1411.8,151.8L1421.9,150.6L1426.3,160.5L1414.2,164.6L1436,177L1425.9,185.8L1429.9,191.1L1415,186.3L1423.3,184.7L1413.4,185.9L1430.5,193.6L1421.6,196.3L1431.7,201L1422.8,201.1L1436.1,203L1434.2,207.9L1438.2,208.4L1433.3,209.4L1447,214.2L1443.7,217.8L1449.9,215.2L1448.4,222.7L1454.7,216L1452.1,229.2L1457.3,227L1448.4,239.8L1465,229.7L1461.6,236.3L1471.4,235.4L1461.9,247.1L1476.3,232.5L1472.2,240.4L1478.8,234.9L1480.8,244.1L1509.6,252.2L1468.7,268.1L1490.6,262.7L1458.5,276.3L1458.4,283.8L1444.8,274.7L1460,284.7L1453.6,291.6L1477.9,279.1L1482.2,271.3L1501.5,267.6L1491.6,266.9L1494.5,262.5L1508.1,264.1L1513.4,271.6L1513.8,277.4L1505.9,281.8L1510.2,282.2L1509.1,286.7L1525.8,276.1L1521,279.4L1534.7,283.3L1529.5,283.4L1538.8,295.5L1531.3,298.7L1537.9,304.4L1531.4,305.8L1539.1,310.3L1525.2,311.8L1538.9,314.7L1538.3,319.6L1530.7,316.5L1541.3,323.1L1517,346.7L1514.1,347.2L1514.1,329.6L1392.1,329.6L1393.8,325.8L1386,315.5L1398.9,310.1L1393.1,296.2L1384.3,304.1L1385.4,325L1376.8,342.8L1376.7,334.7L1367.1,324.5L1354.4,328.3L1345.7,320.2L1342.7,323.6L1344.4,300.4L1331.2,308.6L1334.1,289.4L1323.4,281.5L1324.5,276.3L1318.1,267.7L1323.5,262.6L1321.4,252.6L1331.8,251L1324.6,237.5L1338,247.4L1336.5,229.5L1356.5,248.2L1393.6,251.3L1396.3,234.1L1404.1,229.1L1392.7,213.9L1397.7,209L1387.1,207.4L1389.7,203.1L1384.4,196.8L1389.8,196.5L1385.1,188.3L1389.8,183.3L1394.9,157.6L1386.4,156.6L1379.6,147.1L1390.8,135.5L1386.5,129.4L1397,127.2L1371.4,121.9L1382.1,119.2L1377.7,113.8L1381.2,104.8L1372.3,103.8L1375.5,91.8L1370.8,88.3L1376.5,86.4L1371.8,81.9ZM1536.6,363.7L1532.5,368L1531.5,363L1532.3,370L1525.1,378.1L1518.6,403.2L1532.2,385L1530.9,391.8L1544.2,390.8L1534.3,397.1L1531.2,402.2L1537.4,398.9L1532,406.8L1545.9,404.4L1547.1,410.2L1550.2,403.3L1545.6,418.3L1562.8,403.2L1562.1,411.7L1570.3,405.1L1581,412L1567.8,425.5L1578.4,429L1568,438L1589.8,431.5L1572.1,444.6L1578.3,448.1L1572.3,454L1577.2,463.8L1584,449.5L1592.5,446.6L1584.5,461.3L1587.1,467.1L1593.4,455.4L1595.7,459.8L1590.5,485.8L1578,490.2L1579.1,473.4L1567.5,484.8L1574.6,466.7L1566.2,452.5L1563.6,466L1559.8,468.6L1563.4,461.4L1555.8,466.9L1545.6,483.5L1534.6,480.9L1558.2,459.6L1546.1,457.7L1541.9,467.5L1535.7,466.3L1539,461.9L1532.4,465.6L1541.1,459.3L1535.8,459.8L1538.5,450.8L1533.3,458.6L1531.4,454.5L1531.4,460.5L1520,463.7L1492.6,457L1473.7,461.2L1471.9,452.3L1492.7,434L1475.1,433.6L1483.4,426.2L1480,431.1L1484.6,432.4L1491.2,415L1499.6,420.1L1495,415.9L1500.4,414.1L1495.9,415L1498.9,412.3L1493.5,407.8L1503.2,405.6L1498.6,399.3L1509.1,371.8L1513.2,371.1L1508.7,368.8L1517.3,362.1L1514.3,359L1521.7,349.5L1543.2,341.5L1541.7,350.5L1532.8,348.5L1539.6,354.4L1537.2,362.4Z",cx:1460,cy:190},
    {name:"British Columbia",abr:"BC",d:"M123.2,281.6L119,276L119.8,264.4L128.8,266.1L127.3,271.4L136.4,269.5L135.2,276.2L127.2,279.2L132.9,279.6L130.8,282.5L136.5,278.6L136.1,268.4L145.7,264.8L141,289L135.9,294.8L126.5,291.9L132,289.7L121.1,282ZM156.3,323L152.7,326L135,304.8L133.1,301.3L137.3,299.7L129.2,296.9L143.1,292.1L146.8,298.5L139.4,298.1L146.5,301.8L139.7,303.2L145.8,305.6L142.3,308.3L154.4,322.7ZM228.9,394L229.5,385.3L214.5,385.9L217.5,382.3L214.2,375.7L222.9,378.4L220.7,374.2L223.5,372.3L211.8,376.1L205.1,366.5L211.6,363.4L259.9,380.2L271.7,405.6L287,412.7L294.7,433.6L297.2,429.1L299.5,436L293.8,440.5L265.7,427.6L271.4,412.3L269.6,419.5L259,422L251.7,416.9L256.7,413.2L254,415.1L253.6,408.6L249.1,411.5L251.2,406.5L238.9,407.3L239.1,402L247.6,399.2L232.2,393.7ZM414.1,419.5L303.9,419.5L300,411.3L307.3,406.4L299.6,409.6L301.6,398.6L294.7,408.1L284.9,400.5L287.3,397.3L290.4,404.4L294.7,398.5L287.5,396.6L289.5,385L286.5,383.1L289.7,386.5L287.5,394.8L281.2,397.3L272.6,390.8L273.1,379.7L279.8,374.5L266.4,379.9L270.6,361.5L264.7,377.2L257.3,375.8L259.9,368.1L255,376.7L244.4,374.3L254.9,369.2L258.6,361.6L256.2,356.7L256,366L250.6,369.1L239.3,364.5L246.4,361.5L240,357.4L237.3,363.5L223.8,361.8L221.9,356.6L236.4,359.5L237.5,355.1L216.6,354.6L228.5,350L216.7,349.6L221.9,341.2L238.4,338.2L223.3,339.6L224.7,333.7L219.3,338.6L222.6,339.5L219.4,345.8L215,339.4L215.2,332.6L228,320.2L237.2,330.1L232.2,320.5L236,318.2L227.7,318.2L231.7,304.7L219.9,320.7L215.4,323.4L215.2,314.4L211.7,317.7L215,312.2L205.5,320.8L212.3,302.2L204.7,304.9L203.9,295.3L194.9,283L215.2,292.4L197.8,280.9L204.1,274.6L200.1,272.9L201.6,268.7L194.3,272.8L188.7,288.2L174.2,271.2L175.2,265L181.2,271.1L177.4,264.1L185.8,262.5L173.8,265L171.5,257.6L167.2,258.7L168.4,250.7L176.8,259.8L169.3,249.6L178.3,251.2L172.9,244.2L183,239.7L176.1,239.1L185.8,225.5L181.4,227.3L179.5,220.8L180.1,229L174,239.7L177.1,231.2L172.9,217L174.4,206.1L142.6,191.7L113.1,135.9L85.2,111.3L84,102.7L75.6,95.7L59.6,101.6L55.2,114.8L39,122.5L36.7,112.5L12,89.8L267.8,89.6L359.9,90.1L359.6,275.4L364.5,280.6L361.4,284L382.4,295.9L392.2,318.6L396.2,314.9L400.7,323.6L408.8,324.1L416.2,338.3L420.9,335.7L428.2,350.1L455.6,378.8L456.2,401.3L468.6,419.5L431.9,419.5Z",cx:260,cy:310},
    {name:"New Brunswick",abr:"NB",d:"M1295,470.6L1307.1,462.7L1307.2,451.8L1311.9,449.4L1325.7,454.3L1344.2,447.3L1354.6,452.8L1357.5,460.9L1372.4,455.2L1375.1,457.4L1370.8,468.9L1362.3,476.9L1372.8,477.1L1370.9,484L1377.2,502.9L1391.6,505.8L1378.6,517.8L1373.6,506.8L1375.7,517.9L1355.6,532.1L1348.5,530.3L1350.7,525.6L1342.7,537.3L1326.1,535.8L1324.3,521.7L1317.7,519.1L1317.9,477.7L1309.8,468.9L1295,471.8Z",cx:1340,cy:492},
    {name:"Nova Scotia",abr:"NS",d:"M1450,503.6L1440.5,510.8L1447.4,508L1439.9,518.6L1447.4,519.2L1453.6,509.6L1446.5,511.1L1454.5,500.2L1464.4,504.6L1461.6,508.9L1464.2,511.6L1448.6,522.5L1437.3,523.2L1432.5,508.7L1450,478.5L1455.4,484.4L1450.1,501.8ZM1386.7,509.7L1400.4,517.8L1411.8,516.4L1410.5,521.1L1425.7,512.9L1426.4,518.9L1438.3,524.4L1434.2,529.2L1443.1,531.4L1408.8,548.1L1393.8,548L1394.3,556.4L1388.7,554L1389.6,548.7L1386,555.4L1381.9,552.6L1382.7,561.3L1379.6,559.3L1368.7,578.2L1363,576.4L1360.3,585.5L1347.7,573.5L1348.6,559.3L1353.7,552.2L1347.3,556.7L1378.5,529.4L1384.6,540.1L1384.7,533.7L1399.2,528.6L1370.3,529.7L1384.6,510.4Z",cx:1410,cy:535},
    {name:"Saskatchewan",abr:"SK",d:"M690,89.7L690,214.7L701.6,419.5L543.1,419.5L543.1,89.9L648.3,89.7Z",cx:622,cy:260},
    {name:"Alberta",abr:"AB",d:"M468.6,419.5L456.2,401.3L457.6,387.6L451.1,372.3L439.5,363.9L420.9,335.7L416.2,338.3L408.8,324.1L400.7,323.6L396.2,314.9L392.2,318.6L382.4,295.9L361.4,284L364.5,280.6L359.6,275.4L359.9,90.1L543.1,89.9L543.1,419.5L503,419.5Z",cx:450,cy:260},
    {name:"Prince Edward Island",abr:"PE",d:"M1387.7,497.7L1386.2,490.4L1379.8,489L1387.5,477.6L1388.6,495.2L1424.7,495.8L1413.5,502.5L1415.8,509.3L1405.3,507.6L1406.5,499.9L1401,505.3L1388.8,496.7Z",cx:1403,cy:494},
    {name:"Manitoba",abr:"MB",d:"M690,89.7L822.1,89.7L824.8,109.2L818.6,118.1L829.1,128.2L833.1,125.6L830.2,143.1L833.6,126.6L852.4,127.6L865.9,169.5L857.5,182.4L891.9,171.8L925.3,183.6L815.7,304.8L815.6,419.5L701.6,419.5L690,214.7L690,92.1Z",cx:790,cy:290},
    {name:"Ontario",abr:"ON",d:"M1102.3,360.8L1101.6,466.2L1113.1,494.1L1152.5,513.5L1161,525.8L1192.1,520.4L1196.7,522.5L1198,533.4L1167.7,557.9L1149.2,567.3L1138.6,565.8L1151.7,565.9L1146.4,573.8L1136,568.2L1110.5,574.6L1097.9,589.8L1110.8,591.4L1113.5,602.1L1090.1,605.7L1085.5,611L1091.7,613.2L1069.3,609.9L1047.8,632L1036.5,627.3L1038.2,620L1049.3,618.8L1045.4,613L1048.4,602.5L1061.8,589L1061.8,566.9L1070.5,550.9L1062.7,531.5L1076.4,540.5L1073,546.7L1077.4,545.7L1076.5,551.6L1081.9,547.7L1092.2,555.4L1091.9,544.9L1100.1,546.9L1080.1,511.8L1010.9,495L1010.4,484.7L1013.9,483L1006.1,480L1009.8,470.8L1001.5,461.2L1004.9,451L986.2,449.9L975.7,426.2L942.2,419.7L943.2,431.3L936.7,436.6L941.2,426.7L938.2,423.9L933.4,438.4L929.7,440.1L933,432.1L926.1,435L922.4,446L912.1,449.7L894.4,441.9L881.4,448.2L872.9,438.8L866.8,442.9L856.2,430.7L840.9,434.2L824.1,426.2L821.6,409.6L815.7,408.4L815.7,304.8L925.3,183.6L947.4,196.5L954,209.6L999.7,229.2L994.3,239.9L1002,230.7L1050.8,234.7L1053.5,244.3L1049.1,263.3L1054.7,275.6L1055,291.4L1051.6,300.8L1066.7,320.5L1059.2,324L1066.2,322.6L1082.8,338.2L1086,348.7L1075.2,358.7L1086.6,349.4L1099.6,358.2Z",cx:970,cy:410},
  ];

  function renderMap() {
    const svg = $("#location-map");
    const parts = [];
    CANADA_PROVINCE_PATHS.forEach(({abr, d, cx, cy}) => {
      parts.push("<path class=\"province\" data-province=\"" + abr + "\" d=\"" + d + "\"></path>");
      parts.push("<text class=\"province-label\" x=\"" + cx + "\" y=\"" + (cy + 4) + "\" text-anchor=\"middle\">" + abr + "</text>");
      parts.push("<path class=\"province-hit\" data-province=\"" + abr + "\" d=\"" + d + "\" fill=\"transparent\" cursor=\"pointer\"></path>");
    });
    // Remote placeholder dot (top-right)
    parts.push("<rect class=\"province\" data-province=\"Remote\" x=\"1520\" y=\"40\" width=\"70\" height=\"30\" rx=\"4\"></rect>");
    parts.push("<text class=\"province-label\" x=\"1555\" y=\"59\" text-anchor=\"middle\">Remote</text>");
    parts.push("<rect class=\"province-hit\" data-province=\"Remote\" x=\"1520\" y=\"40\" width=\"70\" height=\"30\" rx=\"4\" fill=\"transparent\" cursor=\"pointer\"></rect>");
    JOBS.forEach((job) => {
      const p = provinceAnchor(job);
      parts.push("<circle class=\"map-dot\" data-job-id=\"" + job.id + "\" cx=\"" + p.x + "\" cy=\"" + p.y + "\" r=\"6\" fill=\"" + colorFor(job) + "\"></circle>");
    });
    svg.innerHTML = parts.join("");
    svg.addEventListener("mousemove", (ev) => {
      const dot = ev.target.closest(".map-dot");
      if (dot) setHover(dot.dataset.jobId, ev);
    });
    svg.addEventListener("mouseleave", () => setHover(null));
    svg.addEventListener("click", (ev) => {
      const dot = ev.target.closest(".map-dot");
      if (dot) { selectJob(dot.dataset.jobId); return; }
      const hit = ev.target.closest(".province-hit");
      if (hit) {
        const p = hit.dataset.province;
        state.filters.province = (state.filters.province === p) ? null : p;
        dirtyFilter = true; dirtyMap = true;
      }
    });
  }

  function provinceAnchor(job) {
    // Centroids in the 1608.4×644 viewBox coordinate space
    const anchors = {
      BC:[260,310], AB:[450,260], SK:[622,260], MB:[790,290],
      ON:[970,410], QC:[1300,330], NB:[1340,492], NS:[1410,535],
      PE:[1403,494], NL:[1460,190], Remote:[1555,55],
    };
    const [x, y] = anchors[job.province] || anchors.Remote;
    const n = job.provinceOrdinal || 1;
    const ring = Math.ceil((Math.sqrt(n) - 1) / 2);
    const angle = n * 2.399963;
    const radius = 10 + ring * 12;
    return { x: x + Math.cos(angle) * radius, y: y + Math.sin(angle) * radius };
  }

  function renderMapState() {
    $("#map-overlay").classList.toggle("open", state.showMap);
    const activeProv = state.filters.province;
    $$(".province").forEach((rect) => {
      const p = rect.dataset.province;
      rect.style.opacity = activeProv && p !== activeProv ? "0.28" : "1";
      rect.style.stroke = p === activeProv ? "rgba(96,165,250,0.9)" : "";
      rect.style.strokeWidth = p === activeProv ? "2.5" : "";
    });
    $$(".map-dot").forEach((dot) => {
      const id = dot.dataset.jobId;
      const job = jobById.get(id);
      dot.setAttribute("fill", job ? colorFor(job) : "#d1d5db");
      dot.classList.toggle("dim", !visibleIds.has(id));
      dot.classList.toggle("hot", id === state.hoveredId || id === state.selectedId);
    });
    dirtyMap = false;
  }

  function syncControls() {
    $("#job-count").textContent = JOBS.length + " roles";
    $("#sx").value = state.focus.sx;
    $("#sy").value = state.focus.sy;
    $("#sz").value = state.focus.sz;
    $("#radius").value = state.focus.radius;
    $("#boundary").value = state.focus.boundary;
    updateFocusLabels();
    updateFilterLabels();
    updateTimelineLabels();
  }

  function updateFocusLabels() {
    const f = state.focus;
    $("#sx-value").textContent = f.sx.toFixed(1) + " " + axisName("x", f.sx);
    $("#sy-value").textContent = f.sy.toFixed(1) + " " + axisName("y", f.sy);
    $("#sz-value").textContent = f.sz.toFixed(1) + " " + axisName("z", f.sz);
    $("#radius-value").textContent = "+/-" + f.radius.toFixed(1);
    $("#boundary-value").textContent = BOUNDARY_LABELS[f.boundary];
    $("#axis-readout").textContent = "X " + axisName("x", f.sx) + " | Y " + axisName("y", f.sy) + " | Z " + axisName("z", f.sz) + " | " + BOUNDARY_LABELS[f.boundary];
  }

  function axisName(axis, value) {
    return AXIS_LABELS[axis][clamp(Math.round(value), 1, 5)];
  }

  function updateFilterLabels() {
    $("#fit-floor-value").textContent = state.filters.fitFloor + "/5";
    const lo = Math.min(state.filters.salaryMin, state.filters.salaryMax);
    const hi = Math.max(state.filters.salaryMin, state.filters.salaryMax);
    $("#salary-range-value").textContent = "$" + lo + "K – $" + hi + "K";
    const fill = $("#salary-fill");
    if (fill) {
      const span = 220 - 55;
      fill.style.left = ((lo - 55) / span * 100).toFixed(1) + "%";
      fill.style.width = ((hi - lo) / span * 100).toFixed(1) + "%";
    }
  }

  function pctToDate(pct) {
    const a = dateMs(minDate), b = dateMs(maxDate);
    return new Date(a + (b - a) * pct / 100).toISOString().slice(0, 10);
  }

  function updateTimelineLabels() {
    const start = state.timeline.startPct;
    const end = state.timeline.endPct;
    $("#tl-start-label").textContent = fmtDate(pctToDate(start));
    $("#tl-end-label").textContent = fmtDate(pctToDate(end));
    const fill = $("#timeline-fill");
    fill.style.left = start + "%";
    fill.style.right = (100 - end) + "%";
  }

  function renderTimelineTicks() {
    const box = $("#tl-ticks");
    if (!box) return;
    const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const ms = dateMs(minDate);
    const me = dateMs(maxDate);
    const total = me - ms;
    if (total <= 0) { box.innerHTML = ""; return; }
    const ticks = [];
    const cursor = new Date(ms);
    cursor.setDate(1);
    cursor.setMonth(cursor.getMonth() + 1);
    while (cursor.getTime() <= me) {
      const pct = (cursor.getTime() - ms) / total * 100;
      if (pct >= 0 && pct <= 100) ticks.push({ pct: pct.toFixed(2), lbl: MONTHS[cursor.getMonth()], today: false });
      cursor.setMonth(cursor.getMonth() + 1);
    }
    const todayMs = dateMs(DATA.today || maxDate);
    if (todayMs >= ms && todayMs <= me) {
      ticks.push({ pct: ((todayMs - ms) / total * 100).toFixed(2), lbl: "Today", today: true });
    }
    box.innerHTML = ticks.map((t) =>
      "<span class=\"tm" + (t.today ? " today" : "") + "\" style=\"left:" + t.pct + "%\"><span class=\"tmk\"></span>" + t.lbl + "</span>"
    ).join("");
  }

  function renderStatusPills() {
    const box = $("#status-pills");
    box.innerHTML = "";
    Object.keys(STATUS_COLORS).forEach((status) => {
      const pill = document.createElement("button");
      pill.type = "button";
      pill.className = "pill";
      pill.dataset.status = status;
      pill.style.color = STATUS_COLORS[status];
      pill.textContent = status;
      pill.addEventListener("click", () => {
        if (state.filters.statuses.has(status)) state.filters.statuses.delete(status);
        else state.filters.statuses.add(status);
        pill.classList.toggle("off", !state.filters.statuses.has(status));
        dirtyFilter = true;
      });
      box.appendChild(pill);
    });
  }

  function resetFilters() {
    state.filters.text = "";
    state.filters.fitFloor = 1;
    state.filters.salaryMin = 55;
    state.filters.salaryMax = 220;
    state.filters.statuses = new Set(Object.keys(STATUS_COLORS));
    $("#filter-text").value = "";
    $("#fit-floor").value = 1;
    $("#salary-min").value = 55;
    $("#salary-max").value = 220;
    $$(".pill").forEach((p) => p.classList.remove("off"));
    updateFilterLabels();
    dirtyFilter = true;
  }

  function resetTimeline() {
    state.timeline = { startPct: 0, endPct: 100, startDate: null, endDate: null };
    $("#tl-start").value = 0;
    $("#tl-end").value = 100;
    updateTimelineLabels();
    dirtyFilter = true;
  }

  function savePreset() {
    const name = $("#preset-name").value.trim();
    if (!name) return;
    const presets = JSON.parse(localStorage.getItem("job-viz-focus-presets") || "{}");
    presets[name] = state.focus;
    localStorage.setItem("job-viz-focus-presets", JSON.stringify(presets));
    $("#preset-name").value = "";
    renderPresets();
  }

  function deletePreset(name) {
    const presets = JSON.parse(localStorage.getItem("job-viz-focus-presets") || "{}");
    delete presets[name];
    localStorage.setItem("job-viz-focus-presets", JSON.stringify(presets));
    renderPresets();
  }

  function renderPresets() {
    const list = $("#preset-list");
    const presets = JSON.parse(localStorage.getItem("job-viz-focus-presets") || "{}");
    list.innerHTML = "";
    Object.keys(presets).forEach((name) => {
      const tag = document.createElement("span");
      tag.className = "preset-tag";
      const load = document.createElement("button");
      load.type = "button";
      load.className = "preset-load";
      load.textContent = name;
      load.addEventListener("click", () => {
        state.focus = Object.assign({}, presets[name]);
        syncControls();
        dirtyFocus = true;
      });
      const del = document.createElement("button");
      del.type = "button";
      del.className = "preset-del";
      del.textContent = "x";
      del.title = "Delete preset";
      del.addEventListener("click", (ev) => { ev.stopPropagation(); deletePreset(name); });
      tag.appendChild(load);
      tag.appendChild(del);
      list.appendChild(tag);
    });
  }

  function copyFocus() {
    const f = state.focus;
    const payload = {
      cx: f.sx, cy: f.sy, cz: f.sz, radius: f.radius, boundary: f.boundary,
      label: { x: axisName("x", f.sx), y: axisName("y", f.sy), z: axisName("z", f.sz) },
      boundary_label: BOUNDARY_LABELS[f.boundary],
      search_bias: {
        x_range: [+(f.sx - f.radius).toFixed(1), +(f.sx + f.radius).toFixed(1)],
        y_range: [+(f.sy - f.radius).toFixed(1), +(f.sy + f.radius).toFixed(1)],
        z_range: [+(f.sz - f.radius * 0.8).toFixed(1), +(f.sz + f.radius * 0.8).toFixed(1)],
      },
    };
    const text = "/pipeline\n\nSearch focus from job_search_viz.html:\nSEARCH_FOCUS=" + JSON.stringify(payload);
    navigator.clipboard.writeText(text).then(() => {
      $("#health-readout").textContent = "Focus copied";
      setTimeout(() => { $("#health-readout").textContent = "Three.js renderer ready"; }, 1600);
    });
  }

  function screenshot() {
    const a = document.createElement("a");
    a.href = renderer.domElement.toDataURL("image/png");
    a.download = "job_search_space.png";
    a.click();
  }

  function bindUi() {
    $(".sidebar").addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-action]");
      if (!btn) return;
      const action = btn.dataset.action;
      if (action === "color") {
        state.colorMode = btn.dataset.mode;
        $$("[data-group='color'] .btn").forEach((b) => b.classList.toggle("active", b === btn));
        if (state.colorMode === "location") state.showMap = true;
        dirtyScene = dirtyMap = true;
      }
      if (action === "toggle-labels") { state.showLabels = !state.showLabels; btn.classList.toggle("active", state.showLabels); }
      if (action === "toggle-connections") { state.showConnections = !state.showConnections; btn.classList.toggle("active", state.showConnections); dirtyScene = true; }
      if (action === "toggle-salary-rings") { state.showSalaryRings = !state.showSalaryRings; btn.classList.toggle("active", state.showSalaryRings); dirtyScene = true; }
      if (action === "toggle-map") { state.showMap = !state.showMap; dirtyMap = true; }
      if (action === "reset-camera") resetCamera();
      if (action === "screenshot") screenshot();
      if (action === "copy-focus") copyFocus();
      if (action === "save-preset") savePreset();
      if (action === "clear-status") { state.filters.statuses.clear(); $$(".pill").forEach((p) => p.classList.add("off")); dirtyFilter = true; }
      if (action === "reset-filters") resetFilters();
    });

    document.body.addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-action='toggle-map']");
      if (btn && btn.closest(".map-overlay")) {
        state.showMap = false;
        dirtyMap = true;
      }
    });

    $("#filter-text").addEventListener("input", (ev) => { state.filters.text = ev.target.value.toLowerCase(); dirtyFilter = true; });
    $("#fit-floor").addEventListener("input", (ev) => { state.filters.fitFloor = parseInt(ev.target.value, 10); updateFilterLabels(); dirtyFilter = true; });
    $("#salary-min").addEventListener("input", (ev) => { state.filters.salaryMin = parseInt(ev.target.value, 10); updateFilterLabels(); dirtyFilter = true; });
    $("#salary-max").addEventListener("input", (ev) => { state.filters.salaryMax = parseInt(ev.target.value, 10); updateFilterLabels(); dirtyFilter = true; });

    $$("[data-focus]").forEach((input) => {
      input.addEventListener("input", () => {
        const key = input.dataset.focus;
        state.focus[key] = key === "boundary" ? parseInt(input.value, 10) : parseFloat(input.value);
        updateFocusLabels();
        dirtyFocus = true;
      });
    });

    $("#detail").addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-action='cycle-outcome']");
      if (btn) cycleOutcome(btn.dataset.jobId);
    });

    $("#tl-start").addEventListener("input", updateTimelineFromControls);
    $("#tl-end").addEventListener("input", updateTimelineFromControls);
    document.body.addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-action='reset-timeline']");
      if (btn) resetTimeline();
    });
  }

  function updateTimelineFromControls() {
    let start = parseInt($("#tl-start").value, 10);
    let end = parseInt($("#tl-end").value, 10);
    if (start > end) {
      const tmp = start;
      start = end;
      end = tmp;
      $("#tl-start").value = start;
      $("#tl-end").value = end;
    }
    state.timeline.startPct = start;
    state.timeline.endPct = end;
    state.timeline.startDate = start <= 0 ? null : pctToDate(start);
    state.timeline.endDate = end >= 100 ? null : pctToDate(end);
    updateTimelineLabels();
    dirtyFilter = true;
  }

  function boot() {
    if (!JOBS.length) return;
    renderStatusPills();
    renderRoleList();
    renderDetail();
    renderPresets();
    renderMap();
    renderTimelineTicks();
    syncControls();
    bindUi();
    applyFilters();
    initThree();
  }

  boot();
})();
</script>
</body>
</html>
"""
    return html.replace("__PAYLOAD__", payload)


def main() -> None:
    jobs = enrich_jobs(load_legacy_jobs())
    backup_existing()
    html = build_html(jobs)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8", newline="\n")
    NEXT.write_text(html, encoding="utf-8", newline="\n")
    center = job_center(jobs)
    print(f"Written: {OUT}")
    print(f"Written: {NEXT}")
    print(f"Three.js job viz: {len(jobs)} roles; center X={center['x']:.2f} Y={center['y']:.2f} Z={center['z']:.2f}")


if __name__ == "__main__":
    main()
