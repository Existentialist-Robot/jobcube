"""Measure commit yield: row-work versus record-work.

ROW-WORK commits touch configured implementation paths; RECORD-WORK commits
touch only other paths. Configuration may be overridden per repository with a
`.yield.json` file in the repository root.

The ledger is the state: unless `--since` is supplied, measurement starts at
the anchor of the ledger row with the HIGHEST commit epoch for this repository
(`end_shas[<repo_name>].epoch`, eden-os D-224, 2026-09-09: a ledger appended by
more than one machine has a file order that is not its time order). Rows that
carry no epoch fall back to the last valid row's `end_sha`, the old behaviour.
With an empty ledger, the last 20 commits form a first baseline.

`--record` keeps ONE ROW PER SESSION (record_target): a re-record of the last
row's session is merged into that row in place; a label that is not the last
row's is refused with exit 4.

Known one-commit off-by-one: a recorded row stores HEAD as `end_sha`, so the
commit that later writes that ledger row cannot be included in that row and
lands in the next window. This is always in the same direction, so trends are
unaffected.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, Sequence


DEFAULT_ROW_DIRS = [
    "tools/",
    "dev/",
    "scripts/",
    "src/",
    "lib/",
    "app/",
    "tests/",
]
DEFAULT_ROW_SUFFIXES = [
    ".py",
    ".sh",
    ".mjs",
    ".ps1",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".rs",
    ".c",
    ".h",
    ".cpp",
    ".java",
    ".sql",
]
DEFAULT_ROW_CONTAINS = ["CLOSED-TASKS/"]
DEFAULT_LEDGER = "ops/yield.jsonl"
FALLBACK_LEDGER = ".yield.jsonl"
CONFIG_NAME = ".yield.json"
BANNED_SESSION_RE = re.compile(
    r"verify|test|selftest|dryrun|dry-run|scratch|tmp", re.IGNORECASE
)


class YieldError(Exception):
    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


@dataclass(frozen=True)
class Config:
    row_dirs: tuple[str, ...]
    row_suffixes: tuple[str, ...]
    row_contains: tuple[str, ...]
    ledger: Path
    ledger_display: str
    repo_name: str
    tier: Any
    target_pct: Any
    definitions_source: str
    ledger_note: str | None


@dataclass(frozen=True)
class Measurement:
    start_sha: str | None
    end_sha: str
    commits: int
    row_work: int
    record_work: int
    record_share_pct: float
    label: str


def fail(message: str, exit_code: int) -> NoReturn:
    raise YieldError(message, exit_code)


def run_process(command: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        fail(f"Could not run command {' '.join(command)!r}: {exc}", 2)
    returncode = completed.returncode
    if returncode != 0:
        stderr = completed.stderr.strip()
        detail = f": {stderr}" if stderr else ""
        fail(
            f"Git command failed (rc={returncode}): {' '.join(command)}{detail}",
            2,
        )
    return completed


def establish_repo(cwd: Path) -> Path:
    command = ["git", "rev-parse", "--is-inside-work-tree"]
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        fail(f"Cannot run git: {exc}", 2)

    returncode = completed.returncode
    if returncode != 0 or completed.stdout.strip() != "true":
        fail(
            f"{cwd} is not a git repository. Refusing to search parent directories.",
            2,
        )

    top = run_process(["git", "rev-parse", "--show-toplevel"], cwd).stdout.strip()
    repo_root = Path(top).resolve()
    if repo_root != cwd.resolve():
        fail(
            f"{cwd} is not the repository root (git reports {repo_root}). "
            "Run this tool from the repository root; parent-repository "
            "measurement is refused.",
            2,
        )
    return repo_root


def strip_leading_dot_slash(value: str) -> str:
    """Remove leading `./` and `/` segments ONLY. Not str.lstrip("./"), which strips a
    character SET and so turned `.tools/` into `tools/` and `.claude/` into `claude/`."""
    while True:
        if value.startswith("./"):
            value = value[2:]
        elif value.startswith("/"):
            value = value[1:]
        else:
            return value


def normalized_dir(value: str) -> str:
    value = value.replace("\\", "/").strip()
    value = strip_leading_dot_slash(value)
    if value and not value.endswith("/"):
        value += "/"
    return value


def normalized_fragment(value: str) -> str:
    return value.replace("\\", "/")


def string_list(data: dict[str, Any], key: str, default: list[str]) -> list[str]:
    if key not in data:
        return list(default)
    value = data[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        fail(f"{CONFIG_NAME}: {key!r} must be a list of strings", 2)
    return list(value)


def safe_ledger_path(repo_root: Path, value: str) -> tuple[Path, str]:
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (repo_root / candidate).resolve()
    try:
        relative = resolved.relative_to(repo_root.resolve())
    except ValueError:
        fail(f"{CONFIG_NAME}: ledger must remain inside the repository", 2)
    return resolved, relative.as_posix()


def load_config(repo_root: Path) -> Config:
    config_path = repo_root / CONFIG_NAME
    data: dict[str, Any] = {}
    source = "built-in defaults"
    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            fail(f"Cannot read {CONFIG_NAME}: {exc}", 2)
        if not isinstance(loaded, dict):
            fail(f"{CONFIG_NAME}: top-level JSON value must be an object", 2)
        data = loaded
        source = CONFIG_NAME

    row_dirs = tuple(
        normalized_dir(item)
        for item in string_list(data, "row_dirs", DEFAULT_ROW_DIRS)
        if normalized_dir(item)
    )
    row_suffixes = tuple(
        normalized_fragment(item)
        for item in string_list(data, "row_suffixes", DEFAULT_ROW_SUFFIXES)
        if item
    )
    row_contains = tuple(
        normalized_fragment(item)
        for item in string_list(data, "row_contains", DEFAULT_ROW_CONTAINS)
        if item
    )

    repo_name = data.get("repo_name", repo_root.name)
    if not isinstance(repo_name, str) or not repo_name.strip():
        fail(f"{CONFIG_NAME}: 'repo_name' must be a non-empty string", 2)

    ledger_value = data.get("ledger", DEFAULT_LEDGER)
    if not isinstance(ledger_value, str) or not ledger_value.strip():
        fail(f"{CONFIG_NAME}: 'ledger' must be a non-empty string", 2)

    ledger_note: str | None = None
    if "ledger" not in data and not (repo_root / "ops").is_dir():
        ledger_value = FALLBACK_LEDGER
        ledger_note = (
            f"Default ledger directory 'ops/' does not exist; using "
            f"{FALLBACK_LEDGER} in the repository root."
        )

    ledger_path, ledger_display = safe_ledger_path(repo_root, ledger_value)
    return Config(
        row_dirs=row_dirs,
        row_suffixes=row_suffixes,
        row_contains=row_contains,
        ledger=ledger_path,
        ledger_display=ledger_display,
        repo_name=repo_name,
        tier=data.get("tier"),
        target_pct=data.get("target_pct"),
        definitions_source=source,
        ledger_note=ledger_note,
    )


def is_row_work(paths: Sequence[str], config: Config) -> bool:
    for original in paths:
        path = strip_leading_dot_slash(normalized_fragment(original))
        if any(path.startswith(directory) for directory in config.row_dirs):
            return True
        if any(path.endswith(suffix) for suffix in config.row_suffixes):
            return True
        if any(fragment in path for fragment in config.row_contains):
            return True
    return False


def read_ledger(config: Config) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    malformed: list[str] = []
    if not config.ledger.exists():
        return rows, malformed
    try:
        with config.ledger.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                text = line.strip()
                if not text:
                    malformed.append(
                        f"{config.ledger_display}:{line_number}: blank ledger line"
                    )
                    continue
                try:
                    value = json.loads(text)
                except json.JSONDecodeError as exc:
                    malformed.append(
                        f"{config.ledger_display}:{line_number}: malformed JSON: {exc.msg}"
                    )
                    continue
                if not isinstance(value, dict):
                    malformed.append(
                        f"{config.ledger_display}:{line_number}: row is not a JSON object"
                    )
                    continue
                if not isinstance(value.get("end_sha"), str) or not value["end_sha"]:
                    malformed.append(
                        f"{config.ledger_display}:{line_number}: missing valid end_sha"
                    )
                    continue
                rows.append(value)
    except OSError as exc:
        fail(f"Cannot read ledger {config.ledger_display}: {exc}", 2)
    return rows, malformed


def ledger_anchor(ledger_rows: Sequence[dict[str, Any]], repo_name: str) -> str | None:
    """The sha the next window starts from: EPOCH-PRIMARY (eden-os D-224).

    The same rule as eden-os tools/gates/session_yield_gate.py root_anchor(): the row
    whose `end_shas[repo_name]` carries the highest integer `epoch` wins, a tie goes
    to the LAST tied row in file order, and when no row carries an epoch for this
    repo the last row's `end_sha` is used exactly as before. Rows written by this
    file alone carry no `end_shas`, so a ledger only this tool writes is unaffected.
    """
    best: tuple[int, str] | None = None
    for row in ledger_rows:
        anchor = (row.get("end_shas") or {}).get(repo_name) if isinstance(row.get("end_shas"), dict) else None
        if not isinstance(anchor, dict):
            continue
        epoch = anchor.get("epoch")
        if not isinstance(epoch, int) or isinstance(epoch, bool):
            continue
        sha = anchor.get("sha")
        if not isinstance(sha, str) or not sha:
            sha = row["end_sha"]  # read_ledger guarantees a non-empty str end_sha
        if best is None or epoch >= best[0]:
            best = (epoch, sha)
    if best is not None:
        return best[1]
    return ledger_rows[-1]["end_sha"] if ledger_rows else None


def head_sha(repo_root: Path) -> str:
    return run_process(["git", "rev-parse", "--verify", "HEAD"], repo_root).stdout.strip()


def commits_for_range(
    repo_root: Path,
    start_sha: str | None,
    first_baseline: bool,
) -> list[str]:
    if first_baseline:
        command = ["git", "rev-list", "--max-count=20", "HEAD"]
    else:
        if start_sha is None:
            fail("Internal error: missing range start", 2)
        command = ["git", "rev-list", f"{start_sha}..HEAD"]
    output = run_process(command, repo_root).stdout
    return [line.strip() for line in output.splitlines() if line.strip()]


def paths_for_commit(repo_root: Path, commit_sha: str) -> list[str]:
    completed = run_process(
        [
            "git",
            "diff-tree",
            "--root",
            "-m",
            "--no-commit-id",
            "--name-only",
            "-r",
            "-z",
            commit_sha,
        ],
        repo_root,
    )
    return [item for item in completed.stdout.split("\0") if item]


def require_nonempty(commits: Sequence[str]) -> None:
    if not commits:
        fail(
            "Empty commit range: measured nothing. This is exit 2 because "
            '"0% overhead" and "measured nothing" must never be the same output.',
            2,
        )


def measure(
    repo_root: Path,
    config: Config,
    start_sha: str | None,
    first_baseline: bool,
) -> Measurement:
    end = head_sha(repo_root)
    commits = commits_for_range(repo_root, start_sha, first_baseline)
    require_nonempty(commits)

    row_count = 0
    for commit in commits:
        if is_row_work(paths_for_commit(repo_root, commit), config):
            row_count += 1
    record_count = len(commits) - row_count
    share = round(record_count * 100.0 / len(commits), 1)
    return Measurement(
        start_sha=start_sha,
        end_sha=end,
        commits=len(commits),
        row_work=row_count,
        record_work=record_count,
        record_share_pct=share,
        label="first baseline" if first_baseline else "session window",
    )


def git_date(repo_root: Path, commit_sha: str) -> str:
    return run_process(
        ["git", "show", "-s", "--format=%cs", commit_sha], repo_root
    ).stdout.strip()


def validate_session(session: str | None) -> str:
    if session is None or not session.strip():
        fail("--record requires --session=LABEL", 2)
    if BANNED_SESSION_RE.search(session):
        fail(
            f"Refusing session label {session!r}: it contains a banned test or "
            "verification term. Recording it would silently rescope every later window.",
            4,
        )
    return session


def record_target(
    ledger_rows: Sequence[dict[str, Any]],
    label: str,
    review_through_shas: Sequence[str] = (),
) -> tuple[str, int | None, str]:
    """Decide where a --record for `label` goes: append, upsert, or refuse.

    ONE ROW PER SESSION. Before this existed, --record appended unconditionally,
    so a session that re-ran its close wrote a SECOND row -- and the window of
    that second row contained only the fixup commits the close itself had just
    surfaced. Those are handoff prose by construction, so the row scored 100%
    record-work and described nothing. Four of the five 100% rows in the ledger
    on 2026-08-29 were made this way; the instrument was measuring its own
    error-correction loop, one row per correction.

    WHY UPSERT AND NOT PLAIN REFUSAL. Refusing the second --record would fail the
    close for a legitimate re-run, and the fixup commits would then roll silently
    into the NEXT session's window -- two sessions scored as one, which is the
    failure specs/handoff-lifecycle.md already warns about. Refusal deletes the
    measurement; upsert keeps it and files it under the session that earned it.

    WHY NOT UPSERT A LABEL ANYWHERE IN THE LEDGER. Rewriting a non-terminal row's
    end_sha breaks tools/overhead_review.py:pending_sessions(), which finds the
    review boundary by exact end_sha match and exits 2 when it cannot. A label
    reappearing after an intervening label is operator error and must be loud.

    Returns (action, index, reason) where action is "append" | "upsert" | "refuse".
    """
    labels = [r.get("session") for r in ledger_rows]
    if label not in labels:
        return ("append", None, "first row for this session")
    last = len(ledger_rows) - 1
    if labels[last] != label:
        first = labels.index(label)
        return (
            "refuse",
            None,
            f"session {label!r} is row {first + 1} but the last row is "
            f"{labels[last]!r}. Re-recording it would rewrite a CLOSED window and "
            f"break the review chain's end_sha lookup. If this is a new session, "
            f"give it a new label.",
        )
    frozen = set(s for s in review_through_shas if s)
    if ledger_rows[last].get("end_sha") in frozen:
        return (
            "refuse",
            None,
            f"session {label!r} is the last row, but its end_sha is already the "
            f"boundary of a recorded overhead review. Upserting would move a sha "
            f"that ops/overhead-reviews.jsonl points at.",
        )
    return ("upsert", last, "same session recording again; windows are merged")


def merge_rows(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Fold a re-recorded window into the row it belongs to.

    ADDITIVE, NOT RE-MEASURED. Each row's window starts where the previous one
    ended, so the two windows are disjoint and contiguous and summing them is
    exact. Re-measuring instead would need the anchor from BEFORE the first
    same-label row, which the ledger no longer carries once the row is written.

    record_share_pct is RECOMPUTED from the summed counts, never averaged --
    averaging 80/100/100/100 gives 95.0 where the true share is 83.3.
    """
    out = dict(existing)
    for key in ("commits", "row_work", "record_work"):
        out[key] = (existing.get(key) or 0) + (new.get(key) or 0)

    repos = dict(existing.get("by_repo") or {})
    for name, incoming in (new.get("by_repo") or {}).items():
        prior = repos.get(name) or {}
        merged = dict(incoming)
        for key in ("commits", "row_work", "record_work"):
            merged[key] = (prior.get(key) or 0) + (incoming.get(key) or 0)
        repos[name] = merged
    if repos:
        out["by_repo"] = repos

    commits = out["commits"]
    out["record_share_pct"] = round(100.0 * out["record_work"] / commits, 1) if commits else 0.0

    # The window GREW: it keeps the start it always had and takes the new end.
    out["start_sha"] = existing.get("start_sha")
    out["end_sha"] = new.get("end_sha")
    if new.get("end_shas"):
        out["end_shas"] = new["end_shas"]
    # A level, not a flow -- the latest reading is the right one.
    if new.get("open_rows") is not None:
        out["open_rows"] = new["open_rows"]
    if new.get("open_rows_error") is not None:
        out["open_rows_error"] = new["open_rows_error"]
    # A session that runs past midnight keeps the date it STARTED.
    if new.get("date") and new.get("date") != existing.get("date"):
        out["date_last"] = new["date"]
    out["record_calls"] = int(existing.get("record_calls") or 1) + 1
    return out


