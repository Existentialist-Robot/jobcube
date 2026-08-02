# working/active/

Live work only — the things you are looking at right now:

| What | Where it comes from |
|---|---|
| `sweep_<YYYY-MM-DD>.md` | one current sweep, from [`../templates/SWEEP_TEMPLATE.md`](../templates/SWEEP_TEMPLATE.md) |
| `job_search_viz.html` | generated — `python working/scripts/viz/build_job_viz_three.py` |
| `search_focus.json` | written by the pipeline skill from the viz's "Copy Focus" button |
| the current interview prep doc | drafted per interview |

Everything else is filed: drafted packets live with their application under
`working/exports/<month>/<date - company - role>/copy/`, and finished sweeps and
sprint notes move to `working/archive/`. If this folder has more than a handful
of files in it, something that should have been filed wasn't.

`*.html` here is gitignored. The viz is build output — regenerate it rather than
committing 100+ KB that re-conflicts on every merge. The data behind it lives in
`build_job_viz.py` (`JOBS`) and `build_sweep_viz.py` (`SWEEPS` / `FUTURE`), which
are tracked.
