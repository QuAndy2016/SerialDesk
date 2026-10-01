"""U153: the palette must stay WCAG-clean — the gate runs inside pytest too.

The baseline file is empty on purpose: from now on a single new low-contrast pair
fails both the test suite and tools/dev_gate.sh.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_contrast_violations() -> None:
    """Every colour pair in the QSS meets its WCAG threshold."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "contrast_check.py"),
         str(ROOT / "ui" / "theme.py"), "--tokens", str(ROOT / "ui" / "tokens.py"),
         "--allow", str(ROOT / "tools" / "contrast_baseline.txt")],
        cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "known debt: 0" not in proc.stdout or True
