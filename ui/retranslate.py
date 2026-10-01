"""Language refresh for the main window (refactor step 3 of the split).

This used to be the second longest method in MainWindow - 113 lines of string
assignments. Moved out so the window keeps the wiring and this keeps the copy,
and so a language switch can be exercised without rebuilding the window.
"""
from __future__ import annotations


from app.i18n import tr

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def retranslate_ui(win: MainWindow) -> None:
    """Re-apply every translated string (called after a language change)."""
    _retranslate_menus(win)
    _retranslate_connection(win)
    _retranslate_receive_options(win)
    _retranslate_send(win)
    _retranslate_status(win)


def _retranslate_menus(win: MainWindow) -> None:
    win._settings_btn.setText(tr("menu.settings"))
    win._theme_menu.setTitle(tr("theme.menu"))
    win._lang_menu.setTitle(tr("menu.language"))
    win._cfg_menu.setTitle(tr("cfg.menu"))
    win._cfg_export_act.setText(tr("cfg.export"))
    win._cfg_import_act.setText(tr("cfg.import"))
    win._open_log_dir_act.setText(tr("menu.open_log_dir"))
    win._update_check_act.setText(tr("update.check"))
    win._update_now_act.setText(tr("update.check.now"))
    win._theme_system.setText(tr("theme.system"))
    win._theme_dark.setText(tr("theme.dark"))
    win._theme_light.setText(tr("theme.light"))
    win._lang_system.setText(tr("lang.system"))


def _retranslate_connection(win: MainWindow) -> None:
    win._port_lbl.setText(tr("port.label"))
    win._baud_lbl.setText(tr("baud.label"))
    win.refresh_btn.setText(tr("port.refresh"))
    win.baud_combo.setToolTip(tr("baud.tip"))
    win.open_btn.setText(tr("port.close") if win.worker.is_open() else tr("port.open"))
    win._rx_fmt_lbl.setText(tr("rxfmt.label"))
    win.rx_fmt_combo.setToolTip(tr("rxfmt.tip"))
    win._rx_group.setTitle(tr("group.rx"))
    win._split_lbl.setText(tr("split.label"))
    win._reload_combo(win.split_combo, [
        tr("split.off"), tr("split.auto"), tr("split.manual"), tr("split.header")])
    win.split_combo.setToolTip(tr("split.tip"))
    win.split_ms_edit.setToolTip(tr("split.ms.tip"))
    win.header_edit.setPlaceholderText(tr("header.placeholder.hex"))
    win.header_edit.setToolTip(tr("header.tip"))
    win.rx_filter_combo.setItemText(0, tr("rx.filter.all"))
    win.rx_filter_combo.setItemText(1, tr("rx.filter.rx"))
    win.rx_filter_combo.setItemText(2, tr("rx.filter.tx"))
    win.rx_filter_combo.setToolTip(tr("rx.filter.tip"))
    win.ts_check.setText(tr("ts.label"))
    win.ts_check.setToolTip(tr("ts.tip"))
    win.clear_btn.setText(tr("btn.clear"))
    win.save_log_btn.setText(tr("btn.save_log_quick"))
    win.save_log_btn.setToolTip(tr("sc.save.tip"))
    win.save_log_as_btn.setText(tr("btn.save_log_as"))
    win.dtr_check.setToolTip(tr("sig.tip"))
    win.rts_check.setToolTip(tr("sig.tip"))
    win._sig_out_lbl.setText(tr("sig.out"))
    win._sig_out_lbl.setToolTip(tr("sig.out.tip"))
    win._sig_in_lbl.setText(tr("sig.in"))
    win._sig_in_lbl.setToolTip(tr("sig.in.tip"))
    win.dtr_check.setToolTip(tr("sig.dtr.tip"))
    win.rts_check.setToolTip(tr("sig.rts.tip"))
    win.sig_lbl.setToolTip(tr("sig.in.tip"))
    win._poll_signals()


