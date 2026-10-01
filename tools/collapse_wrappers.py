#!/usr/bin/env python3
"""Collapse thin wrappers in ui/main_window.py (refactor step 11).

DO NOT RUN ON THIS CODEBASE: the controller modules import each other heavily, so
deleting the wrappers turns the star-shaped "window as aggregator" calls into a
mesh and creates import cycles (retranslate <-> send_controller,
params_controller <-> send_controller). Kept as a reference for the token-level
reference analysis and for a future, properly decoupled layout. See dev doc U147.

After the controller split every moved method is still a three-line wrapper on the
window. This tool rewrites the *call sites* to the module function and deletes the
wrapper, but only when that is provably safe:

  * the wrapper must be exactly `return <fn>(self, ...)` with <fn> imported at module level;
  * <fn> gets no other meaning — a name used as a callback (`connect(self.x)`), as a
    plain attribute or from outside ui/ (tests, app) keeps its wrapper;
  * every rewritten call site must live in a file that can import <fn> without a cycle.

`--dry-run` reports the plan, `--revert` restores the backup.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import shutil
import sys
import tokenize

UI_DIR = "ui"
MW = os.path.join(UI_DIR, "main_window.py")


def wrappers(src):
    tree = ast.parse(src)
    imports = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                imports[a.asname or a.name] = node.module
    out = {}
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name.endswith("MainWindow"))
    for fn in cls.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        body = [b for b in fn.body
                if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))]
        if len(body) != 1 or not isinstance(body[0], ast.Return):
            continue
        call = body[0].value
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
            continue
        if not call.args or not (isinstance(call.args[0], ast.Name) and call.args[0].id == "self"):
            continue
        if call.func.id not in imports:
            continue          # not a module-level function we own
        extra = [ast.unparse(a) for a in call.args[1:]]
        out[fn.name] = (call.func.id, imports[call.func.id], extra, (fn.lineno, fn.end_lineno))
    return out


def references(name, files, own_span=None, own_path=None):
    """Token-level scan: attribute uses split into call sites and other uses.

    A regex over the raw text cannot do this: `self.x` is preceded by a dot, which the
    previous lookbehind rejected, so callbacks such as `connect(self._on_worker_error)`
    looked unused and their wrapper got deleted (the window then failed to build).
    """
    calls, others = [], []
    for path in files:
        toks = [t for t in tokenize.generate_tokens(open(path, encoding="utf-8").readline)
                if t.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT,
                                  tokenize.DEDENT, tokenize.ENCODING)]
        for i, t in enumerate(toks):
            if t.type != tokenize.NAME or t.string != name:
                continue
            if own_span and path == own_path and own_span[0] <= t.start[0] <= own_span[1]:
                continue     # the wrapper itself
            prev = toks[i - 1] if i else None
            nxt = toks[i + 1] if i + 1 < len(toks) else None
            if prev is not None and prev.string == ".":
                owner = toks[i - 2].string if i >= 2 else "?"
                if nxt is not None and nxt.string == "(":
                    calls.append((path, owner))
                else:
                    others.append((path, owner, "<callback>"))
            else:
                others.append((path, "<bare>", t.line.strip()[:60]))
    return calls, others


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    if a.revert:
        shutil.copyfile(MW + ".bak", MW)
        print("reverted", MW)
        return 0

    files = sorted(os.path.join(UI_DIR, f) for f in os.listdir(UI_DIR) if f.endswith(".py"))
    src = open(MW, encoding="utf-8").read()
    wraps = wrappers(src)
    collapse, keep = {}, {}
    for name, (fn, module, extra, span) in wraps.items():
        calls, others = references(name, files, span, MW)
        outside = [c for c in calls if not c[0].endswith("main_window.py")]
        refs = [(p, o, t) for p, o, t in others if not p.endswith("main_window.py")]
        cyclic = [c for c in outside if c[0].endswith(("regions.py", "menus.py"))]
        if refs or others or cyclic:
            keep[name] = (fn, module, len(others) + len(refs), len(outside))
        else:
            collapse[name] = (fn, module, extra, span)

    print("wrappers found: %d | collapsible: %d | kept: %d" % (len(wraps), len(collapse), len(keep)))
    for name, (fn, module, n_other, n_out) in sorted(keep.items())[:15]:
        print("  keep  %-28s non-call-uses=%d external-calls=%d" % (name, n_other, n_out))
    for name in sorted(collapse)[:15]:
        print("  drop  %s" % name)
    if a.dry_run:
        return 0

    # apply: rewrite every call site (main_window `self.x(`, controller `win.x(`) and
    # delete the wrapper; files other than main_window get an import for the function.
    changed = {}
    for name, (fn, module, extra, span) in collapse.items():
        for path in files:
            path_src = open(path, encoding="utf-8").read()
            new_src, n = re.subn(r"\b(self|win)\.%s\s*\(" % re.escape(name),
                                 lambda m, f=fn: "%s(%s%s" % (f, m.group(1), ", " if True else ""),
                                 path_src)
            if not n:
                continue
            changed.setdefault(path, new_src)
        # main_window keeps no wrapper for this name
    # delete the wrappers from the window
    mw_src = changed.get(MW, src)
    mw_lines = mw_src.splitlines()
    for name, (fn, module, extra, span) in sorted(collapse.items(), key=lambda kv: -kv[1][3][0]):
        start, end = span
        # the span is only valid if nothing above it changed the line count: we edited one
        # line per call, so re-locate the wrapper by its definition line instead
        mw_lines = mw_src.splitlines()
        mw_src = "\n".join(mw_lines)
    # safer: drop wrappers by locating `def <name>(` inside the class
    for name in collapse:
        m = re.search(r"\n    def %s\(self[^\n]*\n(?:        [^\n]*\n)*" % re.escape(name), mw_src)
        if m:
            mw_src = mw_src[:m.start()] + "\n" + mw_src[m.end():]
    changed[MW] = mw_src

    # imports for the files that now call a module function
    for path, text in list(changed.items()):
        needed = {}
        for name, (fn, module, extra, span) in collapse.items():
            if re.search(r"(?<![\w.])%s\s*\(" % re.escape(fn), text):
                needed.setdefault(module, set()).add(fn)
        lines = text.splitlines()
        last_import = 0
        for i, line in enumerate(lines):
            if re.match(r"^(from|import)\s", line) or (last_import and line.startswith(("    ", ")"))):
                last_import = i
            elif last_import and line.strip() and not line.startswith(("#", ")", "from", "import")):
                break
        add = ["from %s import %s" % (mod, ", ".join(sorted(fns))) for mod, fns in sorted(needed.items())
               if "from %s import" % mod not in text]
        if add:
            lines[last_import + 1:last_import + 1] = add
        text = "\n".join(lines)
        ast.parse(text)
        if path == MW:
            shutil.copyfile(MW, MW + ".bak")
        open(path, "w", encoding="utf-8").write(text)

    # drop now-unused names from the window's import lines
    src = open(MW, encoding="utf-8").read()
    for m in list(re.finditer(r"from (ui\.\w+) import ([^\n]+)", src)):
        module, names = m.group(1), [n.strip() for n in m.group(2).split(",") if n.strip()]
        alive = [n for n in names if re.search(r"(?<![\w.])%s\b" % re.escape(n), src)]
        if alive != names:
            src = src[:m.start()] + ("from %s import %s" % (module, ", ".join(alive)) if alive else "") + src[m.end():]
    src = re.sub(r"\n\n\n+", "\n\n\n", src)
    ast.parse(src)
    open(MW, "w", encoding="utf-8").write(src)
    print("collapsed %d wrappers; main_window now %d lines" % (len(collapse), len(src.splitlines())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
