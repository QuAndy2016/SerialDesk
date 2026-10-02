"""Tiny i18n layer for SerialDesk: zh/en string table + language state.

Language state is one of "system" (follow OS locale), "zh" or "en", and is
persisted by the caller into config.json under the "language" key.
"""
from __future__ import annotations


from PySide6.QtCore import QLocale

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.protocol import HexFormatError

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
    "cfg.reset.done": {"zh": "已恢复默认设置（原配置已备份）", "en": "Defaults restored (the previous config was backed up)"},
    "cfg.reset.done.tip": {"zh": "原配置备份：{path}", "en": "Previous config backed up to: {path}"},
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
    "portset.tip": {
        "zh": "串口参数：数据位 / 校验位 / 停止位 / 流控 / 编码\n点击这里修改（等价于「串口设置」）",
        "en": "Serial parameters: data bits / parity / stop bits / flow control / encoding\nClick to change them",
    },
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
    "rx.pause": {"zh": "暂停显示", "en": "Pause display"},
    "rx.pause.tip": {"zh": "暂停时数据继续写入日志，恢复后继续显示", "en": "While paused, data keeps going to the log; resume to show live data again"},
    "rx.pause.resumed": {"zh": "已恢复显示（暂停期间数据已写入日志）", "en": "Display resumed (paused data went to the log)"},
    "rx.filter.all": {"zh": "全部", "en": "All"},
    "rx.filter.rx": {"zh": "只看接收", "en": "RX only"},
    "rx.filter.tx": {"zh": "只看发送", "en": "TX only"},
    "rx.filter.tip": {"zh": "过滤接收区显示：全部 / 只看接收 / 只看发送", "en": "Filter the receive pane: all / RX only / TX only"},
    # ---- U180 send auto-increment ----
    "inc.chip": {"zh": "递增", "en": "Increment"},
    "inc.chip.on": {"zh": "递增 ✓", "en": "Increment ✓"},
    "inc.chip.tip": {"zh": "发送自动递增：在发送内容里写 {i} 占位，例如 HEX 的 AA 55 {i:2} 0D 0A；每发一帧自动加一个步长",
                     "en": "Send auto-increment: put an {i} placeholder in the text, e.g. HEX AA 55 {i:2} 0D 0A; it advances one step per send"},
    "inc.enable": {"zh": "启用递增", "en": "Enable"},
    "inc.start": {"zh": "起始值", "en": "Start"},
    "inc.start.tip": {"zh": "打开/修改设置时计数器回到这个值", "en": "The counter returns to this value on enable / settings change"},
    "inc.step": {"zh": "步长", "en": "Step"},
    "inc.step.tip": {"zh": "每次发送后加多少；负数即递减", "en": "Added after each send; negative decrements"},
    "inc.width": {"zh": "位宽", "en": "Width"},
    "inc.width.tip": {"zh": "HEX=字节数；ASCII=补零位数", "en": "HEX: bytes; ASCII: zero-padded digits"},
    "inc.endian": {"zh": "字节序", "en": "Endian"},
    "inc.big": {"zh": "大端", "en": "Big"},
    "inc.little": {"zh": "小端", "en": "Little"},
    "inc.endian.tip": {"zh": "仅 HEX 且位宽>1 时生效", "en": "Only for HEX with width > 1"},
    "inc.base": {"zh": "进制", "en": "Base"},
    "inc.dec": {"zh": "十进制", "en": "Decimal"},
    "inc.hex": {"zh": "十六进制", "en": "Hex"},
    "inc.base.tip": {"zh": "仅 ASCII 模式显示用", "en": "ASCII mode only"},
    "inc.wrap": {"zh": "到上限回绕", "en": "Wrap at the limit"},
    "inc.wrap.tip": {"zh": "勾选：超过范围回到起始值；不勾：到上限就停止发送",
                     "en": "On: wrap back to the start; off: stop sending when the range is exhausted"},
    "inc.reset": {"zh": "重置", "en": "Reset"},
    "inc.reset.tip": {"zh": "把计数器重置为起始值", "en": "Put the counter back to the start value"},
    "inc.reset.done": {"zh": "递增计数已重置", "en": "Increment counter reset"},
    "inc.no_token": {"zh": "已启用递增，但发送内容里没有 {i} 占位符", "en": "Increment is on, but the text has no {i} placeholder"},
    "inc.done": {"zh": "递增已到上限，已停止发送", "en": "Increment reached its limit; sending stopped"},
    "menu.copy_sel_clean": {"zh": "复制选中（不含时间戳/标记）", "en": "Copy selection (no timestamps/markers)"},
    "menu.copy_line": {"zh": "复制当前行", "en": "Copy current line"},
    "menu.copy_all_clean": {"zh": "复制全部（不含时间戳/标记）", "en": "Copy all (no timestamps/markers)"},
    "menu.copy_raw": {"zh": "复制原文（含时间戳/标记）", "en": "Copy raw (with timestamps/markers)"},
    "rx.copied_clean": {"zh": "已复制（不含时间戳/标记）", "en": "Copied (timestamps/markers stripped)"},
    "rx.copied_line": {"zh": "已复制当前行", "en": "Copied the current line"},
    "rx.copied_all": {"zh": "已复制接收区全部内容", "en": "Copied the whole receive pane"},
    "find.count.tip": {"zh": "当前命中 / 总数", "en": "current hit / total"},

    "rx.cleared": {"zh": "已清空接收区（5 秒内可撤销）", "en": "Receive pane cleared (undo within 5 s)"},
    "rx.undo.done": {"zh": "已恢复清空前的显示", "en": "Display restored"},
    "undo.label": {"zh": "撤销", "en": "Undo"},
    "find.label": {"zh": "高亮", "en": "Highlight"},
    "find.placeholder": {"zh": "输入关键词，接收区自动高亮（回车 / 上一下一个跳转）", "en": "Type a keyword to highlight matches (Enter / prev-next to jump)"},
    "find.case": {"zh": "区分大小写", "en": "Case"},
    "find.case.tip": {"zh": "搜索时区分大小写（默认不区分）", "en": "Match case when searching (off by default)"},
    "find.prev": {"zh": "上一个", "en": "Previous"},
    "find.next": {"zh": "下一个", "en": "Next"},
    "find.close.tip": {"zh": "关闭查找（Esc）", "en": "Close the find bar (Esc)"},
    "find.none": {"zh": "未找到: {text}", "en": "Not found: {text}"},
    "sc.send.tip": {"zh": "发送（Ctrl+Enter）", "en": "Send (Ctrl+Enter)"},
    "sc.clear.tip": {"zh": "清空显示与计数（Ctrl+L，5 秒内可撤销）", "en": "Clear the display and the counters (Ctrl+L, undoable within 5 s)"},
    "sc.save.tip": {"zh": "保存接收日志（Ctrl+S）", "en": "Save receive log (Ctrl+S)"},
    "sc.open.tip": {"zh": "打开/关闭串口（F5）", "en": "Open/close the port (F5)"},
    "rx.cap": {
        "zh": "接收区已达显示上限（{n} 行），更早的数据不再显示；自动保存的日志文件不受影响",
        "en": "The receive pane hit its display limit ({n} lines); older data is no longer shown. Auto-saved logs are unaffected",
    },
    "menu.settings": {"zh": "设置(&S)", "en": "&Settings"},
    "menu.settings.tip": {"zh": "设置 (Ctrl+,)", "en": "Settings (Ctrl+,)"},
    "menu.sec.appearance": {"zh": "外观与语言", "en": "Appearance & language"},
    "menu.sec.io": {"zh": "日志与自动应答", "en": "Logging & auto-reply"},
    "menu.sec.config": {"zh": "配置", "en": "Configuration"},
    "menu.sec.danger": {"zh": "危险操作", "en": "Destructive"},
    "theme.menu": {"zh": "主题(&T)", "en": "&Theme"},
    "menu.language": {"zh": "语言(&L)", "en": "&Language"},
    "theme.system": {"zh": "跟随系统(&Y)", "en": "Follow s&ystem"},
    "theme.dark": {"zh": "深色(&D)", "en": "&Dark"},
    "theme.light": {"zh": "浅色(&L)", "en": "&Light"},
    "lang.system": {"zh": "跟随系统", "en": "Follow system"},
    "lang.zh": {"zh": "中文", "en": "中文"},
    "lang.en": {"zh": "English", "en": "English"},
    # ---- connection bar ----
    "port.label": {"zh": "端口:", "en": "Port:"},
    "baud.label": {"zh": "波特率:", "en": "Baud:"},
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
    "split.fixed": {"zh": "定长", "en": "Fixed length"},
    "split.delimited": {"zh": "起止定界", "en": "Start/end delimiter"},
    "split.tlv": {"zh": "长度前缀", "en": "Length-prefixed"},
    "split.fixed.tip": {"zh": "按固定字节数切帧（1~65535）", "en": "Cut a frame every N bytes (1-65535)"},
    "split.delim.start": {"zh": "起始，如 AA 55", "en": "Start, e.g. AA 55"},
    "split.delim.end": {"zh": "结束，如 0D 0A（可空）", "en": "End, e.g. 0D 0A (optional)"},
    "split.delim.tip": {"zh": "按 HEX 起止定界切帧；结束留空则按“起点到下一个起点”切", "en": "Cut frames between HEX start/end bytes; leave end empty to cut start-to-start"},
    "split.tlv.tip": {"zh": "长度前缀字节数（1~4），小端可选", "en": "Length-prefix size (1-4); optional little-endian"},
    "split.tlv.le": {"zh": "小端", "en": "LE"},
    "split.tlv.le.tip": {"zh": "长度字段按小端读取（默认大端）", "en": "Read the length field little-endian (default big-endian)"},
    "split.tlv.crc": {"zh": "CRC", "en": "CRC"},
    "split.tlv.crc.tip": {"zh": "帧尾带 CRC-16/Modbus 校验；校验失败的帧丢弃并重新同步", "en": "Frame ends with a CRC-16/Modbus check; a bad frame is dropped and the stream resynchronises"},
    "qs.example.tip": {"zh": "首次运行示例：可直接发送，或改成你的指令；不需要就清空", "en": "Seeded example: send it as-is, edit it, or clear the row"},
    "btn.more": {"zh": "更多", "en": "More"},
    "btn.more.tip": {"zh": "暂停显示 / 自动换行 / 日志另存为…", "en": "Pause / Wrap / Save log as…"},
    "split.tip": {
        "zh": "分包分行方式\n自动：按波特率 3.5 字符时间\n手动：指定毫秒间隔\n按帧头：识别帧头字符串分行",
        "en": "How frames are split\nAuto: 3.5-char time by baud rate\nManual: fixed millisecond gap\nBy header: split on the header string",
    },
    "split.ms.tip": {"zh": "手动分包间隔（毫秒，0~60000，默认 10）", "en": "Manual split gap in ms (0-60000, default 10)"},
    "header.placeholder.hex": {"zh": "帧头示例：AA 55 或 0xAA,0x55", "en": "e.g. AA 55 or 0xAA,0x55"},
    "header.placeholder.ascii": {"zh": "帧头示例：$GPGGA", "en": "e.g. $GPGGA"},
    "header.tip": {
        "zh": "按帧头分包的帧头字符串：收到这一段字节就开新行\n支持空格分隔、0x 前缀、逗号或短横线分隔\n填写后自动切换为按帧头模式",
        "en": "Frame header for header-based splitting: each time these bytes arrive a new line starts\nSpace separated, 0x prefixes, commas and dashes all work\nTyping one switches to header mode automatically",
    },
    "ts.label": {"zh": "时间戳", "en": "Timestamp"},
    "ts.tip": {
        "zh": "勾选后在接收区每行行首加时间戳，格式固定为 [04:02:10.456]",
        "en": "Tick to prefix every receive line with a timestamp, always shaped like [04:02:10.456]",
    },
    "btn.clear": {"zh": "清空", "en": "Clear"},
    # ---- receive log to file (T4) ----
    "btn.save_log_quick": {"zh": "保存日志", "en": "Save log"},
    "btn.save_log_as": {"zh": "日志另存为…", "en": "Save log as…"},
    "log.quick.tip": {
        "zh": "一键把接收区内容保存到 logs/ 目录（文件名带时间戳），状态栏会给出完整路径",
        "en": "Save the receive pane into logs/ in one click (timestamped file name); the exact path is shown in the status bar",
    },
    "as.title": {"zh": "日志保存设置", "en": "Log saving settings"},
    "as.menu": {"zh": "日志保存设置(&L)…", "en": "&Log saving settings…"},
    "as.group.target": {"zh": "保存位置", "en": "Save location"},
    "as.group.auto": {"zh": "自动保存", "en": "Auto-save"},
    "as.enable": {"zh": "启用自动保存（打开串口后持续写入）", "en": "Enable auto-save (writes while the port is open)"},
    "as.max_mb": {"zh": "单个文件上限 (MB)", "en": "Max size per file (MB)"},
    "as.max_minutes": {"zh": "最长时间 (分钟)", "en": "Max duration (minutes)"},
    "as.quota_mb": {"zh": "日志目录总量上限 (MB，0=不限)", "en": "Log folder quota (MB, 0 = unlimited)"},
    "as.dir": {"zh": "保存目录", "en": "Folder"},
    "as.dir.pick": {"zh": "选择日志保存目录", "en": "Choose the log folder"},
    "as.browse": {"zh": "浏览…", "en": "Browse…"},
    "as.note": {
        "zh": "「保存位置」是日志目录：接收区的「保存日志」、\u300c另存为\u2026\u300d的起始位置和自动保存共用这一个目录，只需记一处。自动保存会把接收到的每一行（含发送回显）实时写入该目录，超过上面的体积或时长就自动换一个新文件，文件名形如 serial_20261001_0200.txt；手动「保存日志」写的是快照，文件名形如 serial_RX_20261001_0200.txt。",
        "en": "Save location is the log folder: the receive pane\u2019s Save log button, the starting folder of Save as\u2026 and auto-save all share it, so there is only one place to remember. Auto-save writes every received line (including TX echo) there and starts a new file once the size or duration above is reached, named like serial_20261001_0200.txt; the manual Save log writes a snapshot named like serial_RX_20261001_0200.txt.",
    },
    "log.autosave.on": {"zh": "自动保存到 {path}", "en": "Auto-saving to {path}"},
    "log.header": {"zh": "# {app} {version} 日志 · {port} @ {baud} · {fmt} 发送 / {rx} 接收 · 开始于 {when}", "en": "# {app} {version} log - {port} @ {baud} - send {fmt} / receive {rx} - started {when}"},
    "log.save.title": {"zh": "保存接收日志", "en": "Save the receive log"},
    "log.save_fail": {"zh": "保存日志失败: {e}", "en": "Could not save the log: {e}"},
    "log.saved": {"zh": "日志已保存到 {path}", "en": "Log saved to {path}"},
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
    "tx.placeholder.hex": {
        "zh": "例如：01 03 00 00（HEX 按字节原样发送，需要行尾请写 0D 0A）",
        "en": "e.g. 01 03 00 00 (HEX sends bytes exactly - add 0D 0A yourself if you need an ending)",
    },
    "tx.placeholder.ascii": {"zh": "例如：AT+VERSION?", "en": "e.g. AT+VERSION?"},
    "tx.input.tip.ascii": {
        "zh": "字符串模式：按文本发送（勾选「解析转义符」后 \\r\\n 等转义生效）",
        "en": "Text mode: sent as characters (\\r\\n escapes apply when the escape option is on)",
    },
    "tx.placeholder": {
        "zh": "在此输入要发送的内容；HEX 模式如 01 03 00 00（支持 0x 前缀与逗号）",
        "en": "Type what to send; in HEX mode e.g. 01 03 00 00 (0x prefixes and commas are fine)",
    },
    "tx.counter": {"zh": "TX {n} 次 · {tx} B　｜　RX {rx} B", "en": "TX {n} · {tx} B | RX {rx} B"},
    "rx.empty.hint": {"zh": "打开串口后，接收到的数据会显示在这里", "en": "Data received after opening a port shows up here"},
    "update.menu": {"zh": "有新版本 {v} 可用…", "en": "Version {v} is available…"},
    "update.available": {"zh": "发现新版本 {v}，设置菜单里可打开下载页", "en": "Version {v} is out - the settings menu links to the download page"},
    "update.check": {"zh": "启动时检查更新", "en": "Check for updates at startup"},
    "update.check.tip": {"zh": "启动时静默查询 GitHub 上的最新版本，只在新版本存在时提示；不发送任何本机信息", "en": "Quietly asks GitHub for the latest version at startup, only mentions it when there is a newer one; nothing about this machine is sent"},
    "update.check.now": {"zh": "立即检查更新…", "en": "Check for updates now…"},
    "update.checking": {"zh": "正在检查更新…", "en": "Checking for updates…"},
    "update.none": {"zh": "已是最新版本", "en": "You are up to date"},
    "update.fail": {"zh": "检查更新失败（网络或服务不可用）", "en": "Update check failed (network or service unavailable)"},
    "menu.open_log_dir": {"zh": "打开日志目录", "en": "Open logs folder"},
    "about.copy": {"zh": "复制诊断信息", "en": "Copy diagnostics"},
    "about.copied": {"zh": "诊断信息已复制到剪贴板", "en": "Diagnostics copied to the clipboard"},
    "menu.shortcuts": {"zh": "快捷键一览…", "en": "Keyboard shortcuts…"},
    "sc.send": {"zh": "发送当前内容", "en": "Send the current input"},
    "sc.clear_rx": {"zh": "清空接收区（可撤销）", "en": "Clear the receive pane (undoable)"},
    "sc.save_log": {"zh": "一键保存日志", "en": "Save the log to the log folder"},
    "sc.focus_input": {"zh": "跳到发送输入框", "en": "Jump to the send input"},
    "sc.toggle_open": {"zh": "打开 / 关闭串口", "en": "Open or close the port"},
    "sc.panel": {"zh": "显示 / 隐藏快速发送面板", "en": "Show or hide the quick-send panel"},
    "sc.hist_prev": {"zh": "上一条发送历史", "en": "Previous send-history entry"},
    "sc.hist_next": {"zh": "下一条发送历史", "en": "Next send-history entry"},
    "sc.find": {"zh": "在接收区查找", "en": "Find in the receive pane"},
    "sc.settings": {"zh": "打开设置菜单", "en": "Open the settings menu"},
    "sc.esc": {"zh": "取消选中 / 关闭查找条", "en": "Clear the selection / close the find bar"},
    "sc.scope.quick_panel": {"zh": "（焦点在快速发送面板时生效）", "en": " (active while the quick-send panel has focus)"},
    "sc.del_quick_row": {"zh": "删除选中的快速发送条目", "en": "Delete the selected quick-send rows"},
    "tx.payload": {"zh": "将发送 {n} 字节", "en": "payload: {n} B"},
    "tx.payload.bad": {"zh": "内容格式有误", "en": "invalid input"},
    "tx.payload.tip": {
        "zh": "按当前格式、校验与换行设置计算的实际发送字节数",
        "en": "Actual bytes sent, with the current format, checksum and CRLF settings applied",
    },
    "tx.escape": {"zh": "解析转义符", "en": "Escapes"},
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
    "tx.newline.label": {"zh": "换行:", "en": "Line ending:"},
    "tx.nl.none": {"zh": "无", "en": "None"},
    "tx.nl.cr": {"zh": "回车 CR", "en": "CR"},
    "tx.nl.lf": {"zh": "换行 LF", "en": "LF"},
    "tx.nl.crlf": {"zh": "回车+换行 CR LF", "en": "CR LF"},
    "tx.newline.hex.tip": {
        "zh": "HEX 模式按字节原样发送，不追加行尾；需要行尾请在内容末尾写 0D 0A，或切到 ASCII 模式用这个选择器",
        "en": "HEX sends bytes exactly and appends nothing; write 0D 0A yourself, or switch to ASCII to use this picker",
    },
    "tx.escape.hex.tip": {
        "zh": "转义符只在 ASCII 模式下解析；HEX 直接输入字节（如 0D 0A）即可",
        "en": "Escapes apply to ASCII text only; in HEX just type the bytes (e.g. 0D 0A)",
    },
    "tx.newline.tip": {
        "zh": "ASCII 模式下发完内容后追加的字节：无 / 回车 0D / 换行 0A / 回车+换行 0D 0A（AT 指令常用）",
        "en": "Bytes appended after the payload in ASCII mode: none / CR 0D / LF 0A / CR+LF 0D 0A (the usual choice for AT commands)",
    },
    # ---- repeat send (T2) / send history (T5) ----
    "tx.content.label": {"zh": "发送内容区（文本输入区）", "en": "Send content (text input)"},
    "tx.interval.label": {"zh": "间隔(ms)", "en": "Interval (ms)"},
    "split.auto.hint": {
        "zh": "按波特率自动",
        "en": "Auto by baud",
    },
    "split.off.hint": {"zh": "不分包", "en": "No split"},
    "tx.repeat": {"zh": "循环发送", "en": "Repeat send"},
    "tx.repeat.tip": {"zh": "按设定间隔重复发送当前内容；点一下开始，运行中按钮变为「停止循环」，再点一下停止",
                      "en": "Repeat the current input at the set interval; click once to start - the button then reads Stop repeat, click again to stop"},
    "tx.repeat.stop": {"zh": "停止循环", "en": "Stop repeat"},
    "tx.repeat.count": {"zh": "次数", "en": "Count"},
    "tx.repeat.count.tip": {"zh": "循环发送的次数；0 = 不限次数（显示 ∞，手动停止）",
                           "en": "How many times to repeat; 0 = unlimited (shows ∞, stop by hand)"},
    "tx.repeat.done": {"zh": "循环发送完成（{n} 次）", "en": "Repeat finished ({n} times)"},
    "tx.interval.tip": {"zh": "重复间隔（毫秒，范围 10~60000，默认 1000）", "en": "Repeat interval (ms, 10-60000, default 1000)"},
    "tx.sent_count": {"zh": "已发送 {n} 次", "en": "sent \u00d7{n}"},
    "tx.history.btn": {"zh": "历史 ({n})", "en": "History ({n})"},
    "tx.history.btn.tip": {"zh": "发送历史（{n} 条）：点击弹出列表，双击回填；输入框内 Ctrl+↑/Ctrl+↓ 也可回填",
                          "en": "Send history ({n}): click for the list, double-click to recall; Ctrl+Up / Ctrl+Down works in the input box too"},
    "tx.history.title": {"zh": "发送历史", "en": "Send history"},
    "tx.history.hint": {"zh": "双击或回车回填 · Delete 删除此条 · Esc 关闭",
                        "en": "Double-click or Enter to recall \u00b7 Delete removes the entry \u00b7 Esc closes"},
    "tx.history.fill": {"zh": "回填", "en": "Use"},
    "tx.history.empty": {"zh": "还没有发送记录", "en": "Nothing sent yet"},
    "tx.history.close": {"zh": "关闭", "en": "Close"},
    "tx.history.delete": {"zh": "删除此条", "en": "Delete this entry"},
    "tx.history.delete.n": {"zh": "删除选中 ({n})", "en": "Delete selected ({n})"},
    "tx.history.clear": {"zh": "清空发送历史", "en": "Clear the history"},
    "tx.history.clear.arm": {"zh": "确认清空？", "en": "Confirm clear?"},
    "tx.history.clear.tip": {"zh": "再次点击确认；会清空全部发送历史（不可撤销）",
                             "en": "Click twice to confirm; removes every remembered command (cannot be undone)"},
    "tx.history.count": {"zh": "共 {n} 条 · 最新在上", "en": "newest first \u00b7 {n} total"},
    "tx.history.count.filtered": {"zh": "匹配 {m} / 共 {n} 条", "en": "matching {m} \u00b7 {n} total"},
    "tx.history.filter.ph": {"zh": "筛选指令…", "en": "Filter commands…"},
    "tx.history.empty.filtered": {"zh": "没有匹配的记录", "en": "No matching entries"},
    "tx.history.ago.now": {"zh": "刚刚", "en": "just now"},
    "tx.history.ago.min": {"zh": "{n} 分钟前", "en": "{n} min ago"},
    "tx.history.ago.hour": {"zh": "{n} 小时前", "en": "{n} h ago"},
    "tx.history.ago.day": {"zh": "{n} 天前", "en": "{n} d ago"},
    "tx.history.removed": {"zh": "已删除历史：{text}", "en": "Removed from history: {text}"},
    "tx.history.removed.n": {"zh": "已删除 {n} 条发送历史", "en": "Removed {n} history entries"},
    "tx.history.cleared": {"zh": "已清空发送历史", "en": "Send history cleared"},
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
    "rb.rules.menu": {"zh": "自动应答规则…", "en": "Auto-reply rules…"},
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
        "en": "Send queue full ({n} pending) - slow down or check whether the device stopped receiving",
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
    "qs.seq.sent": {"zh": "已发 {n} 次", "en": "Sent {n}x"},
    "qs.seq.sent.tip": {"zh": "本序列已完成的发送轮数", "en": "Sequence rounds completed so far"},
    "menu.quick_panel": {"zh": "显示快速发送面板", "en": "Show the quick-send panel"},
    "menu.quick_panel.tip": {"zh": "显示/隐藏快速发送面板 (Ctrl+B)", "en": "Show or hide the quick-send panel (Ctrl+B)"},
    "qs.collapsed": {
        "zh": "已折叠快速发送面板，显示区已加宽（Ctrl+B 或「设置」菜单可恢复）",
        "en": "Quick-send panel collapsed - the log is wider now (Ctrl+B or the Settings menu restores it)",
    },
    "qs.expanded": {"zh": "已展开快速发送面板", "en": "Quick-send panel expanded"},
    "qs.title": {"zh": "快速发送", "en": "Quick send"},
    "qs.add": {"zh": "+ 添加指令", "en": "+ Add command"},
    "qs.add.tip": {"zh": "添加一条快速指令（最多 {n} 条）", "en": "Add a quick command (up to {n})"},
    "qs.max": {"zh": "最多支持 {n} 条指令", "en": "command limit: {n}"},
    "qs.empty_row": {"zh": "（空行）", "en": "(empty)"},
    "qs.send": {"zh": "发送", "en": "Send"},
    "qs.del": {"zh": "删除", "en": "Delete"},
