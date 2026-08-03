#!/usr/bin/env python3
"""Rebuild the visualizations and serve them.

    python -B tools/serve.py [--port 8000] [--host 127.0.0.1] [--no-build]

Opening `job_search_viz.html` off the filesystem works, but it is a bad default:
you have to know the path, `file://` restricts what the page may fetch, and
there is nothing to tell you the file is stale. This rebuilds from the current
`JOBS` and `SWEEPS` data, writes an index, and serves the directory over HTTP.

Serves `working/active/` as the document root. That directory is the repo's
"live work only" area, so anything you are currently looking at is reachable and
nothing else is exposed — in particular `documents/` and `working/outreach/`
stay outside the served tree, which is deliberate.

Binds to localhost by default. Pass `--host 0.0.0.0` to accept connections from
outside the machine, which is what the container does; do not do that on a
network you do not control, because the sweep documents in this directory name
the roles you are applying for.

Stdlib only.
"""

from __future__ import annotations

import argparse
import http.server
import socketserver
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCROOT = ROOT / "working" / "active"
BUILDER = ROOT / "working" / "scripts" / "viz" / "build_job_viz_three.py"


def build() -> bool:
    """Regenerate the viz. Returns False if the build failed."""
    print("Rebuilding the visualization ...")
    result = subprocess.run([sys.executable, "-B", str(BUILDER)], cwd=str(ROOT))
    if result.returncode != 0:
        print("!! build failed — serving whatever is already on disk.")
        return False
    return True


def write_index(built: bool) -> None:
    """A landing page listing what is actually here, rather than a bare file list."""
    pages, docs = [], []
    for path in sorted(DOCROOT.glob("*.html")):
        if path.name == "index.html":
            continue
        pages.append(path.name)
    for path in sorted(DOCROOT.glob("*.md")):
        docs.append(path.name)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    status = "rebuilt just now" if built else "BUILD FAILED — this may be stale"

    def links(names: list[str], empty: str) -> str:
        if not names:
            return f'<p class="empty">{empty}</p>'
        return "\n".join(
            f'      <li><a href="./{n}">{n}</a></li>' for n in names
        )

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>jobcube — local</title>
<style>
  :root {{ --bg:#0b0910; --panel:#15111f; --line:#2a2438; --ink:#e9e6f5;
           --dim:#8d85a8; --violet:#b98cff; --green:#3fca7d;
           --mono: ui-monospace,"Cascadia Mono",Consolas,monospace; }}
  * {{ box-sizing:border-box }}
  body {{ margin:0; min-height:100vh; background:var(--bg); color:var(--ink);
    font:15px/1.6 "Segoe UI",system-ui,sans-serif;
    background-image:linear-gradient(rgba(185,140,255,.055) 1px,transparent 1px),
      linear-gradient(90deg,rgba(185,140,255,.055) 1px,transparent 1px);
    background-size:44px 44px; padding:clamp(28px,6vw,72px) clamp(18px,5vw,48px) }}
  .wrap {{ max-width:760px; margin:0 auto; display:flex; flex-direction:column; gap:30px }}
  h1 {{ font-family:var(--mono); font-size:44px; letter-spacing:-.045em; margin:0; font-weight:600 }}
  h1 .c {{ color:var(--violet) }}
  .tag {{ color:var(--dim); margin:0 }}
  h2 {{ font-family:var(--mono); font-size:12px; letter-spacing:.14em; text-transform:uppercase;
       color:var(--dim); margin:0 0 10px; font-weight:600 }}
  ul {{ list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:1px }}
  li a {{ display:block; padding:13px 16px; background:var(--panel); border:1px solid var(--line);
    border-radius:4px; color:var(--violet); text-decoration:none; font-family:var(--mono); font-size:14px }}
  li a:hover, li a:focus {{ border-color:var(--violet); outline:none }}
  .empty {{ color:var(--dim); font-size:14px; margin:0; padding:13px 16px;
    border:1px dashed var(--line); border-radius:4px }}
  footer {{ color:var(--dim); font-family:var(--mono); font-size:11.5px; letter-spacing:.06em;
    border-top:1px solid var(--line); padding-top:16px }}
  .ok {{ color:var(--green) }} .bad {{ color:#ff8f8f }}
</style></head>
<body><div class="wrap">
  <div>
    <h1>job<span class="c">cube</span></h1>
    <p class="tag">Served locally. Everything below is generated from the data in this repo.</p>
  </div>
  <section>
    <h2>Visualizations</h2>
    <ul>
{links(pages, "Nothing built yet. Run the builder, or start this server without --no-build.")}
    </ul>
  </section>
  <section>
    <h2>Live documents</h2>
    <ul>
{links(docs, "No sweep or interview documents in working/active/ right now.")}
    </ul>
  </section>
  <footer>
    <span class="{'ok' if built else 'bad'}">{status}</span> · {stamp}<br/>
    Document root is working/active/ — documents/ and working/outreach/ are outside it.
  </footer>
</div></body></html>
"""
    (DOCROOT / "index.html").write_text(html, encoding="utf-8")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DOCROOT), **kwargs)

    def end_headers(self):
        # Generated files change on every build; a cached viz is a stale viz.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        # One tidy line per request instead of the default noise.
        print(f"  {self.address_string()} {fmt % args}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and serve the visualizations.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1",
                        help="use 0.0.0.0 to accept outside connections (the container does)")
    parser.add_argument("--no-build", action="store_true", help="serve what is already on disk")
    args = parser.parse_args()

    DOCROOT.mkdir(parents=True, exist_ok=True)
    built = True if args.no_build else build()
    write_index(built)

    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer((args.host, args.port), Handler) as httpd:
            shown = "localhost" if args.host in ("127.0.0.1", "0.0.0.0") else args.host
            print(f"\n  jobcube serving {DOCROOT.relative_to(ROOT).as_posix()}")
            print(f"  http://{shown}:{args.port}/\n")
            print("  Ctrl-C to stop.\n")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped.")
    except OSError as exc:
        print(f"!! could not bind {args.host}:{args.port} — {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
