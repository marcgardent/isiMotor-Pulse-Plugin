#!/usr/bin/env python3
"""Rewrite git commit messages to strip Claude Code attribution trailers.

Removes lines of the form:
    Co-Authored-By: Claude ...
    Claude-Session: ...
(and the blank line separating them from the rest of the message) from
every commit reachable from HEAD. Rewrites history in place via
`git filter-branch --msg-filter` — commit hashes change from the first
rewritten commit onward.

Usage:
    python scripts/strip_commit_attribution.py            # rewrite
    python scripts/strip_commit_attribution.py --dry-run  # preview only, no rewrite
"""

import re
import subprocess
import sys
from pathlib import Path

_ATTRIBUTION_LINE = re.compile(r"^(Co-Authored-By: Claude.*|Claude-Session:.*)$", re.MULTILINE)


def clean_message(message: str) -> str:
    without_trailers = _ATTRIBUTION_LINE.sub("", message)
    without_blank_runs = re.sub(r"\n{3,}", "\n\n", without_trailers)
    return without_blank_runs.rstrip() + "\n"


def run_as_msg_filter() -> None:
    original = sys.stdin.read()
    sys.stdout.write(clean_message(original))


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    )
    return Path(result.stdout.strip())


def commits_with_attribution() -> list[str]:
    result = subprocess.run(
        ["git", "log", "--format=%H", "--grep=Co-Authored-By: Claude"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def preview(commit_hashes: list[str]) -> None:
    if not commit_hashes:
        print("No commits with a Claude Code attribution trailer found.")
        return
    print(f"{len(commit_hashes)} commit(s) would be rewritten:")
    for commit_hash in commit_hashes:
        subject = subprocess.run(
            ["git", "log", "-1", "--format=%s", commit_hash], capture_output=True, text=True, check=True
        ).stdout.strip()
        print(f"  {commit_hash[:12]}  {subject}")


def rewrite_history() -> None:
    subprocess.run(
        [
            "git",
            "filter-branch",
            "--force",
            "--msg-filter",
            f"{sys.executable} {Path(__file__).resolve()} --msg-filter",
            "--",
            "--all",
        ],
        check=True,
    )
    subprocess.run(["git", "for-each-ref", "--format=%(refname)", "refs/original/"], check=False)
    print(
        "\nDone. Old refs kept under refs/original/ — remove them "
        "(git update-ref -d ...) once you've confirmed the result, and "
        "run `git gc --prune=now` to actually drop the old objects."
    )


def main() -> int:
    if "--msg-filter" in sys.argv:
        run_as_msg_filter()
        return 0

    root = repo_root()
    import os

    os.chdir(root)

    commit_hashes = commits_with_attribution()
    preview(commit_hashes)
    if "--dry-run" in sys.argv:
        return 0
    if not commit_hashes:
        return 0

    rewrite_history()
    return 0


if __name__ == "__main__":
    sys.exit(main())