"tx.settings.tip": {"zh": "发送格式与校验（点击修改）", "en": "Send format and checksum (click to change)"},
    "qs.chip.tip": {"zh": "本行的格式与延迟（点击修改）", "en": "This row's format and delay (click to change)"},
    "qs.del.tip": {
        "zh": "删除选中的命令行（勾选左侧方框或单击行选中，也可以按 Delete 键）；删除后 3 秒内可撤销",
        "en": "Delete the selected commands (tick the box on the left or click the row, or press Delete); undo is available for 3 seconds",
    },
    "qs.row.tip": {"zh": "单击选中这一行（或勾选左侧方框），再用「删除」删除", "en": "Click to select this row (or tick the box), then press Delete"},
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
    "qs.name.ph": {"zh": "名称（可选）", "en": "Name (optional)"},
    "qs.name.tip": {"zh": "给这条命令起个名字（例如“查询IMEI”）；留空则只显示命令内容",
                     "en": "A display name for this command (e.g. 'Query IMEI'); empty shows the command only"},
    "qs.note.title": {"zh": "命令备注", "en": "Command note"},
    "qs.note.label": {"zh": "备注（悬停该行可看）", "en": "Note (shown when hovering the row)"},
    "qs.seq": {"zh": "序列模式", "en": "Sequence mode"},
    "qs.seq.tip": {
        "zh": "按顺序发送：每条指令可单独设延迟（毫秒），点「运行」依次自动发出",
        "en": "Send rows in order: each row has its own delay (ms); press Run to fire them automatically",
    },
    "qs.run": {"zh": "运行", "en": "Run"},
    "qs.stop": {"zh": "停止", "en": "Stop"},
    "qs.delay.tip": {"zh": "本条发送后等待的毫秒数（0~60000，默认 500）", "en": "Delay after this row, in ms (0-60000, default 500)"},
    "qs.delay.unit": {"zh": "ms", "en": "ms"},
    "qs.rail.tip": {"zh": "展开快速发送面板（Ctrl+B）", "en": "Show the quick-send panel (Ctrl+B)"},
    "qs.seq.progress": {"zh": "序列 {i}/{n}", "en": "Step {i}/{n}"},
    "qs.seq.done": {"zh": "序列发送完成", "en": "Sequence finished"},
    "qs.seq.done.n": {"zh": "序列发送完成（{n} 轮）", "en": "Sequence finished ({n} rounds)"},
    "qs.loops": {"zh": "循环", "en": "Loops"},
    "qs.loops.tip": {"zh": "序列整体重复几轮；0 = 不限轮数（显示 ∞，手动停止）",
                     "en": "How many rounds to repeat the whole sequence; 0 = unlimited (shows ∞)"},
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
    except (RuntimeError, AttributeError):   # no Qt platform at all (headless CI or a
        # broken locale): Chinese as the safe default rather than a crash
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


def hex_error_message(exc: HexFormatError) -> str:
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
