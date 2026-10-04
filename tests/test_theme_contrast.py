"""The palette must stay WCAG-clean.

The colour checker and its baseline are not part of this repository, so the test skips
instead of failing when they are absent - a fresh clone still runs the whole suite.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_checker = os.environ.get("CONTRAST_CHECKER")      # optional external checker, if one is configured
GATE = Path(_checker).parent if _checker else None


def test_no_contrast_violations() -> None:
    """Every colour pair in the QSS meets its WCAG threshold."""
    if GATE is None:
        pytest.skip("no external contrast checker configured")
    script = GATE / "contrast_check.py"
    if not script.exists():
        pytest.skip("contrast checker is not installed on this host")
    proc = subprocess.run(
        [sys.executable, str(script),
         str(ROOT / "ui" / "theme.py"), "--tokens", str(ROOT / "ui" / "tokens.py"),
         "--allow", str(GATE / "contrast_baseline.txt")],
        cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
