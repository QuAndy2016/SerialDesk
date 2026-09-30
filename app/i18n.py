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
    "cfg.menu": {"zh": "配置", "en": "Config"},
    "cfg.export": {"zh": "导出配置…", "en": "Export config…"},
    "cfg.import": {"zh": "导入配置…", "en": "Import config…"},
    "cfg.export.title": {"zh": "导出配置", "en": "Export config"},
    "cfg.import.title": {"zh": "导入配置", "en": "Import config"},
    "cfg.filter": {"zh": "JSON 配置 (*.json)", "en": "JSON config (*.json)"},
    "cfg.exported": {"zh": "配置已导出: {path}", "en": "Config exported: {path}"},
    "cfg.imported": {"zh": "配置已导入: {path}", "en": "Config imported: {path}"},
    "cfg.export_fail": {"zh": "导出配置失败: {e}", "en": "Export failed: {e}"},
    "cfg.import_fail": {"zh": "导入配置失败: {e}", "en": "Import failed: {e}"},
    "cfg.import_bad": {"zh": "文件格式不正确（不是 SerialDesk 配置）", "en": "Unsupported file (not a SerialDesk config)"},
    "menu.view": {"zh": "视图", "en": "View"},
    "menu.settings": {"zh": "设置", "en": "Settings"},
    "theme.menu": {"zh": "主题", "en": "Theme"},
    "menu.language": {"zh": "语言", "en": "Language"},
    "theme.system": {"zh": "跟随系统", "en": "Follow system"},
    "theme.dark": {"zh": "深色", "en": "Dark"},
    "theme.light": {"zh": "浅色", "en": "Light"},
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
    "split.ms.tip": {"zh": "手动分包间隔（毫秒）", "en": "Manual split interval (ms)"},
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
        "zh": "按波特率自动（约 3.5 字符）",
        "en": "Auto by baud (~3.5 chars)",
    },
    "split.off.hint": {"zh": "不按时间分包", "en": "No time-based split"},
    "tx.repeat": {"zh": "循环发送", "en": "Repeat send"},
    "tx.repeat.tip": {"zh": "按设定间隔重复发送当前内容", "en": "Repeat the current input at the set interval"},
    "tx.interval.tip": {"zh": "重复间隔（毫秒，10~60000）", "en": "Repeat interval (ms, 10~60000)"},
    "tx.sent_count": {"zh": "已发送 {n} 次", "en": "Sent {n} times"},
    "tx.history": {"zh": "发送历史:", "en": "History:"},
    "tx.history.tip": {"zh": "最近发送过的指令（最多 {n} 条），选中即回填", "en": "Recently sent commands (up to {n}); pick one to fill the box"},
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
    "err.tx.closed": {"zh": "发送失败：串口未打开", "en": "Send failed: port is not open"},
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
    "qs.delay.tip": {"zh": "本条发送后等待的毫秒数", "en": "Milliseconds to wait after sending this row"},
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
