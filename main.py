"""Entry point: python main.py"""

import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow

import ui.theme as theme


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SerialDesk")   # taskbar / window grouping
    dark = theme.apply_theme(app)          # follow OS color scheme
    win = MainWindow()
    win.show()
    # live switch when OS theme changes
    theme.watch_system_theme(app, lambda is_dark: theme.apply_theme(app, is_dark))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())