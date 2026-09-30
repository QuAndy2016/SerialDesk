"""Tiny i18n layer for SerialDesk: zh/en string table + language state.

Language state is one of "system" (follow OS locale), "zh" or "en", and is
persisted by the caller into config.json under the "language" key.
"""

from __future__ import annotations

from PySide6.QtCore import QLocale

SYSTEM = "system"
SUPPORTED = (SYSTEM, "zh", "en")

_lang: str = SYSTEM

# key -> {"zh": ..., "en": ...}
STRINGS: dict[str, dict[str, str]] = {
    # ---- menus / theme / language ----
    # ---- config import / export (T15) ----
    "cfg.menu": {"zh": "配置(&C)", "en": "&Config"},
    "cfg.reset": {"zh": "恢复默认设置(&R)…", "en": "&Restore defaults…"},
    "cfg.reset.title": {"zh": "恢复默认设置", "en": "Restore default settings"},
    "cfg.reset.text": {
        "zh": "将把主题、语言、自动保存、自动重连、接收区选项、快速发送列表、发送历史与自动应答规则全部恢复为默认值。\n\n当前配置会先自动备份到数据目录（config.backup_日期_时间.json），随时可以手工恢复。\n\n确定继续吗？",
        "en": "This resets theme, language, auto-save, auto-reconnect, receive options, the quick-send list, send history and auto-reply rules to their defaults.\n\nYour current config is backed up first (config.backup_<date>_<time>.json in the data folder), so it can be restored by hand.\n\nContinue?",
    },
    "cfg.reset.done": {"zh": "已恢复默认设置；原配置备份在 {path}", "en": "Defaults restored; the previous config was backed up to {path}"},
    "cfg.reset.fail": {"zh": "恢复默认设置失败：{e}", "en": "Could not restore defaults: {e}"},
    "cfg.export": {"zh": "导出配置(&E)…", "en": "&Export config…"},
    "cfg.import": {"zh": "导入配置(&I)…", "en": "&Import config…"},
    "cfg.export.title": {"zh": "导出配置", "en": "Export config"},
    "cfg.import.title": {"zh": "导入配置", "en": "Import config"},
    "cfg.filter": {"zh": "JSON 配置 (*.json)", "en": "JSON config (*.json)"},
    "cfg.exported": {"zh": "配置已导出: {path}", "en": "Config exported: {path}"},
    "cfg.imported": {"zh": "配置已导入: {path}", "en": "Config imported: {path}"},
    "cfg.export_fail": {"zh": "导出配置失败: {e}", "en": "Export failed: {e}"},
    "cfg.import_fail": {"zh": "导入配置失败: {e}", "en": "Import failed: {e}"},
    "cfg.import_bad": {"zh": "文件格式不正确（不是 SerialDesk 配置）", "en": "Unsupported file (not a SerialDesk config)"},
    "menu.view": {"zh": "视图", "en": "View"},
    "conn.auto": {"zh": "断线自动重连", "en": "Auto-reconnect"},
    "conn.auto.tip": {
        "zh": "串口意外断开（拔线、驱动异常）时按 0.5~5 秒退避自动重连；手动关闭串口不会触发",
        "en": "Re-open automatically after an unexpected loss (unplug, driver error) with 0.5-5 s backoff; a manual close never triggers it",
    },
    "conn.auto.on": {"zh": "已开启断线自动重连", "en": "Auto-reconnect enabled"},
    "conn.auto.off": {"zh": "已关闭断线自动重连", "en": "Auto-reconnect disabled"},
    "conn.reconnecting": {"zh": "连接中断，正在重连（第 {n} 次）…", "en": "Connection lost - reconnecting (attempt {n})…"},
    "conn.reconnected": {"zh": "已自动重新连接", "en": "Reconnected automatically"},
    "conn.lost": {"zh": "连接已断开", "en": "Connection lost"},
    "portset.locked": {
        "zh": "串口已打开：数据位 / 校验位 / 停止位 / 流控 需关闭串口后才能修改；编码与信号线可随时调整。",
        "en": "Port is open: data bits / parity / stop bits / flow control can only change after closing it. Encoding and the signal lines stay available.",
    },
    "portset.free": {
        "zh": "这些参数在「打开串口」时生效；信号线可随时控制。",
        "en": "These settings apply when the port opens; the signal lines can be driven at any time.",
    },
    "portset.title": {"zh": "串口设置", "en": "Port settings"},
    "portset.open": {"zh": "串口设置…", "en": "Port settings…"},
    "portset.tip": {
        "zh": "数据位 / 校验位 / 停止位 / 流控 / 编码 与信号线（低频设置，独立窗口）",
        "en": "Data bits, parity, stop bits, flow control, encoding and the signal lines",
    },
    "portset.summary.tip": {
        "zh": "当前串口参数；点右侧「串口设置…」修改",
        "en": "Current port parameters - use Port settings… to change them",
    },
    "portset.menu": {"zh": "串口设置(&P)…", "en": "&Port settings…"},
    "about.menu": {"zh": "关于 SerialDesk(&A)…", "en": "&About SerialDesk…"},
    "about.title": {"zh": "关于 SerialDesk", "en": "About SerialDesk"},
    "about.text": {
        "zh": "<b>SerialDesk 串口台 {version}</b><br><br>一个干净、够用的跨平台串口调试工具。<br><br>PySide6 {pyside} · pySerial {pyserial}<br>许可证：MIT<br><br><a href='https://github.com/QuAndy2016/SerialDesk'>github.com/QuAndy2016/SerialDesk</a>",
        "en": "<b>SerialDesk {version}</b><br><br>A clean, capable, cross-platform serial debugging tool.<br><br>PySide6 {pyside} · pySerial {pyserial}<br>License: MIT<br><br><a href='https://github.com/QuAndy2016/SerialDesk'>github.com/QuAndy2016/SerialDesk</a>",
    },
    "hint.first_run": {
        "zh": "提示：选择串口后点「打开」即可开始收发；快捷键 Ctrl+Enter 发送、Ctrl+F 查找、F5 开关串口",
        "en": "Tip: pick a port and press Open to start. Shortcuts: Ctrl+Enter send, Ctrl+F find, F5 open/close",
    },
    "rx.autoscroll": {"zh": "自动滚动", "en": "Auto-scroll"},
    "rx.autoscroll.tip": {
        "zh": "接收时自动滚到底部；取消勾选可暂停（手动滚动时也会自动暂停）",
        "en": "Scroll to the newest line while receiving; untick to pause (manual scrolling pauses it too)",
    },
    "rx.cleared": {"zh": "已清空接收区（5 秒内可撤销）", "en": "Receive pane cleared (undo within 5 s)"},
    "rx.undo.done": {"zh": "已恢复清空前的显示", "en": "Display restored"},
    "undo.label": {"zh": "撤销", "en": "Undo"},
    "find.label": {"zh": "查找:", "en": "Find:"},
    "find.placeholder": {"zh": "要在接收区查找的文本", "en": "Text to find in the receive pane"},
    "find.prev": {"zh": "上一个", "en": "Previous"},
    "find.next": {"zh": "下一个", "en": "Next"},
    "find.close.tip": {"zh": "关闭查找（Esc）", "en": "Close the find bar (Esc)"},
    "find.none": {"zh": "未找到: {text}", "en": "Not found: {text}"},
    "sc.send.tip": {"zh": "发送（Ctrl+Enter）", "en": "Send (Ctrl+Enter)"},
    "sc.clear.tip": {"zh": "清空显示与计数（Ctrl+L，可撤销）", "en": "Clear display and counters (Ctrl+L, undoable)"},
    "sc.save.tip": {"zh": "保存接收日志（Ctrl+S）", "en": "Save receive log (Ctrl+S)"},
    "sc.open.tip": {"zh": "打开/关闭串口（F5）", "en": "Open/close the port (F5)"},
    "sc.find.tip": {"zh": "查找（Ctrl+F）", "en": "Find (Ctrl+F)"},
    "rx.cap": {
        "zh": "接收区已达显示上限（{n} 行），更早的数据不再显示；自动保存的日志文件不受影响",
        "en": "The receive pane hit its display limit ({n} lines); older data is no longer shown. Auto-saved logs are unaffected",
    },
    "menu.settings": {"zh": "设置(&S)", "en": "&Settings"},
    "theme.menu": {"zh": "主题(&T)", "en": "&Theme"},
    "menu.language": {"zh": "语言(&L)", "en": "&Language"},
    "theme.system": {"zh": "跟随系统(&Y)", "en": "Follow s&ystem"},
    "theme.dark": {"zh": "深色(&D)", "en": "&Dark"},
    "theme.light": {"zh": "浅色(&L)", "en": "&Light"},
    "lang.system": {"zh": "跟随系统", "en": "Follow system"},
    "lang.zh": {"zh": "中文", "en": "中文"},
    "lang.en": {"zh": "English", "en": "English"},
    # ---- connection bar ----
    "port.refresh": {"zh": "刷新", "en": "Refresh"},
    "port.open": {"zh": "打开", "en": "Open"},
    "port.close": {"zh": "关闭", "en": "Close"},
    "baud.tip": {
        "zh": "可直接输入自定义波特率（如 1000000），或点右侧箭头选择 26 档预设",
        "en": "Type a custom baud rate (e.g. 1000000), or use the arrow to pick from the 26 presets",
    },
    "rxfmt.label": {"zh": "接收格式:", "en": "RX format:"},
    "rxfmt.tip": {
        "zh": "接收显示格式\nASCII：字符显示\nHEX：十六进制显示\nHEX+ASCII：两者对照",
        "en": "Receive display format\nASCII: characters\nHEX: hexadecimal\nHEX+ASCII: side by side",
    },
    # ---- receive group ----
    "group.rx": {"zh": "接收", "en": "Receive"},
    "split.label": {"zh": "分包:", "en": "Split:"},
    "split.off": {"zh": "不分包", "en": "Off"},
    "split.auto": {"zh": "自动(按波特率)", "en": "Auto (by baud)"},
    "split.manual": {"zh": "手动(ms)", "en": "Manual (ms)"},
    "split.header": {"zh": "按帧头", "en": "By header"},
    "split.tip": {
        "zh": "分包分行方式\n自动：按波特率 3.5 字符时间\n手动：指定毫秒间隔\n按帧头：识别帧头字符串分行",
        "en": "How frames are split\nAuto: 3.5-char time by baud rate\nManual: fixed millisecond gap\nBy header: split on the header string",
    },
    "split.ms.tip": {"zh": "手动分包间隔（毫秒，0~60000，默认 10）", "en": "Manual split gap in ms (0-60000, default 10)"},
    "header.placeholder": {"zh": "帧头如 fw:", "en": "Header, e.g. fw:"},
    "header.tip": {
        "zh": "按帧头分包的帧头字符串\n填写后自动切换为按帧头模式",
        "en": "Header string for header-based splitting\nTyping one switches to header mode automatically",
    },
    "ts.label": {"zh": "时间戳:", "en": "Timestamp:"},
    "ts.off": {"zh": "不显示", "en": "None"},
    "ts.tip": {
        "zh": "行首时间戳格式\n建议 SHELL 调试用 HH:MM:SS.mmm",
        "en": "Timestamp format at the start of each line\nHH:MM:SS.mmm is handy for shell debugging",
    },
    "btn.clear": {"zh": "清空", "en": "Clear"},
    "rx.echo_tx": {"zh": "显示发送", "en": "Echo TX"},
    "rx.echo_tx.tip": {
        "zh": "在接收区回显发送的数据：TX 行以 -> 标记并染色，RX 行以 <- 标记，两者等宽不会打乱 HEX 对齐；取消勾选则只显示接收数据",
        "en": "Echo sent data into the receive pane: TX lines are marked with -> and coloured, RX lines with <-; equal-width markers keep HEX columns aligned. Untick to show received data only",
    },
    # ---- receive log to file (T4) ----
    "btn.save_log": {"zh": "保存日志", "en": "Save log"},
    "btn.save_log_quick": {"zh": "保存日志", "en": "Save log"},
    "btn.save_log_as": {"zh": "另存为…", "en": "Save as…"},
    "log.quick.tip": {
        "zh": "一键把接收区内容保存到 logs/ 目录（文件名带时间戳），状态栏会给出完整路径",
        "en": "Save the receive pane into logs/ in one click (timestamped file name); the exact path is shown in the status bar",
    },
    "as.title": {"zh": "自动保存设置", "en": "Auto-save settings"},
    "as.menu": {"zh": "自动保存设置(&A)…", "en": "&Auto-save settings…"},
    "as.enable": {"zh": "启用自动保存（打开串口后持续写入）", "en": "Enable auto-save (writes while the port is open)"},
    "as.max_mb": {"zh": "单个文件上限 (MB)", "en": "Max size per file (MB)"},
    "as.max_minutes": {"zh": "最长时间 (分钟)", "en": "Max duration (minutes)"},
    "as.dir": {"zh": "保存目录", "en": "Folder"},
    "as.dir.pick": {"zh": "选择日志保存目录", "en": "Choose the log folder"},
    "as.browse": {"zh": "浏览…", "en": "Browse…"},
    "as.note": {
        "zh": "接收到的每一行（含发送回显）会实时写入日志文件；超过上面的体积或时长就自动换一个新文件，文件名形如 serial_20261001_0200.txt。勾选右侧的「自动保存」开关与这里的「启用」是同一个状态。",
        "en": "Every received line (including TX echo) is written live to a log file; a new file starts once the size or duration above is reached, named like serial_20261001_0200.txt. The Auto-save switch in the receive toolbar and Enable here are the same state.",
    },
    "log.autosave": {"zh": "自动保存", "en": "Auto-save"},
    "log.autosave.tip": {
        "zh": "勾选后接收数据自动写入 logs/ 目录，单个文件超过 2 MB 或每 30 分钟自动分段",
        "en": "When enabled, received data is written to the logs/ folder; a new segment starts every 2 MB or 30 minutes",
    },
    "log.save.title": {"zh": "保存接收日志", "en": "Save receive log"},
    "log.saved": {"zh": "已保存: {path}", "en": "Saved: {path}"},
    "log.save_fail": {"zh": "保存日志失败: {e}", "en": "Failed to save log: {e}"},
    "log.autosave.on": {"zh": "自动保存到 {path}", "en": "Auto-saving to {path}"},
    # ---- send group ----
    "group.tx": {"zh": "发送", "en": "Send"},
    "txfmt.label": {"zh": "格式:", "en": "Format:"},
    "txfmt.tip": {
        "zh": "发送格式\nHEX：十六进制数据\nASCII：文本（支持 \\r\\n 转义）",
        "en": "Send format\nHEX: hexadecimal bytes\nASCII: text (\\r\\n escapes supported)",
    },
    "crc.label": {"zh": "校验:", "en": "Checksum:"},
    "crc.none": {"zh": "无", "en": "None"},
    "crc.tip": {
        "zh": "发送时自动追加的校验\nCRC16-Modbus：低字节在前（Modbus RTU）\nCRC16-CCITT：高字节在前\nCRC32：4 字节大端\nSUM8：单字节累加和",
        "en": "Checksum appended on send\nCRC16-Modbus: low byte first (Modbus RTU)\nCRC16-CCITT: high byte first\nCRC32: 4 bytes, big endian\nSUM8: single-byte sum",
    },
    # ---- serial parameters (T1) ----
    "params.databits": {"zh": "数据位:", "en": "Data bits:"},
    "params.parity": {"zh": "校验位:", "en": "Parity:"},
    "params.stopbits": {"zh": "停止位:", "en": "Stop bits:"},
    "params.flow": {"zh": "流控:", "en": "Flow:"},
    "params.encoding": {"zh": "编码:", "en": "Encoding:"},
    "params.encoding.tip": {
        "zh": "接收文本与发送文本使用的编码（ASCII 模式按字节显示，非可打印字符显示为 .）",
        "en": "Encoding used for received and sent text (ASCII shows bytes, non-printables as .)",
    },
    "sig.out": {"zh": "输出:", "en": "Out:"},
    "sig.out.tip": {
        "zh": "输出控制线：勾选 = 置高（部分无源 485/422 转换器需要）",
        "en": "Output control lines: checked = driven high (needed by some passive 485/422 converters)",
    },
    "sig.dtr.tip": {
        "zh": "DTR（Data Terminal Ready，数据终端就绪）：输出信号，勾选置高",
        "en": "DTR (Data Terminal Ready): output line, checked = high",
    },
    "sig.rts.tip": {
        "zh": "RTS（Request To Send，请求发送）：输出信号；开启硬件流控后由驱动自动管理",
        "en": "RTS (Request To Send): output line; managed automatically under hardware flow control",
    },
    "sig.in": {"zh": "输入:", "en": "In:"},
    "sig.in.tip": {
        "zh": "输入状态线（只读，每 50 ms 刷新）：CTS 清除发送 / DSR 数据装置就绪 / DCD 载波检测 / RI 振铃指示",
        "en": "Input status lines (read-only, refreshed every 50 ms): CTS / DSR / DCD / RI",
    },
    "sig.high": {"zh": "高", "en": "High"},
    "sig.low": {"zh": "低", "en": "Low"},
    "sig.cts.tip": {
        "zh": "CTS（Clear To Send，清除发送）：对端允许我方发送；硬件流控下用它暂停发送",
        "en": "CTS (Clear To Send): peer allows us to send; pauses TX under hardware flow control",
    },
    "sig.dsr.tip": {
        "zh": "DSR（Data Set Ready，数据装置就绪）：对端设备已上电并可通信",
        "en": "DSR (Data Set Ready): peer device is powered and ready",
    },
    "sig.dcd.tip": {
        "zh": "DCD（Data Carrier Detect，载波检测）：调制解调器检测到载波",
        "en": "DCD (Data Carrier Detect): modem detected a carrier",
    },
    "sig.ri.tip": {
        "zh": "RI（Ring Indicator，振铃指示）：调制解调器检测到来电振铃",
        "en": "RI (Ring Indicator): modem detected an incoming ring",
    },
    "sig.tip": {
        "zh": "信号线状态（CTS/DSR/DCD/RI），每 50 ms 刷新；DTR/RTS 为输出控制",
        "en": "Modem status lines (CTS/DSR/DCD/RI), refreshed every 50 ms; DTR/RTS are output controls",
    },
    "tx.hex.tip": {
        "zh": "十六进制格式：可空格分隔，也支持 0x 前缀与逗号/短横线分隔",
        "en": "Hex format: space separated; 0x prefix and comma/dash separators also accepted",
    },
    "tx.placeholder": {
        "zh": "在此输入要发送的内容；HEX 模式如 01 03 00 00（支持 0x 前缀与逗号）",
        "en": "Type what to send; in HEX mode e.g. 01 03 00 00 (0x prefixes and commas are fine)",
    },
    "tx.payload": {"zh": "将发送 {n} 字节", "en": "{n} bytes to send"},
    "tx.payload.bad": {"zh": "内容格式有误", "en": "invalid input"},
    "tx.payload.tip": {
        "zh": "按当前格式、校验与换行设置计算的实际发送字节数",
        "en": "Actual bytes sent, with the current format, checksum and CRLF settings applied",
    },
    "tx.escape": {"zh": "解析转义符", "en": "Parse escapes"},
    "tx.escape.tip": {
        "zh": "勾选时 \\r \\n \\t \\xNN 会被解释为控制字符；取消勾选则按字面发送",
        "en": "When checked \\r \\n \\t \\xNN become control bytes; unchecked sends them literally",
    },
    "params.tip": {
        "zh": "串口参数在打开端口时生效；修改后请重新打开端口",
        "en": "Serial parameters apply when the port is opened; reopen the port after changing them",
    },
    "parity.none": {"zh": "无", "en": "None"},
    "parity.odd": {"zh": "奇", "en": "Odd"},
    "parity.even": {"zh": "偶", "en": "Even"},
    "flow.none": {"zh": "无", "en": "None"},
    "flow.sw": {"zh": "软件(XON/XOFF)", "en": "Software (XON/XOFF)"},
    "flow.hw": {"zh": "硬件(RTS/CTS)", "en": "Hardware (RTS/CTS)"},
    # ---- append CRLF (T3) ----
    "tx.crlf": {"zh": "追加 \\r\\n", "en": "Append \\r\\n"},
    "tx.crlf.tip": {
        "zh": "ASCII 模式下发送时自动追加回车换行（AT 指令常用）",
        "en": "Append CRLF when sending in ASCII mode (handy for AT commands)",
    },
    # ---- repeat send (T2) / send history (T5) ----
    "tx.interval.label": {"zh": "间隔(ms)", "en": "Interval (ms)"},
    "split.auto.hint": {
        "zh": "按波特率自动",
        "en": "Auto by baud",
    },
    "split.off.hint": {"zh": "不分包", "en": "No split"},
    "tx.repeat": {"zh": "循环发送", "en": "Repeat send"},
    "tx.repeat.tip": {"zh": "按设定间隔重复发送当前内容", "en": "Repeat the current input at the set interval"},
    "tx.interval.tip": {"zh": "重复间隔（毫秒，范围 10~60000，默认 1000）", "en": "Repeat interval (ms, 10-60000, default 1000)"},
    "tx.sent_count": {"zh": "已发送 {n} 次", "en": "Sent {n} times"},
    "tx.history.delete": {"zh": "删除此条", "en": "Delete this entry"},
    "tx.history.clear": {"zh": "清空发送历史", "en": "Clear the history"},
    "tx.history.removed": {"zh": "已删除历史：{text}", "en": "Removed from history: {text}"},
    "tx.history.cleared": {"zh": "已清空发送历史", "en": "Send history cleared"},
    "tx.history": {"zh": "发送历史:", "en": "History:"},
    "tx.history.tip": {
        "zh": "最近发送过的指令（最多 {n} 条），选中即回填；在下拉列表里右键可删除单条或清空历史（也可按 Delete 键删除高亮项）",
        "en": "Recently sent commands (up to {n}); pick one to fill the box. Right-click an entry to delete it or clear the list (Delete removes the highlighted one)",
    },
    # ---- file send (T6) ----
    "btn.send_file": {"zh": "发送文件", "en": "Send file"},
    "btn.cancel_send": {"zh": "取消发送", "en": "Cancel send"},
    "file.dialog.title": {"zh": "选择要发送的文件", "en": "Choose a file to send"},
    "file.filter.all": {"zh": "所有文件 (*)", "en": "All files (*)"},
    "file.filter.hex": {"zh": "HEX 文本 (*.hex)", "en": "HEX text (*.hex)"},
    "file.filter.text": {"zh": "文本 (*.txt)", "en": "Text (*.txt)"},
    "file.filter.bin": {"zh": "二进制 (*.bin)", "en": "Binary (*.bin)"},
    "file.info": {"zh": "{size} · {baud} baud ≈ {eta} 秒", "en": "{size} · {baud} baud ≈ {eta}s"},
    "file.progress": {"zh": "已发送 {sent} / {total}（{pct}%）", "en": "Sent {sent} / {total} ({pct}%)"},
    "file.done": {"zh": "文件发送完成：{name}（{size}）", "en": "File sent: {name} ({size})"},
    "file.error": {"zh": "文件发送失败: {e}", "en": "File send failed: {e}"},
    "file.no_port": {"zh": "请先打开串口再发送文件", "en": "Open the port before sending a file"},
    # ---- auto reply (T10) ----
    "rb.enable": {"zh": "自动应答", "en": "Auto-reply"},
    "rb.enable.tip": {
        "zh": "勾选后，收到匹配串即自动发送响应串；规则在「规则…」中配置",
        "en": "When enabled, a matching frame triggers the reply; edit rules in \"Rules…\"",
    },
    "rb.rules_btn": {"zh": "规则…", "en": "Rules…"},
    "rb.title": {"zh": "自动应答规则", "en": "Auto-reply rules"},
    "rb.match": {"zh": "匹配串", "en": "Match"},
    "rb.reply": {"zh": "响应串", "en": "Reply"},
    "rb.enabled": {"zh": "启用", "en": "Enabled"},
    "rb.hex.tip": {"zh": "按 HEX 解析匹配串与响应串", "en": "Parse the match and reply strings as HEX"},
    "rb.add": {"zh": "+ 添加规则", "en": "+ Add rule"},
    "rb.delete": {"zh": "删除此条", "en": "Delete this row"},
    "rb.match.ph": {"zh": "如 01 03 00 00 00 02", "en": "e.g. 01 03 00 00 00 02"},
    "rb.reply.ph": {"zh": "匹配后自动发送的内容", "en": "Sent automatically on match"},
    "rb.saved": {"zh": "自动应答规则已保存（{n} 条）", "en": "Auto-reply rules saved ({n})"},
    "rb.sent": {"zh": "自动应答：已回复 {n} 字节", "en": "Auto-reply: sent {n} bytes"},
    "btn.ok": {"zh": "确定", "en": "OK"},
    "btn.cancel": {"zh": "取消", "en": "Cancel"},
    "btn.send": {"zh": "发送", "en": "Send"},
    # ---- status bar / log ----
    "status.disconnected": {"zh": "● 未连接", "en": "● Disconnected"},
    "status.connected": {"zh": "● 已连接 {port} @ {baud}", "en": "● Connected {port} @ {baud}"},
    "status.idle": {"zh": "未打开串口", "en": "Port not open"},
    "status.no_port": {"zh": "未发现串口", "en": "No serial port found"},
    "status.bad_baud": {"zh": "波特率格式错误", "en": "Invalid baud rate"},
    "status.opened": {"zh": "串口已打开", "en": "Port opened"},
    "err.tx.timeout": {
        "zh": "发送超时：设备没有读取数据（发送缓冲已满）。请检查设备是否在线、波特率与流控设置",
        "en": "Send timed out: the device is not draining its buffer. Check that it is online and that baud rate / flow control match",
    },
    "tx.need_port": {"zh": "请先打开串口", "en": "Open the serial port first"},
    "err.tx.closed": {"zh": "发送失败：串口未打开", "en": "Send failed: port is not open"},
    "err.tx.cts": {
        "zh": "设备 CTS 未就绪（硬件流控），该帧已丢弃。若设备不支持硬件流控，请把「流控」改为「无」",
        "en": "Peer CTS is not asserted (hardware flow control) - the frame was dropped. If the device does not drive CTS, set Flow to None",
    },
    "err.tx.degraded": {
        "zh": "发送已暂停：设备无响应。请重新打开串口后继续（必要时拔插一次 USB 转串口）",
        "en": "Sending paused: the device stopped responding. Re-open the port to continue (re-plug the USB adapter if needed)",
    },
    "err.tx.queue": {
        "zh": "发送队列已满（{n} 帧待发），请降低发送频率或检查设备是否停止接收",
        "en": "Send queue is full ({n} frames pending). Slow down or check whether the device stopped receiving",
    },
    "err.tx.io": {"zh": "发送失败：{e}", "en": "Send failed: {e}"},
    "err.open.denied": {
        "zh": "打开串口失败：没有权限（{e}）。请关闭占用该端口的程序，或以管理员身份运行",
        "en": "Cannot open port: access denied ({e}). Close the program holding the port, or run as administrator",
    },
    "err.open.busy": {
        "zh": "打开串口失败：端口被占用（{e}）。请先关闭其他正在使用该端口的程序",
        "en": "Cannot open port: busy ({e}). Close the other program using this port first",
    },
    "err.open.missing": {
        "zh": "打开串口失败：端口不存在或设备已拔出（{e}）。请刷新端口列表后重试",
        "en": "Cannot open port: device missing ({e}). Refresh the port list and retry",
    },
    "err.open.other": {
        "zh": "打开串口失败：{e}",
        "en": "Failed to open port: {e}",
    },
    "status.closed": {"zh": "串口已关闭", "en": "Port closed"},
    "log.send_error": {"zh": "发送内容错误: {e}", "en": "Send error: {e}"},
    # ---- quick send panel ----
    "qs.title": {"zh": "快速发送", "en": "Quick send"},
    "qs.add": {"zh": "+ 添加指令", "en": "+ Add command"},
    "qs.add.tip": {"zh": "添加一条快速指令（最多 {n} 条）", "en": "Add a quick command (up to {n})"},
    "qs.max": {"zh": "最多支持 {n} 条指令", "en": "Up to {n} commands supported"},
    "qs.placeholder": {"zh": "指令内容", "en": "Command"},
    "qs.send": {"zh": "发送", "en": "Send"},
    "qs.del_selected": {"zh": "删除选中", "en": "Delete selected"},
    "qs.del_selected.tip": {
        "zh": "删除选中的指令（也可以按 Delete 键）；删除后 3 秒内可撤销",
        "en": "Delete the selected command (or press Delete); undo is available for 3 seconds",
    },
    "qs.row.tip": {"zh": "单击选中这一行（左侧高亮），再用「删除选中」删除", "en": "Click to select this row, then use Delete selected"},
    "qs.sel.tip": {
        "zh": "勾选后点「运行」只按顺序发送勾选的指令；一个都不勾则发送全部",
        "en": "Tick to include this row when running the sequence; with nothing ticked every row runs",
    },
    "qs.sel.order.tip": {"zh": "该指令在序列中的顺序", "en": "Position of this command in the sequence"},
    "qs.deleted": {
        "zh": "已删除该指令（3 秒内可撤销）",
        "en": "Command deleted (undo within 3 s)",
    },
    "qs.undo.done": {"zh": "已恢复该指令", "en": "Command restored"},
    "qs.undo": {"zh": "撤销删除", "en": "Undo delete"},
    "qs.delete.tip": {"zh": "删除此条", "en": "Delete this row"},
    "qs.empty": {"zh": "指令内容为空", "en": "Command is empty"},
    "hex.empty": {
        "zh": "十六进制内容为空（只有分隔符）",
        "en": "Hex content is empty (separators only)",
    },
    "hex.odd": {
        "zh": "十六进制长度为奇数：第 {pos} 个字符后缺少一位",
        "en": "Hex length is odd: one digit missing after position {pos}",
    },
    "hex.bad_char": {
        "zh": "第 {pos} 个字符 '{ch}' 不是合法的十六进制字符",
        "en": "'{ch}' at position {pos} is not a valid hex digit",
    },
    "hex.fullwidth": {
        "zh": "检测到全角字符 '{ch}'（第 {pos} 位），请切换到英文输入法",
        "en": "Full-width char '{ch}' at position {pos}; switch to the English IME",
    },
    "hex.prefix_missing": {
        "zh": "第 {pos} 位的 0x 后面缺少十六进制数字",
        "en": "Missing hex digits after 0x at position {pos}",
    },
    "qs.bad_fmt": {"zh": "指令格式错误: {e}", "en": "Invalid command format: {e}"},
    "qs.save_fail": {"zh": "保存配置失败: {e}", "en": "Failed to save config: {e}"},
    # ---- command sequence (T13) ----
    "qs.seq": {"zh": "序列模式", "en": "Sequence mode"},
    "qs.seq.tip": {
        "zh": "按顺序发送：每条指令可单独设延迟（毫秒），点「运行」依次自动发出",
        "en": "Send rows in order: each row has its own delay (ms); press Run to fire them automatically",
    },
    "qs.run": {"zh": "运行", "en": "Run"},
    "qs.stop": {"zh": "停止", "en": "Stop"},
    "qs.delay.tip": {"zh": "本条发送后等待的毫秒数（0~60000，默认 500）", "en": "Delay after this row, in ms (0-60000, default 500)"},
    "qs.seq.progress": {"zh": "序列 {i}/{n}", "en": "Step {i}/{n}"},
    "qs.seq.done": {"zh": "序列发送完成", "en": "Sequence finished"},
    "qs.seq.none": {"zh": "没有可发送的指令", "en": "No commands to send"},
}