def duplicate_session_labels(ledger_rows: Sequence[dict[str, Any]]) -> list[str]:
    """Labels appearing in more than one row -- the invariant this module enforces."""
    seen: dict[str, int] = {}
    for row in ledger_rows:
        name = row.get("session")
        if name is not None:
            seen[name] = seen.get(name, 0) + 1
    return sorted(k for k, n in seen.items() if n > 1)


def replace_last_record(path: Path, row: dict[str, Any], session: str | None) -> None:
    """Rewrite the LAST VALID ledger row in place (the upsert record_target chose).

    Every other line is kept byte-for-byte: the ledger may hold rows another writer
    serialized differently, and re-serializing them would be a rewrite of history.
    Written beside the ledger and renamed into place, so a failure leaves it intact."""
    validate_session(session)
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            lines = handle.readlines()
    except OSError as exc:
        fail(f"Cannot read ledger {path}: {exc}", 2)
    target = None
    for index, line in enumerate(lines):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("end_sha"), str) and value["end_sha"]:
            target = index
    if target is None:
        fail(f"Internal error: no valid row to update in {path}", 2)
    lines[target] = json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            handle.writelines(lines)
        os.replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink()
        except OSError:
            pass
        fail(f"Cannot update ledger {path}: {exc}", 2)


