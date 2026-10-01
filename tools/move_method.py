#!/usr/bin/env python3
"""Move a MainWindow method into its own module, leaving a thin wrapper behind.

Same lesson as tools/refactor_extract.py: mechanical moves must not be able to
delete code silently. This one

  * takes the method by name (no line numbers);
  * rewrites both `self.attr` and bare `self` (the parent-argument case that bit us);
  * moves any module-level helper/constant the method needs into the new module and
    re-imports it in the window, so existing references keep working;
  * parses before writing, keeps a .bak, and supports --dry-run / --revert.
"""

from __future__ import annotations

import argparse
import ast
import re
import shutil
import sys
import textwrap

QT_PREFIXES = ("PySide6", "from app", "from ui")


def module_level(src):
    tree = ast.parse(src)
    imported, defined = set(), {}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                imported.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    defined[t.id] = (node.lineno, node.end_lineno)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            defined[node.name] = (node.lineno, node.end_lineno)
    return tree, imported, defined


def move(path, cls_name, method, out_path, module_doc, fn_name=None, dry=False, revert=False):
    if revert:
        shutil.copyfile(path + ".bak", path)
        print("reverted from %s.bak" % path)
        return
    src = open(path, encoding="utf-8").read()
    lines = src.splitlines()
    tree, imported, defined = module_level(src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls_name)
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method)
    fn_name = fn_name or method.lstrip("_")

    chunk = textwrap.dedent("\n".join(lines[fn.lineno - 1: fn.end_lineno]))
    body = textwrap.dedent("\n".join(lines[fn.body[0].lineno - 1: fn.end_lineno]))
    body = re.sub(r"\bself\b(?!\s*\.)", "win", body)      # bare self FIRST
    body = re.sub(r"\bself\.", "win.", body)              # then attributes

    sub = ast.parse(chunk)
    assigned, loaded = set(), set()
    for node in ast.walk(sub):
        if isinstance(node, ast.Name):
            (assigned if isinstance(node.ctx, ast.Store) else loaded).add(node.id)
        elif isinstance(node, ast.arg):
            assigned.add(node.arg)
    moved = sorted(n for n in (loaded - assigned - {"self"})
                   if n in defined and n not in imported and not n.startswith("__"))

    imports = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            seg = "\n".join(lines[node.lineno - 1: node.end_lineno])
            if "ui.main_window" not in seg:
                imports.append(seg)

    parts = ['"""%s"""' % module_doc, "", "from __future__ import annotations", "",
             "\n".join(imports)]
    for name in moved:
        parts.append(textwrap.dedent("\n".join(lines[defined[name][0] - 1: defined[name][1]])))
    parts.append('def %s(win) -> None:\n    "%s"\n%s\n' % (
        fn_name, module_doc.splitlines()[0], textwrap.indent(body.rstrip("\n"), "    ")))
    module = "\n".join(parts)
    ast.parse(module)
    if dry:
        print("dry-run: would write %s (%d lines), moving %s" % (out_path, len(module.splitlines()), moved))
        return
    open(out_path, "w", encoding="utf-8").write(module)

    wrapper = '    def %s(self) -> None:\n        """%s (implementation in %s)."""\n        %s(self)\n' % (
        method, module_doc.splitlines()[0], out_path.replace("/", ".")[:-3], fn_name)
    new_src = "\n".join(lines[:fn.lineno - 1] + [wrapper.rstrip("\n")] + lines[fn.end_lineno:])
    anchor = "from ui.regions import ("
    assert anchor in new_src
    new_src = new_src.replace(anchor, "from %s import %s\n%s" % (
        out_path.replace("/", ".")[:-3], fn_name, anchor), 1)
    ast.parse(new_src)
    shutil.copyfile(path, path + ".bak")
    open(path, "w", encoding="utf-8").write(new_src)
    print("moved %s -> %s (%d lines); window now %d lines (backup .bak)" % (
        method, out_path, len(module.splitlines()), len(new_src.splitlines())))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--class", dest="cls_name", default="MainWindow")
    ap.add_argument("--method", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--fn-name", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    move(a.path, a.cls_name, a.method, a.out, a.doc, a.fn_name, a.dry_run, a.revert)
    return 0


if __name__ == "__main__":
    sys.exit(main())