def set_language(lang: str) -> None:
    """Set the active language ("system" | "zh" | "en"). Unknown values fall back to system."""
    global _lang
    _lang = lang if lang in SUPPORTED else SYSTEM


def get_language() -> str:
    """Return the stored setting ("system" | "zh" | "en")."""
    return _lang


def current() -> str:
    """Resolve the effective language code, consulting the OS locale when following system."""
    if _lang in ("zh", "en"):
        return _lang
    try:
        return "zh" if QLocale.system().language() == QLocale.Language.Chinese else "en"
    except Exception:
        return "zh"


def tr(key: str, **kw) -> str:
    """Look up a string in the current language (falls back to zh, then to the key)."""
    table = STRINGS.get(key)
    if not table:
        return key
    text = table.get(current()) or table.get("zh") or key
    if kw:
        try:
            return text.format(**kw)
        except (KeyError, IndexError):
            return text
    return text


def hex_error_message(exc) -> str:
    """Localized, actionable text for a HexFormatError (falls back to str)."""
    kind = getattr(exc, "kind", None)
    if kind == "empty":
        return tr("hex.empty")
    if kind == "odd":
        return tr("hex.odd", pos=exc.pos)
    if kind == "bad_char":
        return tr("hex.bad_char", pos=exc.pos, ch=exc.ch)
    if kind == "fullwidth":
        return tr("hex.fullwidth", pos=exc.pos, ch=exc.ch)
    if kind == "prefix":
        return tr("hex.prefix_missing", pos=exc.pos)
    return str(exc)
