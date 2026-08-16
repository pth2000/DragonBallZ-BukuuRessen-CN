"""Minimal BPS patch reader/writer.

The writer intentionally emits only SourceRead and TargetRead actions.  It is
not the smallest possible encoding, but it is deterministic and suitable for
ROM translation builds.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass


class BPSError(ValueError):
    pass


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    shift = 1
    while True:
        if pos >= len(data):
            raise BPSError("truncated BPS varint")
        byte = data[pos]
        pos += 1
        value += (byte & 0x7F) * shift
        if byte & 0x80:
            return value, pos
        shift <<= 7
        value += shift


def _write_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("BPS varints are unsigned")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value == 0:
            out.append(byte | 0x80)
            return bytes(out)
        out.append(byte)
        value -= 1


def _decode_signed(value: int) -> int:
    magnitude = value >> 1
    return -magnitude if value & 1 else magnitude


@dataclass(frozen=True)
class BPSInfo:
    source_size: int
    target_size: int
    metadata: bytes
    source_crc32: int
    target_crc32: int
    patch_crc32: int


def inspect_patch(patch: bytes) -> BPSInfo:
    if not patch.startswith(b"BPS1"):
        raise BPSError("not a BPS patch")
    pos = 4
    source_size, pos = _read_varint(patch, pos)
    target_size, pos = _read_varint(patch, pos)
    metadata_size, pos = _read_varint(patch, pos)
    if pos + metadata_size > len(patch) - 12:
        raise BPSError("invalid BPS metadata size")
    metadata = patch[pos : pos + metadata_size]
    source_crc, target_crc, patch_crc = struct.unpack_from("<III", patch, len(patch) - 12)
    return BPSInfo(source_size, target_size, metadata, source_crc, target_crc, patch_crc)


def apply_patch(source: bytes, patch: bytes, *, verify_crc: bool = True) -> bytes:
    info = inspect_patch(patch)
    if len(source) != info.source_size:
        raise BPSError(f"source size mismatch: expected {info.source_size}, got {len(source)}")
    if verify_crc and (zlib.crc32(source) & 0xFFFFFFFF) != info.source_crc32:
        raise BPSError("source CRC32 mismatch")
    if verify_crc and (zlib.crc32(patch[:-4]) & 0xFFFFFFFF) != info.patch_crc32:
        raise BPSError("patch CRC32 mismatch")

    pos = 4
    _, pos = _read_varint(patch, pos)
    _, pos = _read_varint(patch, pos)
    metadata_size, pos = _read_varint(patch, pos)
    pos += metadata_size

    target = bytearray()
    source_relative = 0
    target_relative = 0
    while len(target) < info.target_size:
        action_word, pos = _read_varint(patch, pos)
        action = action_word & 3
        length = (action_word >> 2) + 1
        if action == 0:  # SourceRead
            start = len(target)
            target += source[start : start + length]
        elif action == 1:  # TargetRead
            if pos + length > len(patch) - 12:
                raise BPSError("truncated TargetRead data")
            target += patch[pos : pos + length]
            pos += length
        elif action == 2:  # SourceCopy
            delta, pos = _read_varint(patch, pos)
            source_relative += _decode_signed(delta)
            if source_relative < 0 or source_relative + length > len(source):
                raise BPSError("invalid SourceCopy range")
            target += source[source_relative : source_relative + length]
            source_relative += length
        else:  # TargetCopy
            delta, pos = _read_varint(patch, pos)
            target_relative += _decode_signed(delta)
            if target_relative < 0 or target_relative >= len(target):
                raise BPSError("invalid TargetCopy range")
            for _ in range(length):
                if target_relative >= len(target):
                    raise BPSError("TargetCopy reads beyond generated data")
                target.append(target[target_relative])
                target_relative += 1

    if len(target) != info.target_size:
        raise BPSError("target size mismatch after patching")
    result = bytes(target)
    if verify_crc and (zlib.crc32(result) & 0xFFFFFFFF) != info.target_crc32:
        raise BPSError("target CRC32 mismatch")
    return result


def create_patch(source: bytes, target: bytes, metadata: bytes = b"") -> bytes:
    """Create a deterministic BPS patch.

    Equal bytes at equal offsets use SourceRead.  All other runs use
    TargetRead.  This is simple, robust, and adequate for the project's two
    compressed resource files.
    """
    out = bytearray(b"BPS1")
    out += _write_varint(len(source))
    out += _write_varint(len(target))
    out += _write_varint(len(metadata))
    out += metadata

    pos = 0
    target_size = len(target)
    while pos < target_size:
        equal = pos < len(source) and source[pos] == target[pos]
        start = pos
        if equal:
            while pos < target_size and pos < len(source) and source[pos] == target[pos]:
                pos += 1
            length = pos - start
            out += _write_varint(((length - 1) << 2) | 0)
        else:
            while pos < target_size and not (pos < len(source) and source[pos] == target[pos]):
                pos += 1
            length = pos - start
            out += _write_varint(((length - 1) << 2) | 1)
            out += target[start:pos]

    out += struct.pack("<I", zlib.crc32(source) & 0xFFFFFFFF)
    out += struct.pack("<I", zlib.crc32(target) & 0xFFFFFFFF)
    out += struct.pack("<I", zlib.crc32(out) & 0xFFFFFFFF)
    return bytes(out)
