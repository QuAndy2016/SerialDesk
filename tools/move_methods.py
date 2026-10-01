#!/usr/bin/env python3
"""Move a group of MainWindow methods into one module (batched sibling of move_method.py).

Same safeties as move_method.py plus:
  * several methods per run, so one cluster (log, receive, send, ...) lands in one file;
  * signatures are preserved (`win` is prepended), the wrapper keeps the return statement;
  * decorated methods are refused (a slot/property needs class scope, do not move those);
  * module-level helpers/constants the group needs move along and are re-imported;
  * AST is parsed before anything is written; --dry-run and --revert available.
"""

from __future__ import annotations

import argparse
import ast
import re
import shutil
import sys
import textwrap

QT_PREFIXES = ("PySide6", "from app", "from ui")


def clean(name: str) -> str:
    return name[1:] if name.startswith("_") else name


def signature(node: ast.FunctionDef, first: str) -> str:
    a = node.args
    parts = [first]
    defaults = [None] * (len(a.args) - len(a.defaults)) + list(a.defaults)
    for arg, default in zip(a.args, defaults):
        if arg.arg == "self":
            continue
        text = arg.arg
        if arg.annotation is not None:
            text += ": " + ast.unparse(arg.annotation)
        if default is not None:
            text += " = " + ast.unparse(default)
        parts.append(text)
    if a.vararg:
        parts.append("*" + a.vararg.arg)
    ret = " -> " + ast.unparse(node.returns) if node.returns else ""
    return "(%s)%s" % (", ".join(parts), ret)


def call_args(node: ast.FunctionDef, first: str) -> str:
    names = [a.arg for a in node.args.args if a.arg != "self"]
    if node.args.vararg:
        names.append("*" + node.args.vararg.arg)
    return ", ".join([first] + names)


def move(path, cls_name, methods, out_path, doc, dry=False, revert=False):
    if revert:
        shutil.copyfile(path + ".bak", path)
        print("reverted from %s.bak" % path)
        return
    src = open(path, encoding="utf-8").read()
    lines = src.splitlines()
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

    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls_name)
    index = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    missing = [m for m in methods if m not in index]
    assert not missing, "not found: %s" % missing
    decorated = [m for m in methods if index[m].decorator_list]
    # a moved method cannot keep a zero-arg super() (no __class__ cell outside the class)
    zero_super = [m for m in methods
                  if any(isinstance(n, ast.Name) and n.id in ("super", "__class__")
                         for n in ast.walk(index[m]))]
    assert not zero_super, "refusing to move methods that call super(): %s" % zero_super
    # never re-move an already moved method: its body is just a call back into the module
    def is_wrapper(node: ast.FunctionDef) -> bool:
        body = [b for b in node.body if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))]
        if len(body) != 1:
            return False
        stmt = body[0]
        call = stmt.value if isinstance(stmt, (ast.Return, ast.Expr)) else None
        return (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                and bool(call.args) and isinstance(call.args[0], ast.Name)
                and call.args[0].id == "self")
    already = [m for m in methods if is_wrapper(index[m])]
    assert not already, "already moved (refusing to move a wrapper twice): %s" % already
    assert not decorated, "refusing to move decorated methods: %s" % decorated

    needed, chunks, wrappers = set(), [], []
    for name in methods:
        fn = index[name]
        chunk = textwrap.dedent("\n".join(lines[fn.lineno - 1: fn.end_lineno]))
        body = textwrap.dedent("\n".join(lines[fn.body[0].lineno - 1: fn.end_lineno]))
        body = re.sub(r"\bself\b(?!\s*\.)", "win", body)
        body = re.sub(r"\bself\.", "win.", body)
        chunks.append('def %s%s:\n    "%s"\n%s\n' % (
            clean(name), signature(fn, "win"), name.strip("_").replace("_", " "),
            textwrap.indent(body.rstrip("\n"), "    ")))
        wrappers.append((fn, '    def %s:  # moved to %s\n        """See %s."""\n        return %s(%s)\n' % (
            name + signature(fn, "self"), out_path, out_path, clean(name), call_args(fn, "self"))))
        sub = ast.parse(chunk)
        assigned, loaded = set(), set()
        for node in ast.walk(sub):
            if isinstance(node, ast.Name):
                (assigned if isinstance(node.ctx, ast.Store) else loaded).add(node.id)
            elif isinstance(node, ast.arg):
                assigned.add(node.arg)
        for n in (loaded - assigned - {"self"}):
            if n in defined and n not in imported and not n.startswith("__"):
                needed.add(n)

    imports = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            seg = "\n".join(lines[node.lineno - 1: node.end_lineno])
            if "ui.main_window" not in seg and out_path.replace("/", ".")[:-3] not in seg:
                imports.append(seg)
    parts = ['"""%s"""' % doc, "", "from __future__ import annotations", "", "\n".join(imports)]
    for n in sorted(needed):
        parts.append(textwrap.dedent("\n".join(lines[defined[n][0] - 1: defined[n][1]])))
    parts.extend(chunks)
    module = "\n".join(parts)
    ast.parse(module)
    if dry:
        print("dry-run: %s would hold %s (moves %s)" % (out_path, sorted(clean(m) for m in methods), sorted(needed)))
        return

    edits = [(fn.lineno, fn.end_lineno, text) for fn, text in wrappers]
    for start, end, text in sorted(edits, key=lambda e: -e[0]):
        lines[start - 1:end] = [text.rstrip("\n")]
    new_src = "\n".join(lines)
    names = ", ".join(sorted(clean(m) for m in methods))
    anchor = "from ui.regions import ("
    assert anchor in new_src
    new_src = new_src.replace(anchor, "from %s import %s\n%s" % (out_path.replace("/", ".")[:-3], names, anchor), 1)
    ast.parse(new_src)
    open(out_path, "w", encoding="utf-8").write(module)
    shutil.copyfile(path, path + ".bak")
    open(path, "w", encoding="utf-8").write(new_src)
    print("moved %d methods -> %s (%d lines); window now %d lines" % (
        len(methods), out_path, len(module.splitlines()), len(new_src.splitlines())))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--class", dest="cls_name", default="MainWindow")
    ap.add_argument("--methods")
    ap.add_argument("--out")
    ap.add_argument("--doc")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    if not a.revert and not (a.methods and a.out and a.doc):
        ap.error("--methods, --out and --doc are required unless --revert is used")
    move(a.path, a.cls_name, [m.strip() for m in (a.methods or "").split(",") if m.strip()],
         a.out, a.doc, a.dry_run, a.revert)
    return 0


if __name__ == "__main__":
    sys.exit(main())
