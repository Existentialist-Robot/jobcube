"""
Job search 3D scatter visualiser
================================
Regenerate:  python working/scripts/viz/build_job_viz.py
Output:      working/active/job_search_viz.html  (self-contained, no server needed)

AXES
  X = Public-sector proximity   1=Startup ↔ 5=Core government
  Y = Innovation focus          1=Ops/Compliance ↔ 5=Ecosystem/R&D
  Z = Seniority                 1=Specialist ↔ 5=Branch-head/C-suite

PLOTLY TRACE REGISTRY (do NOT renumber without updating all JS restyle calls)
  0  roles          — job dots (scatter3d markers); primary interactive trace
  1  focus sphere   — Fibonacci point cloud; updated by updateSphere()
  2  connections    — Interview → nearest non-Interview lines; toggleConnections()
  3  compare sphere — optional second search-focus sphere; toggleCompareSphere()
  4  salary halos   — outer rings sized by salary band; toggleSalaryRings()
  5  sphere outline — ghost wireframe at sphere surface; updated by updateSphere()
  6  exp boundary   — expanded wireframe on sphere hover; wireSphereHover()

CSS ARCHITECTURE NOTE (SIDEBAR REWRITE — fixes the recurring "buttons stop working" bug)
  The previous design floated controls over the chart with position:absolute / position:fixed
  panels and a full-page modal backdrop. Those overlays periodically got stuck on top of the
  chart (the modal backdrop stayed display:block, or a .sec-body dropdown drifted over the
  canvas) and silently intercepted every click — buttons appeared dead.

  This version is a TWO-COLUMN flex ROW:
    body            → display:flex (row), height:100vh
    #sidebar        → flex:0 0 240px, normal document flow, ALL controls live here
    #chart-area     → flex:1, column: #title / #viz / #timeline-wrap (all in-flow)

  There are NO absolute/fixed-position control panels anywhere. Controls and chart occupy
  separate physical columns, so a control can never overlay the chart and intercept its
  clicks. The ONLY position:fixed element left is the dot-click modal — it is opened by an
  explicit click, has a VISIBLE semi-transparent backdrop, and closes on backdrop click,
  its close button, AND the Escape key, with state reset on every open.

  #viz has flex:1 1 0 + min-height and NO overflow:hidden (Plotly needs wheel events for
  scroll-zoom). The Plotly layout sets NO height — responsive:true + fitViz() own sizing.

ADDING A NEW JOB
  Append to JOBS list. Fields: label, org, loc, x/y/z, fit(1-5), p(int%), sal, sal_min,
  sal_max, status, date (YYYY-MM-DD), outcome (None/"pending"/"offer"/"no-offer"), note,
  closes.
  Run the script to regenerate the HTML. Status colours are in STATUS_MAP.
"""

import os
import sys
from pathlib import Path

if os.environ.get("JOB_VIZ_LEGACY") != "1":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_job_viz_three

    build_job_viz_three.main()
    sys.exit(0)

import json, math

# ── job data ──────────────────────────────────────────────────────────────────
# EXAMPLE DATA — replace every entry below with your own applications.
#
# x   = public-sector proximity (1=startup … 5=core government)
# y   = innovation focus        (1=ops/compliance … 5=ecosystem/R&D)
# z   = seniority               (1=specialist … 5=branch-head/C-suite)
#       Use 0.1 resolution so dots don't stack on identical coordinates.
# fit = your assessment, 1–5 stars
# p   = P(interview) estimate, integer %
# sal = salary midpoint in $K; sal_min/sal_max bound the range
# loc = "City, XX" / "XX" / "Remote" — drives the map layer. XX is a Canadian
#       province or US state code; anything unrecognized plots as Remote.
# status must be a key of STATUS_MAP; outcome is None / "pending" / "offer" /
# "no-offer"; closes is optional.
JOBS = [
    dict(label="Sr Strategy Advisor",           org="Example Gov Agency",
         loc="Edmonton, AB",
         x=4.8, y=3.5, z=2.5, fit=4, p=20, sal=95,  sal_min=82,  sal_max=107,
         status="Applied",   date="2025-01-15", outcome=None,
         note="Government strategy role — policy generalist mandate"),

    dict(label="Dir, Innovation Programs",      org="Example Nonprofit",
         loc="Toronto, ON",
         x=2.5, y=4.2, z=3.8, fit=4, p=25, sal=110, sal_min=95,  sal_max=125,
         status="Interview", date="2025-01-20", outcome="pending",
         note="Interview scheduled"),

    dict(label="Ecosystem Manager",             org="Example Innovation Hub",
         loc="Calgary, AB",
         x=2.0, y=4.0, z=3.2, fit=3, p=22, sal=90,  sal_min=80,  sal_max=100,
         status="Ported",    date="2025-02-01", outcome=None,
         note="Ported to the design template, awaiting export greenlight"),

    dict(label="Head of Partnerships",          org="Example Tech Co",
         loc="Remote",
         x=1.5, y=4.4, z=3.0, fit=3, p=18, sal=105, sal_min=90,  sal_max=120,
         status="Drafted",   date="2025-02-10", outcome=None),

    dict(label="Dir, Economic Development",     org="Example Regional Agency",
         loc="Vancouver, BC",
         x=3.2, y=3.8, z=4.0, fit=5, p=30, sal=130, sal_min=115, sal_max=148,
         status="Target",    date="2025-02-15", outcome=None,
         note="Archetype: quasi-gov regional development, generalist director mandate"),

    dict(label="Sr Mgr, Strategic Partnerships", org="Example University",
         loc="Montreal, QC",
         x=3.5, y=3.5, z=3.5, fit=4, p=20, sal=100, sal_min=88,  sal_max=115,
         status="Applied",   date="2025-02-20", outcome=None,
         closes="2025-03-15"),

    dict(label="Program Lead, Founder Programs", org="Example Accelerator",
         loc="New York, NY",
         x=1.8, y=4.6, z=3.4, fit=4, p=15, sal=115, sal_min=100, sal_max=132,
         status="Queued",    date="2025-02-22", outcome=None,
         note="US role — confirm work authorization before drafting"),
]

# Half-star fits (4.5) are legal in the data and are what build_job_viz_three.py
# renders; this legacy path indexes and multiplies by fit in several places, so
# floor it once here rather than coercing at each use site.
for _j in JOBS:
    _j["fit"] = int(_j.get("fit", 1))

xs = [j["x"] for j in JOBS]
ys = [j["y"] for j in JOBS]
zs = [j["z"] for j in JOBS]
cx = sum(xs)/len(xs)
cy = sum(ys)/len(ys)
cz = sum(zs)/len(zs)

# ── Fibonacci sphere point cloud (Python, for initialization) ────────────────
def sphere_points_py(cx, cy, cz, rx, ry, rz, n=400, dispersion=0.0):
    import math
    xs, ys, zs = [], [], []
    gr = (1 + math.sqrt(5)) / 2
    for i in range(n):
        theta = math.acos(1 - 2*(i+0.5)/n)
        phi   = 2*math.pi*i/gr
        jit   = 1 + dispersion*(math.cos(i*7.389+theta)*0.6 + math.sin(i*2.718+phi)*0.4)
        xs.append(cx + rx*jit*math.sin(theta)*math.cos(phi))
        ys.append(cy + ry*jit*math.sin(theta)*math.sin(phi))
        zs.append(cz + rz*jit*math.cos(theta))
    return xs, ys, zs

# ── wireframe sphere helper — kept for slider step pre-generation ─────────────
def wireframe_sphere(cx, cy, cz, rx, ry, rz, n_lat=10, n_lon=14):
    import math
    xs, ys, zs = [], [], []
    # Latitude rings
    for i in range(1, n_lat):
        u = math.pi * i / n_lat
        for j in range(n_lon + 1):
            v = 2 * math.pi * j / n_lon
            xs.append(cx + rx * math.sin(u) * math.cos(v))
            ys.append(cy + ry * math.sin(u) * math.sin(v))
            zs.append(cz + rz * math.cos(u))
        xs.append(None); ys.append(None); zs.append(None)
    # Longitude lines
    for j in range(n_lon):
        v = 2 * math.pi * j / n_lon
        for i in range(n_lat + 1):
            u = math.pi * i / n_lat
            xs.append(cx + rx * math.sin(u) * math.cos(v))
            ys.append(cy + ry * math.sin(u) * math.sin(v))
            zs.append(cz + rz * math.cos(u))
        xs.append(None); ys.append(None); zs.append(None)
    return xs, ys, zs

