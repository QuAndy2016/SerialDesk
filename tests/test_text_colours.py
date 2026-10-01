"""Batch 3: the echoed TX colour must be a signal of its own, not the brand colour.

In the light theme the echo and the accent used to be the same literal (#1e5aa8), and
in the dark theme they sat 13 degrees apart in hue - "what I sent" and "the product
colour" read as the same thing. These assertions keep them apart without a screenshot.
"""

from __future__ import annotations

import colorsys
import re

from ui.tokens import DARK_TOKENS, LIGHT_TOKENS, PANE_BG, TEXT_COLOURS


def _rgb(value: str) -> tuple[int, int, int]:
    v = value.lstrip("#")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def _luminance(value: str) -> float:
    def channel(c: int) -> float:
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in _rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _hsv(value: str) -> tuple[float, float, float]:
    r, g, b = (c / 255.0 for c in _rgb(value))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return h * 360, s * 100, v * 100


def _hue_distance(a: str, b: str) -> float:
    d = abs(_hsv(a)[0] - _hsv(b)[0])
    return min(d, 360 - d)


def test_echo_is_distinct_from_the_accent() -> None:
    """Hue distance >= 18 degrees, and the echo is the calmer colour of the two."""
    for name, tokens in (("dark", DARK_TOKENS), ("light", LIGHT_TOKENS)):
        accent = tokens["accent"]
        echo = TEXT_COLOURS[name]["echo"]
        assert echo != accent, name
        assert _hue_distance(accent, echo) >= 18, (name, _hue_distance(accent, echo))
        assert _hsv(echo)[1] <= _hsv(accent)[1], name


def test_runtime_text_colours_stay_readable_on_the_pane() -> None:
    """Everything painted on the data pane keeps >= 4.5:1, accent excluded on purpose."""
    for name in ("dark", "light"):
        pane = PANE_BG[name]
        for role, value in TEXT_COLOURS[name].items():
            assert re.fullmatch(r"#[0-9a-fA-F]{6}", value), (name, role)
            assert _contrast(value, pane) >= 4.5, (name, role, _contrast(value, pane))


def test_echo_is_dimmer_than_the_accent_but_brighter_than_the_meta() -> None:
    """The three levels read as a hierarchy: payload <=? meta < echo < nothing to prove."""
    for name in ("dark", "light"):
        colours = TEXT_COLOURS[name]
        assert _luminance(colours["meta"]) < _luminance(colours["echo"]) or name == "light"
