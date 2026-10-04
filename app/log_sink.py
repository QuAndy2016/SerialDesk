"""Auto-save log writing, as a plain object (refactor step 2).

Extracted from the window so the file rules - segment naming, rotation by size or
age, and the session header - can be tested without a QApplication. It writes one
segment at a time and rotates when the configured byte or time limit is reached.

The header exists because a captured log without port settings, framing and a
start time cannot be reproduced by the person you send it to.
"""
from __future__ import annotations


import os
import time

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Callable

SEGMENT_PATTERN = "serial_%Y%m%d_%H%M%S.txt"


def prune_log_dir(directory: str, quota_bytes: int, keep: str = "") -> int:
    """Delete the oldest segments until the folder is under quota (E4/d).

    Only *.txt segments are candidates, oldest first; the currently open segment
    (``keep``) is never removed. ``quota_bytes <= 0`` means unlimited. Returns the
    number of files deleted.
    """
    if quota_bytes <= 0:
        return 0
    keep_abs = os.path.abspath(keep) if keep else ""
    files = []
    try:
        names = os.listdir(directory)
    except OSError:
        return 0
    for name in names:
        if not name.endswith(".txt"):
            continue
        path = os.path.join(directory, name)
        if os.path.abspath(path) == keep_abs:
            continue
        try:
            files.append((os.path.getmtime(path), os.path.getsize(path), path))
        except OSError:
            continue
    total = sum(size for _, size, _ in files)
    if keep_abs:
        try:
            total += os.path.getsize(keep_abs)
        except OSError:
            pass
    removed = 0
    for _, size, path in sorted(files):
        if total <= quota_bytes:
            break
        try:
            os.remove(path)
            total -= size
            removed += 1
        except OSError:
            continue
    return removed


class LogSink:
    """Append-only log writer with size/age rotation and a session header."""

    def __init__(self, directory: str, max_bytes: int = 2 * 1024 * 1024,
                 max_seconds: int = 30 * 60, header: str=None, clock: Callable[[], float]=time.time) -> None:
        self._dir = directory
        self._max_bytes = max(1, int(max_bytes))
        self._max_seconds = max(1, int(max_seconds))
        self._header = header            # callable -> str, written at each segment start
        self._clock = clock
        self._fp = None
        self._path = ""
        self._started = 0.0
        self._written = 0

    # -- configuration -------------------------------------------------------

    @property
    def directory(self) -> str:
        """Directory the log file is written to."""
        return self._dir

    def configure(self, directory: str | None = None, max_bytes: int | None = None,
                  max_seconds: int | None = None) -> None:
        """Update directory and rotation limits (settings changed)."""
        if directory:
            self._dir = directory
        if max_bytes:
            self._max_bytes = max(1, int(max_bytes))
        if max_seconds:
            self._max_seconds = max(1, int(max_seconds))

    @property
    def is_open(self) -> bool:
        """True while a log segment is open for writing."""
        return self._fp is not None

    @property
    def path(self) -> str:
        """Path of the open segment, or an empty string."""
        return self._path

    @property
    def bytes_written(self) -> int:
        """Bytes written into the current segment."""
        return self._written

    # -- writing -------------------------------------------------------------

    def open(self) -> str:
        """Start a new segment (creating the directory) and return its path."""
        os.makedirs(self._dir, exist_ok=True)
        self._path = self._unique_path()
        self._fp = open(self._path, "a", encoding="utf-8")
        self._started = self._clock()
        self._written = 0
        header = self._header() if callable(self._header) else ""
        if header:
            self._write(header.rstrip("\n") + "\n")
        return self._path

    def _unique_path(self) -> str:
        """A segment name that does not exist yet (rotation can happen twice in a
        second, which would otherwise append two segments into one file)."""
        base = os.path.join(self._dir, time.strftime(SEGMENT_PATTERN))
        if not os.path.exists(base):
            return base
        stem, ext = os.path.splitext(base)
        index = 2
        while os.path.exists("%s-%d%s" % (stem, index, ext)):
            index += 1
        return "%s-%d%s" % (stem, index, ext)

    def append(self, text: str) -> None:
        """Write a chunk, rotating first when a limit is already exceeded."""
        if self._fp is None:
            return
        if (self._written > self._max_bytes
                or self._clock() - self._started > self._max_seconds):
            self.close()
            self.open()
        self._write(text)

    def close(self) -> None:
        """Flush and close the current segment."""
        if self._fp is not None:
            try:
                self._fp.close()
            except OSError:
                pass
            self._fp = None

    def _write(self, text: str) -> None:
        if self._fp is None:
            return
        self._fp.write(text)
        self._fp.flush()
        self._written += len(text.encode("utf-8"))

    def __enter__(self):            # pragma: no cover - convenience
        return self

    def __exit__(self, *exc):       # pragma: no cover - convenience
        self.close()
