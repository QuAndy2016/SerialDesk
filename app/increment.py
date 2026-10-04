"""Send auto-increment: {i} placeholders substituted at send time.

Pure functions (no Qt) so the substitution and the counter rules can be tested
directly; the caller owns the counter value.

Placeholder syntax:
    {i}            current value, using the default width
    {i:2}          width 2 (HEX: bytes, ASCII: zero-padded digits)
    {i:2:le}       ... and little-endian (HEX with width > 1)
    \\{i}          a literal "{i}" (not substituted)

The template is rendered in display text (HEX text or ASCII text) *before* it is
parsed into bytes, so the substituted value is part of the frame the checksum is
computed over.
"""

from __future__ import annotations

import re

_PLACEHOLDER = re.compile(r"(?<!\\)\{i(?::(\d+))?(?::(le|be))?\}")
_ESCAPED = re.compile(r"\\\{i(?::\d+)?(?::(?:le|be))?\}")

DEFAULT_CFG = {"start": 0, "step": 1, "width": 1, "endian": "big", "base": 10, "wrap": True}


def has_placeholder(template: str) -> bool:
    """True when the template contains at least one live {i} placeholder."""
    return _PLACEHOLDER.search(template) is not None


def _span(width: int, is_hex: bool, base: int) -> tuple:
    """(lo, hi) the counter may take for this width / format."""
    if is_hex:
        return 0, (1 << (8 * max(1, width))) - 1
    top = (16 ** width if base == 16 else 10 ** width) - 1
    return 0, top


def _format(value: int, width: int, endian: str, is_hex: bool, base: int) -> str:
    """Format one value the way the placeholder asked for."""
    lo, hi = _span(width, is_hex, base)
    if value < lo or value > hi:
        value = lo + (value - lo) % (hi - lo + 1)
    if is_hex:
        order = "little" if endian == "le" else "big"
        return " ".join("%02X" % b for b in value.to_bytes(max(1, width), order))
    if base == 16:
        return "%0*X" % (width, value)
    return "%0*d" % (width, value)


def render(template: str, *, is_hex: bool, value: int, cfg: dict) -> str:
    """Substitute every live {i}; a \\{i} becomes a literal {i}."""
    width = int(cfg.get("width", 1))
    endian = str(cfg.get("endian", "big"))
    base = int(cfg.get("base", 10))

    def repl(match: re.Match) -> str:
        w = int(match.group(1)) if match.group(1) else width
        e = match.group(2) or endian
        return _format(value, w, e, is_hex, base)

    return _ESCAPED.sub(lambda m: m.group(0)[1:], _PLACEHOLDER.sub(repl, template))


def next_value(value: int, *, is_hex: bool, cfg: dict) -> int | None:
    """The counter after one advance; None when exhausted with wrap off."""
    lo, hi = _span(int(cfg.get("width", 1)), is_hex, int(cfg.get("base", 10)))
    nxt = value + int(cfg.get("step", 1))
    if lo <= nxt <= hi:
        return nxt
    if not bool(cfg.get("wrap", True)):
        return None
    return lo + (nxt - lo) % (hi - lo + 1)


def apply_increment(template: str, *, is_hex: bool, value: int,
                    cfg: dict) -> tuple:
    """Render the template and return (text, next_value).

    ``next_value`` is None when the counter ran past its range and wrap is off
    (the caller sends this frame, then stops the loop). Without a placeholder the
    template and value come back unchanged.
    """
    if not has_placeholder(template):
        return template, value
    text = render(template, is_hex=is_hex, value=value, cfg=cfg)
    return text, next_value(value, is_hex=is_hex, cfg=cfg)
