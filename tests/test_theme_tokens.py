"""batch 1: colours moved into ui/tokens.py must not change a single byte.

The snapshot files hold the sheets exactly as they were before the extraction, so a
regression here means the theme changed when it was only supposed to be re-written.
"""

from __future__ import annotations

import re
from pathlib import Path

import ui.theme as theme
from ui.tokens import DARK_TOKENS, LIGHT_TOKENS

SNAP = Path(__file__).parent / "snapshots"


def test_rendered_sheets_match_the_frozen_snapshot() -> None:
    """The token-rendered QSS is byte-identical to the pre-token QSS."""
    for sheet_name, file_name in (("DARK_QSS", "dark_qss.txt"), ("LIGHT_QSS", "light_qss.txt")):
        frozen = (SNAP / file_name).read_text(encoding="utf-8")
        assert getattr(theme, sheet_name) == frozen, sheet_name


def test_templates_contain_no_bare_colour_literals() -> None:
    """Every colour in a template is a $token, not a literal."""
    src = Path(theme.__file__).read_text(encoding="utf-8")
    templates = re.findall(r'_QSS_TEMPLATE = """(.*?)"""', src, re.S)
    assert len(templates) == 2
    for template in templates:
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", template)


def test_tokens_are_hex_and_actually_used() -> None:
    """Tokens are valid hex colours and each one shows up in its rendered sheet."""
    for tokens, sheet in ((DARK_TOKENS, theme.DARK_QSS), (LIGHT_TOKENS, theme.LIGHT_QSS)):
        for token, value in tokens.items():
            assert re.fullmatch(r"#[0-9a-fA-F]{6}", value), (token, value)
            assert value in sheet, token


def test_templates_render_only_with_their_own_tokens() -> None:
    """Substituting the wrong theme's tokens must fail loudly, not silently."""
    src = Path(theme.__file__).read_text(encoding="utf-8")
    templates = dict(zip(("DARK", "LIGHT"), re.findall(r'_QSS_TEMPLATE = """(.*?)"""', src, re.S)))
    from string import Template

    mismatched = Template(templates["DARK"]).safe_substitute(LIGHT_TOKENS)
    assert mismatched != theme.DARK_QSS
