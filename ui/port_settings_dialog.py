"""Serial-port parameter dialog (U35-P3).

Data bits, parity, stop bits, flow control, encoding and the modem signal lines
are configured once and then rarely touched, so they live here instead of eating
a permanent row of the main window. The main window keeps a one-line summary and
a button that opens this dialog.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from app.i18n import tr

BYTESIZE_ITEMS = ["5", "6", "7", "8"]
STOPBITS_ITEMS = ["1", "1.5", "2"]


class PortSettingsDialog(QDialog):
    """Modeless dialog holding the low-frequency port settings (U35-P3)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(False)
        self.setMinimumWidth(360)

        root = QVBoxLayout(self)
        form = QFormLayout()

        self._dbit_lbl = QLabel(tr("params.databits"))
        self.dbits_combo = QComboBox()
        self.dbits_combo.addItems(BYTESIZE_ITEMS)
        self.dbits_combo.setCurrentIndex(len(BYTESIZE_ITEMS) - 1)     # 8
        form.addRow(self._dbit_lbl, self.dbits_combo)

        self._parity_lbl = QLabel(tr("params.parity"))
        self.parity_combo = QComboBox()
        self.parity_combo.addItems([tr("parity.none"), tr("parity.odd"),
                                    tr("parity.even"), "Mark", "Space"])
        form.addRow(self._parity_lbl, self.parity_combo)

        self._stopbit_lbl = QLabel(tr("params.stopbits"))
        self.stopbits_combo = QComboBox()
        self.stopbits_combo.addItems(STOPBITS_ITEMS)
        form.addRow(self._stopbit_lbl, self.stopbits_combo)

        self._flow_lbl = QLabel(tr("params.flow"))
        self.flow_combo = QComboBox()
        self.flow_combo.addItems([tr("flow.none"), tr("flow.sw"), tr("flow.hw")])
        form.addRow(self._flow_lbl, self.flow_combo)

        self._enc_lbl = QLabel(tr("params.encoding"))
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(["ASCII", "UTF-8", "GBK", "GB2312"])
        self.encoding_combo.setToolTip(tr("params.encoding.tip"))
        form.addRow(self._enc_lbl, self.encoding_combo)

        root.addLayout(form)

        out_row = QHBoxLayout()
        self._sig_out_lbl = QLabel(tr("sig.out"))
        self._sig_out_lbl.setEnabled(False)
        self._sig_out_lbl.setToolTip(tr("sig.out.tip"))
        out_row.addWidget(self._sig_out_lbl)
        self.dtr_check = QCheckBox("DTR")
        self.dtr_check.setToolTip(tr("sig.dtr.tip"))
        out_row.addWidget(self.dtr_check)
        self.rts_check = QCheckBox("RTS")
        self.rts_check.setToolTip(tr("sig.rts.tip"))
        out_row.addWidget(self.rts_check)
        out_row.addStretch(1)
        root.addLayout(out_row)

        in_row = QHBoxLayout()
        self._sig_in_lbl = QLabel(tr("sig.in"))
        self._sig_in_lbl.setEnabled(False)
        self._sig_in_lbl.setToolTip(tr("sig.in.tip"))
        in_row.addWidget(self._sig_in_lbl)
        self.sig_lbl = QLabel("CTS -  DSR -  DCD -  RI -")
        self.sig_lbl.setTextFormat(Qt.TextFormat.RichText)
        self.sig_lbl.setToolTip(tr("sig.in.tip"))
        in_row.addWidget(self.sig_lbl)
        in_row.addStretch(1)
        root.addLayout(in_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.hide)
        root.addWidget(buttons)

        self.setWindowTitle(tr("portset.title"))

    def retranslate(self) -> None:
        """Refresh every string (called by the main window's retranslate)."""
        self.setWindowTitle(tr("portset.title"))
        self._dbit_lbl.setText(tr("params.databits"))
        self._parity_lbl.setText(tr("params.parity"))
        self._stopbit_lbl.setText(tr("params.stopbits"))
        self._flow_lbl.setText(tr("params.flow"))
        self._enc_lbl.setText(tr("params.encoding"))
        self._sig_out_lbl.setText(tr("sig.out"))
        self._sig_out_lbl.setToolTip(tr("sig.out.tip"))
        self._sig_in_lbl.setText(tr("sig.in"))
        self._sig_in_lbl.setToolTip(tr("sig.in.tip"))
        self.sig_lbl.setToolTip(tr("sig.in.tip"))
        self.dtr_check.setToolTip(tr("sig.dtr.tip"))
        self.rts_check.setToolTip(tr("sig.rts.tip"))
