"""The send box's input rule: Enter runs the command, trailing spaces are not data.

Why this widget exists (user report 2026-10-04: "按 ENTER 就换行，光标往下跑…空格键也是
一样，不能允许数据后有空格")
------------------------------------------------------------------------------
Two official rules decide it:

* ``uxguide/inter-keyboard.md:78`` - "**Spacebar, Enter, and Esc keys.** The spacebar
  activates the control with input focus, whereas **the Enter key activates the default
  button**." The send box's default button *is* Send (``send_btn.setDefault(True)``), so
  Enter must run the command instead of inserting a line break. ``Shift+Enter`` stays as
  the explicit way to type a line break (an ASCII payload may contain one on purpose).
* ``uxguide/ctrl-text-boxes.md:211`` - "If the user enters a character that isn't valid,
  **ignore the character** and display an input problem balloon that explains the valid
  characters." A space that would end up *after* the data is never part of the payload
  (the send path strips it anyway), so it is ignored at the keystroke and explained once
  through :attr:`rejected`.

A serial command is one line of data; the line ending is the job of the「行尾」picker, not
of the Enter key - that is why the trailing break is not accepted here.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QPlainTextEdit


class TxInputEdit(QPlainTextEdit):
    """The send box: Enter submits, Shift+Enter breaks the line, no trailing spaces."""

    submitted = Signal()
    rejected = Signal(str)      # a short reason, shown once by the window

    def keyPressEvent(self, event: QKeyEvent):  # noqa: N802 - Qt naming
        """Enter = the default command; Space at the very end is not data."""
        key = event.key()
        mods = event.modifiers()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if mods & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)        # explicit line break
            else:
                self.submitted.emit()               # Enter runs the command
            event.accept()
            return
        if key == Qt.Key.Key_Space and self._space_would_trail():
            self.rejected.emit("tx.reject.trailing_space")
            event.accept()
            return
        super().keyPressEvent(event)

    def _space_would_trail(self) -> bool:
        """True when a space typed right now would sit *after* the data."""
        text = self.toPlainText()
        cursor = self.textCursor()
        return bool(text) and not cursor.hasSelection() and cursor.position() >= len(text)
