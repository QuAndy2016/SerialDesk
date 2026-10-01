"""Shared config.json read/write helpers (quick-send, theme, future settings)."""

from __future__ import annotations

import json
import os

import sys


def data_dir() -> str:
    """Where SerialDesk keeps config.json and logs/ (U34).

    - frozen build with a ``portable.txt`` next to the exe -> that folder, so a
      "green"/portable copy still writes nothing outside its own directory;
    - frozen build otherwise -> a per-user folder (never %TEMP%, which is where a
      onefile build would have landed);
    - running from source -> the repository folder, unchanged for development.
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        if os.path.exists(os.path.join(exe_dir, "portable.txt")):
            return exe_dir
        if sys.platform.startswith("win"):
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
            return os.path.join(base, "SerialDesk")
        if sys.platform == "darwin":
            return os.path.expanduser("~/Library/Application Support/SerialDesk")
        return os.path.join(os.environ.get("XDG_CONFIG_HOME",
                                           os.path.expanduser("~/.config")), "serialdesk")
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def log_dir() -> str:
    """Directory for saved receive logs (created on demand)."""
    path = os.path.join(data_dir(), "logs")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


CONFIG_PATH = os.path.join(data_dir(), "config.json")


def migrate_legacy_config() -> str | None:
    """One-off migration for the data-root move (U102).

    Before U34 the frozen build read and wrote ``config.json`` next to the
    executable; U34 moved the data root to ``%APPDATA%/SerialDesk`` (or to the
    portable folder). Upgrading users would silently lose their settings, so on
    the first run of a new build: if the new location has no config and an old
    file still sits beside the exe, copy it over. Returns the migrated path, or
    ``None`` when there is nothing to do (source runs, portable mode, already
    migrated, or no legacy file).
    """
    if not getattr(sys, "frozen", False):
        return None
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    legacy = os.path.join(exe_dir, "config.json")
    if os.path.exists(CONFIG_PATH) or not os.path.exists(legacy):
        return None
    try:
        with open(legacy, "rb") as src:
            data = src.read()
        with open(CONFIG_PATH, "wb") as dst:
            dst.write(data)
        return CONFIG_PATH
    except OSError:
        return None


CONFIG_VERSION = 1


def migrate_config(data: dict) -> dict:
    """Bring an on-disk config up to CONFIG_VERSION (idempotent, pure-ish).

    Every migration step is one `if version < N` block, so older files keep
    working after a field changes shape (review finding M2 / E2).
    """
    version = int(data.get("config_version", 0) or 0)
    if version < 1:
        # v0 -> v1: the line ending used to be a boolean key ("crlf")
        if "newline" not in data and "crlf" in data:
            data["newline"] = "crlf" if data.get("crlf") else "none"
        data.pop("crlf", None)
    data["config_version"] = CONFIG_VERSION
    return data


def load_config() -> dict:
    """Load config.json; return {} if missing or malformed.

    The file is migrated in memory on every read, so callers always see the
    current shape and save_config writes it back upgraded.
    """
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return migrate_config(data) if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(data: dict, merge: bool = True) -> bool:
    """Write config.json atomically; returns success.

    Merges into whatever is on disk by default. Callers that persist a single key (the
    panel's folded flag, for instance) used to replace the whole file, silently
    dropping every other setting - folding the quick-send panel wiped the theme, the
    language, the log directory and the auto-save settings (U109).
    """
    try:
        payload = dict(data)
        if merge:
            current = load_config()
            current.update(payload)
            payload = current
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)
        return True
    except OSError:
        return False