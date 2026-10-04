"""The log folder resolution follows a documented priority (installer choice + config).

Order: portable copy -> config.json:log_dir -> logs_dir.txt beside the exe -> per-user
default. A choice that cannot be written falls back to the default instead of failing.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402


def test_configured_folder_wins(tmp_path):
    chosen = tmp_path / "my_logs"
    config.save_config({"log_dir": str(chosen)})
    assert config.log_dir() == str(chosen)


def test_blank_configuration_falls_back_to_the_default(tmp_path):
    config.save_config({"log_dir": ""})
    default = os.path.join(config.data_dir(), "logs")
    assert config.log_dir() == default


def test_unwritable_choice_falls_back(tmp_path):
    """A folder that cannot be created falls back to the default.

    The old case used "/proc/serialdesk-cannot-write", which is only unwritable while the
    write is sandboxed: run unsandboxed on Windows it resolves to "<drive>:\\proc\\..." and
    gets created happily, so the test littered the drive root and then failed (ledger E-021).
    A file standing where the folder should be fails on every OS and permission model.
    """
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("a file, not a folder", encoding="utf-8")
    config.save_config({"log_dir": str(blocker)})
    default = os.path.join(config.data_dir(), "logs")
    assert config.log_dir() == default


def test_seed_file_is_only_read_for_a_frozen_build(monkeypatch, tmp_path):
    seed_dir = tmp_path
    (seed_dir / "logs_dir.txt").write_text(str(tmp_path / "from_installer"), encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert config._installer_log_dir() == ""
