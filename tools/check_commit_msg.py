"""Process policy gate: a source commit must name its task and carry the review checklist.

Why a machine check: rules that live only in a prompt are essays. The industry consensus
(OWASP LLM01:2025 prompt injection; deterministic control planes for coding agents) is that a
rule is only real once something deterministic checks it. This turns two process clauses of the
project standard into gates:

  - traceability: the work item is named   (U### / B#-P# / #issue)
  - delivery:     the commit carries the review-checklist marker (standard clause 31)

Docs-only changes skip the check (exit 0), so they stay cheap.

Local use (git commit-msg hook):  python3 tools/check_commit_msg.py --message-file "$1"
CI / audit use (any revision):     python3 tools/check_commit_msg.py --from-git HEAD
"""

from __future__ import annotations

import argparse
import re
import subprocess

SOURCE_PREFIXES = ("app/", "ui/", "tools/", "tests/", "installer/", ".github/")
TASK_REF = re.compile(r"\b(U\d{2,}|B\d+-P\d+|#\d+)\b")
CHECKLIST = re.compile(r"§\s*31|review checklist|审查清单|评审清单", re.IGNORECASE)


def _run(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True).stdout


def staged_files() -> list[str]:
    return [f for f in _run("git", "diff", "--cached", "--name-only").splitlines() if f.strip()]


def commit_files(rev: str) -> list[str]:
    return [f for f in _run("git", "show", "--pretty=format:", "--name-only", rev).splitlines()
            if f.strip()]


def commit_message(rev: str) -> str:
    return _run("git", "log", "-1", "--pretty=%B", rev)


def main() -> int:
    parser = argparse.ArgumentParser(description="commit-message policy gate")
    parser.add_argument("--message-file", help="pending commit message (commit-msg hook)")
    parser.add_argument("--from-git", metavar="REV", help="validate an existing revision (CI)")
    args = parser.parse_args()
    if args.from_git:
        files, message = commit_files(args.from_git), commit_message(args.from_git)
    elif args.message_file:
        files = staged_files()
        with open(args.message_file, encoding="utf-8") as fh:
            message = fh.read()
    else:
        parser.error("give --message-file or --from-git")

    if not any(f.startswith(SOURCE_PREFIXES) for f in files):
        print("[policy] no source files in this change - commit-message check skipped")
        return 0

    missing = []
    if not TASK_REF.search(message):
        missing.append("task reference (U###, B#-P#, or #issue)")
    if not CHECKLIST.search(message):
        missing.append("review-checklist marker (§31)")
    if missing:
        print("[policy] commit message is missing: %s" % "; ".join(missing))
        print("[policy] name the work item and add a '§31 review checklist' paragraph "
              "(function / UI-UX / architecture / performance / maintainability).")
        return 1
    print("[policy] commit message ok (task reference + review checklist)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
