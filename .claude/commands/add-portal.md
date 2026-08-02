# /add-portal — Investigate a job board and register it

You are helping the user add a job board to this repo's search registry.

`.claude/skills/pipeline/boards.md` is the hand-maintained list of boards that
have been *verified* to return plain HTML that WebFetch can read, along with
their search-URL patterns and the boards that are known to fail.
`.claude/skills/pipeline/sources.json` is the machine-readable side: job APIs
and ATS endpoints. Both are only as good as the verification behind them, and
an unverified row is worse than no row — it sends every future sweep at a board
that returns nothing.

This command does the verification, then writes the row. It never registers a
board it has not successfully fetched real results from.

`$ARGUMENTS` may contain a subcommand, a portal URL, or nothing.

Follow these steps **in order**.

---

## Step 0: Parse arguments

- `--list`: read `boards.md` and print the current registry — board name, sector
  focus, and last-verified date — plus the Known Failures table. Then stop.
- `--recheck <board>`: skip the interview, take the board's existing row as the
  starting hypothesis, and run Steps 2–4 against it. Use this when a sweep comes
  back empty from a board that used to work.
- A URL: treat it as the portal URL and go to Step 1.
- Nothing: start the interview at Step 1.

---

## Step 1: Interview

Ask only what `$ARGUMENTS` hasn't already answered:

1. **Portal URL** — the board's public site.
2. **Sector focus** — what this board is *for* (government, nonprofit,
   municipal, tech/startup, post-secondary, aggregator). This becomes the Sector
   Focus column and is what makes the registry useful; a board with no focus is
   just another aggregator.
3. **Market and language** — country/region, and the language postings are
   written in. Non-English boards need their local-language search terms
   recorded, or every future query will be in the wrong language.
4. **A realistic test query** — a role title the user would actually search for.
   Used for the live test in Step 3.

---

## Step 2: Investigate

Reconnaissance before writing anything. This is the step that decides whether
the board belongs in the registry at all.

1. **Check access rules first, before fetching search pages.**
   - Fetch `robots.txt`. Note whether the search and detail paths are
     disallowed.
   - If the board requires a login to see listings, **stop.** This repo's search
     path is WebFetch against public pages; an auth-walled board cannot work
     that way. Tell the user, and check whether the board has an official API —
     if it does, that belongs in `sources.json`, not `boards.md`.
   - If robots.txt disallows the paths, or the terms prohibit automated access,
     say so plainly and let the user decide. If they proceed, the registry row
     must carry a personal-use-only note: keep volume low, no bulk or commercial
     use, their own responsibility.

2. **Find the search URL pattern.** Load the search page and identify the search
   endpoint and its parameters: the keyword parameter, and any for location,
   posting age, and pagination. Write it in the registry's `{placeholder}`
   style — `https://example.com/search?q={keywords}&l={location}`.

3. **Prefer an API if one exists.** Check the page source for XHR calls to
   `/api/` paths, and check whether the board is really an ATS in disguise
   (Greenhouse, Lever, and Ashby all expose keyless JSON — the endpoint patterns
   are documented at the top of `sources.json`). **A JSON endpoint belongs in
   `sources.json`, not `boards.md`**, and is worth far more than an HTML board:
   structured fields, no parsing, no markup drift.

4. **Fetch one real search-results page** for the test query and confirm you can
   actually read: title, organization, location, posting date, and the link to
   each posting. Note what anchors each field.

5. **Decide the verdict.** A board qualifies for the registry only if the search
   results arrive as plain HTML that WebFetch returns and you can parse. If it
   is JS-rendered, 403s, or returns an empty shell, it goes in **Known
   Failures** with the specific reason — that row saves the next sweep from
   retrying it.

---

## Step 3: Live test (MANDATORY)

Never register a board that has not returned real results.

1. WebFetch the search URL with the user's test query substituted in.
2. Confirm the results are real: multiple distinct postings, populated titles
   and organizations, links that resolve back to the board. An HTML shell with
   no postings in it means JS-rendered — that is a Known Failure, not a board.
3. Follow one result through to its detail page and confirm the description,
   close date, and apply route are readable.
4. Run the query a second time with a different keyword to confirm the pattern
   generalizes rather than working by accident on one term.
5. Keep the volume low — a handful of requests, not a crawl. If the board rate-
   limits you mid-test, back off and tell the user.

If any of this fails, go back to Step 2 and fix the URL pattern, or record the
board as a Known Failure. Do not register a half-working board.

---

## Step 4: Register

**If it passed** — add a row to the Board Registry table in `boards.md`:

| # | Board | Base URL | Search URL Pattern | Sector Focus | Notes |

Notes should carry what the next person needs: the local-language search terms
for a non-English board, pagination quirks, whether location is a real parameter
or has to go inside the keyword query, and the personal-use warning if Step 2
found one. Update the "Last verified" line at the top of the file with today's
date.

**If it has a JSON API or is an ATS** — add it to `sources.json` instead, under
`apis` or `ats_verified`, with a `trust` level (3 = full posting text, safe to
rate from; 2 = partial, verify against the source; 1 = discovery only) and a
`verified` date. Note it in `boards.md` only if it *also* has a usable HTML
search.

**If it failed** — add a row to the Known Failures table with the specific
reason (JS-rendered, 403, auth-walled, no usable search endpoint). This is not a
consolation prize; it is the row that stops the board being retried every sweep.

Also add the board's own search terms to the Search Keywords section if its
sector isn't already covered there.

---

## Step 5: Confirm

Present a short summary:

> **`<board>` — <registered | recorded as a known failure>.**
>
> - Sector: `<focus>` · Market: `<market/language>`
> - Search pattern: `<url pattern>`
> - Live test: `<test query>` returned `<N>` results; detail page verified
> - Recorded in: `boards.md` `<Registry | Known Failures>` / `sources.json`
> - `<personal-use warning, if any>`

Then remind the user that registry rows expire: when a sweep comes back empty
from a board that used to work, re-run this command with `--recheck` rather than
assuming the market is quiet.

---

## Design principles

- **Investigate before registering.** The command never writes a row from a
  guess. Step 2 fetches real responses and Step 3 verifies against live data.
- **A failure is a result worth recording.** Known Failures is the half of the
  registry that saves the most time, because it stops the same dead board being
  retried indefinitely.
- **APIs beat HTML.** An ATS JSON endpoint is worth more than five scraped
  boards. Always check whether a board is one before writing a scraping row.
- **Access rules are surfaced, not bypassed.** Auth-walled boards are declined,
  robots.txt and ToS restrictions are reported and left to the user's judgment,
  and restricted boards carry a visible personal-use-only note.
- **The output is yours.** Which boards matter depends entirely on your market
  and sector. The generator is the reusable part; the registry it fills in is
  local to your fork.
