"""U172: the port dropdown shows the full device name while the box stays short.

Kept in its own module so both ``ui.regions`` (which builds the combo) and
``ui.connection_controller`` (which fills it) can use it without importing each
other - that import used to be circular (regions -> connection_controller ->
menus -> regions).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

#: Item role holding the full "COM5 - USB-SERIAL CH340" text for the popup.
PORT_FULL_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class PortItemDelegate(QStyledItemDelegate):
    """Paint each dropdown row with the full device name.

    A QComboBox uses one text for both the closed box and the popup; the item
    text stays short ("COM5") and this delegate substitutes the full name when
    the popup is drawn.
    """

    def paint(self, painter, option, index):  # noqa: N802 - Qt naming
        full = index.data(PORT_FULL_ROLE)
        if not full:
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = str(full)
        widget = opt.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)
