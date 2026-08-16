"""Small Nintendo DS ROM filesystem reader and in-place/relocating replacer."""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileEntry:
    file_id: int
    path: str
    start: int
    end: int

    @property
    def size(self) -> int:
        return self.end - self.start


class NDSError(ValueError):
    pass


class NDSRom:
    def __init__(self, data: bytes | bytearray):
        self.data = bytearray(data)
        if len(self.data) < 0x200:
            raise NDSError("file is too small to be an NDS ROM")
        self.fnt_offset, self.fnt_size = struct.unpack_from("<II", self.data, 0x40)
        self.fat_offset, self.fat_size = struct.unpack_from("<II", self.data, 0x48)
        if self.fnt_offset + self.fnt_size > len(self.data) or self.fat_offset + self.fat_size > len(self.data):
            raise NDSError("invalid FNT/FAT range")
        self._paths = self._parse_fnt()

    @classmethod
    def from_file(cls, path: str | Path) -> NDSRom:
        return cls(Path(path).read_bytes())

    @property
    def game_code(self) -> str:
        return bytes(self.data[0x0C:0x10]).decode("ascii", errors="replace")

    @property
    def rom_version(self) -> int:
        return self.data[0x1E]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()

    def _parse_fnt(self) -> list[str]:
        fnt = bytes(self.data[self.fnt_offset : self.fnt_offset + self.fnt_size])
        file_count = self.fat_size // 8
        if len(fnt) < 8:
            raise NDSError("truncated FNT")
        _, _, directory_count = struct.unpack_from("<IHH", fnt, 0)
        directories = [struct.unpack_from("<IHH", fnt, index * 8) for index in range(directory_count)]
        paths = [""] * file_count

        def walk(directory_id: int, prefix: str) -> None:
            table_index = directory_id - 0xF000
            if not 0 <= table_index < len(directories):
                raise NDSError(f"invalid directory id {directory_id:#x}")
            sub_offset, file_id, _ = directories[table_index]
            pos = sub_offset
            while True:
                if pos >= len(fnt):
                    raise NDSError("truncated FNT name table")
                length = fnt[pos]
                pos += 1
                if length == 0:
                    return
                is_directory = bool(length & 0x80)
                name_length = length & 0x7F
                name = fnt[pos : pos + name_length].decode("ascii", errors="replace")
                pos += name_length
                if is_directory:
                    if pos + 2 > len(fnt):
                        raise NDSError("truncated FNT child id")
                    child_id = struct.unpack_from("<H", fnt, pos)[0]
                    pos += 2
                    walk(child_id, prefix + name + "/")
                else:
                    if not 0 <= file_id < len(paths):
                        raise NDSError("FNT file id exceeds FAT")
                    paths[file_id] = prefix + name
                    file_id += 1

        walk(0xF000, "")
        return paths

    def list_files(self) -> list[FileEntry]:
        result: list[FileEntry] = []
        for file_id, path in enumerate(self._paths):
            start, end = struct.unpack_from("<II", self.data, self.fat_offset + file_id * 8)
            result.append(FileEntry(file_id, path, start, end))
        return result

    def find(self, path: str) -> FileEntry:
        for entry in self.list_files():
            if entry.path == path:
                return entry
        raise KeyError(path)

    def get_file(self, path: str) -> bytes:
        entry = self.find(path)
        return bytes(self.data[entry.start : entry.end])

    def arm9(self) -> bytes:
        offset = struct.unpack_from("<I", self.data, 0x20)[0]
        size = struct.unpack_from("<I", self.data, 0x2C)[0]
        return bytes(self.data[offset : offset + size])

    def replace_file(self, path: str, new_data: bytes, *, align: int = 0x200, allow_relocate: bool = True) -> FileEntry:
        entry = self.find(path)
        files = self.list_files()
        later_starts = sorted(item.start for item in files if item.start > entry.start)
        capacity = (later_starts[0] if later_starts else len(self.data)) - entry.start

        if len(new_data) <= capacity:
            new_start = entry.start
        elif allow_relocate:
            max_end = max(item.end for item in files)
            new_start = (max_end + align - 1) // align * align
            if new_start + len(new_data) > len(self.data):
                raise NDSError(
                    f"not enough free ROM space to relocate {path}: need {len(new_data)} bytes"
                )
        else:
            raise NDSError(
                f"replacement for {path} is {len(new_data)} bytes; current capacity is {capacity}"
            )

        old_start, old_end = entry.start, entry.end
        self.data[new_start : new_start + len(new_data)] = new_data
        if new_start == old_start and new_start + len(new_data) < old_end:
            self.data[new_start + len(new_data) : old_end] = b"\0" * (old_end - new_start - len(new_data))
        elif new_start != old_start:
            self.data[old_start:old_end] = b"\0" * (old_end - old_start)

        fat_pos = self.fat_offset + entry.file_id * 8
        struct.pack_into("<II", self.data, fat_pos, new_start, new_start + len(new_data))
        return FileEntry(entry.file_id, path, new_start, new_start + len(new_data))

    def save(self, path: str | Path) -> None:
        Path(path).write_bytes(self.data)
