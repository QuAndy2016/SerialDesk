"""Test isolation: never read or write the developer's own config.json.

Run from source the app resolves its data dir to the repository folder, so the
suite picks up the developer's ``config.json``. A full panel (99 quick-send rows)
then changes what the UI fixtures see - the same class of trap that once passed
locally and failed on the Windows runner. Point the config at a throw-away
directory for the whole session, before any ui module imports it by value.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="serialdesk-test-data-"))

os.environ.setdefault("XDG_CONFIG_HOME", str(_TMP))
os.environ.setdefault("APPDATA", str(_TMP))

import app.config as config          # noqa: E402

config.CONFIG_PATH = str(_TMP / "config.json")

# Pin the UI language for the whole suite. Several tests assert Chinese UI text, and a window
# built by the suite applies the *config's* language at startup - with an empty config that is
# "system", which is Chinese on this developer's machine and English on the CI runner. The
# v1.10.0 tag run failed exactly this way:
#     FAILED tests/test_ui_smoke.py::test_the_send_chip_shows_the_line_ending
#            - AssertionError: (0, 'ASCII · None · Checksum:None')
#     test_quick_panel_selection: assert '1 selected' == '已选 1'
# Nothing about the product was wrong - the suite was reading its own machine.
config.save_config({"language": "zh"})

# A modal confirmation dialog would block any headless test that exercises the delete
# action, so the suite switches it off; tests that check the confirmation drive it directly.
os.environ.setdefault("SERIALDESK_SKIP_CONFIRM", "1")
