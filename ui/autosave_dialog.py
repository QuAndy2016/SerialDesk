"""Auto-save settings dialog (U75).

Auto-save writes every received line (and echoed TX lines) to a file while the
port is open. This dialog lets the user decide whether it runs, how large a
segment may grow and how long it may stay open, plus where the files land.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from app.i18n import tr


class AutoSaveDialog(QDialog):
    """Modeless auto-save settings; every change applies immediately (U75)."""

    settingsChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(False)
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)

        self.enable_check = QCheckBox(tr("as.enable"))
        self.enable_check.toggled.connect(lambda *_: self.settingsChanged.emit())
        root.addWidget(self.enable_check)

        form = QFormLayout()
        self._mb_lbl = QLabel(tr("as.max_mb"))
        self.max_mb_edit = QLineEdit("2")
        self.max_mb_edit.setValidator(QIntValidator(1, 4096, self))
        self.max_mb_edit.textChanged.connect(lambda *_: self.settingsChanged.emit())
        form.addRow(self._mb_lbl, self.max_mb_edit)

        self._min_lbl = QLabel(tr("as.max_minutes"))
        self.max_min_edit = QLineEdit("30")
        self.max_min_edit.setValidator(QIntValidator(1, 1440, self))
        self.max_min_edit.textChanged.connect(lambda *_: self.settingsChanged.emit())
        form.addRow(self._min_lbl, self.max_min_edit)

        self._dir_lbl = QLabel(tr("as.dir"))
        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit("")
        self.dir_edit.setReadOnly(True)
        dir_row.addWidget(self.dir_edit, 1)
        self.browse_btn = QPushButton(tr("as.browse"))
        self.browse_btn.clicked.connect(self._choose_dir)
        dir_row.addWidget(self.browse_btn)
        form.addRow(self._dir_lbl, dir_row)

        root.addLayout(form)

        self.note_lbl = QLabel(tr("as.note"))
        self.note_lbl.setWordWrap(True)
        root.addWidget(self.note_lbl)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.hide)
        root.addWidget(buttons)

        self.setWindowTitle(tr("as.title"))

    # -- helpers -------------------------------------------------------------

    def _choose_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("as.dir.pick"), self.dir_edit.text())
        if path:
            self.dir_edit.setText(path)
            self.settingsChanged.emit()

    def set_values(self, *, enabled: bool, max_mb: int, max_minutes: int, folder: str) -> None:
        """Seed the widgets (blocking signals so seeding does not re-apply)."""
        for widget in (self.enable_check, self.max_mb_edit, self.max_min_edit):
            widget.blockSignals(True)
        self.enable_check.setChecked(bool(enabled))
        self.max_mb_edit.setText(str(int(max_mb)))
        self.max_min_edit.setText(str(int(max_minutes)))
        for widget in (self.enable_check, self.max_mb_edit, self.max_min_edit):
            widget.blockSignals(False)
        self.dir_edit.setText(folder)

    def values(self) -> dict:
        def _num(text: str, default: int) -> int:
            try:
                return max(1, int((text or "").strip()))
            except ValueError:
                return default

        return {
            "enabled": self.enable_check.isChecked(),
            "max_mb": _num(self.max_mb_edit.text(), 2),
            "max_minutes": _num(self.max_min_edit.text(), 30),
            "dir": self.dir_edit.text().strip(),
        }

    def retranslate(self) -> None:
        self.setWindowTitle(tr("as.title"))
        self.enable_check.setText(tr("as.enable"))
        self._mb_lbl.setText(tr("as.max_mb"))
        self._min_lbl.setText(tr("as.max_minutes"))
        self._dir_lbl.setText(tr("as.dir"))
        self.browse_btn.setText(tr("as.browse"))
        self.note_lbl.setText(tr("as.note"))