def append_record(path: Path, row: dict[str, Any], session: str | None) -> None:
    validate_session(session)
    if not path.parent.is_dir():
        fail(
            f"Ledger directory does not exist: {path.parent}. "
            "Directories are not created automatically.",
            2,
        )
    serialized = json.dumps(row, ensure_ascii=False, sort_keys=True)
    try:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized + "\n")
    except OSError as exc:
        fail(f"Cannot append ledger {path}: {exc}", 2)


def definition_object(config: Config) -> dict[str, Any]:
    return {
        "source": config.definitions_source,
        "row_dirs": list(config.row_dirs),
        "row_suffixes": list(config.row_suffixes),
        "row_contains": list(config.row_contains),
    }


def measurement_object(
    config: Config,
    measurement: Measurement,
    malformed: Sequence[str],
    recorded: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "repo_name": config.repo_name,
        "tier": config.tier,
        "label": measurement.label,
        "start_sha": measurement.start_sha,
        "end_sha": measurement.end_sha,
        "commits": measurement.commits,
        "row_work": measurement.row_work,
        "record_work": measurement.record_work,
        "record_share_pct": measurement.record_share_pct,
        "target_pct": config.target_pct,
        "ledger": config.ledger_display,
        "ledger_note": config.ledger_note,
        "definitions": definition_object(config),
        "malformed_ledger_lines": list(malformed),
        "malformed_ledger_count": len(malformed),
        "recorded": recorded,
    }
    return result


