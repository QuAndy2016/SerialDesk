"""The shortcut table - one source of truth for registration and for the help dialog.

The window registers the handlers; this module owns the keys and their labels, so
the help can never drift from reality (the review battery checks they agree).
"""

from __future__ import annotations

# (key sequence, i18n label key, extra scope note key or None)
HELP_ROWS = (
    ("Ctrl+Return", "sc.send", None),
    ("Ctrl+L", "sc.clear_rx", None),
    ("Ctrl+S", "sc.save_log", None),
    ("Ctrl+K", "sc.focus_input", None),
    ("F5", "sc.toggle_open", None),
    ("Ctrl+B", "sc.panel", None),
    ("Ctrl+,", "sc.settings", None),
    ("Ctrl+Up", "sc.hist_prev", None),
    ("Ctrl+Down", "sc.hist_next", None),
    ("Ctrl+F", "sc.find", None),
    ("Esc", "sc.esc", None),
    ("Delete", "sc.del_quick_row", "sc.scope.quick_panel"),
)


def keys() -> tuple:
    """Just the key sequences, for registration consistency checks."""
    return tuple(key for key, _label, _scope in HELP_ROWS)