# ── colour maps per mode ──────────────────────────────────────────────────────
FIT_CMAP   = ["#d73027","#fc8d59","#fee090","#91bfdb","#4575b4"]
STATUS_MAP = {
    "Applied":"#4575b4",
    "Interview":"#f59e0b",
    "Ready":"#a78bfa",
    "Ported":"#38bdf8",
    "Queued":"#74c476",
    "Drafted":"#fc8d59",
    "Target":"#22d3ee",      # cyan — archetypal/search-focus roles
    "Declined":"#7f8795",    # keep in step with STATUS_COLORS in
    "Closed":"#5c5350",      # build_job_viz_three.py — a status only defined
                             # there raises KeyError on this path
}
# normalize legacy status names from the data
_STATUS_ALIAS = {"File-ready":"Ready","Canva-ported":"Ported"}
for _j in JOBS:
    _j["status"] = _STATUS_ALIAS.get(_j["status"], _j["status"])

def _months():
    return ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
def _fmt(iso):
    if not iso: return ""
    p=iso.split("-"); return f"{p[0][2:]}-{_months()[int(p[1])-1]}-{p[2]}"

hover = [
    f"<b>{j['label']}</b><br>{j['org']}<br>"
    f"Sector: {j['x']} | Innovation: {j['y']} | Seniority: {j['z']}<br>"
    f"Fit: {'★'*j['fit']}{'☆'*(5-j['fit'])} | P(int): {j['p']}% | Sal: ${j['sal']}K<br>"
    f"Status: {j['status']} | Submitted: {_fmt(j.get('date',''))}"
    + (f"<br>Interview: {_fmt(j.get('outcome','')) if j.get('outcome') and j.get('outcome')!='pending' else '(pending)' if j.get('outcome')=='pending' else ''}" if j.get("status")=="Interview" else "")
    + (f"<br><i>{j['note']}</i>" if j.get("note") else "")
    for j in JOBS
]

# ── build plotly traces as plain dicts (no plotly dep needed to write file) ──
scatter_base = dict(
    type="scatter3d",
    x=[j["x"] for j in JOBS],
    y=[j["y"] for j in JOBS],
    z=[j["z"] for j in JOBS],
    mode="markers",
    text=[j["label"] for j in JOBS],
    textposition="top center",
    textfont=dict(size=10, color="rgba(220,225,255,0.85)"),
    hovertemplate="%{customdata}<extra></extra>",
    customdata=hover,
    marker=dict(
        size=[20 if j["status"]=="Interview" else 12 for j in JOBS],
        symbol=["diamond" if j["status"]=="Interview" else "cross" if j["status"]=="Target" else "circle" for j in JOBS],
        color=[FIT_CMAP[j["fit"]-1] for j in JOBS],
        colorscale="RdYlBu",
        cmin=1, cmax=5,
        colorbar=dict(title="Fit ★", thickness=8, x=1.03, len=0.42, y=0.72, yanchor="top", tickfont=dict(size=9)),
        line=dict(color=[("#f59e0b" if j["status"]=="Interview" else "white") for j in JOBS], width=[3 if j["status"]=="Interview" else 1 for j in JOBS]),
        opacity=0.9,
    ),
    showlegend=False,
    name="roles",
)

# sphere — Fibonacci point cloud, markers only (no lines, no connections)
_spx, _spy, _spz = sphere_points_py(cx, cy, cz, rx=1.0, ry=1.0, rz=0.8, n=500, dispersion=0.0)
_sphere_hover = (
    f"<b>Search Focus</b><br>"
    f"X (Sector): {cx:.2f} — {['','Startup','Innovation org','Nonprofit','Post-secondary','Gov'][min(5,max(1,round(cx)))]}<br>"
    f"Y (Innovation): {cy:.2f} — {['','Ops','Change mgmt','Strategy','Programs/Partnerships','Ecosystem/R&D'][min(5,max(1,round(cy)))]}<br>"
    f"Z (Seniority): {cz:.2f} — {['','Specialist','Officer/Advisor','Manager','Director/ED','VP/C-suite'][min(5,max(1,round(cz)))]}<br>"
    f"Radius: ±1.0  Boundary: Medium<br><i>Click sphere to inspect · Sliders to shift</i>"
    f"<extra></extra>"
)
ellipsoid_trace = dict(
    type="scatter3d",
    x=_spx, y=_spy, z=_spz,
    mode="markers",
    marker=dict(size=3.5, color="rgba(100,160,255,0.35)", opacity=0.35),
    hovertemplate=_sphere_hover,
    showlegend=False,
    name="focus sphere",
)

layout = dict(
    scene=dict(
        # aspectmode=cube + manual aspectratio → scene never rescales when the
        # boundary slider disperses sphere points beyond the axis range.
        aspectmode="cube",
        aspectratio=dict(x=1, y=1, z=1),
        xaxis=dict(title=dict(text="X · Sector", font=dict(size=12)), ticklabelstandoff=6,
                   range=[0.5,5.5], tickvals=[1,2,3,4,5], autorange=False,
                   ticktext=["1 Startup","2 Innov.org","3 Nonprofit","4 Post-secondary","5 Gov"],
                   tickfont=dict(size=11)),
        yaxis=dict(title=dict(text="Y · Innovation", font=dict(size=12)), ticklabelstandoff=6,
                   range=[0.5,5.5], tickvals=[1,2,3,4,5], autorange=False,
                   ticktext=["1 Ops","2 Change","3 Strategy","4 Programs","5 Ecosystem"],
                   tickfont=dict(size=11)),
        zaxis=dict(title=dict(text="Z · Seniority", font=dict(size=12)), ticklabelstandoff=6,
                   range=[0.5,5.5], tickvals=[1,2,3,4,5], autorange=False,
                   ticktext=["1 Specialist","2 Officer/Advisor","3 Manager","4 Director/ED","5 VP/C"],
                   tickfont=dict(size=11)),
        camera=dict(eye=dict(x=1.5, y=1.5, z=1.0)),
        bgcolor="rgba(10,10,20,1)",
        xaxis_gridcolor="rgba(255,255,255,0.1)",
        yaxis_gridcolor="rgba(255,255,255,0.1)",
        zaxis_gridcolor="rgba(255,255,255,0.1)",
    ),
    paper_bgcolor="rgba(10,10,20,1)",
    font=dict(color="white"),
    margin=dict(l=0, r=60, t=0, b=30),
    # NOTE: no height here — let responsive:true size the chart to the #viz flex slot.
    # Setting height here caused Plotly's drag surface to overflow the container and
    # misalign with the visible canvas, breaking both 3D rotate and the control sliders.
    annotations=[
        dict(text="Drag to rotate  ·  Scroll to zoom  ·  Click dot for detail  ·  Click sphere wire for focus coords",
             showarrow=False, x=0.5, y=-0.01, xref="paper", yref="paper",
             font=dict(size=10, color="rgba(200,200,200,0.6)"), align="center")
    ],
)

# ── write self-contained HTML ─────────────────────────────────────────────────
# Empty connection-lines trace (updated by JS when toggled)
conn_trace = dict(type="scatter3d", x=[], y=[], z=[], mode="lines",
                  line=dict(color="rgba(255,220,100,0.4)", width=2),
                  hoverinfo="skip", showlegend=False, name="connections")

# Empty comparison sphere trace (updated by JS when toggled)
compare_trace = dict(type="scatter3d", x=[], y=[], z=[], mode="markers",
                     marker=dict(size=2.5, color="rgba(255,100,160,0.3)"),
                     hoverinfo="skip", showlegend=False, name="compare sphere",
                     visible=False)

# Ghost wireframe outline — always shows sphere boundary surface regardless of point scatter
_gwx, _gwy, _gwz = wireframe_sphere(cx, cy, cz, rx=1.0, ry=1.0, rz=0.8, n_lat=6, n_lon=9)
ghost_wire_trace = dict(type="scatter3d",
    x=_gwx, y=_gwy, z=_gwz,
    mode="lines",
    line=dict(color="rgba(120,170,255,0.10)", width=1),
    hoverinfo="skip", showlegend=False, name="sphere outline")

# Salary halo trace — large translucent outer rings, initially hidden
salary_halo_trace = dict(type="scatter3d",
    x=[j["x"] for j in JOBS], y=[j["y"] for j in JOBS], z=[j["z"] for j in JOBS],
    mode="markers",
    marker=dict(size=[0]*len(JOBS), color="rgba(0,0,0,0)", opacity=1, line=dict(width=0)),
    hoverinfo="skip", showlegend=False, name="salary halos", visible=False)

# Expanded boundary trace — shows max dispersion radius on hover, normally invisible
exp_wire_trace = dict(type="scatter3d", x=[], y=[], z=[],
    mode="lines", line=dict(color="rgba(160,200,255,0.0)", width=1),
    hoverinfo="skip", showlegend=False, name="exp boundary", visible=True)

fig_data    = json.dumps([scatter_base, ellipsoid_trace, conn_trace, compare_trace, salary_halo_trace, ghost_wire_trace, exp_wire_trace])
_jobs_json  = json.dumps([{
    "label":j["label"], "org":j["org"], "status":j["status"],
    "x":j["x"], "y":j["y"], "z":j["z"],
    "fit":j["fit"], "p":j["p"], "sal":j["sal"],
    "sal_min":j.get("sal_min",j["sal"]), "sal_max":j.get("sal_max",j["sal"]),
    "date":j.get("date","2026-01-01"), "outcome":j.get("outcome"),
    "note":j.get("note",""), "closes":j.get("closes","")
} for j in JOBS])
fig_layout = json.dumps(layout)

