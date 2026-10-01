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


def check_i18n_keys():
    from app.i18n import STRINGS
    used = set()
    pattern = re.compile(r'tr\(\s*"([^"]+)"')
    for path in sources():
        used |= set(pattern.findall(read(path)))
    missing = sorted(k for k in used if k not in STRINGS)
    unused = sorted(k for k in STRINGS if k not in used)
    return missing, unused


def check_shortcuts():
    text = read(os.path.join(ROOT, "ui", "main_window.py"))
    registered = set(re.findall(r'\("([^"]+)",\s*(?:self\.|lambda)', text))
    table = set(re.findall(r'\("([^"]+)",\s*"sc\.', text))
    return sorted(registered - table), sorted(table - registered)


def check_theme_literals():
    text = read(os.path.join(ROOT, "ui", "theme.py"))
    blocks = re.findall(r'[A-Z_]+_QSS\s*=\s*"""(.*?)"""', text, re.S)
    counts = [len(re.findall(r"#[0-9a-fA-F]{6}", b)) for b in blocks]
    return counts


def _code_lines(text):
    """Yield (line_number, line) with module/function docstrings removed."""
    in_doc = False
    for num, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.count('"""') == 1:
            in_doc = not in_doc
            continue
        if in_doc or stripped.startswith('"""'):
            continue
        yield num, line


def check_hardcoded_strings():
    hits = []
    for path in sources():
        if os.path.basename(path) in ("i18n.py", "config.py", "update.py"):
            continue
        for num, line in _code_lines(read(path)):
            stripped = line.strip()
            if stripped.startswith("#") or "tr(" in line:
                continue
            for literal in re.findall(r'"([^"]{2,})"', line):
                if re.search(r"[\u4e00-\u9fff]", literal) or (
                        literal[:1].isupper() and " " in literal and literal.endswith((".", "…"))):
                    hits.append("%s:%d %s" % (os.path.relpath(path, ROOT), num, stripped[:70]))
                    break
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

    print("\n=== findings to carry into the review: %d mechanical + %s ===" %
          (problems, "dynamic gate failed" if code else "dynamic gate clean"))
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
