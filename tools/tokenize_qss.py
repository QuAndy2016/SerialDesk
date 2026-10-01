#!/usr/bin/env python3
"""Extract the QSS colours of ui/theme.py into tokens (U132 batch 1).

The whole point of this batch is that *nothing visible changes*: every literal becomes
``$token`` and the sheet is rendered with ``string.Template.substitute``. The tool

  1. freezes the current sheets into tests/snapshots/ so the change can be proven equal;
  2. inverts ui/tokens.py into a literal -> token map (erroring on collisions);
  3. rewrites theme.py to templates + one render call per theme;
  4. re-imports theme and asserts the rendered sheets are byte-identical to the snapshot.

``--revert`` restores theme.py from the .bak it wrote.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import re
import shutil
import sys
from pathlib import Path

THEME = Path("ui/theme.py")
SNAP_DIR = Path("tests/snapshots")
BLOCK = re.compile(r'^([A-Z_]+_QSS) = """(.*?)"""$', re.S | re.M)
LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b")

IMPORT_LINE = "from ui.tokens import DARK_TOKENS, LIGHT_TOKENS"
HELPER = '''

def _render(template: str, tokens: dict[str, str]) -> str:
    """Fill $token placeholders in a QSS template."""
    return Template(template).substitute(tokens)
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--revert", action="store_true")
    ap.add_argument("--check", action="store_true", help="only verify render equality")
    a = ap.parse_args()
    if a.revert:
        shutil.copyfile(str(THEME) + ".bak", THEME)
        print("reverted", THEME)
        return 0

    src = THEME.read_text(encoding="utf-8")
    blocks = dict(BLOCK.findall(src))
    if "DARK_QSS" not in blocks or "LIGHT_QSS" not in blocks:
        raise SystemExit("could not find both QSS blocks")

    sys.path.insert(0, ".")
    tokens_mod = importlib.import_module("ui.tokens")
    maps = {"DARK_QSS": {}, "LIGHT_QSS": {}}
    for theme_name, table in (("DARK_QSS", tokens_mod.DARK_TOKENS), ("LIGHT_QSS", tokens_mod.LIGHT_TOKENS)):
        inverted: dict[str, str] = {}
        for token, value in table.items():
            if value in inverted:
                raise SystemExit("%s: %s and %s share the literal %s" % (theme_name, inverted[value], token, value))
            inverted[value] = token
        maps[theme_name] = inverted

    if a.check:
        return 0

    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    for name, sheet in blocks.items():
        (SNAP_DIR / ("%s.txt" % name.lower())).write_text(sheet, encoding="utf-8")
    print("snapshots written:", sorted(p.name for p in SNAP_DIR.glob("*.txt")))

    out = src
    for name, sheet in blocks.items():
        inverted = maps[name]
        unknown = sorted({m.group(0) for m in LITERAL.finditer(sheet)} - set(inverted))
        if unknown:
            raise SystemExit("%s: literals missing from ui/tokens.py: %s" % (name, unknown))
        templated = LITERAL.sub(lambda m: "$" + inverted[m.group(0)], sheet)
        out = out.replace('%s = """%s"""' % (name, sheet),
                          '_%s_TEMPLATE = """%s"""' % (name, templated))
    render = "\nDARK_QSS = _render(_DARK_QSS_TEMPLATE, DARK_TOKENS)\nLIGHT_QSS = _render(_LIGHT_QSS_TEMPLATE, LIGHT_TOKENS)\n"
    out = out.replace(IMPORT_LINE + "\n", "")            # idempotence
    out = out.replace("from __future__ import annotations\n",
                      "from __future__ import annotations\n\nfrom string import Template\n\n" + IMPORT_LINE + "\n", 1)
    # the helper must exist before the templates are rendered, and the render calls must
    # come AFTER the light template (the first attempt inserted them before it)
    out = out.replace('_LIGHT_QSS_TEMPLATE = """', HELPER.strip("\n") + '\n\n\n_LIGHT_QSS_TEMPLATE = """', 1)
    lit = re.search(r'_LIGHT_QSS_TEMPLATE = """.*?"""\n', out, re.S)
    out = out[:lit.end()] + render + out[lit.end():]
    ast.parse(out)
    THEME.with_suffix(".py.bak").write_text(src, encoding="utf-8")
    THEME.write_text(out, encoding="utf-8")

    # prove it: render and compare with the snapshot
    sys.path.insert(0, ".")
    for mod in ("ui.theme", "ui.tokens"):
        sys.modules.pop(mod, None)
    theme = importlib.import_module("ui.theme")
    ok = True
    for name in ("DARK_QSS", "LIGHT_QSS"):
        frozen = (SNAP_DIR / ("%s.txt" % name.lower())).read_text(encoding="utf-8")
        now = getattr(theme, name)
        same = now == frozen
        ok &= same
        print("%s: %d chars, byte-identical=%s" % (name, len(now), same))
    print("batch 1 result:", "no visual change (proven by render equality)" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