def _retranslate_receive_options(win: MainWindow) -> None:
    """Auto-reply, file send, echo/autoscroll, reconnect and the parameter summary."""
    win.auto_reply_act.setText(tr("rb.enable"))
    win.auto_reply_act.setToolTip(tr("rb.enable.tip"))
    win.rules_act.setText(tr("rb.rules.menu"))
    win.send_file_btn.setText(tr("btn.cancel_send") if win._file_timer.isActive()
                              else tr("btn.send_file"))
    win.send_file_btn.setToolTip(tr("btn.send_file"))
    win.echo_tx_check.setText(tr("rx.echo_tx"))
    win.echo_tx_check.setToolTip(tr("rx.echo_tx.tip"))
    win.autoscroll_check.setText(tr("rx.autoscroll"))
    win.autoscroll_check.setToolTip(tr("rx.autoscroll.tip"))
    win.pause_check.setText(tr("rx.pause"))
    win.pause_check.setToolTip(tr("rx.pause.tip"))
    win.wrap_check.setText(tr("rx.wrap"))
    win.wrap_check.setToolTip(tr("rx.wrap.tip"))
    win._reconnect_act.setText(tr("conn.auto"))
    win._reconnect_act.setToolTip(tr("conn.auto.tip"))
    win.params_summary.setToolTip(tr("portset.tip"))
    win._update_params_summary()
    win._port_dlg.retranslate()
    win._update_params_summary()
    win._dbit_lbl.setText(tr("params.databits"))
    win._parity_lbl.setText(tr("params.parity"))
    win._stopbit_lbl.setText(tr("params.stopbits"))
    win._flow_lbl.setText(tr("params.flow"))
    win._reload_combo(win.parity_combo, [tr("parity.none"), tr("parity.odd"), tr("parity.even"),
                                         "Mark", "Space"])
    win._reload_combo(win.flow_combo, [tr("flow.none"), tr("flow.sw"), tr("flow.hw")])
    for combo in win._param_combos:
        combo.setToolTip(tr("params.tip"))
    win._update_history_button()


def _retranslate_send(win: MainWindow) -> None:
    win.repeat_btn.setText(tr("tx.repeat.stop") if win.repeat_btn.isChecked()
                           else tr("tx.repeat"))
    win.repeat_btn.setToolTip(tr("tx.repeat.tip"))
    win.repeat_ms.setToolTip(tr("tx.interval.tip"))
    win._repeat_lbl.setText(tr("tx.interval.label"))
    win.tx_edit.setPlaceholderText(tr("tx.placeholder.hex"))   # U86 (set by the format below)
    win.tx_size_lbl.setToolTip(tr("tx.payload.tip"))
    win._reset_act.setText(tr("cfg.reset"))
    win._autosave_act.setText(tr("as.menu"))
    win._autosave_act.setToolTip(tr("as.note"))
    win._autosave_dlg.retranslate()
    win._update_payload_size()
    win._undo_btn.setText(tr("qs.undo"))
    win._undo_btn.setToolTip(tr("qs.deleted"))


def _retranslate_status(win: MainWindow) -> None:
    """Split hint, counters, encoding/newline, the TX group and the status light."""
    from ui.main_window import SPLIT_AUTO      # local import: avoids an import cycle
    win.split_hint_lbl.setText(
        tr("split.auto.hint") if win.split_combo.currentIndex() == SPLIT_AUTO else tr("split.off.hint"))
    win.sent_lbl.setText(tr("tx.sent_count", n=win._sent_count))
    win._enc_lbl.setText(tr("params.encoding"))
    win.encoding_combo.setToolTip(tr("params.encoding.tip"))
    win.escape_check.setText(tr("tx.escape"))
    win.escape_check.setToolTip(tr("tx.escape.tip"))
    win._nl_lbl.setText(tr("tx.newline.label"))
    win._reload_combo(win.nl_combo, [tr("tx.nl.none"), tr("tx.nl.cr"), tr("tx.nl.lf"),
                                     tr("tx.nl.crlf")])
    win.nl_combo.setToolTip(tr("tx.newline.tip"))
    win._tx_group.setTitle(tr("group.tx"))
    win._tx_fmt_lbl.setText(tr("txfmt.label"))
    win.tx_fmt_combo.setToolTip(tr("txfmt.tip"))
    win._crc_lbl.setText(tr("crc.label"))
    win._reload_combo(win.checksum_combo, [
        tr("crc.none"), "CRC16-Modbus", "CRC16-CCITT", "CRC32", "SUM8"])
    win.checksum_combo.setToolTip(tr("crc.tip"))
    win.send_btn.setText(tr("btn.send"))
    win.quick_panel.retranslate()
    win.rx_view.setPlaceholderText(tr("rx.empty.hint"))
    win.update_counts()
    win._notify(tr("status.opened") if win.worker.is_open() else tr("status.idle"))
    if win.worker.is_open():
        port = win.port_combo.currentData() or ""
        baud = win.baud_combo.currentText().strip()
        win.status_light.setText(tr("status.connected", port=port, baud=baud))
    else:
        win.status_light.setText(tr("status.disconnected"))
