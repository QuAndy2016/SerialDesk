"""Update check (U127): ask GitHub for the latest release, quietly.

Design rules this module follows:
  * stdlib only - the project does not take a dependency for one HTTP GET;
  * never blocks the UI (the caller runs :func:`fetch_latest_tag` on a worker thread);
  * never nags: the caller records the version it has already seen;
  * fails silently - offline, rate-limited or a blocked API all mean "no news";
  * sends nothing about the user; it is a plain GET for the public releases API.

The pure helpers (:func:`parse_version`, :func:`is_newer`) are what the tests pin
down, so version handling stays honest even when the network is not available.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

RELEASES_API = "https://api.github.com/repos/QuAndy2016/SerialDesk/releases/latest"
RELEASES_PAGE = "https://github.com/QuAndy2016/SerialDesk/releases/latest"
USER_AGENT = "SerialDesk-update-check"
TIMEOUT_S = 5.0


def parse_version(text: str) -> tuple:
    """"v1.4.0" / "1.4.0" / "1.4" -> (1, 4, 0); anything unparseable -> ()"""
    cleaned = str(text or "").strip().lstrip("vV")
    if not cleaned:
        return ()
    parts = []
    for chunk in cleaned.split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        if not digits:
            return ()
        parts.append(int(digits))
    return tuple(parts)


def is_newer(candidate: str, current: str) -> bool:
    """True when `candidate` is a strictly newer version than `current`."""
    a, b = parse_version(candidate), parse_version(current)
    if not a or not b:
        return False
    length = max(len(a), len(b))
    a = a + (0,) * (length - len(a))
    b = b + (0,) * (length - len(b))
    return a > b


def fetch_latest_tag(timeout: float = TIMEOUT_S) -> str:
    """The latest release tag, or "" when it cannot be determined (never raises)."""
    request = urllib.request.Request(
        RELEASES_API,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return ""
    tag = payload.get("tag_name") if isinstance(payload, dict) else None
    return str(tag or "")
