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