def print_definitions(config: Config) -> None:
    print(f"Definitions source: {config.definitions_source}")
    print(f"ROW-WORK directories: {', '.join(config.row_dirs) or '(none)'}")
    print(f"ROW-WORK suffixes: {', '.join(config.row_suffixes) or '(none)'}")
    print(f"ROW-WORK path contains: {', '.join(config.row_contains) or '(none)'}")
    print("RECORD-WORK: every commit not classified as ROW-WORK")
    print(f"Ledger: {config.ledger_display}")
    if config.ledger_note:
        print(config.ledger_note)


def print_malformed(malformed: Sequence[str]) -> None:
    for message in malformed:
        print(f"MALFORMED LEDGER LINE: {message}")
    if malformed:
        print(f"Malformed ledger lines counted: {len(malformed)}")


def print_human(
    config: Config,
    measurement: Measurement,
    rows: Sequence[dict[str, Any]],
    malformed: Sequence[str],
    recorded: bool,
) -> None:
    print_definitions(config)
    print_malformed(malformed)
    print()
    print(f"Repository: {config.repo_name}")
    if config.tier is not None:
        print(f"Tier: {config.tier}")
    print(f"Window: {measurement.label}")
    if measurement.start_sha:
        print(f"Range: {measurement.start_sha}..{measurement.end_sha}")
    else:
        print(f"Range: last {measurement.commits} commits through {measurement.end_sha}")
    print()
    print("COMMITS  ROW-WORK  RECORD-WORK  RECORD-WORK SHARE")
    print(
        f"{measurement.commits:7d}  "
        f"{measurement.row_work:8d}  "
        f"{measurement.record_work:11d}  "
        f"{measurement.record_share_pct:16.1f}%"
    )
    if config.target_pct is not None:
        print(f"Target record-work share: {config.target_pct}%")
    print()
    shares: list[str] = []
    for row in rows[-5:]:
        value = row.get("record_share_pct")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            shares.append(f"{float(value):.1f}%")
    shares.append(f"{measurement.record_share_pct:.1f}%")
    print(f"Trend (oldest to newest): {' -> '.join(shares)}")
    if recorded:
        print(f"Recorded one row in {config.ledger_display}.")


