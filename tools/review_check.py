#!/usr/bin/env python3
"""Review battery: the mechanical half of a code/design review.

Run this FIRST in any review - it collects the evidence a review has to cite.
It does not replace reading the code; it stops the review from skipping the
things a machine can check (which is exactly how reviews go soft).

Static checks
  * i18n keys used in code but missing from the table (would raise at runtime)
  * shortcuts registered vs the help table (the two must agree)
  * colour literals left in the stylesheet (token debt)
  * hardcoded CJK/ASCII UI strings that bypass tr()
  * broad excepts, TODO/FIXME, threads touching widgets
Dynamic checks
  * delegates to tools/check_ui.py (contrast + overflow + tests)
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SKIP_DIRS = {"__pycache__", ".git", "build", "dist", ".venv"}
FILES = []


_CACHE = []


def sources():
    if _CACHE:
        return _CACHE
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            if name.endswith(".py") and not name.startswith("test_"):
                path = os.path.join(base, name)
                if os.path.relpath(path, ROOT).startswith(("tools", "tests")):
                    continue
                FILES.append(path)
    _CACHE.extend(FILES)
    return _CACHE


def read(path):
    return open(path, encoding="utf-8").read()


def check_i18n_keys() -> tuple[list[str], list[str]]:
    """Keys used but missing from the table, and table keys nothing references.

    A key counts as used when it appears in a ``tr("...")`` call *or* as a plain
    string literal outside the table: the shortcut help loads its labels from
    app.shortcuts, tips come from dicts and some keys sit inside a conditional
    expression. Counting only ``tr("...")`` reported live keys as "unused".
    """
    from app.i18n import STRINGS

    i18n_path = os.path.join(ROOT, "app", "i18n.py")
    direct, indirect = set(), set()
    for path in sources():
        text = read(path)
        direct |= set(re.findall(r'tr\(\s*"([^"]+)"', text))
        if path != i18n_path:
            indirect |= set(re.findall(r'"([a-z][a-z0-9_.]*)"', text))
    used = direct | indirect
    missing = sorted(k for k in direct if k not in STRINGS)
    unused = sorted(k for k in STRINGS if k not in used)
    return missing, unused


def check_shortcuts():
    """Compare the shortcut reference table with the shortcuts the window really has.

    The old version regexed ui/main_window.py for `("Ctrl+X", self.` - after the window
    was split into modules the registrations moved to ui/actions_controller.py, so the
    check kept "passing" while reporting every shortcut as unregistered. Ask the window
    instead of the source text, and fall back to a static scan only if Qt cannot start.
    """
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtGui import QAction, QShortcut
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from app.shortcuts import HELP_ROWS
        from ui.main_window import MainWindow

        from PySide6.QtGui import QKeySequence

        win = MainWindow()

        def texts(sequence):
            """QKeySequence can hold several bindings; "Ctrl+," must not be split on ","."""
            return [QKeySequence(sequence[i]).toString() for i in range(sequence.count())]

        registered = set()
        for shortcut in win.findChildren(QShortcut):
            registered.update(texts(shortcut.key()))
        for action in win.findChildren(QAction):
            if not action.shortcut().isEmpty():
                registered.update(texts(action.shortcut()))
        win.deleteLater()
        app.processEvents()
        table = {row[0].strip() for row in HELP_ROWS}
        # A row may carry a scope note: those keys are handled by a focus-scoped key
        # handler (the quick-send panel's Delete), not by a QShortcut, so "no
        # QShortcut" is correct for them. Anything else unregistered is a real gap.
        scoped = {row[0].strip() for row in HELP_ROWS if len(row) > 2 and row[2]}
        missing = sorted(k for k in (table - registered) if k not in scoped)
        return sorted(registered - table), missing
    except Exception as exc:            # Qt or the app cannot start: degrade to text
        text = read(os.path.join(ROOT, "ui", "main_window.py"))
        registered = set(re.findall(r'\("([^"]+)",\s*(?:self\.|lambda)', text))
        table = set(re.findall(r'\("([^"]+)",\s*"sc\.', text))
        return sorted(registered - table), sorted(table - registered) + ["(static scan: %s)" % exc]


def check_theme_literals():
    text = read(os.path.join(ROOT, "ui", "theme.py"))
    blocks = re.findall(r'[A-Z_]+_QSS\s*=\s*"""(.*?)"""', text, re.S)
    counts = [len(re.findall(r"#[0-9a-fA-F]{6}", b)) for b in blocks]
    return counts


def _docstring_lines(text):
    """Line numbers covered by a docstring (module, class, function), via the AST.

    The previous heuristic only understood triple-quoted docstrings that start a line,
    so a one-line `"text"` docstring - the way every extracted module is documented -
    was reported as hard-coded user-facing text.
    """
    import ast

    covered = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return covered
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", [])
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            for line in range(body[0].value.lineno, body[0].value.end_lineno + 1):
                covered.add(line)
    return covered


def _code_lines(text):
    """Yield (line_number, line) with docstrings removed."""
    docs = _docstring_lines(text)
    for num, line in enumerate(text.splitlines(), 1):
        if num in docs:
            continue
        yield num, line


#: Calls that put text in front of the user: a literal there must go through tr().
TEXT_SETTERS = (
    "setText", "setToolTip", "setWindowTitle", "setPlaceholderText", "setTitle",
    "setLabelText", "setStatusTip", "setWhatsThis", "addItem", "addItems", "showMessage",
    "setInformativeText", "setDetailedText", "information", "warning", "critical",
)


def check_hardcoded_strings():
    """User-facing text passed to a widget setter without tr().

    Rewritten to look at call arguments through the AST. The old text heuristic had two
    problems: it reported docstrings (a one-line `"Settings menu construction"` is not
    user-facing text) and it missed anything spanning a line break.
    """
    import ast

    cjk = re.compile(r"[\u4e00-\u9fff]")
    hits = []
    for path in sources():
        rel = os.path.relpath(path, ROOT)
        if os.path.basename(path) in ("i18n.py", "config.py", "update.py"):
            continue
        try:
            tree = ast.parse(read(path))
        except SyntaxError as exc:
            hits.append("%s: syntax error %s" % (rel, exc))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else (
                node.func.id if isinstance(node.func, ast.Name) else "")
            if name not in TEXT_SETTERS:
                continue
            for arg in node.args:
                if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                    continue
                text = arg.value
                sentence = text[:1].isupper() and " " in text and text.endswith((".", "…"))
                if len(text) >= 2 and (cjk.search(text) or sentence):
                    hits.append("%s:%d %s(%r)" % (rel, node.lineno, name, text[:48]))
    return hits


def check_hygiene():
    broad, todos, threads = [], [], []
    for path in sources():
        for num, line in enumerate(read(path).splitlines(), 1):
            rel = "%s:%d" % (os.path.relpath(path, ROOT), num)
            if re.search(r"except\s*(Exception)?\s*:", line) and "noqa" not in line:
                broad.append(rel + " " + line.strip()[:60])
            if re.search(r"\b(TODO|FIXME|XXX)\b", line):
                todos.append(rel + " " + line.strip()[:60])
            if re.search(r"threading|QThread", line):
                threads.append(rel + " " + line.strip()[:60])
    return broad, todos, threads


def check_code_structure():
    """Structural checks: the programming half of the review battery."""
    import ast
    long_funcs, no_doc, dangerous, broad = [], 0, [], []
    ann_missing = ann_total = 0
    for path in sources():
        try:
            tree = ast.parse(read(path))
        except SyntaxError as exc:
            dangerous.append("%s: syntax error %s" % (os.path.relpath(path, ROOT), exc))
            continue
        rel = os.path.relpath(path, ROOT)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                length = (node.end_lineno or node.lineno) - node.lineno
                if length > 60:
                    long_funcs.append("%s:%d %s (%d lines)" % (rel, node.lineno, node.name, length))
                if not ast.get_docstring(node) and not node.name.startswith("_"):
                    no_doc += 1
                args = [a for a in node.args.args if a.arg not in ("self", "cls")]
                ann_total += len(args)
                ann_missing += sum(1 for a in args if a.annotation is None)
            if isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Name) \
                    and node.type.id in ("Exception", "BaseException"):
                broad.append("%s:%d" % (rel, node.lineno))
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", "")
                if name in ("eval", "exec"):
                    dangerous.append("%s:%d %s()" % (rel, node.lineno, name))
    return long_funcs, no_doc, (ann_missing, ann_total), broad, dangerous


def check_coverage():
    """TOTAL coverage, or None when pytest-cov is not installed."""
    try:
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "--cov=app", "--cov=ui",
                               "--cov-report=term"], cwd=ROOT, text=True, capture_output=True)
    except OSError:
        return None
    if proc.returncode not in (0, 1) or "unrecognized arguments" in (proc.stderr or ""):
        return None
    for line in (proc.stdout or "").splitlines():
        if line.strip().startswith("TOTAL"):
            parts = line.split()
            return parts[-1]
    return None


def dynamic():
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check_ui.py")],
                          cwd=ROOT, text=True, capture_output=True, env=env)
    return proc.returncode, (proc.stdout or proc.stderr).strip()


def main() -> int:
    strict = "--strict" in sys.argv        # CI uses this: blockers fail the build
    blockers = []
    problems = 0
    print("=== review battery ===")
    missing, unused = check_i18n_keys()
    print("\n[i18n] keys used but missing:", missing or "none")
    if missing:
        problems += len(missing)
    print("[i18n] keys defined but unused (%d):" % len(unused), ", ".join(unused[:10]) or "none")

    reg_extra, table_extra = check_shortcuts()
    print("\n[shortcuts] registered but undocumented:", reg_extra or "none")
    print("[shortcuts] documented but not registered:", table_extra or "none")
    if reg_extra or table_extra:
        problems += len(reg_extra) + len(table_extra)

    counts = check_theme_literals()
    print("\n[theme] colour literals inside QSS blocks:", counts, "(token debt)")

    hits = check_hardcoded_strings()
    print("\n[strings] hardcoded text that bypasses tr() (%d):" % len(hits))
    for line in hits[:8]:
        print("   ", line)
    if hits:
        problems += len(hits)

    broad, todos, threads = check_hygiene()
    print("\n[hygiene] broad excepts (%d):" % len(broad))
    for line in broad[:6]:
        print("   ", line)
    print("[hygiene] TODO/FIXME (%d):" % len(todos), "; ".join(todos[:4]) or "none")
    print("[hygiene] threads/QThread (%d) - check GUI access is signal-based:" % len(threads))
    for line in threads[:4]:
        print("   ", line)

    long_funcs, no_doc, (ann_missing, ann_total), broad, dangerous = check_code_structure()
    print("\n[code] functions over 60 lines (%d):" % len(long_funcs))
    for line in long_funcs[:6]:
        print("   ", line)
    print("[code] public functions without a docstring:", no_doc)
    print("[code] unannotated parameters: %d/%d" % (ann_missing, ann_total))
    print("[code] broad excepts (%d):" % len(broad), ", ".join(broad[:8]) or "none")
    print("[code] eval/exec or syntax errors:", dangerous or "none")
    if dangerous:
        problems += len(dangerous)

    coverage = check_coverage()
    print("\n[coverage]", coverage if coverage else "not measured (pip install pytest-cov)")

    code, out = dynamic()
    print("\n[dynamic] tools/check_ui.py ->", out.splitlines()[-1] if out else "no output")
    problems += 1 if code else 0

    # `problems` counts what must be fixed now. The code-structure numbers are real but
    # informational (they drive the refactor backlog, they do not block a build) - the
    # summary used to lump the two together, which is how a broken shortcut check once
    # read as "13 mechanical findings".
    informational = len(long_funcs) + no_doc + ann_missing + len(broad)
    print("\n=== findings to carry into the review: %d blockers + %d informational "
          "(code structure) + %s ===" %
          (problems, informational, "dynamic gate failed" if code else "dynamic gate clean"))
    if strict:
        if missing:
            blockers.append("i18n keys used but missing: %s" % ", ".join(missing))
        if dangerous:
            blockers.append("eval/exec or syntax errors: %s" % ", ".join(dangerous))
        if code:
            blockers.append("tools/check_ui.py failed")
        for line in blockers:
            print("BLOCKER:", line)
        return 1 if blockers else 0
    return 0        # default: report only; the UI gate is the hard failure


if __name__ == "__main__":
    sys.exit(main())
