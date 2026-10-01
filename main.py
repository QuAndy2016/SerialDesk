"""Entry point: python main.py"""

import faulthandler
import os
import sys
import traceback

from PySide6.QtWidgets import QApplication

from app.config import log_dir, migrate_legacy_config
from ui.main_window import MainWindow

import ui.theme as theme


def install_crash_log() -> str:
    """E3: keep the last crash on disk, so a bug report can actually be diagnosed.

    C-level faults go to the same file through faulthandler, Python exceptions through
    sys.excepthook; the About box points the user at logs/lasterror.log.
    """
    path = os.path.join(log_dir(), "lasterror.log")
    try:
        stream = open(path, "a", encoding="utf-8", buffering=1)
    except OSError:
        return path
    faulthandler.enable(stream)

    def hook(exc_type, exc, tb):
        traceback.print_exception(exc_type, exc, tb, file=stream)
        stream.flush()
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = hook
    return path


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SerialDesk")   # taskbar / window grouping
    migrate_legacy_config()                # U102: inherit a pre-U34 config.json
    install_crash_log()                    # E3: logs/lasterror.log
    dark = theme.apply_theme(app)          # follow OS color scheme
    win = MainWindow()
    win.show()
    theme.apply_native_dark(win, bool(dark))   # U51: match native title bar
    # live switch when OS theme changes
    theme.watch_system_theme(app, lambda is_dark: theme.apply_theme(app, is_dark))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())