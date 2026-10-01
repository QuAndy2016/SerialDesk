#!/usr/bin/env python3
"""Move a contiguous block of a method into a new method (mechanical refactor helper).

Written after two failed hand attempts (2026-10-01): the body was removed while the
new method was never inserted (string anchor did not match), and once the body was
inserted at the wrong indentation. Both times the test gate caught it, but the tool
now makes the failure impossible:

  * line surgery only - never a string replace, so a drifted anchor cannot silently
    delete code;
  * the extracted body is re-indented for a class method (8 spaces), which is the
    mistake that produced class-level code;
  * parses before and after, and writes only if both parse;
  * keeps a .bak next to the file, plus --revert;
  * --dry-run prints the result without touching anything.
"""

from __future__ import annotations

import argparse
import ast
import shutil
import sys
import textwrap


def locate(path, parent, method, start_marker, end_marker):
    src = open(path, encoding="utf-8").read()
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == parent)
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method)
    start = end = None
    for i in range(fn.lineno - 1, fn.end_lineno):
        if start is None and start_marker in lines[i]:
            start = i + 1
        elif start is not None and end_marker in lines[i]:
            end = i
            break
    if start is None or end is None or end <= start:
        sys.exit("could not locate the block (%s .. %s)" % (start, end))
    return fn, start, end, lines


def run(path, parent, method, start_marker, end_marker, name, doc, params, dry, revert):
    if revert:
        shutil.copyfile(path + ".bak", path)
        print("reverted from %s.bak" % path)
        return
    fn, start, end, lines = locate(path, parent, method, start_marker, end_marker)
    body = textwrap.dedent("".join(lines[start - 1:end]))
    if not body.strip():
        sys.exit("refusing: the block is empty")
    sig = ", ".join(("self",) + tuple(params))
    new_method = '    def %s(%s) -> None:\n        """%s"""\n%s\n' % (
        name, sig, doc, textwrap.indent(body.rstrip("\n"), " " * 8))
    call = "        self.%s(%s)\n" % (name, ", ".join(params))
    out = "".join(lines[: fn.lineno - 1] + [new_method]
                  + lines[fn.lineno - 1: start - 1] + [call] + lines[end:])
    ast.parse(out)                                  # refuse to write broken code
    assert new_method in out and call in out
    print("block lines %d..%d -> method %s(...) [%d lines]" % (start, end, name, new_method.count("\n")))
    if dry:
        print("dry-run: nothing written")
        return
    shutil.copyfile(path, path + ".bak")
    open(path, "w", encoding="utf-8").write(out)
    print("written (backup: %s.bak)" % path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--class", dest="parent", default="MainWindow")
    ap.add_argument("--method", required=True)
    ap.add_argument("--from-marker", required=True)
    ap.add_argument("--to-marker", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--doc", default="Extracted block (mechanical refactor).")
    ap.add_argument("--param", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()
    run(args.path, args.parent, args.method, args.from_marker, args.to_marker,
        args.name, args.doc, args.param, args.dry_run, args.revert)
    return 0


if __name__ == "__main__":
    sys.exit(main())
