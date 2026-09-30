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


def load_config() -> dict:
    """Load config.json; return {} if missing or malformed."""
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(data: dict) -> bool:
    """Write config.json atomically; returns success."""
    try:
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)
        return True
    except OSError:
        return False