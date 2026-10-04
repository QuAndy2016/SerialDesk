"""A single-line field that rests showing its first character.

Why this class exists (user report 2026-10-04: "可以让文字任何时候都从第一个字符开始显示吗，
现在是居中显示到名称的字框里")
------------------------------------------------------------------------------------
``QLineEdit`` keeps the caret visible and ``setText()`` leaves the caret at the end, so a value
wider than the field is painted as its *end* - the first character gets cut off - and that
horizontal offset **survives losing focus**. With the quick-send panel's width-capped name box
(96 px) and command box, the row then showed "取设备序列号" for the name "读取设备序列号" and
looked as if the text sat centred in the box. Reproduced and fixed in
``local_docs/05_tooling/cache/name_align_probe7.py``.

That outcome is what the platform guide warns against for a field whose width is a deliberate
cap: "**Don't make users scroll unnecessarily.** If you expect data to be larger than the text
box and you can readily make the text box larger without harming the layout, size the box to
eliminate the need for scrolling" and "**Choose a width appropriate for the longest valid
data.** In most situations, users shouldn't have to scroll the longest likely string they'll
enter or view" (``uxguide/ctrl-text-boxes.md:78``,``:257``; local mirror ``08_refs/ms-win32``).

The rule this class implements:

======================  ==========================================================
state                   what the field shows
======================  ==========================================================
not edited              its text **from the first character** (the view rests at 0)
being edited            the caret's slice - Qt's contract is that the caret stays
                        visible, and a long value only fits scrolled
gaining focus          caret at the end, so typing appends and never prepends
clicked                 insertion point where the user clicked (Qt delivers the
                        focus-in event before the mouse press, so the click wins)
======================  ==========================================================

The click half of that table is standard platform behaviour - "Single left-click: Activates or
selects the object. **For text, sets the insertion point**" (``uxguide/inter-mouse.md:210``) -
and is covered by ``tests/test_quick_panel_interaction.py``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QLineEdit

if TYPE_CHECKING:
    from PySide6.QtGui import QFocusEvent


class StartVisibleLineEdit(QLineEdit):
    """Editable field that rests at its first character (see the module docstring)."""

    def setText(self, text: str) -> None:  # noqa: N802 - Qt naming
        """Set the value and show it from the beginning.

        ``QLineEdit.setText`` moves the caret to the end of the new text, which is what makes
        the field paint its tail; the row loads every name and command through here.
        """
        super().setText(text)
        self.setCursorPosition(0)

    def focusInEvent(self, event: QFocusEvent) -> None:  # noqa: N802 - Qt naming
        """Put the caret at the end so typing appends to the value the user sees."""
        super().focusInEvent(event)
        self.setCursorPosition(len(self.text()))

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802 - Qt naming
        """Undo the editing scroll: the field leaves showing its first character."""
        super().focusOutEvent(event)
        self.setCursorPosition(0)
