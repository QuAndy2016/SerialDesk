"""Built-in declarative templates: Modbus RTU, AT, NMEA 0183.

Sources checked 2026-10-03 (per the project rule: find the existing, authoritative
definition before writing one):

- Modbus: MODBUS Application Protocol Specification V1.1b3 (modbus.org) - FC 0x03/0x04
  read holding/input registers, 0x06 write single register, 0x10 write multiple registers.
  The CRC-16 (Modbus) sits in the last two bytes, low byte first and covers everything
  before it; the standard check value for "123456789" is 0x4B37, which the app's existing
  app/protocol.crc16_modbus already reproduces.
- NMEA 0183: sentences start with '$', end with <CR><LF>; fields are comma separated and
  the checksum is the XOR of the characters between '$' and '*', written as two hex digits.
- AT: command lines begin with "AT" and are terminated by <CR> (ITU-T V.250 / 3GPP
  TS 27.007); a device answers with <CR><LF>-terminated lines.

These are *templates*: they describe the common shape of each protocol, and the caller can
copy one and adjust fields for a specific device.
"""

from __future__ import annotations

from app.parserspec import BitField, ChecksumSpec, FieldSpec, FrameSpec
from app.parsers import ERR_UNKNOWN_FUNCTION, parse_frame

MODBUS_READ_FUNCTIONS = (0x03, 0x04)     # read holding / input registers
MODBUS_WRITE_SINGLE = 0x06
MODBUS_WRITE_MULTIPLE = 0x10             # a.k.a. 16
MODBUS_FUNCTIONS = MODBUS_READ_FUNCTIONS + (MODBUS_WRITE_SINGLE, MODBUS_WRITE_MULTIPLE)

_MODBUS_CRC = ChecksumSpec(kind="crc16-modbus", cover_start=0, cover_end=None,
                           size=2, endian="le")


def modbus_rtu_request(function_code: int) -> FrameSpec:
    """Request frame of a Modbus RTU master for the supported function codes."""
    if function_code in MODBUS_READ_FUNCTIONS:
        return FrameSpec(
            name="modbus-rtu-req-%02X" % function_code,
            endian="be",
            length_mode="fixed", frame_size=8, min_frame_size=8,
            checksum=_MODBUS_CRC,
            fields=(FieldSpec("slave", "u8"), FieldSpec("function", "u8"),
                    FieldSpec("start", "u16"), FieldSpec("quantity", "u16")),
        )
    if function_code == MODBUS_WRITE_SINGLE:
        return FrameSpec(
            name="modbus-rtu-req-06", endian="be",
            length_mode="fixed", frame_size=8, min_frame_size=8,
            checksum=_MODBUS_CRC,
            fields=(FieldSpec("slave", "u8"), FieldSpec("function", "u8"),
                    FieldSpec("register", "u16"), FieldSpec("value", "u16")),
        )
    if function_code == MODBUS_WRITE_MULTIPLE:
        # 1+1+2+2+1 header, then `byte_count` data bytes, then 2 CRC bytes.
        return FrameSpec(
            name="modbus-rtu-req-10", endian="be",
            length_mode="field", length_offset=6, length_width=1, length_endian="be",
            length_adjust=9, min_frame_size=11,
            checksum=_MODBUS_CRC,
            fields=(FieldSpec("slave", "u8"), FieldSpec("function", "u8"),
                    FieldSpec("start", "u16"), FieldSpec("quantity", "u16"),
                    FieldSpec("byte_count", "u8"),
                    FieldSpec("data", "bytes", length_field="byte_count")),
        )
    raise ValueError("unsupported Modbus RTU function code 0x%02X" % function_code)


def modbus_rtu_response(function_code: int) -> FrameSpec:
    """Response frame a Modbus RTU slave sends for the supported function codes."""
    if function_code in MODBUS_READ_FUNCTIONS:
        # 1+1+1 header, then `byte_count` data bytes, then 2 CRC bytes.
        return FrameSpec(
            name="modbus-rtu-rsp-%02X" % function_code, endian="be",
            length_mode="field", length_offset=2, length_width=1, length_endian="be",
            length_adjust=5, min_frame_size=5,
            checksum=_MODBUS_CRC,
            fields=(FieldSpec("slave", "u8"), FieldSpec("function", "u8"),
                    FieldSpec("byte_count", "u8"),
                    FieldSpec("data", "bytes", length_field="byte_count")),
        )
    if function_code in (MODBUS_WRITE_SINGLE, MODBUS_WRITE_MULTIPLE):
        return FrameSpec(
            name="modbus-rtu-rsp-%02X" % function_code, endian="be",
            length_mode="fixed", frame_size=8, min_frame_size=8,
            checksum=_MODBUS_CRC,
            fields=(FieldSpec("slave", "u8"), FieldSpec("function", "u8"),
                    FieldSpec("register", "u16") if function_code == MODBUS_WRITE_SINGLE
                    else FieldSpec("start", "u16"),
                    FieldSpec("value", "u16") if function_code == MODBUS_WRITE_SINGLE
                    else FieldSpec("quantity", "u16")),
        )
    raise ValueError("unsupported Modbus RTU function code 0x%02X" % function_code)