def history_rows(repo_root: Path, config: Config) -> list[dict[str, Any]]:
    completed = run_process(
        ["git", "log", "--format=%H%x00%cs", "--all"], repo_root
    )
    entries: list[tuple[str, str]] = []
    for line in completed.stdout.splitlines():
        if "\0" not in line:
            continue
        sha, date = line.split("\0", 1)
        if sha and date:
            entries.append((sha, date))
    require_nonempty([sha for sha, _ in entries])

    by_day: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for sha, date in entries:
        if is_row_work(paths_for_commit(repo_root, sha), config):
            by_day[date][0] += 1
        else:
            by_day[date][1] += 1

    result: list[dict[str, Any]] = []
    for date in sorted(by_day):
        row_work, record_work = by_day[date]
        commits = row_work + record_work
        result.append(
            {
                "date": date,
                "commits": commits,
                "row_work": row_work,
                "record_work": record_work,
                "record_share_pct": round(record_work * 100.0 / commits, 1),
            }
        )
    return result


def print_history(
    config: Config,
    rows: Sequence[dict[str, Any]],
    malformed: Sequence[str],
) -> None:
    print_definitions(config)
    print_malformed(malformed)
    print()
    print("DATE        COMMITS  ROW-WORK  RECORD-WORK  RECORD-WORK SHARE")
    for row in rows:
        print(
            f"{row['date']:10s}  "
            f"{row['commits']:7d}  "
            f"{row['row_work']:8d}  "
            f"{row['record_work']:11d}  "
            f"{row['record_share_pct']:16.1f}%"
        )


