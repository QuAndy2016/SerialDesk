#!/usr/bin/env python3
"""Compact three-line wrappers in ui/main_window.py into one line (refactor step 12).

A wrapper shaped like

    def _x(self, a) -> None:
        "See ui.ctrl.py."
        return x(self, a)

becomes

    def _x(self, a) -> None: return x(self, a)

Only when the result stays within MAX_LEN, and only for bodies that are exactly an
optional docstring plus a single return of a module function. AST-verified, keeps a .bak.
"""

from __future__ import annotations

import argparse
import ast
import re
import shutil
import sys

PATH = "ui/main_window.py"
MAX_LEN = 110


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    if a.revert:
        shutil.copyfile(PATH + ".bak", PATH)
        print("reverted")
        return 0
    src = open(PATH, encoding="utf-8").read()
    lines = src.splitlines()
    tree = ast.parse(src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name.endswith("MainWindow"))
    edits, skipped = [], 0
    for fn in cls.body:
        if not isinstance(fn, ast.FunctionDef) or len(fn.body) != 2:
            continue
        doc, ret = fn.body
        if not (isinstance(doc, ast.Expr) and isinstance(doc.value, ast.Constant)):
            continue
        if not isinstance(ret, ast.Return) or not isinstance(ret.value, ast.Call):
            continue
        if ret.value.args and not (isinstance(ret.value.args[0], ast.Name)
                                   and ret.value.args[0].id == "self"):
            continue
        # a trailing "# moved to ..." comment would swallow the return statement
        def_line = re.sub(r"\s+#(?![\'\"]).*$", "", lines[fn.lineno - 1]).rstrip()
        ret_line = lines[ret.lineno - 1]
        one = def_line.rstrip() + " " + ret_line.strip()
        if len(one) > MAX_LEN or ret.end_lineno != ret.lineno:
            skipped += 1
            continue
        edits.append((fn.lineno, ret.end_lineno, one))
    for start, end, one in sorted(edits, key=lambda e: -e[0]):
        lines[start - 1:end] = [one]
    out = "\n".join(lines)
    ast.parse(out)
    shutil.copyfile(PATH, PATH + ".bak")
    open(PATH, "w", encoding="utf-8").write(out)
    print("compacted %d wrappers (kept %d verbose for line length); main_window now %d lines"
          % (len(edits), skipped, len(out.splitlines())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
