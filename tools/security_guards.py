#!/usr/bin/env python3
"""Guards for the ways this repo can leak personal data or widen trust.

    python -B tools/security_guards.py

This is a template people fork and then fill with real personal data — CVs,
postings, the names of real hiring managers. The guards below make the
dangerous changes LOUD rather than impossible: a change that genuinely needs
one must update the allowlist in this file in the same diff, so it shows up in
review instead of sliding through.

Checks:
1. Nothing personal is actually tracked. Reads `git ls-files` and fails on any
   tracked file under documents/ or working/outreach/, any .env, and generated
   viz HTML. This is the check that matters most: the .gitignore rules can be
   right while a file added before the rule stays tracked forever.
2. .gitignore still carries the personal-data rules, and no un-allowlisted
   negation re-includes them. .gitignore is order-sensitive, so a rule can be
   present and still not take effect.
3. .claude/settings.json — every permissions.allow entry is in the reviewed
   allowlist. Pre-approved permissions run without prompting on every fork.
4. Any package.json under .agents/ — no install lifecycle scripts and no
   trustedDependencies, both of which execute code during a dependency install.

Adapted from upstream. The allowlists are this repo's, not upstream's, and
check 1 is new: upstream inferred safety from the ignore rules alone, which
cannot see an already-tracked file.

Stdlib only. Exit 0 on success, 1 with a failure list otherwise.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
errors: list[str] = []

# Permission entries this repo ships. Empty by design — it ships no
# pre-approved permissions, so any entry that appears must be added here in the
# same change.
ALLOWED_PERMISSIONS: set[str] = set()

# Personal-data ignore rules that must never disappear.
REQUIRED_IGNORE_RULES = [
    "salary_data.json",
    "job_scraper/seen_jobs.json",
    "documents/**",
    "working/outreach/**",
    "working/active/*.html",
    ".env",
]

# Negations this repo legitimately ships. Anything else is a failure: a
# negation re-includes a path an earlier rule excluded, which can silently
# re-expose personal data while the required rule above is still present.
ALLOWED_IGNORE_NEGATIONS = {
    "!working/exports/**/*.pdf",
    "!documents/**/",
    "!documents/README.md",
    "!documents/**/.gitkeep",
    "!working/outreach/**/",
    "!working/outreach/.gitkeep",
    "!working/outreach/README.md",
    "!cover_letters/OpenFonts/fonts/**",
}

# Tracked paths that must never appear, as (predicate description, matcher).
# Explicit exceptions are the scaffolding that keeps a folder in the tree.
TRACKED_EXCEPTIONS = {
    "documents/README.md",
    "working/outreach/README.md",
    "working/outreach/.gitkeep",
}

FORBIDDEN_SCRIPTS = {"preinstall", "install", "postinstall", "prepare", "prepack"}


def tracked_files() -> list[str] | None:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=str(ROOT),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return None
    return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]


def check_nothing_personal_tracked() -> None:
    files = tracked_files()
    if files is None:
        print("note: not a git repository — skipped the tracked-file check")
        return

    for rel in files:
        if rel in TRACKED_EXCEPTIONS or rel.endswith("/.gitkeep"):
            continue

        why = None
        if rel.startswith("documents/"):
            why = "private intake — CVs, postings, references"
        elif rel.startswith("working/outreach/"):
            why = "outreach logs name real third-party people"
        elif rel.endswith(".env") or rel == ".env":
            why = "credentials"
        elif rel.startswith("working/active/") and rel.endswith(".html"):
            why = "generated viz output"
        elif rel.startswith("working/archive/viz/") and rel.endswith(".html"):
            why = "generated viz backup"

        if why:
            errors.append(
                f"tracked file that should never be committed: {rel} ({why}). "
                f"A .gitignore rule does not untrack a file added before it: "
                f"run `git rm --cached {rel}`."
            )


def check_gitignore() -> None:
    path = ROOT / ".gitignore"
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    except OSError as exc:
        errors.append(f".gitignore: unreadable: {exc}")
        return

    rules = set(lines)
    for rule in REQUIRED_IGNORE_RULES:
        if rule not in rules:
            errors.append(
                f".gitignore: required personal-data rule missing: {rule!r}. "
                "If it moved or was renamed intentionally, update "
                "REQUIRED_IGNORE_RULES in tools/security_guards.py in the same change."
            )

    for line in lines:
        if line.startswith("!") and line not in ALLOWED_IGNORE_NEGATIONS:
            errors.append(
                f".gitignore: negation not in the reviewed allowlist: {line!r}. "
                "A negation re-includes a path an earlier rule excluded and can "
                "silently re-expose personal data. If intentional, add it to "
                "ALLOWED_IGNORE_NEGATIONS in tools/security_guards.py in the same change."
            )


def check_permissions() -> None:
    path = ROOT / ".claude" / "settings.json"
    if not path.exists():
        return  # this repo ships no settings.json; nothing pre-approved
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f".claude/settings.json: unreadable or invalid JSON: {exc}")
        return
    if not isinstance(data, dict):
        errors.append(".claude/settings.json: top-level JSON value must be an object")
        return
    permissions = data.get("permissions", {})
    if not isinstance(permissions, dict):
        errors.append(".claude/settings.json: permissions must be an object")
        return
    allow = permissions.get("allow", [])
    if not isinstance(allow, list) or not all(isinstance(e, str) for e in allow):
        errors.append(".claude/settings.json: permissions.allow must be a list of strings")
        return
    for entry in allow:
        if entry not in ALLOWED_PERMISSIONS:
            errors.append(
                f".claude/settings.json: permission not in the reviewed allowlist: {entry!r}. "
                "Pre-approved permissions run without prompting on every fork. If this entry "
                "is intentional, add it to ALLOWED_PERMISSIONS in tools/security_guards.py "
                "in the same change."
            )


def check_package_manifests() -> None:
    manifests = [
        p for p in ROOT.glob(".agents/**/package.json") if "node_modules" not in p.parts
    ]
    # No manifests is fine here — the vendored tooling is Python, not Node.
    for manifest in manifests:
        relpath = manifest.relative_to(ROOT).as_posix()
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{relpath}: unreadable or invalid JSON: {exc}")
            continue
        if not isinstance(data, dict):
            errors.append(f"{relpath}: top-level JSON value must be an object")
            continue
        scripts = data.get("scripts", {})
        if not isinstance(scripts, dict):
            errors.append(f"{relpath}: scripts must be an object")
            continue
        bad = FORBIDDEN_SCRIPTS & set(scripts)
        if bad:
            errors.append(
                f"{relpath}: lifecycle script(s) {sorted(bad)} are forbidden — they run "
                "arbitrary code during a dependency install on every user's machine."
            )
        if "trustedDependencies" in data:
            errors.append(
                f"{relpath}: trustedDependencies is forbidden — it re-enables the dependency "
                "lifecycle scripts the package manager blocks by default."
            )


def main() -> int:
    check_nothing_personal_tracked()
    check_gitignore()
    check_permissions()
    check_package_manifests()

    if errors:
        print(f"security_guards: {len(errors)} failure(s)")
        for err in errors:
            print(f"  - {err}")
        return 1
    print(
        "security_guards: OK (no personal data tracked, gitignore rules intact, "
        "permissions allowlist, package manifests)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
