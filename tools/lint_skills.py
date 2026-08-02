#!/usr/bin/env python3
"""Lint this repo's skill, command, and settings files.

    python -B tools/lint_skills.py

Checks:
- every `.claude/skills/*/SKILL.md` has YAML frontmatter that parses, with
  non-empty `name` and `description`
- `name` matches the skill's directory name — Claude Code resolves skills by
  directory, so a mismatch means the skill silently never loads
- `framework_version` is present and looks like semver, so
  tools/check_upstream_updates.py can compare it
- `.claude/commands/*.md` (if any) start with a `# /<name>` title
- `.claude/settings.json` (if present) is valid JSON with a
  `permissions.allow` list

Adapted from the upstream version. Differences: it also enforces the
name/directory match and framework_version, it does not require PyYAML (it
falls back to a small frontmatter reader so the repo stays stdlib-only), and
missing `.claude/commands/` or `settings.json` is not a failure — not every
fork has them.

Exit 0 on success, 1 with a failure list otherwise.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # optional — the fallback covers the keys we check
    yaml = None

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_KEYS = ("name", "description")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

errors: list[str] = []


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def parse_frontmatter_fallback(block: str) -> dict:
    """Read top-level `key: value` pairs without PyYAML.

    Handles the two shapes these files use: a plain scalar, and a `>` folded
    block whose continuation lines are indented. Good enough for presence and
    equality checks; PyYAML is still used when installed.
    """
    data: dict[str, str] = {}
    key = None
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1].isspace():  # continuation of a folded value
            if key:
                data[key] = (data[key] + " " + line.strip()).strip()
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        data[key] = "" if value in (">", "|", ">-", "|-") else value.strip("\"'")
    return data


def read_frontmatter(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        errors.append(f"{rel(path)}: missing YAML frontmatter (file must start with ---)")
        return None
    end = text.find("\n---", 3)
    if end == -1:
        errors.append(f"{rel(path)}: unterminated YAML frontmatter")
        return None
    block = text[3:end].lstrip("\n")
    if yaml is not None:
        try:
            data = yaml.safe_load(block)
        except yaml.YAMLError as exc:
            errors.append(f"{rel(path)}: frontmatter is not valid YAML: {exc}")
            return None
        if not isinstance(data, dict):
            errors.append(f"{rel(path)}: frontmatter did not parse to a mapping")
            return None
        return data
    return parse_frontmatter_fallback(block)


def check_skill(path: Path) -> None:
    data = read_frontmatter(path)
    if data is None:
        return

    for key in REQUIRED_KEYS:
        if not str(data.get(key, "")).strip():
            errors.append(f"{rel(path)}: frontmatter missing required key '{key}'")

    directory = path.parent.name
    name = str(data.get("name", "")).strip()
    if name and name != directory:
        errors.append(
            f"{rel(path)}: name is '{name}' but the directory is '{directory}'. "
            "Skills are resolved by directory, so this skill would never load."
        )

    version = str(data.get("framework_version", "")).strip()
    if not version:
        errors.append(
            f"{rel(path)}: missing 'framework_version'. "
            "tools/check_upstream_updates.py uses it to tell you when upstream "
            "has changed a file you have personalized."
        )
    elif not SEMVER.match(version):
        errors.append(f"{rel(path)}: framework_version '{version}' is not MAJOR.MINOR.PATCH")


def check_command(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").lstrip().splitlines()
    first = lines[0] if lines else ""
    if not first.startswith("# /"):
        errors.append(
            f"{rel(path)}: command file must start with a '# /<name>' title "
            f"(found: {first[:50]!r})"
        )


def check_settings() -> None:
    path = ROOT / ".claude" / "settings.json"
    if not path.exists():
        return  # optional
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f".claude/settings.json: {exc}")
        return
    if not isinstance(data, dict):
        errors.append(".claude/settings.json: top-level JSON value must be an object")
        return
    permissions = data.get("permissions", {})
    if not isinstance(permissions, dict):
        errors.append(".claude/settings.json: permissions must be an object")
        return
    if "allow" in permissions and not isinstance(permissions["allow"], list):
        errors.append(".claude/settings.json: permissions.allow must be a list")


def main() -> int:
    skills = sorted(ROOT.glob(".claude/skills/*/SKILL.md"))
    skills += sorted(ROOT.glob(".agents/skills/*/SKILL.md"))
    commands = sorted((ROOT / ".claude" / "commands").glob("*.md"))

    if not skills:
        errors.append("no SKILL.md files found — the glob roots are wrong or the tree moved")

    for skill in skills:
        check_skill(skill)
    for command in commands:
        check_command(command)
    check_settings()

    if errors:
        print(f"lint_skills: {len(errors)} failure(s)")
        for err in errors:
            print(f"  - {err}")
        return 1

    backend = "PyYAML" if yaml else "builtin fallback parser"
    print(
        f"lint_skills: OK ({len(skills)} skill(s), {len(commands)} command(s), "
        f"settings.json checked if present; frontmatter read with {backend})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
