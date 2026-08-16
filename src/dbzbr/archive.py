"""Reader/writer for the game's 76-byte-entry packed archives."""
from __future__ import annotations

import struct
from dataclasses import dataclass

from .compression import lz10_compress, lz10_decompress, rl_compress, rl_decompress


@dataclass
class ArchiveEntry:
    name: str
    unpacked_size: int
    packed_size: int
    relative_offset: int
    packed_data: bytes


class ArchiveError(ValueError):
    pass


class PackedArchive:
    ENTRY_SIZE = 76

    def __init__(self, data: bytes):
        if len(data) < 8:
            raise ArchiveError("truncated archive")
        self.original = data
        self.magic, self.header_size = struct.unpack_from("<II", data, 0)
        if self.header_size < 8 or (self.header_size - 8) % self.ENTRY_SIZE:
            raise ArchiveError("invalid archive header size")
        self.count = (self.header_size - 8) // self.ENTRY_SIZE
        if self.header_size > len(data):
            raise ArchiveError("archive header exceeds file")
        self.header_template = bytearray(data[: self.header_size])
        self.entries: list[ArchiveEntry] = []
        self._overrides: dict[str, tuple[bytes, bytes]] = {}
        for index in range(self.count):
            pos = 8 + index * self.ENTRY_SIZE
            name = data[pos : pos + 64].split(b"\0", 1)[0].decode("ascii")
            unpacked_size, packed_size, relative_offset = struct.unpack_from("<III", data, pos + 64)
            start = self.header_size + relative_offset
            end = start + packed_size
            if end > len(data):
                raise ArchiveError(f"entry {name} exceeds archive")
            self.entries.append(
                ArchiveEntry(name, unpacked_size, packed_size, relative_offset, data[start:end])
            )

    def names(self) -> list[str]:
        return [entry.name for entry in self.entries]

    def entry(self, name: str) -> ArchiveEntry:
        for entry in self.entries:
            if entry.name == name:
                return entry
        raise KeyError(name)

    @staticmethod
    def decompress(packed: bytes) -> bytes:
        if not packed:
            raise ArchiveError("empty compressed stream")
        if packed[0] == 0x10:
            return lz10_decompress(packed)
        if packed[0] == 0x30:
            return rl_decompress(packed)
        raise ArchiveError(f"unsupported compression type {packed[0]:#x}")

    @staticmethod
    def compress(unpacked: bytes, compression_type: int) -> bytes:
        if compression_type == 0x10:
            return lz10_compress(unpacked)
        if compression_type == 0x30:
            return rl_compress(unpacked)
        raise ArchiveError(f"unsupported compression type {compression_type:#x}")

    def unpack(self, name: str) -> bytes:
        if name in self._overrides:
            return self._overrides[name][0]
        entry = self.entry(name)
        result = self.decompress(entry.packed_data)
        if len(result) != entry.unpacked_size:
            raise ArchiveError(f"unpacked size mismatch for {name}")
        return result

    def replace_unpacked(self, name: str, unpacked: bytes, *, compression_type: int | None = None) -> None:
        entry = self.entry(name)
        ctype = entry.packed_data[0] if compression_type is None else compression_type
        packed = self.compress(unpacked, ctype)
        if self.decompress(packed) != unpacked:
            raise ArchiveError(f"compression round-trip failed for {name}")
        self._overrides[name] = (unpacked, packed)

    def build(self) -> bytes:
        header = bytearray(self.header_template)
        payload = bytearray()
        relative_offset = 0
        for index, entry in enumerate(self.entries):
            if entry.name in self._overrides:
                unpacked, packed = self._overrides[entry.name]
                unpacked_size = len(unpacked)
            else:
                packed = entry.packed_data
                unpacked_size = entry.unpacked_size
            pos = 8 + index * self.ENTRY_SIZE + 64
            struct.pack_into("<III", header, pos, unpacked_size, len(packed), relative_offset)
            payload += packed
            relative_offset += len(packed)
        return bytes(header + payload)
