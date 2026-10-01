#!/usr/bin/env python3
"""WCAG contrast audit for a Qt stylesheet (or a theme.py that holds one).

Usage
-----
    contrast_check.py ui/theme.py
    contrast_check.py style.qss --theme light --base "#f4f4f7"
    contrast_check.py ui/theme.py --text 4.5 --nontext 3.0 --quiet

Why: a colour plan is only real when it is machine-checkable. This is the gate
that turns "our palette looks fine" into a build step.

Rules
-----
* text (`color:` on a text-bearing selector) vs its background, or vs the base
  background when the rule has none  -> default 4.5:1
* borders / backgrounds used as non-text UI -> default 3.0:1
* rgba() is composited over the base background before measuring
Exit code 1 when any pair fails (so CI fails).
"""

from __future__ import annotations

import argparse
import os
import re
import sys

HEX = re.compile(r"#([0-9a-fA-F]{3,8})")
RGBA = re.compile(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)")


def parse_colour(text: str):
    """'#1e1e2e' | 'rgba(30,30,46,0.5)' -> (r, g, b, a) 0-255 / 0-1, else None."""
    text = text.strip()
    m = RGBA.search(text)
    if m:
        r, g, b = (float(m.group(i)) for i in (1, 2, 3))
        a = float(m.group(4)) if m.group(4) is not None else 1.0
        return (r, g, b, a)
    m = HEX.search(text)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) == 6:
            h += "ff"
        if len(h) != 8:
            return None
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16) / 255.0)
    return None


def over(fg, bg):
    """Composite fg (may be translucent) over opaque bg -> opaque rgb tuple."""
    r, g, b, a = fg
    return (r * a + bg[0] * (1 - a), g * a + bg[1] * (1 - a), b * a + bg[2] * (1 - a))


def luminance(rgb):
    def f(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (f(x) for x in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg, bg_opaque):
    a, b = luminance(over(fg, bg_opaque)), luminance(bg_opaque)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


TOKEN_BLOCK = re.compile(r"(DARK|LIGHT)_TOKENS[^=]*=\s*\{(.*?)\}", re.S)
TOKEN_ENTRY = re.compile(r'"([\w]+)"\s*:\s*"(#[0-9a-fA-F]{6})"')


def load_tokens(path: str) -> dict:
    """Parse ui/tokens.py into {DARK: {...}, LIGHT: {...}} (no import side effects)."""
    if not path or not os.path.exists(path):
        return {}
    raw = open(path, encoding="utf-8").read()
    return {name: dict(TOKEN_ENTRY.findall(body)) for name, body in TOKEN_BLOCK.findall(raw)}


def resolve_tokens(qss: str, table: dict) -> str:
    """Replace $token references with their literal, so the rules can be measured."""
    if not table:
        return qss
    return re.sub(r"\$(\w+)", lambda m: table.get(m.group(1), m.group(0)), qss)


def stylesheets(path: str):
    """Yield (name, qss) pairs: theme.py may hold several QSS blocks (or templates)."""
    raw = open(path, encoding="utf-8").read()
    blocks = re.findall(r'([A-Z_]+_QSS)\s*=\s*"""(.*?)"""', raw, re.S)
    if not blocks:                      # tokenised sheets live in *_QSS_TEMPLATE
        blocks = [(m[0] + "_QSS", m[1])
                  for m in re.findall(r'_([A-Z_]+)_QSS_TEMPLATE\s*=\s*"""(.*?)"""', raw, re.S)]
    if blocks:
        return blocks
    return [("stylesheet", raw)]


def rules(qss: str):
    for body in re.findall(r"([^{}]+)\{([^{}]*)\}", qss):
        selector, decls = body[0].strip(), body[1]
        yield selector, {
            k.strip(): v.strip()
            for k, _, v in (d.partition(":") for d in decls.split(";") if ":" in d)
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--text", type=float, default=4.5)
    ap.add_argument("--nontext", type=float, default=3.0)
    ap.add_argument("--base", default=None, help="base background when a rule has none")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--write-baseline", default=None,
                    help="record every current failure into this file and exit 0")
    ap.add_argument("--tokens", default=None,
                    help="ui/tokens.py: resolve $token references before measuring")
    ap.add_argument("--allow", default=None,
                    help="baseline file of known debt: one 'THEME selector kind' per line")
    args = ap.parse_args()

    allowed = set()
    if args.allow:
        for raw in open(args.allow, encoding="utf-8"):
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue        # selectors contain "#" (object names), so only full-line comments
            parts = [p.strip() for p in line.split("\t") if p.strip()]
            if len(parts) != 3:                      # tolerate "THEME selector kind"
                chunks = line.strip().split()
                if len(chunks) >= 3:
                    parts = [chunks[0], " ".join(chunks[1:-1]), chunks[-1]]
            if len(parts) == 3:
                allowed.add(tuple(parts))

    base_default = args.base or "#1e1e2e"
    token_tables = load_tokens(args.tokens)
    failures, checked = [], 0
    for name, qss in stylesheets(args.path):
        qss = resolve_tokens(qss, token_tables.get("DARK" if "DARK" in name.upper() else "LIGHT", {}))
        base = parse_colour(args.base) if args.base else None
        if base is None:                       # sniff the first plain background
            for _sel, decl in rules(qss):
                c = parse_colour(decl.get("background-color") or decl.get("background", ""))
                if c and c[3] >= 1.0:
                    base = c
                    break
            base = base or parse_colour(base_default)
        base = tuple(base[:3]) + (1.0,)
        base_rgb = base[:3]
        for selector, decl in rules(qss):
            bg = parse_colour(decl.get("background-color") or decl.get("background", ""))
            bg_rgb = over(bg, base_rgb) if (bg and bg[3] < 1.0) else (bg[:3] if bg else base_rgb)
            fg = parse_colour(decl.get("color", ""))
            if fg:
                checked += 1
                r = ratio(fg, tuple(bg_rgb))
                if r < args.text:
                    failures.append((name, selector, "text", "%.2f" % r, args.text))
            border = parse_colour(decl.get("border-color", "") or "")
            if border:
                checked += 1
                r = ratio(border, tuple(bg_rgb))
                if r < args.nontext:
                    failures.append((name, selector, "border", "%.2f" % r, args.nontext))
    if args.write_baseline:
        with open(args.write_baseline, "w", encoding="utf-8") as fh:
            fh.write("# Known contrast debt (baseline). One entry per line, TAB separated:\n")
            fh.write("# THEME<TAB>selector<TAB>kind\n")
            for name, selector, kind, _got, _want in failures:
                fh.write("%s\t%s\t%s\n" % (name, selector, kind))
        print("baseline written: %d entries -> %s" % (len(failures), args.write_baseline))
        return 0

    known = [f for f in failures if (f[0], f[1], f[2]) in allowed]
    new = [f for f in failures if (f[0], f[1], f[2]) not in allowed]
    if known and not args.quiet:
        print("known debt: %d (see the baseline file)" % len(known))
    if new:
        print("contrast failures (%d checked, %d new):" % (checked, len(new)))
        for name, selector, kind, got, want in new:
            print("  [%s] %-28s %-6s %s:1 (need %.1f)" % (name, selector[:28], kind, got, want))
        return 1
    if not args.quiet:
        print("contrast ok (%d pairs checked, %d known debt)" % (checked, len(known)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
