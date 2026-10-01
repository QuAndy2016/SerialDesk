"""Entry point: python main.py"""

import sys

from PySide6.QtWidgets import QApplication

from app.config import migrate_legacy_config
from ui.main_window import MainWindow

import ui.theme as theme


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SerialDesk")   # taskbar / window grouping
    migrate_legacy_config()                # U102: inherit a pre-U34 config.json
    dark = theme.apply_theme(app)          # follow OS color scheme
    win = MainWindow()
    win.show()
    theme.apply_native_dark(win, bool(dark))   # U51: match native title bar
    # live switch when OS theme changes
    theme.watch_system_theme(app, lambda is_dark: theme.apply_theme(app, is_dark))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())