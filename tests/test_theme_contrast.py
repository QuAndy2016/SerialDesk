"""The palette must stay WCAG-clean - the gate runs inside pytest too.

The checker and its baseline live in the internal gate directory
($SERIALDESK_GATE, default ~/personal/tools/serialdesk_gate), not in the repository:
colour checking is internal tooling. On a host without the gate the test skips
instead of failing, so a fresh clone still runs the suite.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE = Path(os.environ.get("SERIALDESK_GATE", "/root/personal/tools/serialdesk_gate"))


def test_no_contrast_violations() -> None:
    """Every colour pair in the QSS meets its WCAG threshold."""
    script = GATE / "contrast_check.py"
    if not script.exists():
        pytest.skip("contrast checker is not installed on this host")
    proc = subprocess.run(
        [sys.executable, str(script),
         str(ROOT / "ui" / "theme.py"), "--tokens", str(ROOT / "ui" / "tokens.py"),
         "--allow", str(GATE / "contrast_baseline.txt")],
        cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
