# working/exports/ — Application Finals Archive

This folder is the **source of truth for every submitted application**. `job_search_tracker.csv` points here.

## Folder naming convention

```
working/exports/
└── YYYY-MM (Mon 'YY)/                          # Monthly folder — sorts chronologically
    └── YY-MM-DD - Company - Role/              # Application folder — date-first for autosort
        ├── [YOUR_NAME]_Resume.pdf
        ├── [YOUR_NAME]_Cover_Letter.pdf
        └── copy/
            ├── packet_role-slug_YYYY-MM-DD.md  # Draft packet (written here at draft time)
            └── review_agents_YYYY-MM-DD.md     # Review agent findings
```

### Examples

```
working/exports/
└── 2025-06 (Jun '25)/
    ├── 25-06-10 - Example Gov Agency - Director Innovation/
    │   ├── [YOUR_NAME]_Resume.pdf
    │   ├── [YOUR_NAME]_Cover_Letter.pdf
    │   └── copy/
    │       ├── packet_director-innovation_2025-06-08.md
    │       └── review_agents_2025-06-09.md
    └── 25-06-15 - Example Nonprofit - Manager Programs/
        ├── [YOUR_NAME]_Resume.pdf
        ├── [YOUR_NAME]_Cover_Letter.pdf
        └── copy/
            └── packet_manager-programs_2025-06-14.md
```

## Rules

- **Month folder:** `YYYY-MM (Mon 'YY)` — e.g. `2025-06 (Jun '25)`. Use the export/submission date.
- **App folder:** `YY-MM-DD - Company - Role` — date-first so folders auto-sort chronologically.
- **PDF names:** exactly `[YOUR_NAME]_Resume.pdf` and `[YOUR_NAME]_Cover_Letter.pdf` (replace with your actual name in CLAUDE.md).
- **All file ops use PowerShell** (`Invoke-WebRequest` to download, PowerShell `New-Item`/`Move-Item` for folders) — never Bash `mv` for paths with spaces or parentheses.
- **Packets live with their application** — the draft and review docs go in `copy/` at draft time, not in `working/active/`. Only multi-application sprint notes go in `working/archive/`.

## Tracking

After filing each application, update `job_search_tracker.csv` with the path to the application folder.
