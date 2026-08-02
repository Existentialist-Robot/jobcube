#!/usr/bin/env python3
"""Preview which of your personalized files an upstream change would touch.

    python -B tools/check_upstream_updates.py [--remote upstream] [--branch master]

This repo is meant to be forked and personalized. That makes merging upstream
changes risky: a straight merge can overwrite the very files you rewrote. So
methodology files carry a `framework_version` in their YAML frontmatter, and
this script compares yours against the remote's before you merge anything.

    ---
    name: pipeline
    description: ...
    framework_version: 1.0.0
    ---

It reports four things:
  * files where upstream's version is newer than yours — the ones to review
  * framework files that exist upstream but not locally — new methodology
  * files you version that upstream doesn't — usually yours alone, no action
  * versioned files whose content matches upstream exactly despite a version
    bump, which means the bump was cosmetic

Nothing is fetched into your working tree and nothing is merged. This only
looks, so it is safe to run any time. It also works between any two related
repos — point --remote at whichever one you sync from.

Unlike the version this was adapted from, the file list is discovered rather
than hardcoded, so it keeps working when you rename, add, or reorganize skills.

Stdlib only. Exit codes: 0 = nothing to review (or updates found without
--exit-code), 1 = updates found with --exit-code, 2 = could not run.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Where versioned methodology can live. Everything else is treated as content.
SEARCH_GLOBS = [
    ".claude/skills/**/*.md",
    ".claude/commands/**/*.md",
    ".claude/agents/**/*.md",
    "*.md",
]

VERSION_RE = re.compile(r"^\s*framework_version\s*:\s*['\"]?([^'\"\s]+)", re.MULTILINE)
SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


def run_git(args: list[str]) -> tuple[int, str, str]:
    # encoding is explicit: text=True decodes with the locale codec, which on a
    # Windows cp1252 console raises UnicodeDecodeError on any non-ASCII file
    # content git hands back.
    result = subprocess.run(
        ["git"] + args,
        cwd=str(ROOT),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, result.stdout or "", result.stderr or ""


def frontmatter_version(text: str) -> str | None:
    """Read framework_version out of a leading YAML frontmatter block."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    match = VERSION_RE.search(text[3:end])
    return match.group(1) if match else None


def parse_semver(value: str) -> tuple[int, int, int]:
    match = SEMVER_RE.match(value)
    if not match:
        return (0, 0, 0)
    a, b, c = match.groups()
    return (int(a), int(b), int(c))


def local_versioned_files() -> dict[str, str]:
    """Every local file carrying a framework_version, path -> version."""
    found: dict[str, str] = {}
    for pattern in SEARCH_GLOBS:
        for path in ROOT.glob(pattern):
            if not path.is_file() or ".git" in path.parts:
                continue
            try:
                version = frontmatter_version(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
            if version:
                found[path.relative_to(ROOT).as_posix()] = version
    return found


def remote_versioned_files(ref: str) -> dict[str, str]:
    """Same, for a git ref, without touching the working tree."""
    rc, listing, _ = run_git(["ls-tree", "-r", "--name-only", ref])
    if rc != 0:
        return {}
    found: dict[str, str] = {}
    for rel in listing.splitlines():
        if not rel.endswith(".md"):
            continue
        parts = rel.split("/")
        # Same shape as SEARCH_GLOBS: dot-claude subtrees, or a root-level doc.
        if not (rel.startswith(".claude/") or len(parts) == 1):
            continue
        rc, text, _ = run_git(["show", f"{ref}:{rel}"])
        if rc != 0:
            continue
        version = frontmatter_version(text)
        if version:
            found[rel] = version
    return found


def same_content(ref: str, rel: str) -> bool:
    rc, remote_text, _ = run_git(["show", f"{ref}:{rel}"])
    if rc != 0:
        return False
    try:
        local_text = (ROOT / rel).read_text(encoding="utf-8")
    except OSError:
        return False
    return local_text.replace("\r\n", "\n") == remote_text.replace("\r\n", "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare framework_version against a remote before merging."
    )
    parser.add_argument("--remote", default="upstream",
                        help="remote to compare against (default: upstream, falls back to origin)")
    parser.add_argument("--branch", default="master", help="branch on that remote (default: master)")
    parser.add_argument("--no-fetch", action="store_true", help="use cached tracking refs")
    parser.add_argument("--exit-code", action="store_true",
                        help="exit 1 when updates are available (for CI or a watch loop)")
    args = parser.parse_args()

    rc, stdout, _ = run_git(["remote"])
    if rc != 0:
        print("Error: not a git repository, or git is unavailable.")
        return 2
    remotes = stdout.split()
    remote = args.remote
    if remote not in remotes:
        if "origin" in remotes:
            print(f"Remote '{remote}' not found; falling back to 'origin'.")
            remote = "origin"
        else:
            print(f"Error: no remote named '{remote}', and no 'origin' to fall back to.")
            return 2

    if not args.no_fetch:
        print(f"Fetching {remote} ...")
        rc, _, stderr = run_git(["fetch", remote])
        if rc != 0:
            print(f"  fetch failed ({stderr.strip()}); using cached tracking refs.")

    ref = f"{remote}/{args.branch}"
    rc, _, _ = run_git(["rev-parse", "--verify", ref])
    if rc != 0:
        print(f"Error: '{ref}' does not exist. Check --branch, or fetch first.")
        return 2

    local = local_versioned_files()
    remote_files = remote_versioned_files(ref)

    if not local and not remote_files:
        print("No file on either side carries a framework_version.")
        print("Add one to the frontmatter of each methodology file you want tracked.")
        return 0

    updates, cosmetic, ahead, new_upstream = [], [], [], []

    for rel, remote_version in sorted(remote_files.items()):
        local_version = local.get(rel)
        if local_version is None:
            new_upstream.append((rel, remote_version))
            continue
        if parse_semver(remote_version) > parse_semver(local_version):
            if same_content(ref, rel):
                cosmetic.append((rel, local_version, remote_version))
            else:
                updates.append((rel, local_version, remote_version))

    for rel, local_version in sorted(local.items()):
        if rel not in remote_files:
            ahead.append((rel, local_version))

    print(f"\nComparing {len(local)} local versioned file(s) against {ref}\n")

    if updates:
        print("UPDATES AVAILABLE — review before merging:")
        for rel, lv, rv in updates:
            print(f"  {rel}")
            print(f"      yours {lv}  <  upstream {rv}")
            print(f"      git diff {ref} -- {rel}")
        print()

    if new_upstream:
        print("NEW UPSTREAM FRAMEWORK FILES (no local counterpart):")
        for rel, rv in new_upstream:
            print(f"  {rel}  ({rv})    git show {ref}:{rel}")
        print()

    if cosmetic:
        print("VERSION BUMPED BUT CONTENT IDENTICAL (no review needed):")
        for rel, lv, rv in cosmetic:
            print(f"  {rel}  {lv} -> {rv}")
        print()

    if ahead:
        print("LOCAL-ONLY VERSIONED FILES (yours; upstream has nothing to merge):")
        for rel, lv in ahead:
            print(f"  {rel}  ({lv})")
        print()

    if not updates and not new_upstream:
        print("Nothing to review — no upstream framework file is newer than yours.")

    print(
        "\nNothing was merged. These files are personalized by design: read each diff\n"
        "and port the parts you want by hand rather than accepting them wholesale."
    )

    return 1 if (updates and args.exit_code) else 0


if __name__ == "__main__":
    sys.exit(main())