def at_line(separator: str = " ") -> FrameSpec:
    """AT command/response line: `command` plus the rest of the line as `args`.

    Devices answer with <CR><LF>-terminated lines ("+CSQ: 20,99"), so both are accepted.
    """
    return FrameSpec(
        name="at-line", length_mode="delimiter", delimiter=b"\r\n",
        min_frame_size=1, checksum=ChecksumSpec(kind="none"),
        text_separator=separator, separator_strip="\r\n",
        fields=(FieldSpec("command", "ascii", text=True),
                FieldSpec("args", "ascii", text=True, optional=True, join_rest=True)),
    )


def nmea_0183(max_fields: int = 14) -> FrameSpec:
    """NMEA 0183 sentence: `$type,f1,f2,...*HH` with XOR written as two hex digits.

    `max_fields` follows the longest common sentence (GGA has 14); extra fields are
    optional, so shorter sentences (RMC and friends) parse without errors.
    """
    fields = [FieldSpec("type", "ascii", text=True)]
    fields += [FieldSpec("f%d" % i, "ascii", text=True, optional=True)
               for i in range(1, max_fields + 1)]
    return FrameSpec(
        name="nmea-0183", header=b"$", length_mode="delimiter", delimiter=b"\r\n",
        min_frame_size=1,
        checksum=ChecksumSpec(kind="xor8", as_text=True, size=1,
                              cover_start=0, cover_end=None),
        text_separator=",", separator_strip="\r\n",
        fields=tuple(fields),
    )


def bit_field_example() -> FrameSpec:
    """Status-byte template: one byte carrying four named flags (bits field demo)."""
    return FrameSpec(
        name="status-bits", endian="be", length_mode="fixed", frame_size=3,
        min_frame_size=3, checksum=ChecksumSpec(kind="none"),
        fields=(FieldSpec("status", "bits", byte_offset=0, bits=(
            BitField("run", 0), BitField("fault", 1), BitField("ready", 2),
            BitField("mode", 3, 2))),
            FieldSpec("counter", "u16", byte_offset=1)),
    )


def template_names() -> list[str]:
    """Names of the templates shipped with P1 (for a picker in )."""
    return ["modbus-rtu", "at", "nmea-0183", "status-bits"]


def modbus_shape(frame: bytes) -> str:
    """Guess request vs response from the function code and the frame length.

    This is what a sniffer can know: FC 0x03/0x04 requests are 8 bytes while responses
    carry a byte count, 0x06 uses the same 8 bytes in both directions, and 0x10 differs
    between the two. Anything else is "unknown" here (the caller may still have a spec).
    """
    if len(frame) < 4:
        return "unknown"
    fc = frame[1]
    if fc in MODBUS_READ_FUNCTIONS:
        if len(frame) == 8:
            return "request"
        if len(frame) >= 5 and frame[2] == len(frame) - 5:
            return "response"
        return "unknown"
    if fc == MODBUS_WRITE_SINGLE:
        return "request" if len(frame) == 8 else "unknown"
    if fc == MODBUS_WRITE_MULTIPLE:
        if len(frame) >= 11 and frame[6] == len(frame) - 9:
            return "request"
        if len(frame) == 8:
            return "response"
        return "unknown"
    return "unknown"


def parse_modbus_frame(frame: bytes) -> tuple[dict, dict]:
    """Parse a Modbus RTU frame, choosing the spec from the function code.

    An unsupported function code or an unrecognised length comes back as a structured
    error (code ERR_UNKNOWN_FUNCTION), never as an exception: a device on the wire may
    send anything.
    """
    shape = modbus_shape(frame)
    fc = frame[1] if len(frame) > 1 else None
    if shape == "unknown" or fc not in MODBUS_FUNCTIONS:
        detail = ("function code 0x%02X is not in the supported set %s"
                  % (fc, [hex(f) for f in MODBUS_FUNCTIONS])) if fc is not None else "frame too short"
        return {}, {"ok": False,
                    "errors": [{"code": ERR_UNKNOWN_FUNCTION, "function_code": fc,
                                "detail": detail}]}
    spec = (modbus_rtu_request if shape == "request" else modbus_rtu_response)(fc)
    return parse_frame(spec, frame)
