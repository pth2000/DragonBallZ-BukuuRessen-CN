"""Story script parser and fixed-layout translation writer."""
from __future__ import annotations

import struct
from collections.abc import Callable, Iterable
from dataclasses import dataclass

TEXT_OPS = {0x12, 0x13, 0x14, 0x17}
TEXT_START = {0x12: 6, 0x14: 6, 0x13: 14, 0x17: 14}


class ScriptError(ValueError):
    pass


@dataclass(frozen=True)
class Command:
    block_index: int
    event_id: int
    command_index: int
    offset: int
    opcode: int
    length: int


class ScriptFile:
    def __init__(self, data: bytes):
        self.data = bytearray(data)
        if len(data) < 4:
            raise ScriptError("truncated script")
        self.data_start, self.block_count = struct.unpack_from("<HH", data, 0)
        if 4 + self.block_count * 8 > len(data):
            raise ScriptError("truncated block table")
        self.entries = [struct.unpack_from("<II", data, 4 + index * 8) for index in range(self.block_count)]
        self.blocks: list[list[Command]] = []
        for block_index, (event_id, relative_offset) in enumerate(self.entries):
            start = self.data_start + relative_offset
            if block_index + 1 < self.block_count:
                end = self.data_start + self.entries[block_index + 1][1]
            else:
                end = len(data)
            if not 0 <= start <= end <= len(data):
                raise ScriptError(f"invalid block range {block_index}")
            commands: list[Command] = []
            pos = start
            command_index = 0
            while pos < end:
                if pos + 2 > end:
                    raise ScriptError(f"truncated command at {pos:#x}")
                opcode, length = data[pos], data[pos + 1]
                if length < 2 or pos + length > end:
                    raise ScriptError(
                        f"invalid command at {pos:#x}: opcode={opcode:#x}, length={length}"
                    )
                commands.append(Command(block_index, event_id, command_index, pos, opcode, length))
                pos += length
                command_index += 1
            self.blocks.append(commands)

    def command(self, block_index: int, command_index: int) -> Command:
        return self.blocks[block_index][command_index]

    def raw_text(self, command: Command) -> bytes | None:
        if command.opcode not in TEXT_OPS:
            return None
        start = command.offset + 2 + TEXT_START[command.opcode]
        end = command.offset + command.length
        return bytes(self.data[start:end]).rstrip(b"\0")

    def decode_text(self, command: Command, encoding: str = "shift_jis") -> str | None:
        raw = self.raw_text(command)
        return None if raw is None else raw.decode(encoding, errors="replace")

    def replace_text(self, command: Command, encoded: bytes) -> tuple[int, int]:
        if command.opcode not in TEXT_OPS:
            raise ScriptError(f"command {command.command_index} is not a text command")
        start = command.offset + 2 + TEXT_START[command.opcode]
        end = command.offset + command.length
        capacity = end - start
        if len(encoded) > capacity:
            raise ScriptError(
                f"text is {len(encoded)} bytes but command capacity is {capacity} bytes"
            )
        # The two bytes immediately before the text field store the active
        # text byte length.  Leaving the original Japanese length here was the
        # cause of early malformed rendering/hangs during the prototype phase.
        struct.pack_into("<H", self.data, start - 2, len(encoded))
        self.data[start:end] = encoded + b"\0" * (capacity - len(encoded))
        return len(encoded), capacity

    def build(self) -> bytes:
        return bytes(self.data)


def apply_translation_rows(
    script_data: bytes,
    rows: Iterable[dict[str, str]],
    encoder: Callable[[str], bytes],
) -> tuple[bytes, list[dict[str, object]]]:
    script = ScriptFile(script_data)
    report: list[dict[str, object]] = []
    for row in rows:
        text = row.get("简体中文", "")
        if not text:
            continue
        block_index = int(row["剧情块"])
        command_index = int(row["指令序号"])
        command = script.command(block_index, command_index)
        expected_event = int(row["事件ID"], 16)
        expected_opcode = int(row["指令"], 16)
        if command.event_id != expected_event:
            raise ScriptError(
                f'row {row.get("ID")}: event mismatch {command.event_id:08X} != {expected_event:08X}'
            )
        if command.opcode != expected_opcode:
            raise ScriptError(
                f'row {row.get("ID")}: opcode mismatch {command.opcode:02X} != {expected_opcode:02X}'
            )
        encoded = encoder(text)
        used, capacity = script.replace_text(command, encoded)
        report.append(
            {
                "ID": row.get("ID", ""),
                "script": row["脚本"],
                "block": block_index,
                "command": command_index,
                "used_bytes": used,
                "capacity_bytes": capacity,
                "remaining_bytes": capacity - used,
            }
        )
    return script.build(), report


def iter_code_units(raw: bytes) -> Iterable[int]:
    """Yield Shift-JIS-style one- or two-byte code units from a raw text field."""
    pos = 0
    while pos < len(raw):
        first = raw[pos]
        if (0x81 <= first <= 0x9F or 0xE0 <= first <= 0xFC) and pos + 1 < len(raw):
            yield (first << 8) | raw[pos + 1]
            pos += 2
        else:
            yield first
            pos += 1
