"""Auto-reply rule editor dialog (T10)."""
from __future__ import annotations


from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr


class AutoReplyDialog(QDialog):
    """Edit the auto-reply rules: when a match string arrives, send the reply."""

    def __init__(self, rules: list[dict], parent: QWidget | None=None):
        super().__init__(parent)
        self.setWindowTitle(tr("rb.title"))
        self.resize(720, 440)
        self._rows: list[dict] = []

        layout = QVBoxLayout(self)
        head = QHBoxLayout()
        head.addWidget(QLabel(tr("rb.match")), 3)
        head.addWidget(QLabel(tr("rb.reply")), 3)
        head.addWidget(QLabel("HEX"))
        head.addWidget(QLabel(tr("rb.enabled")))
        head.addSpacing(28)
        layout.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        self._rows_layout = QVBoxLayout(holder)
        self._rows_layout.addStretch(1)
        scroll.setWidget(holder)
        layout.addWidget(scroll, 1)

        for rule in rules:
            self.add_row(str(rule.get("match", "")), str(rule.get("reply", "")),
                         bool(rule.get("hex", False)), bool(rule.get("enabled", True)))

        add_btn = QPushButton(tr("rb.add"))
        add_btn.clicked.connect(lambda: self.add_row("", "", False, True))
        layout.addWidget(add_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(tr("btn.ok"))
        buttons.button(QDialogButtonBox.Cancel).setText(tr("btn.cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # -- rows ----------------------------------------------------------------

    def add_row(self, match: str = "", reply: str = "", is_hex: bool = False,
                enabled: bool = True) -> None:
        """Append one auto-reply rule as an editable row."""
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)

        m = QLineEdit(match)
        m.setPlaceholderText(tr("rb.match.ph"))
        h.addWidget(m, 3)

        r = QLineEdit(reply)
        r.setPlaceholderText(tr("rb.reply.ph"))
        h.addWidget(r, 3)

        hx = QCheckBox()
        hx.setChecked(is_hex)
        hx.setToolTip(tr("rb.hex.tip"))
        h.addWidget(hx)

        en = QCheckBox()
        en.setChecked(enabled)
        h.addWidget(en)

        dele = QPushButton("×")
        dele.setFixedWidth(28)
        dele.setStyleSheet("padding: 0px;")
        dele.setToolTip(tr("rb.delete"))
        dele.clicked.connect(lambda: self._delete(row))
        h.addWidget(dele)

        self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)
        self._rows.append({"widget": row, "match": m, "reply": r, "hex": hx, "enabled": en})

    def _delete(self, row: QWidget) -> None:
        for entry in list(self._rows):
            if entry["widget"] is row:
                self._rows.remove(entry)
                row.setParent(None)
                break

    # -- result --------------------------------------------------------------

    def rules(self) -> list[dict]:
        """Collect the edited rules, skipping rows without a match string."""
        out: list[dict] = []
        for e in self._rows:
            match = e["match"].text().strip()
            if not match:
                continue
            out.append({
                "match": match,
                "reply": e["reply"].text(),
                "hex": e["hex"].isChecked(),
                "enabled": e["enabled"].isChecked(),
            })
        return out