def test_config(row_dirs: Sequence[str]) -> Config:
    return Config(
        row_dirs=tuple(normalized_dir(item) for item in row_dirs),
        row_suffixes=tuple(DEFAULT_ROW_SUFFIXES),
        row_contains=tuple(DEFAULT_ROW_CONTAINS),
        ledger=Path("unused.jsonl"),
        ledger_display="unused.jsonl",
        repo_name="selftest",
        tier=None,
        target_pct=None,
        definitions_source="selftest",
        ledger_note=None,
    )


def run_selftest() -> int:
    failures = 0

    def report(name: str, passed: bool, detail: str = "") -> None:
        nonlocal failures
        status = "PASS" if passed else "FAIL"
        suffix = f": {detail}" if detail else ""
        print(f"{status} {name}{suffix}")
        if not passed:
            failures += 1

    prose_config = test_config(DEFAULT_ROW_DIRS)
    prose_result = is_row_work(
        ["README.md", "docs/design.md", "notes/handoff.txt"], prose_config
    )
    report(
        "prose-only paths are rejected as ROW-WORK",
        prose_result is False,
        f"classifier returned {prose_result}",
    )

    unusual_path = ["engine/widget.xyz"]
    before = is_row_work(unusual_path, test_config(DEFAULT_ROW_DIRS))
    after = is_row_work(
        unusual_path, test_config([*DEFAULT_ROW_DIRS, "engine/"])
    )
    report(
        "overridden row_dir applies only after override is loaded",
        before is False and after is True,
        f"before={before}, after={after}",
    )

    hidden = is_row_work([".tools/README.md"], prose_config)
    explicit = is_row_work(["./tools/README.md"], prose_config)
    report(
        "only a literal ./ prefix is stripped (.tools/ is not tools/)",
        hidden is False and explicit is True,
        f"hidden={hidden}, explicit={explicit}",
    )

    forked = [
        {"end_sha": "late", "end_shas": {"selftest": {"sha": "late", "epoch": 900}}},
        {"end_sha": "early", "end_shas": {"selftest": {"sha": "early", "epoch": 800}}},
    ]
    legacy = [{"end_sha": "one"}, {"end_sha": "two"}]
    report(
        "the anchor is the highest-epoch row, not the last line (D-224)",
        ledger_anchor(forked, "selftest") == "late" and ledger_anchor(legacy, "selftest") == "two",
        f"forked={ledger_anchor(forked, 'selftest')}, legacy={ledger_anchor(legacy, 'selftest')}",
    )

    with tempfile.TemporaryDirectory() as temporary:
        ledger = Path(temporary) / "ledger.jsonl"
        kept = '{"end_sha":"a","session":"other"}\n'
        ledger.write_text(kept + '{"end_sha": "b", "session": "same", "commits": 1}\n',
                          encoding="utf-8", newline="")
        replace_last_record(ledger, {"end_sha": "c", "session": "same", "commits": 2}, "same")
        lines = ledger.read_text(encoding="utf-8").splitlines(keepends=True)
        report(
            "an upsert rewrites only the last row; other lines stay byte-for-byte",
            len(lines) == 2 and lines[0] == kept and json.loads(lines[1])["end_sha"] == "c",
            repr(lines),
        )

    with tempfile.TemporaryDirectory() as temporary:
        ledger = Path(temporary) / "ledger.jsonl"
        banned_exit: int | None = None
        try:
            append_record(ledger, {"end_sha": "abc"}, "verification-test")
        except YieldError as exc:
            banned_exit = exc.exit_code
        wrote_anything = ledger.exists() and ledger.stat().st_size > 0
        report(
            "banned session exits 4 and writes nothing",
            banned_exit == 4 and not wrote_anything,
            f"exit={banned_exit}, wrote={wrote_anything}",
        )

    empty_exit: int | None = None
    try:
        require_nonempty([])
    except YieldError as exc:
        empty_exit = exc.exit_code
    report(
        "empty commit range exits 2",
        empty_exit == 2,
        f"exit={empty_exit}",
    )

    if failures:
        print(f"SELFTEST FAILED: {failures} control(s) failed")
        return 1
    print("SELFTEST PASSED")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Measure record-work share in git commits."
    )
    result.add_argument("--json", action="store_true", help="emit one JSON object")
    result.add_argument("--record", action="store_true", help="append a ledger row")
    result.add_argument("--session", help="session label for --record")
    result.add_argument("--since", help="override the starting git reference")
    result.add_argument(
        "--history", action="store_true", help="show per-day whole-history results"
    )
    result.add_argument(
        "--selftest", action="store_true", help="run negative controls"
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)

    if args.selftest:
        if args.record or args.history or args.since or args.session or args.json:
            fail("--selftest cannot be combined with other options", 2)
        return run_selftest()

    if args.history and (args.record or args.since or args.session):
        fail("--history cannot be combined with --record, --since, or --session", 2)
    if args.session and not args.record:
        fail("--session is valid only with --record", 2)
    if args.record:
        validate_session(args.session)

    repo_root = establish_repo(Path.cwd())
    config = load_config(repo_root)
    ledger_rows, malformed = read_ledger(config)

    if args.history:
        daily = history_rows(repo_root, config)
        if args.json:
            output = {
                "repo_name": config.repo_name,
                "tier": config.tier,
                "ledger": config.ledger_display,
                "ledger_note": config.ledger_note,
                "definitions": definition_object(config),
                "malformed_ledger_lines": malformed,
                "malformed_ledger_count": len(malformed),
                "history": daily,
            }
            print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        else:
            print_history(config, daily, malformed)
        return 0

    if args.since:
        start_sha = args.since
        first_baseline = False
    elif ledger_rows:
        start_sha = ledger_anchor(ledger_rows, config.repo_name)
        first_baseline = False
    else:
        start_sha = None
        first_baseline = True

    measurement = measure(repo_root, config, start_sha, first_baseline)
    recorded = False

    if args.record:
        row: dict[str, Any] = {
            "repo_name": config.repo_name,
            "tier": config.tier,
            "session": args.session,
            "machine": socket.gethostname(),
            "date": git_date(repo_root, measurement.end_sha),
            "start_sha": measurement.start_sha,
            "end_sha": measurement.end_sha,
            "commits": measurement.commits,
            "row_work": measurement.row_work,
            "record_work": measurement.record_work,
            "record_share_pct": measurement.record_share_pct,
        }
        if config.target_pct is not None:
            row["target_pct"] = config.target_pct
        # ONE ROW PER SESSION -- record_target() and merge_rows() existed, but this path
        # appended unconditionally, so a re-run close wrote the duplicate they forbid.
        action, index, reason = record_target(ledger_rows, args.session)
        if action == "refuse":
            fail(f"Refusing --record: {reason}", 4)
        if action == "upsert" and index is not None:
            replace_last_record(config.ledger, merge_rows(ledger_rows[index], row), args.session)
        else:
            append_record(config.ledger, row, args.session)
        recorded = True

    if args.json:
        print(
            json.dumps(
                measurement_object(
                    config, measurement, malformed, recorded
                ),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        print_human(
            config,
            measurement,
            ledger_rows,
            malformed,
            recorded,
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except YieldError as exc:
        print(exc.message, file=sys.stderr)
        sys.exit(exc.exit_code)

