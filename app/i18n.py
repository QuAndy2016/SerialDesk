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
    "menu.view": {"zh": "视图", "en": "View"},
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
    "btn.send": {"zh": "发送", "en": "Send"},
    # ---- status bar / log ----
    "status.disconnected": {"zh": "● 未连接", "en": "● Disconnected"},
    "status.connected": {"zh": "● 已连接 {port} @ {baud}", "en": "● Connected {port} @ {baud}"},
    "status.idle": {"zh": "未打开串口", "en": "Port not open"},
    "status.no_port": {"zh": "未发现串口", "en": "No serial port found"},
    "status.bad_baud": {"zh": "波特率格式错误", "en": "Invalid baud rate"},
    "status.opened": {"zh": "串口已打开", "en": "Port opened"},
    "status.closed": {"zh": "串口已关闭", "en": "Port closed"},
    "log.send_error": {"zh": "发送内容错误: {e}", "en": "Send error: {e}"},
    # ---- quick send panel ----
    "qs.title": {"zh": "快速发送", "en": "Quick send"},
    "qs.add": {"zh": "+ 添加指令", "en": "+ Add command"},
    "qs.add.tip": {"zh": "添加一条快速指令（最多 {n} 条）", "en": "Add a quick command (up to {n})"},
    "qs.max": {"zh": "最多支持 {n} 条指令", "en": "Up to {n} commands supported"},
    "qs.placeholder": {"zh": "指令内容", "en": "Command"},
    "qs.send": {"zh": "发送", "en": "Send"},
    "qs.delete.tip": {"zh": "删除此条", "en": "Delete this row"},
    "qs.empty": {"zh": "指令内容为空", "en": "Command is empty"},
    "qs.bad_fmt": {"zh": "指令格式错误: {e}", "en": "Invalid command format: {e}"},
    "qs.save_fail": {"zh": "保存配置失败: {e}", "en": "Failed to save config: {e}"},
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
