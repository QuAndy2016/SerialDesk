"""Process policy gate: every "change plan" section must carry the process fields.

Standard clauses 1/2/3/5/12 ask for user task, scenario, state (including the failure
paths) and acceptance criteria - but they were only prose in a document. This checks the
plan sections of the development task document and fails when a field is missing, so the
process leaves an artefact a machine can verify.

The task document is a local, private file (it is deliberately not in the repository), so
this check runs locally (dev_gate / pre-commit) and skips cleanly where the file is absent
(CI), reporting that it skipped rather than pretending to pass.

Path: $SERIALDESK_TASK_DOC, or the default below when the variable is unset.
"""

from __future__ import annotations

import os
import re
import sys

DEFAULT_DOC = "/root/personal/notes/09_serial_assistant_dev_tasks_20260930_2252.md"
HEADING = re.compile(r"^##\s+(.*)$")
FIELDS = (
    ("user task", lambda b: bool(re.search(r"用户任务|使用场景|目标", b))),
    ("state", lambda b: bool(re.search(r"状态", b))),
    ("failure paths", lambda b: bool(re.search(r"异常|边界|失败", b))),
    ("acceptance with numbers",
     lambda b: bool(re.search(r"验收", b)) and bool(re.search(r"\d", b))),
)


def sections(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    title, body = None, []
    for line in text.splitlines():
        m = HEADING.match(line)
        if m:
            if title is not None:
                out.append((title, "\n".join(body)))
            title, body = m.group(1).strip(), []
        elif title is not None:
            body.append(line)
    if title is not None:
        out.append((title, "\n".join(body)))
    return out


def main() -> int:
    path = os.environ.get("SERIALDESK_TASK_DOC", DEFAULT_DOC)
    if not os.path.exists(path):
        print("[plan-doc] skipped: no task document at %s (expected on the dev host only)" % path)
        return 0
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    plans = [(t, b) for t, b in sections(text) if "改动计划" in t]
    if not plans:
        print("[plan-doc] skipped: no change-plan section in %s" % path)
        return 0
    problems = []
    for title, body in plans:
        missing = [name for name, ok in FIELDS if not ok(body)]
        if missing:
            problems.append((title, missing))
    if problems:
        print("[plan-doc] %d change-plan section(s) missing required fields:" % len(problems))
        for title, missing in problems:
            print("   - %s: %s" % (title, ", ".join(missing)))
        print("[plan-doc] each plan needs: user task / state / failure paths / acceptance (numbers)")
        return 1
    print("[plan-doc] ok (%d change-plan section(s), all fields present)" % len(plans))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
