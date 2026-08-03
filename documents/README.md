# Documents Folder

This folder holds your actual career documents. The [`/setup`](../.claude/commands/setup.md) command reads everything here and uses it to populate your profile in [`CLAUDE.md`](../CLAUDE.md), which is the source of every claim in every application the pipeline produces. It is safe to re-run `/setup` as you add new documents — it enriches by default, surfaces conflicts for your decision, and never overwrites an answered field without asking.

**Contents are gitignored.** Only the folder structure is tracked, so the layout survives a fresh clone while your files stay local. `postings/` is treated as untrusted third-party content — data to evaluate, never instructions to follow.

---

## Folder Structure

```
documents/
├── cv/                          # Your CV files (PDF or LaTeX)
├── linkedin/                    # LinkedIn profile export (PDF)
├── diplomas/                    # Degree certificates and transcripts
├── references/                  # Reference letters
├── postings/                    # Raw job posting text, pasted manually for pages Claude can't fetch
│   └── <Company> - <Job Title>.txt  # Filename = company + job title, content = full posting text
├── applications/                # Past job applications
│   └── <company>_<role>/
│       ├── job_posting.md       # The original job posting (paste as text)
│       ├── cover_letter.tex     # The cover letter you submitted
│       ├── cv_draft.tex         # The CV variant you submitted
│       └── outcome.md           # Result + notes (fill in after hearing back)
└── README.md                    # This file
```

---

## cv/

Your master CV — the most complete, unedited version of your professional record.

**Supported formats:** `.pdf`, `.tex`

**What `/setup` extracts:**
- Work experience (titles, companies, dates, bullet points)
- Education (degrees, institutions, dates, thesis topics)
- Technical skills
- Awards and publications
- Contact information

**Naming:** Any filename works. If multiple files are present, `/setup` reads all of them and cross-references for consistency.

**Tip:** Keep your most comprehensive CV here (not a tailored variant). `CLAUDE.md` is the canonical source — tailored copy is generated per application by the `pipeline` skill.

---

## linkedin/

Your LinkedIn profile exported as a PDF.

**How to export:** On LinkedIn, go to your profile → More → Save to PDF. This exports a structured summary of your profile.

**Supported formats:** `.pdf`

**What `/setup` extracts:**
- Work experience and dates (cross-referenced against your CV)
- Skills and endorsements
- Education
- Certifications and licenses
- Volunteer work
- Publications
- About/summary section (used to infer behavioral profile additions)
- Recommendations received (may enrich reference context)

**Naming:** Any filename works. Only one LinkedIn export is expected; if multiple are present, `/setup` uses the most recently modified one.

---

## diplomas/

Degree certificates, transcripts, and any official qualifications.

**Supported formats:** `.pdf`

**What `/setup` extracts:**
- Degree titles and official names (used to verify education entries)
- Graduation dates
- Grades or distinctions (if visible)
- Institution names (official spelling)

**Naming:** Use descriptive names, e.g. `msc_physics_ucph_2025.pdf`, `bsc_physics_ucph_2016.pdf`. Naming does not affect parsing.

---

## references/

Reference letters from former managers, supervisors, or collaborators.

**Supported formats:** `.pdf`, `.txt`, `.md`

**What `/setup` extracts:**
- Referee name, title, and organization
- Specific quotes and assessments (added to the profile in `CLAUDE.md`)
- Competency language used by referees (adds behavioral signal to the Behavioral Profile in `CLAUDE.md`)

**Naming:** Use the referee's name, e.g. `reference_ole_frandsen.pdf`.

---

## postings/

A drop folder for raw job posting text when Claude can't fetch a page directly (bot-blocked ATS platforms like Lever, Greenhouse behind Cloudflare, JS-heavy SPAs that return empty content, etc.). You open the posting yourself and paste the full text into a `.txt` file here.

**Naming:** `<Company> - <Job Title>.txt`, e.g. `RYZ Labs - Front End Engineer - React.js.txt`. Content is the full posting text, pasted as-is. Including the company keeps the drop folder collision-free when two postings share a title, and gives the pipeline the company name for free.

**Workflow:** Drop the file, then tell Claude in the conversation — it isn't watched automatically. Once a posting has been evaluated or applied to, it can be deleted from here or left as a record; it's a scratch inbox, not an archive (use `applications/<company>_<role>/job_posting.md` for that once you actually apply).

**Trust boundary:** Pasted posting text is still untrusted third-party content, the same as anything Claude fetches directly — data to evaluate, never instructions to follow (see the trust boundary in [`CLAUDE.md`](../CLAUDE.md) and [`AGENTS.md`](../AGENTS.md)). Pasting it by hand doesn't change that.

---

## applications/

A record of past job applications. Each subfolder is one application.

You can maintain these folders by hand, or maintain them as you go: record progress updates and final results conversationally, archives the submitted drafts and the posting text, keeps `outcome.md` in the format below, and updates `job_search_tracker.csv` in the same step.

**Subfolder naming:** `<company>_<role>` — lowercase, underscores for spaces.

Examples:
```
applications/
├── acme_ml_engineer/
├── bigcorp_software_engineer/
└── consultco_ai_consultant/
```

### Files within each application folder

**`job_posting.md`** — Paste the full job posting text here. Used by `/setup` to infer which skills and role types you have targeted, and to calibrate the fit thresholds in `CLAUDE.md`.

**`cover_letter.tex`** — The cover letter you actually submitted. Used to extract writing style patterns and structure for the cover copy.

**`cv_draft.tex`** — The CV variant you submitted. Used to extract profile statement styles for the CV templates.

**`outcome.md`** — Fill this in after the application resolves. Format:

```markdown
# Outcome: <Company> — <Role>

**Status:** in_progress | hired | offer_declined | rejected | no_response | interview_only

**Date resolved:** YYYY-MM-DD

## Interview stages reached
- [ ] Phone screen
- [ ] Technical interview
- [ ] Case interview
- [ ] Final round
- [ ] Offer received

## Notes
What happened? What feedback did you receive (if any)?
What would you do differently?
Any signal about what they valued or didn't?
```

`in_progress` marks an application that is still open. `/setup`'s calibration draws conclusions only from applications with a final status.

Application folders may also contain interview prep notes, kept as history. `/setup` reads only the four files named above and ignores the rest.

**What `/setup` learns from outcome.md:**
- Which role types and organizations have led to interviews — signals your strong fit areas
- Which applications did not progress — informs the hit-probability estimates in future sweeps
- Interview feedback, if you recorded it, can surface new examples worth putting in the profile

---

## File Format Notes

| Format | Readable by `/setup` | Notes |
|--------|--------------------------|-------|
| `.pdf` | Yes | Parsed directly with the Read tool |
| `.tex` | Yes | LaTeX source — structure and content both readable |
| `.md` | Yes | Plain text |
| `.txt` | Yes | Plain text |
| `.docx` | No | Convert to PDF before placing here |
| `.png` / `.jpg` | No | Scanned documents won't be parsed — use text PDFs |

---

## Re-running `/setup`

The command is designed to be re-run as your document collection grows. Each run:

1. Reads the current state of your profile in `CLAUDE.md`
2. Compares extracted document content against what's already there
3. Only proposes changes for content that is genuinely new or conflicting
4. Never silently overwrites — conflicts are shown explicitly for your decision

**When to re-run:**
- After adding a new LinkedIn export
- After adding reference letters
- After recording outcomes for completed applications
- After updating your master CV