_fit_colors   = json.dumps([FIT_CMAP[j["fit"]-1] for j in JOBS])
_p_vals        = json.dumps([j["p"]   for j in JOBS])
_sal_vals      = json.dumps([j["sal"] for j in JOBS])
_status_colors = json.dumps([STATUS_MAP[j["status"]] for j in JOBS])

html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Job Search Space</title>
  <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
  <style>
    *  {{ box-sizing:border-box; }}

    /* ── SIDEBAR LAYOUT (the bug fix) ──────────────────────────────────────
       body is a horizontal flexbox ROW at height:100vh: a fixed-width #sidebar
       (left, normal flow) + a flexible #chart-area (right). Controls and chart
       occupy SEPARATE physical columns, so no control can ever overlay the chart
       and intercept its clicks. There are NO position:absolute control panels and
       NO position:fixed elements except the explicitly-triggered dot modal. */
    body {{
      display:flex; height:100vh; margin:0;
      max-width:1600px; margin-left:auto; margin-right:auto;
      background:#0a0a14; color:white; font-family:system-ui,sans-serif;
    }}

    /* ── left control column — everything lives here, in normal document flow ── */
    #sidebar {{
      flex:0 0 240px;
      overflow-y:auto;            /* scroll if controls are taller than viewport */
      overflow-x:hidden;
      background:rgba(13,14,30,0.98);
      border-right:1px solid rgba(255,255,255,0.1);
      padding:10px 12px;
      display:flex; flex-direction:column; gap:10px;
      z-index:10;                 /* above chart, but no overlay needed */
    }}
    #sidebar h1 {{
      font-size:13px; font-weight:700; color:rgba(200,210,255,0.95);
      margin:0 0 2px; letter-spacing:.02em;
    }}

    /* collapsible section — pure <details>/<summary>, NO absolute positioning */
    details.sec {{
      border:1px solid rgba(255,255,255,0.07); border-radius:6px;
      background:rgba(8,9,20,0.6); overflow:hidden;
    }}
    details.sec > summary {{
      list-style:none; cursor:pointer; user-select:none;
      padding:6px 9px; font-size:10px; font-weight:600;
      color:rgba(180,190,225,0.85); text-transform:uppercase; letter-spacing:.07em;
      display:flex; justify-content:space-between; align-items:center;
    }}
    details.sec > summary::-webkit-details-marker {{ display:none; }}
    details.sec > summary::after {{ content:"▸"; color:#5a6090; font-size:11px; }}
    details.sec[open] > summary::after {{ content:"▾"; }}
    details.sec > summary:hover {{ color:#c8d4ff; }}
    .sec-inner {{ padding:8px 9px 10px; display:flex; flex-direction:column; gap:7px; }}

    .btn-row {{ display:flex; flex-wrap:wrap; gap:5px; }}

    /* buttons */
    .cbtn {{
      background:#14163a; color:#fff; border:1px solid #2e3268;
      padding:4px 10px; border-radius:4px; cursor:pointer; font-size:12px;
      transition:background .12s, color .12s; white-space:nowrap;
    }}
    .cbtn:hover  {{ background:#232656; }}
    .cbtn.active {{ background:#4b5cc4; color:#fff; border-color:#6b7ce8; }}
    .cbtn.active.dark {{ color:#000; }}

    /* status pills */
    .spill {{
      font-size:11px; padding:3px 9px; border-radius:20px; cursor:pointer;
      border:1px solid rgba(255,255,255,0.15); transition:opacity .15s;
      user-select:none;
    }}
    .spill.off {{ opacity:0.3; }}

    /* range sliders */
    .srow {{ display:flex; flex-direction:column; gap:7px; }}
    .srow label {{
      font-size:11px; color:rgba(210,215,235,0.8);
      display:flex; align-items:center; gap:6px; justify-content:space-between;
    }}
    .srow label > span.lbl {{ flex:0 0 auto; min-width:62px; }}
    .srow input[type=range] {{ flex:1 1 0; min-width:0; accent-color:#4b5cc4; cursor:pointer; }}
    .sval {{ font-size:9px; color:#7080b0; text-align:right; min-width:30px; flex:0 0 auto; }}
    input[type=text] {{
      background:#0d0f22; border:1px solid #2e3268; color:#e8eaed;
      border-radius:4px; padding:4px 8px; font-size:12px; width:100%;
    }}
    input[type=text]::placeholder {{ color:#4a5080; }}
    .cg-lbl {{
      font-size:9px; color:rgba(180,185,210,0.6);
      text-transform:uppercase; letter-spacing:.08em; margin-bottom:1px;
    }}

    /* ── right column — title / chart / timeline, all in normal flow ── */
    #chart-area {{
      flex:1 1 0; min-width:0;
      display:flex; flex-direction:column;
    }}
    #title {{
      flex:0 0 auto; padding:6px 14px;
      font-size:14px; font-weight:600; color:rgba(200,210,255,0.9);
      letter-spacing:.03em;
    }}
    /* CHART CONTAINER.
       flex:1 1 0 → fills remaining height between title and timeline.
       min-height → never collapses on short viewports.
       NO overflow:hidden → Plotly NEEDS wheel events for scroll-zoom.
       DO NOT set Plotly layout.height — responsive:true + fitViz() own sizing.
       transform:translateZ(0) promotes the canvas to its own GPU compositor layer
       so WebGL rotation repaints sync immediately rather than waiting for the
       next browser-triggered repaint (the "drag lags until you move the mouse" bug). */
    #viz {{ flex:1 1 0; min-height:200px; position:relative; transform:translateZ(0); }}

    /* timeline bar — IN NORMAL FLOW at the bottom of #chart-area.
       No position:fixed, no left/right/z-index — it can't overlap the chart. */
    #timeline-wrap {{
      flex:0 0 auto;
      background:rgba(10,11,22,0.97); border-top:1px solid rgba(255,255,255,0.07);
      padding:4px 12px; display:flex; flex-direction:column; gap:2px;
      font-size:10px; color:#7080b0;
    }}
    #tl-row {{ display:flex; align-items:center; gap:8px; }}
    #tl-start-lbl,#tl-end-lbl {{
      min-width:54px; font-size:10px; color:#7da0e0;
      font-variant-numeric:tabular-nums; white-space:nowrap;
    }}
    #tl-end-lbl {{ text-align:right; }}
    #tl-ticks {{ position:relative; height:16px; margin:0 2px; }}
    #tl-ticks .tm {{ /* month tick */
      position:absolute; transform:translateX(-50%);
      font-size:10px; color:#7da0e0; white-space:nowrap;
      display:flex; flex-direction:column; align-items:center; gap:0;
    }}
    #tl-ticks .tm .tmk {{ /* tick mark line */
      width:1px; height:5px; background:rgba(120,160,220,0.45); margin-bottom:1px;
    }}
    #tl-ticks .tm.today {{ color:#f59e0b; }}
    #tl-ticks .tm.today .tmk {{ background:rgba(245,158,11,0.7); }}

    /* ── dual-handle range slider (unchanged) ──────────────────────────── */
    .range-wrap {{
      position:relative; flex:1; height:20px; display:flex; align-items:center;
    }}
    .range-track {{
      position:absolute; left:0; right:0; height:4px; border-radius:2px;
      background:rgba(255,255,255,0.08); pointer-events:none;
    }}
    .range-fill {{
      position:absolute; height:100%; border-radius:2px;
      background:#4b5cc4; pointer-events:none;
    }}
    .range-wrap input[type=range] {{
      position:absolute; width:100%; height:4px;
      -webkit-appearance:none; appearance:none;
      background:transparent; pointer-events:none;
      margin:0; padding:0;
    }}
    .range-wrap input[type=range]::-webkit-slider-thumb {{
      -webkit-appearance:none; appearance:none;
      pointer-events:auto; cursor:pointer;
      width:13px; height:13px; border-radius:50%;
      background:#4b5cc4; border:2px solid rgba(200,210,255,0.9);
      box-shadow:0 0 4px rgba(75,92,200,0.6);
    }}
    .range-wrap input[type=range]::-moz-range-thumb {{
      pointer-events:auto; cursor:pointer;
      width:13px; height:13px; border-radius:50%;
      background:#4b5cc4; border:2px solid rgba(200,210,255,0.9);
      box-shadow:0 0 4px rgba(75,92,200,0.6);
    }}

    /* ── dot-click modal — the ONE remaining position:fixed element.
       VISIBLE backdrop (rgba(0,0,0,0.4)), closes on backdrop/✕/Escape. ── */
    #modal-backdrop {{
      display:none; position:fixed; inset:0; z-index:199;
      background:rgba(0,0,0,0.4);          /* visible — never a transparent click-trap */
    }}
    #modal-backdrop.open {{ display:block; }}
    #dot-modal {{
      display:none; position:fixed; z-index:200;
      background:rgba(12,14,30,0.98); border:1px solid rgba(255,255,255,0.12);
      border-radius:12px; box-shadow:0 12px 40px rgba(0,0,0,0.6);
      width:320px; max-height:70vh; overflow-y:auto;
      font-size:12px; color:#e8eaed;
    }}
    #dot-modal.open {{ display:block; }}
    #dot-modal-header {{
      display:flex; justify-content:space-between; align-items:flex-start;
      padding:12px 14px 8px; border-bottom:1px solid rgba(255,255,255,0.07);
    }}
    #dot-modal-title {{ font-size:14px; font-weight:600; color:#c8d4ff; line-height:1.3; }}
    #dot-modal-org {{ font-size:11px; color:#8090b0; margin-top:2px; }}
    #dot-modal-close {{
      background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.15);
      border-radius:6px; color:#c0c8e8; font-size:15px; line-height:1;
      cursor:pointer; padding:8px 12px; flex-shrink:0; margin-left:8px;
    }}
    #dot-modal-close:hover {{ background:rgba(255,80,80,0.25); color:#fff; }}
    #dot-modal-meta {{ padding:8px 14px; display:flex; flex-wrap:wrap; gap:6px; border-bottom:1px solid rgba(255,255,255,0.07); }}
    .meta-chip {{
      background:rgba(75,92,200,0.15); border:1px solid rgba(75,92,200,0.3);
      border-radius:4px; padding:2px 7px; font-size:10px; color:#a0b0e0;
      font-variant-numeric:tabular-nums;
    }}
    .modal-section {{ border-bottom:1px solid rgba(255,255,255,0.06); }}
    .modal-section-hdr {{
      width:100%; background:none; border:none; color:#9090c0;
      font-size:10px; text-transform:uppercase; letter-spacing:.06em;
      padding:7px 14px; cursor:pointer; text-align:left; display:flex; justify-content:space-between;
    }}
    .modal-section-hdr:hover {{ color:#c0c8e8; }}
    .modal-section-body {{ padding:6px 14px 10px; font-size:11px; color:#b0b8d0; line-height:1.7; display:none; }}
    .modal-section-body.open {{ display:block; }}

    /* preset list */
    #preset-list {{ display:flex; flex-wrap:wrap; gap:5px; }}
    .preset-tag {{
      background:#1a1d40; border:1px solid #2e3268; border-radius:4px;
      font-size:11px; padding:2px 7px 2px 10px; cursor:pointer; display:flex; align-items:center; gap:4px;
    }}
    .preset-tag:hover {{ background:#252860; }}
    .preset-tag .pdel {{ color:#d73027; font-size:10px; cursor:pointer; margin-left:2px; }}

    /* outcome badge */
    .outcome-pending {{ color:#e0b15b; }}
    .outcome-offer   {{ color:#46c08a; }}
    .outcome-no-offer {{ color:#d73027; }}
  </style>
</head>
<body>

<!-- ═══ LEFT COLUMN: all controls, normal document flow ═══ -->
<div id="sidebar">
  <h1>Job Search Space</h1>

  <!-- 1 · Colour -->
  <details class="sec" open>
    <summary>Colour</summary>
    <div class="sec-inner">
      <div class="btn-row">
        <button class="cbtn active" id="btn-fit"    onclick="setColor(this,'fit')">Fit ★</button>
        <button class="cbtn"        id="btn-prob"   onclick="setColor(this,'prob')">P(int)</button>
        <button class="cbtn"        id="btn-sal"    onclick="setColor(this,'sal')">Salary</button>
        <button class="cbtn"        id="btn-status" onclick="setColor(this,'status')">Status</button>
      </div>
    </div>
  </details>

  <!-- 2 · Show / Hide -->
  <details class="sec" open>
    <summary>Show / Hide</summary>
    <div class="sec-inner">
      <div class="btn-row">
        <button class="cbtn" id="btn-labels" onclick="toggleLabels(this)">Labels</button>
        <button class="cbtn" onclick="deselectAll()" title="Clear all — add back additively">Clear all</button>
      </div>
      <div class="btn-row">
        <span class="spill" style="background:rgba(71,117,180,0.3);color:#7db3ff"  onclick="toggleStatus(this,'Applied')">Applied</span>
        <span class="spill" style="background:rgba(245,158,11,0.25);color:#fbbf24" onclick="toggleStatus(this,'Interview')">Interview</span>
        <span class="spill" style="background:rgba(116,196,118,0.25);color:#74c476"onclick="toggleStatus(this,'Queued')">Queued</span>
        <span class="spill" style="background:rgba(252,141,89,0.25);color:#fc8d59" onclick="toggleStatus(this,'Drafted')">Drafted</span>
        <span class="spill" style="background:rgba(56,189,248,0.2);color:#38bdf8"  onclick="toggleStatus(this,'Ported')">Ported</span>
        <span class="spill" style="background:rgba(167,139,250,0.25);color:#a78bfa"onclick="toggleStatus(this,'Ready')">Ready</span>
        <span class="spill" style="background:rgba(34,211,238,0.15);color:#22d3ee" onclick="toggleStatus(this,'Target')">+ Target</span>
      </div>
    </div>
  </details>

  <!-- 3 · Focus Sphere -->
  <details class="sec" open>
    <summary>Focus Sphere</summary>
    <div class="sec-inner">
      <div class="srow">
        <label><span class="lbl">X Sector</span><input type="range" id="sx" min="1" max="5" step="0.1" value="{cx:.1f}" oninput="updateSphere()"><span class="sval" id="sx-v">{cx:.1f}</span></label>
        <label><span class="lbl">Y Innov.</span><input type="range" id="sy" min="1" max="5" step="0.1" value="{cy:.1f}" oninput="updateSphere()"><span class="sval" id="sy-v">{cy:.1f}</span></label>
        <label><span class="lbl">Z Senior.</span><input type="range" id="sz" min="1" max="5" step="0.1" value="{cz:.1f}" oninput="updateSphere()"><span class="sval" id="sz-v">{cz:.1f}</span></label>
        <label><span class="lbl">Size</span><input type="range" id="sr" min="0.3" max="2.0" step="0.1" value="1.0" oninput="updateSphere()"><span class="sval" id="sr-v">1.0</span></label>
        <label><span class="lbl">Boundary</span><input type="range" id="ss" min="1" max="10" step="1" value="5" oninput="updateSphere()"></label>
        <span class="sval" id="ss-v" style="font-size:9px;text-align:left">Medium</span>
      </div>
    </div>
  </details>

  <!-- 4 · Filter -->
  <details class="sec">
    <summary>Filter</summary>
    <div class="sec-inner">
      <div>
        <div class="cg-lbl">Search text</div>
        <input type="text" id="f-text" placeholder="e.g. director" oninput="applyFilters()">
      </div>
      <div class="srow">
        <label><span class="lbl">★ floor</span><input type="range" id="f-fit" min="1" max="5" step="1" value="1" oninput="applyFilters()"><span class="sval" id="f-fit-v">1★</span></label>
        <label><span class="lbl">Sal min</span><input type="range" id="f-smin" min="55" max="200" step="5" value="55" oninput="applyFilters()"><span class="sval" id="f-smin-v">55</span></label>
        <label><span class="lbl">Sal max</span><input type="range" id="f-smax" min="55" max="220" step="5" value="220" oninput="applyFilters()"><span class="sval" id="f-smax-v">220</span></label>
      </div>
    </div>
  </details>

  <!-- 5 · Overlays -->
  <details class="sec">
    <summary>Overlays</summary>
    <div class="sec-inner">
      <div class="btn-row">
        <button class="cbtn" id="btn-conn"      onclick="toggleConnections(this)">Connections</button>
        <button class="cbtn" id="btn-cmp"       onclick="toggleCompareSphere(this)">Compare Sphere</button>
        <button class="cbtn" id="btn-sal-rings" onclick="toggleSalaryRings(this)">Salary Rings</button>
      </div>
      <div id="cmp-controls" style="display:none">
        <div class="cg-lbl">Compare sphere</div>
        <div class="srow">
          <label><span class="lbl">CX</span><input type="range" id="cx2" min="1" max="5" step="0.1" value="2.5" oninput="updateCompareSphere()"><span class="sval" id="cx2-v">2.5</span></label>
          <label><span class="lbl">CY</span><input type="range" id="cy2" min="1" max="5" step="0.1" value="4.5" oninput="updateCompareSphere()"><span class="sval" id="cy2-v">4.5</span></label>
          <label><span class="lbl">CZ</span><input type="range" id="cz2" min="1" max="5" step="0.1" value="3.5" oninput="updateCompareSphere()"><span class="sval" id="cz2-v">3.5</span></label>
        </div>
      </div>
    </div>
  </details>

  <!-- 6 · Presets -->
  <details class="sec">
    <summary>Presets</summary>
    <div class="sec-inner">
      <div style="display:flex;gap:5px">
        <input type="text" id="preset-name" placeholder="Name this focus">
        <button class="cbtn" onclick="savePreset()">Save</button>
      </div>
      <div id="preset-list"></div>
    </div>
  </details>

  <!-- 7 · Pipeline -->
  <details class="sec">
    <summary>Pipeline</summary>
    <div class="sec-inner">
      <div class="btn-row" style="align-items:center">
        <button class="cbtn" onclick="copyFocus()">Copy Focus</button>
        <span id="copy-msg" style="font-size:10px;color:#74c476;display:none">Copied!</span>
      </div>
    </div>
  </details>

  <!-- 8 · Outcomes -->
  <details class="sec">
    <summary>Outcomes</summary>
    <div class="sec-inner">
      <div id="outcome-list" style="font-size:11px;line-height:1.8"></div>
    </div>
  </details>

  <!-- 9 · Export -->
  <details class="sec">
    <summary>Export</summary>
    <div class="sec-inner">
      <div class="btn-row">
        <button class="cbtn" onclick="screenshot()">Screenshot PNG</button>
      </div>
    </div>
  </details>
</div><!-- end #sidebar -->

<!-- ═══ RIGHT COLUMN: title / chart / timeline ═══ -->
<div id="chart-area">
  <div id="title">Job Search Space</div>
  <div id="viz"></div>

  <!-- timeline bar — proper dual-handle range with shared track fill, in normal flow -->
  <div id="timeline-wrap">
    <div id="tl-row">
      <span id="tl-start-lbl">—</span>
      <div class="range-wrap" id="tl-wrap">
        <div class="range-track"></div>
        <div class="range-fill" id="tl-fill"></div>
        <input type="range" id="tl-start" min="0" max="100" value="0"   oninput="filterTimeline()">
        <input type="range" id="tl-end"   min="0" max="100" value="100" oninput="filterTimeline()">
      </div>
      <span id="tl-end-lbl">—</span>
      <button class="cbtn" onclick="resetTimeline()" style="padding:2px 7px;font-size:11px;margin-left:4px">Reset</button>
    </div>
    <div id="tl-ticks"></div>
  </div>
</div><!-- end #chart-area -->

<!-- dot click modal — backdrop is VISIBLE and the only fixed-position overlay -->
<div id="modal-backdrop" onclick="closeModal()"></div>
<div id="dot-modal">
  <div id="dot-modal-header">
    <div>
      <div id="dot-modal-title">—</div>
      <div id="dot-modal-org">—</div>
    </div>
    <button id="dot-modal-close" onclick="closeModal()">✕</button>
  </div>
  <div id="dot-modal-meta"></div>
  <div class="modal-section">
    <button class="modal-section-hdr" onclick="toggleModalSec(this)">Application <span>▶</span></button>
    <div class="modal-section-body" id="modal-application"></div>
  </div>
  <div class="modal-section">
    <button class="modal-section-hdr" onclick="toggleModalSec(this)">Fit & Probability <span>▶</span></button>
    <div class="modal-section-body" id="modal-fit"></div>
  </div>
  <div class="modal-section">
    <button class="modal-section-hdr" onclick="toggleModalSec(this)">Salary Range <span>▶</span></button>
    <div class="modal-section-body" id="modal-salary"></div>
  </div>
  <div class="modal-section">
    <button class="modal-section-hdr" onclick="toggleModalSec(this)">Notes <span>▶</span></button>
    <div class="modal-section-body" id="modal-notes"></div>
  </div>
</div>

<script>
// ── TRACE REGISTRY (indices used in all Plotly.restyle calls below) ──────────
// 0 roles          job dots
// 1 focus sphere   Fibonacci point cloud
// 2 connections    Interview→nearest lines
// 3 compare sphere optional second sphere
// 4 salary halos   outer rings
// 5 sphere outline ghost wireframe at sphere surface
// 6 exp boundary   expanded hover wireframe

var data   = {fig_data};
var layout = {fig_layout};
// newPlot is ASYNC — it returns a promise that resolves once gd.data/_fullData
// exist. Any Plotly.restyle("viz", …) called BEFORE this resolves silently
// no-ops (no throw), which is why early slider drags moved the value labels but
// not the 3D sphere. VIZ_READY gates every restyle on the plot being built.
var VIZ_READY = false;
var VIZ_READY_PROMISE = Plotly.newPlot("viz", data, layout, {{responsive:true, displayModeBar:true}})
  .then(function(){{ VIZ_READY = true; }});

// Fit the chart to the #viz flex slot on load and resize.
// responsive:true owns sizing; this nudges it after flex resolves the column width.
// Guard on typeof window so this is a no-op in the Node-based syntax checker.
function fitViz() {{ try {{ Plotly.Plots.resize("viz"); }} catch(e) {{}} }}
if (typeof window !== "undefined") {{
  window.addEventListener("resize", fitViz);
  window.addEventListener("load",   fitViz);
  requestAnimationFrame(fitViz);
}}

// ── core data ──
var JOBS_DATA = {_jobs_json};

// sort dates for timeline
var ALL_DATES = [...new Set(JOBS_DATA.map(j=>j.date))].sort();
var tlMin = ALL_DATES[0], tlMax = ALL_DATES[ALL_DATES.length-1];
var tlCutoffStart = null, tlCutoffEnd = null;

// Formats: "yy-MMM-dd" e.g. "26-Jun-19"
var MONTHS=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
function fmtDate(iso) {{
  if(!iso) return "";
  var p=iso.split("-"); return p[0].slice(2)+"-"+MONTHS[parseInt(p[1])-1]+"-"+p[2];
}}
// lean numeric for tick marks: "yy-mm-dd"
function leanDate(iso) {{ return iso ? iso.slice(2) : ""; }}

// Initialize two-slider timeline
(function initTimeline() {{
  var ms=new Date(tlMin).getTime(), me=new Date(tlMax).getTime(), total=me-ms;
  var today="2026-06-21";

  // Month boundary ticks
  var ticks=[];
  var cursor=new Date(tlMin);
  cursor.setDate(1); cursor.setMonth(cursor.getMonth()+1); // first day of next month
  while(cursor.getTime()<=me) {{
    var pct=(cursor.getTime()-ms)/total*100;
    if(pct>=0&&pct<=100) {{
      var lbl=MONTHS[cursor.getMonth()];
      ticks.push({{pct:pct.toFixed(2), lbl:lbl, isToday:false}});
    }}
    cursor.setMonth(cursor.getMonth()+1);
  }}

  // "Today" marker if in range
  var todayMs=new Date(today).getTime();
  if(todayMs>=ms&&todayMs<=me) {{
    var tp=(todayMs-ms)/total*100;
    ticks.push({{pct:tp.toFixed(2), lbl:"Today", isToday:true}});
  }}

  // Build absolute-positioned tick marks
  var html="";
  ticks.forEach(function(t) {{
    var cls="tm"+(t.isToday?" today":"");
    html+='<span class="'+cls+'" style="left:'+t.pct+'%"><span class="tmk"></span>'+t.lbl+'</span>';
  }});
  document.getElementById("tl-ticks").innerHTML=html;
  document.getElementById("tl-start-lbl").textContent=fmtDate(tlMin);
  document.getElementById("tl-end-lbl").textContent  =fmtDate(tlMax);
}})();

function pctToDate(pct) {{
  var ms=new Date(tlMin).getTime(), me=new Date(tlMax).getTime();
  return new Date(ms+(pct/100)*(me-ms)).toISOString().slice(0,10);
}}

// ── active filter state ──
var activeStatuses = new Set(["Applied","Interview","Queued","Drafted","Ready","Ported","Target"]);
var showLabels    = false;
var showSalRings  = false;
var showConn      = false;
var showCmp       = false;
// tlCutoffStart / tlCutoffEnd managed by filterTimeline()
var fitFloor      = 1;
var salMin        = 55, salMax = 220;
var textFilter    = "";

// Base marker sizes and colors (by index)
var BASE_SIZES  = JOBS_DATA.map(j => j.status==="Interview" ? 20 : j.status==="Target" ? 9 : 12);
var BASE_SYMB   = JOBS_DATA.map(j => j.status==="Interview" ? "diamond" : j.status==="Target" ? "cross" : "circle");
var FIT_COLORS  = {_fit_colors};
var P_VALS      = {_p_vals};
var SAL_VALS    = {_sal_vals};
var STA_COLORS  = {_status_colors};

var colorMode = "fit";

function applyFilters() {{
  // text filter value
  textFilter = document.getElementById("f-text").value.toLowerCase();
  fitFloor   = parseInt(document.getElementById("f-fit").value);
  salMin     = parseInt(document.getElementById("f-smin").value);
  salMax     = parseInt(document.getElementById("f-smax").value);
  document.getElementById("f-fit-v").textContent  = "★".repeat(fitFloor);
  document.getElementById("f-smin-v").textContent = salMin+"K";
  document.getElementById("f-smax-v").textContent = salMax+"K";

  var sizes = JOBS_DATA.map((j,i) => {{
    if (!activeStatuses.has(j.status)) return 0;
    if (j.fit < fitFloor) return 0;
    if (j.sal < salMin || j.sal > salMax) return 0;
    if (tlCutoffStart && j.date < tlCutoffStart) return 0;
    if (tlCutoffEnd   && j.date > tlCutoffEnd)   return 0;
    if (textFilter && !(j.label+j.org+j.status).toLowerCase().includes(textFilter)) return 0;
    return j.status==="Interview" ? 20 : 12;
  }});

  var modes = showLabels ? ["markers+text"] : ["markers"];
  var tcolor = JOBS_DATA.map((j,i) => sizes[i]>0 ? "rgba(220,225,255,0.85)" : "rgba(0,0,0,0)");

  // Salary rings: outer halo trace (trace[4]) sized by salary band — very visible
  var lw, lc, markerSizes;
  lw = JOBS_DATA.map((j,i) => j.status==="Interview" ? 3 : 1);
  lc = JOBS_DATA.map((j,i) => j.status==="Interview" ? "#f59e0b" : "rgba(255,255,255,0.5)");
  markerSizes = sizes;

  if (showSalRings) {{
    // Halo: ring size = salary band, color = salary tier
    var haloSizes = JOBS_DATA.map((j,i) => {{
      if(!sizes[i]) return 0;
      // Base dot + outer ring: band width $140K→32, $120K→26, $100K→22, $80K→18, <80→14
      return j.sal>160?38:j.sal>140?32:j.sal>120?26:j.sal>100?22:j.sal>80?18:14;
    }});
    var haloColors = JOBS_DATA.map((j,i) => {{
      if(!sizes[i]) return "rgba(0,0,0,0)";
      return j.sal>140?"rgba(246,195,50,0.35)":j.sal>110?"rgba(80,200,120,0.30)":"rgba(140,160,220,0.25)";
    }});
    Plotly.restyle("viz",{{
      x:[JOBS_DATA.map(j=>j.x)], y:[JOBS_DATA.map(j=>j.y)], z:[JOBS_DATA.map(j=>j.z)],
      visible:[true], mode:["markers"],
      "marker.size":[haloSizes], "marker.color":[haloColors],
      "marker.opacity":[1], "marker.line.width":[2],
      "marker.line.color":[haloColors.map(c=>c.replace("0.35","0.7").replace("0.30","0.65").replace("0.25","0.6"))],
      hoverinfo:["skip"]
    }}, [4]);
  }} else {{
    Plotly.restyle("viz",{{visible:[false]}}, [4]);
  }}

  Plotly.restyle("viz", {{
    "marker.size": [markerSizes], mode: modes,
    "textfont.color": [tcolor],
    "marker.line.width": [lw],
    "marker.line.color": [lc]
  }}, [0]);
}}

function toggleStatus(pill, status) {{
  pill.classList.toggle("off");
  if (activeStatuses.has(status)) activeStatuses.delete(status);
  else activeStatuses.add(status);
  applyFilters();
}}

function toggleLabels(btn) {{
  showLabels = !showLabels;
  btn.classList.toggle("active", showLabels);
  applyFilters();
}}

function toggleSalaryRings(btn) {{
  showSalRings = !showSalRings;
  btn.classList.toggle("active", showSalRings);
  applyFilters();
}}

// ── colour mode ──
var COLOR = {{
  fit:    {{ colors:FIT_COLORS, cmin:1,   cmax:5,   cs:"RdYlBu", title:"Fit ★" }},
  prob:   {{ colors:P_VALS,     cmin:0,   cmax:50,  cs:"Blues",  title:"P(int) %" }},
  sal:    {{ colors:SAL_VALS,   cmin:60,  cmax:210, cs:"Greens", title:"Salary $K" }},
  status: {{ colors:STA_COLORS, cmin:null,cmax:null, cs:[[0,"#d73027"],[0.5,"#fc8d59"],[1,"#4b5cc4"]], title:"" }}
}};

function setColor(btn, mode) {{
  colorMode = mode;
  document.querySelectorAll("#sidebar .cbtn").forEach(b => {{
    if (["btn-fit","btn-prob","btn-sal","btn-status"].includes(b.id)) b.classList.remove("active");
  }});
  btn.classList.add("active");
  var c = COLOR[mode];
  Plotly.restyle("viz", {{
    "marker.color": [c.colors], "marker.cmin": [c.cmin], "marker.cmax": [c.cmax],
    "marker.colorscale": [c.cs], "marker.colorbar.title": [c.title]
  }}, [0]);
}}

// ── axis / sphere utils ──
var AXIS_LABELS = {{
  x: ["","Startup","Innovation org","Nonprofit","Post-secondary","Gov"],
  y: ["","Ops","Change mgmt","Strategy","Programs/Partnerships","Ecosystem/R&D"],
  z: ["","Specialist","Officer/Advisor","Manager","Director/ED","VP/C-suite"]
}};
var BOUNDARY_LABELS = ["","Very strict","Strict","Fairly strict","Moderate","Medium",
                        "Fairly loose","Loose","Very loose","Very loose","Fuzzy"];

function wireframeSphere(cx,cy,cz,rx,ry,rz,nLat,nLon) {{
  var xs=[],ys=[],zs=[];
  for(var i=1;i<nLat;i++){{
    var u=Math.PI*i/nLat;
    for(var j=0;j<=nLon;j++){{ var v=2*Math.PI*j/nLon; xs.push(cx+rx*Math.sin(u)*Math.cos(v)); ys.push(cy+ry*Math.sin(u)*Math.sin(v)); zs.push(cz+rz*Math.cos(u)); }}
    xs.push(null);ys.push(null);zs.push(null);
  }}
  for(var j=0;j<nLon;j++){{
    var v=2*Math.PI*j/nLon;
    for(var i=0;i<=nLat;i++){{ var u=Math.PI*i/nLat; xs.push(cx+rx*Math.sin(u)*Math.cos(v)); ys.push(cy+ry*Math.sin(u)*Math.sin(v)); zs.push(cz+rz*Math.cos(u)); }}
    xs.push(null);ys.push(null);zs.push(null);
  }}
  return[xs,ys,zs];
}}

function spherePointCloud(cx,cy,cz,rx,ry,rz,n,disp) {{
  var xs=[],ys=[],zs=[],gr=(1+Math.sqrt(5))/2;
  for(var i=0;i<n;i++){{
    var theta=Math.acos(1-2*(i+0.5)/n), phi=2*Math.PI*i/gr;
    var jit=1+disp*(Math.cos(i*7.389+theta)*0.6+Math.sin(i*2.718+phi)*0.4);
    xs.push(cx+rx*jit*Math.sin(theta)*Math.cos(phi));
    ys.push(cy+ry*jit*Math.sin(theta)*Math.sin(phi));
    zs.push(cz+rz*jit*Math.cos(theta));
  }}
  return[xs,ys,zs];
}}

function dist3(a,b){{ return Math.sqrt((a.x-b.x)**2+(a.y-b.y)**2+(a.z-b.z)**2); }}

function getSphereCoords() {{
  return {{
    sx:parseFloat(document.getElementById("sx").value),
    sy:parseFloat(document.getElementById("sy").value),
    sz:parseFloat(document.getElementById("sz").value),
    sr:parseFloat(document.getElementById("sr").value),
    ss:parseInt(document.getElementById("ss").value)
  }};
}}

function updateSphere() {{
  var p=getSphereCoords();
  document.getElementById("sx-v").textContent=p.sx.toFixed(1);
  document.getElementById("sy-v").textContent=p.sy.toFixed(1);
  document.getElementById("sz-v").textContent=p.sz.toFixed(1);
  document.getElementById("sr-v").textContent=p.sr.toFixed(1);
  var s2=11-p.ss;
  var nPts2=Math.round(200+s2*35), disp2=(Math.max(0,(10-s2)/10*0.55)).toFixed(2), opac2=(0.20+(p.ss/10)*0.22).toFixed(2);
  document.getElementById("ss-v").textContent=BOUNDARY_LABELS[p.ss]+" · "+nPts2+"pts disp:"+disp2+" α:"+opac2;
  var xl=AXIS_LABELS.x[Math.min(5,Math.max(1,Math.round(p.sx)))];
  var yl=AXIS_LABELS.y[Math.min(5,Math.max(1,Math.round(p.sy)))];
  var zl=AXIS_LABELS.z[Math.min(5,Math.max(1,Math.round(p.sz)))];
  var hov="<b>Search Focus</b><br>X:"+p.sx.toFixed(1)+" "+xl+"<br>Y:"+p.sy.toFixed(1)+" "+yl+"<br>Z:"+p.sz.toFixed(1)+" "+zl+"<br>Radius:±"+p.sr.toFixed(1)+"  Boundary:"+BOUNDARY_LABELS[p.ss]+"<extra></extra>";
  var s=11-p.ss;  // s: 1(fuzzy)→10(strict)
  // Opacity INCREASES as points disperse (fuzzy = brighter per-point so scattered dots stay visible)
  var nPts =Math.round(200+s*35),         // 235(fuzzy)→550(strict)
      disp =Math.max(0,(10-s)/10*0.55),   // 0.55(fuzzy)→0(strict)
      opac =0.20+(p.ss/10)*0.22,          // 0.22(strict ss=1)→0.42(fuzzy ss=10)
      msize=2.4+s*0.11;                   // 3.5(strict)→2.51(fuzzy)
  if(!VIZ_READY) return;  // plot not built yet → restyle would silently no-op
  var pc=spherePointCloud(p.sx,p.sy,p.sz,p.sr,p.sr,p.sr*0.8,nPts,disp);
  Plotly.restyle("viz",{{x:[pc[0]],y:[pc[1]],z:[pc[2]],mode:["markers"],
    "marker.size":[msize],"marker.color":["rgba(100,160,255,"+opac.toFixed(2)+")"],
    "marker.opacity":[opac],"line.width":[0],hovertemplate:[hov]}}, [1]);

  // Ghost wireframe outline — always at the sphere surface; alpha rises with fuzziness
  // so the dissolved boundary stays spatially legible even when points have scattered
  var gwA=(0.07+(p.ss/10)*0.10).toFixed(3); // 0.077(strict)→0.17(fuzzy)
  var gw=wireframeSphere(p.sx,p.sy,p.sz,p.sr,p.sr,p.sr*0.8,6,9);
  Plotly.restyle("viz",{{x:[gw[0]],y:[gw[1]],z:[gw[2]],
    "line.color":["rgba(120,170,255,"+gwA+")"],"line.width":[1]}}, [5]);

  if(showConn) updateConnectionLines();
}}

// ── connection lines (Interview → nearest non-Interview) ──
function toggleConnections(btn) {{
  showConn = !showConn; btn.classList.toggle("active",showConn);
  if(showConn) updateConnectionLines();
  else Plotly.restyle("viz",{{x:[[]],y:[[]],z:[[]]}}, [2]);
}}
function updateConnectionLines() {{
  var interviews = JOBS_DATA.filter(j=>j.status==="Interview");
  var targets    = JOBS_DATA.filter(j=>j.status!=="Interview"&&j.status!=="Declined");
  var xs=[],ys=[],zs=[];
  interviews.forEach(iv=>{{
    var best=targets.reduce((b,t)=>{{var d=dist3(iv,t);return d<b.d?{{d,t}}:b;}},{{d:Infinity,t:null}});
    if(best.t){{xs.push(iv.x,best.t.x,null);ys.push(iv.y,best.t.y,null);zs.push(iv.z,best.t.z,null);}}
  }});
  Plotly.restyle("viz",{{x:[xs],y:[ys],z:[zs]}}, [2]);
}}

// ── comparison sphere ──
function toggleCompareSphere(btn) {{
  showCmp=!showCmp; btn.classList.toggle("active",showCmp);
  document.getElementById("cmp-controls").style.display=showCmp?"block":"none";
  if(showCmp) updateCompareSphere();
  else Plotly.restyle("viz",{{x:[[]],y:[[]],z:[[]],visible:[false]}}, [3]);
}}
function updateCompareSphere() {{
  var cx2=parseFloat(document.getElementById("cx2").value);
  var cy2=parseFloat(document.getElementById("cy2").value);
  var cz2=parseFloat(document.getElementById("cz2").value);
  document.getElementById("cx2-v").textContent=cx2.toFixed(1);
  document.getElementById("cy2-v").textContent=cy2.toFixed(1);
  document.getElementById("cz2-v").textContent=cz2.toFixed(1);
  var sr=parseFloat(document.getElementById("sr").value);
  var pc=spherePointCloud(cx2,cy2,cz2,sr,sr,sr*0.8,400,0.05);
  Plotly.restyle("viz",{{x:[pc[0]],y:[pc[1]],z:[pc[2]],visible:[true],
    mode:["markers"],"marker.size":[3],"marker.color":["rgba(255,100,160,0.35)"],"marker.opacity":[0.35]}}, [3]);
}}

// ── timeline: two independent sliders (start + end) ──
function updateTlFill() {{
  var ps=parseInt(document.getElementById("tl-start").value);
  var pe=parseInt(document.getElementById("tl-end").value);
  var fill=document.getElementById("tl-fill");
  if(fill){{ fill.style.left=ps+"%"; fill.style.width=(pe-ps)+"%"; }}
}}
function filterTimeline() {{
  var ps=parseInt(document.getElementById("tl-start").value);
  var pe=parseInt(document.getElementById("tl-end").value);
  updateTlFill();
  if(ps>pe){{ // swap if crossed
    document.getElementById("tl-start").value=pe;
    document.getElementById("tl-end").value=ps;
    ps=pe; pe=ps; // re-read after swap attempt — just clamp
    var tmp=ps; ps=parseInt(document.getElementById("tl-start").value);
    pe=parseInt(document.getElementById("tl-end").value);
  }}
  var dStart=pctToDate(ps), dEnd=pctToDate(pe);
  tlCutoffStart=(ps<=0)?null:dStart;
  tlCutoffEnd  =(pe>=100)?null:dEnd;
  document.getElementById("tl-start-lbl").textContent=fmtDate(dStart);
  document.getElementById("tl-end-lbl").textContent  =fmtDate(dEnd);
  applyFilters();
}}
function resetTimeline() {{
  document.getElementById("tl-start").value=0;
  document.getElementById("tl-end").value=100;
  tlCutoffStart=null; tlCutoffEnd=null;
  document.getElementById("tl-start-lbl").textContent=fmtDate(tlMin);
  document.getElementById("tl-end-lbl").textContent  =fmtDate(tlMax);
  updateTlFill();
  applyFilters();
}}

// ── deselect all status pills ──
function deselectAll() {{
  activeStatuses.clear();
  document.querySelectorAll(".spill").forEach(p=>p.classList.add("off"));
  applyFilters();
}}

// ── presets (localStorage) ──
function renderPresets() {{
  var presets=JSON.parse(localStorage.getItem("wiz-presets")||"{{}}");
  var list=document.getElementById("preset-list");
  list.innerHTML="";
  var names=Object.keys(presets);
  names.forEach(name=>{{
    var t=document.createElement("span");
    t.className="preset-tag";
    var lbl=document.createElement("span");
    lbl.textContent=name;
    lbl.addEventListener("click",function(){{ loadPreset(name); }});
    var del=document.createElement("span");
    del.className="pdel";
    del.textContent="✕";
    del.addEventListener("click",function(e){{ e.stopPropagation(); deletePreset(name); }});
    t.appendChild(lbl); t.appendChild(del);
    list.appendChild(t);
  }});
  if(!names.length) list.innerHTML='<span style="color:#444;font-size:11px">No presets saved</span>';
}}
function savePreset() {{
  var name=document.getElementById("preset-name").value.trim(); if(!name)return;
  var p=getSphereCoords();
  var presets=JSON.parse(localStorage.getItem("wiz-presets")||"{{}}");
  presets[name]=p; localStorage.setItem("wiz-presets",JSON.stringify(presets));
  document.getElementById("preset-name").value=""; renderPresets();
}}
function loadPreset(name) {{
  var presets=JSON.parse(localStorage.getItem("wiz-presets")||"{{}}");
  var p=presets[name]; if(!p)return;
  document.getElementById("sx").value=p.sx; document.getElementById("sy").value=p.sy;
  document.getElementById("sz").value=p.sz; document.getElementById("sr").value=p.sr;
  document.getElementById("ss").value=p.ss; updateSphere();
}}
function deletePreset(name) {{
  var presets=JSON.parse(localStorage.getItem("wiz-presets")||"{{}}");
  delete presets[name]; localStorage.setItem("wiz-presets",JSON.stringify(presets)); renderPresets();
}}

// ── screenshot ──
function screenshot() {{
  Plotly.downloadImage("viz",{{format:"png",filename:"job_search_space",width:1400,height:900}});
}}

// ── interview outcomes ──
var OUTCOMES = ["pending","offer","no-offer","waitlisted"];
var OUTCOME_COLORS = {{pending:"#e0b15b",offer:"#46c08a","no-offer":"#d73027",waitlisted:"#a78bfa"}};
var jobOutcomes = {{}};
JOBS_DATA.forEach(j=>{{ if(j.outcome!==null&&j.outcome!==undefined) jobOutcomes[j.label]=j.outcome||"pending"; }});

function renderOutcomes() {{
  var ol=document.getElementById("outcome-list"); ol.innerHTML="";
  Object.keys(jobOutcomes).forEach(label=>{{
    var outcome=jobOutcomes[label];
    var row=document.createElement("div");
    row.style="display:flex;align-items:center;gap:6px;cursor:pointer";
    row.innerHTML='<span style="color:'+OUTCOME_COLORS[outcome]+';font-size:10px">●</span>'+
      '<span style="font-size:11px">'+label+'</span>'+
      '<span style="color:#555;font-size:10px">('+outcome+')</span>';
    row.onclick=()=>cycleOutcome(label);
    ol.appendChild(row);
  }});
}}
function cycleOutcome(label) {{
  var cur=jobOutcomes[label]||"pending";
  var idx=(OUTCOMES.indexOf(cur)+1)%OUTCOMES.length;
  jobOutcomes[label]=OUTCOMES[idx]; renderOutcomes();
}}

// ── dot click modal — bulletproof: reset state on every open, close on
//    backdrop click / ✕ / Escape. The backdrop is VISIBLE (rgba(0,0,0,0.4)). ──
function openModal(job, clickX, clickY) {{
  var m=document.getElementById("dot-modal");
  var bd=document.getElementById("modal-backdrop");

  // Reset cleanly: collapse any section left open from a prior view
  document.querySelectorAll("#dot-modal .modal-section-body").forEach(function(b){{
    b.classList.remove("open");
    var hdr=b.previousElementSibling;
    if(hdr){{ var arr=hdr.querySelector("span"); if(arr) arr.textContent="▶"; }}
  }});

  document.getElementById("dot-modal-title").textContent=job.label;
  document.getElementById("dot-modal-org").textContent=job.org+" · "+job.status;

  // Meta chips
  var meta=document.getElementById("dot-modal-meta"); meta.innerHTML="";
  var chips=[
    ["Fit","★".repeat(job.fit)+"☆".repeat(5-job.fit)],
    ["P(int)",job.p+"%"],["Submitted",fmtDate(job.date)],
    ["Closes",job.closes?fmtDate(job.closes):"—"],
  ];
  chips.forEach(function(c){{
    var s=document.createElement("span"); s.className="meta-chip";
    s.textContent=c[0]+": "+c[1]; meta.appendChild(s);
  }});

  // Application section
  document.getElementById("modal-application").innerHTML=
    "<b>Status:</b> "+job.status+"<br>"+
    "<b>Submitted:</b> "+fmtDate(job.date)+"<br>"+
    (job.outcome?"<b>Outcome:</b> "+job.outcome+"<br>":"")+
    (job.note?"<b>Note:</b> "+job.note:"");

  // Fit section
  document.getElementById("modal-fit").innerHTML=
    "<b>Fit:</b> "+"★".repeat(job.fit)+"☆".repeat(5-job.fit)+" ("+job.fit+"/5)<br>"+
    "<b>P(interview):</b> "+job.p+"%<br>"+
    "<b>P(hire|int):</b> ~"+Math.round(job.p*0.85)+"%<br>"+
    "<b>Coords:</b> X:"+job.x+" Y:"+job.y+" Z:"+job.z;

  // Salary section
  document.getElementById("modal-salary").innerHTML=
    "<b>Est. midpoint:</b> $"+job.sal+"K<br>"+
    "<b>Range:</b> $"+job.sal_min+"K – $"+job.sal_max+"K<br>"+
    "<b>Band width:</b> $"+(job.sal_max-job.sal_min)+"K";

  // Notes
  document.getElementById("modal-notes").innerHTML=
    job.note ? job.note : "<i style='color:#5a6090'>No notes</i>";

  // Position modal near click but keep on screen
  var mw=330, mh=340;
  var vw=window.innerWidth, vh=window.innerHeight;
  var left=Math.max(8, Math.min(clickX+12, vw-mw-16));
  var top=Math.max(8, Math.min(clickY-20, vh-mh-60));
  m.style.left=left+"px"; m.style.top=top+"px";
  m.classList.add("open");
  bd.classList.add("open");
}}
function closeModal() {{
  document.getElementById("dot-modal").classList.remove("open");
  document.getElementById("modal-backdrop").classList.remove("open");
}}
function toggleModalSec(hdr) {{
  var body=hdr.nextElementSibling;
  var arr=hdr.querySelector("span");
  var isOpen=body.classList.contains("open");
  body.classList.toggle("open",!isOpen);
  if(arr) arr.textContent=isOpen?"▶":"▼";
}}
// Escape closes the modal (bulletproofing — never leave a backdrop stuck)
if (typeof document !== "undefined" && typeof document.addEventListener === "function") {{
  document.addEventListener("keydown", function(e) {{
    if (e.key === "Escape") closeModal();
  }});
}}

// Hover over sphere cloud → show expanded radius wireframe
(function wireSphereHover() {{
  var el=document.getElementById("viz");
  if(!el||typeof el.on!=="function") return;
  el.on("plotly_hover",function(ev) {{
    if(!ev||!ev.points||!ev.points.length) return;
    if(ev.points[0].data.name!=="focus sphere") return; // only on sphere trace
    var p=getSphereCoords();
    var s=11-p.ss;
    var disp=Math.max(0,(10-s)/10*0.55);
    var rExp=p.sr*(1+disp*0.90); // outer edge of dispersed cloud
    if(disp<0.05){{ // near-strict: no meaningful expansion to show
      Plotly.restyle("viz",{{"line.color":["rgba(160,200,255,0.0)"]}}, [6]);
      return;
    }}
    var alpha=(0.12+disp*0.20).toFixed(3); // more visible the more dispersed
    var ew=wireframeSphere(p.sx,p.sy,p.sz,rExp,rExp,rExp*0.8,5,8);
    Plotly.restyle("viz",{{x:[ew[0]],y:[ew[1]],z:[ew[2]],
      "line.color":["rgba(180,220,255,"+alpha+")"],"line.width":[1]}}, [6]);
  }});
  el.on("plotly_unhover",function() {{
    Plotly.restyle("viz",{{"line.color":["rgba(160,200,255,0.0)"]}}, [6]);
  }});
}})();

// Wire up Plotly click event (Plotly attaches .on after newPlot)
(function wireClick() {{
  var el=document.getElementById("viz");
  if(el&&typeof el.on==="function") {{
    el.on("plotly_click",function(ev) {{
      if(!ev||!ev.points||!ev.points.length) return;
      var pt=ev.points[0];
      if(!pt||!pt.data||pt.data.name!=="roles") return;
      var idx=pt.pointIndex, job=JOBS_DATA[idx];
      if(!job) return;
      openModal(job, ev.event?ev.event.clientX:600, ev.event?ev.event.clientY:400);
    }});
  }}
}})();

// ── copy focus (pipeline prompt) ──
function copyFocus() {{
  var p=getSphereCoords();
  var xl=AXIS_LABELS.x[Math.min(5,Math.max(1,Math.round(p.sx)))];
  var yl=AXIS_LABELS.y[Math.min(5,Math.max(1,Math.round(p.sy)))];
  var zl=AXIS_LABELS.z[Math.min(5,Math.max(1,Math.round(p.sz)))];
  var bl=BOUNDARY_LABELS[p.ss];
  var xr=[+(p.sx-p.sr).toFixed(1),+(p.sx+p.sr).toFixed(1)];
  var yr=[+(p.sy-p.sr).toFixed(1),+(p.sy+p.sr).toFixed(1)];
  var zr=[+(p.sz-p.sr*0.8).toFixed(1),+(p.sz+p.sr*0.8).toFixed(1)];
  var prompt="/pipeline\\n\\nSearch focus from job_search_viz.html:\\nSEARCH_FOCUS="+
    JSON.stringify({{cx:p.sx,cy:p.sy,cz:p.sz,radius:p.sr,boundary:p.ss,
      label:{{x:xl,y:yl,z:zl}},boundary_label:bl,
      search_bias:{{x_range:xr,y_range:yr,z_range:zr}}}})+"\\n\\n"+
    "Sector:"+xl+" X="+p.sx.toFixed(1)+" ["+xr+"]\\n"+
    "Innovation:"+yl+" Y="+p.sy.toFixed(1)+" ["+yr+"]\\n"+
    "Seniority:"+zl+" Z="+p.sz.toFixed(1)+" ["+zr+"]\\n"+
    "Boundary:"+bl+" ("+( p.ss<=3?"strict: only close roles":"broader sweep ok")+")";
  navigator.clipboard.writeText(prompt).then(()=>{{
    var m=document.getElementById("copy-msg"); m.style.display="inline";
    setTimeout(()=>m.style.display="none",2500);
  }});
}}

// ── init ──
renderPresets();
renderOutcomes();
updateTlFill();
// updateSphere() restyles trace[1], so it MUST wait for newPlot to resolve —
// running it synchronously here races the async plot build and no-ops.
VIZ_READY_PROMISE.then(updateSphere);
</script>
</body>
</html>"""

out = Path(__file__).resolve().parents[3] / "working" / "active" / "job_search_viz.html"
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print(f"Written: {out}")
print(f"Centre of current search cluster: X={cx:.2f} Y={cy:.2f} Z={cz:.2f}")
