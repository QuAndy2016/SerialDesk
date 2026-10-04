"""The rounds wheel: one spin box that carries "keep going" as a value of its own.

Windows' spin-control guide asks for exactly this shape:

* "**At the end of a range of valid values, restart the range.** The spin control metaphor
  is that the user is spinning a wheel of values" (uxguide/ctrl-spin-controls.md:117) - the
  exception ("don't restart when the next value is certain to be wrong") does not apply:
  every value in this wheel is valid.
* "**Use text instead of special numeric values.** Allow users to spin to these special
  values instead of having to know them and type them in." (:124, and ":128 In this example,
  Never is a special value but users can spin to it.")

Both the quick-send sequence and the send area's repeat loop ask the same question ("how
many times?"), so the widget lives here and both import it: one wheel, one behaviour
(project standard UI-15…UI-18).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QSpinBox, QWidget

#: The top of the wheel. Everything above it is the "keep going" state, not a bigger number.
ROUNDS_LIMIT = 999


class RoundsSpinBox(QSpinBox):
    """How many times to repeat: one control, ∞ included.

    The wheel is ``∞ -up-> 1 -up-> 2 ... 999 -up-> ∞`` and backwards the same way; typing a
    number still works, and so does typing ∞. Internally the ∞ state is the spin box's
    minimum (0) shown through ``specialValueText`` - the documented Qt mechanism for a
    special value - so nothing in the UI ever shows or asks for "0".

    The wording (tooltip / accessible name) belongs to the caller, so each area describes
    its own counter and a language switch can refresh it.
    """

    ENDLESS = 0

    def __init__(self, parent: QWidget | None=None, tip: str = "", name: str = ""):
        super().__init__(parent)
        self.setRange(self.ENDLESS, ROUNDS_LIMIT)
        self.setValue(self.ENDLESS)              # default: run until stopped
        self.setSpecialValueText("\u221e")
        self.setMinimumWidth(56)
        self.setMaximumWidth(72)
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if tip:
            self.setToolTip(tip)
        if name:
            self.setAccessibleName(name)

    def endless(self) -> bool:
        """True while the loop runs until it is stopped."""
        return self.value() == self.ENDLESS

    def stepBy(self, steps: int) -> None:  # noqa: N802 - Qt naming
        """Spin the wheel: ∞ sits just below 1 and just above the maximum."""
        value = self.value()
        if steps == 1:
            self.setValue(1 if value == self.ENDLESS else
                          (self.ENDLESS if value >= ROUNDS_LIMIT else value + 1))
            return
        if steps == -1:
            if value == self.ENDLESS:            # ∞ wraps backwards to the top of the wheel
                self.setValue(ROUNDS_LIMIT)
            elif value <= 1:                     # 1 -> ∞
                self.setValue(self.ENDLESS)
            else:
                self.setValue(value - 1)
            return
        if steps > 0 and value == self.ENDLESS:
            self.setValue(min(ROUNDS_LIMIT, steps))
            return
        super().stepBy(steps)

    def valueFromText(self, text: str) -> int:  # noqa: N802 - Qt naming
        """Typed "∞" (or 0) means the endless state."""
        if text.strip().lower() in ("\u221e", "inf", "infinity"):
            return self.ENDLESS
        return super().valueFromText(text)

    def validate(self, text: str, pos: int):  # noqa: N802 - Qt naming
        """Let the special value pass validation so it can be typed and committed."""
        if text.strip().lower() in ("\u221e", "inf", "infinity"):
            return (QValidator.State.Acceptable, text, pos)
        return super().validate(text, pos)
