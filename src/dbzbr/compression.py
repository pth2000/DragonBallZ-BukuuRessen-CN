"""Nintendo DS LZ10 and RLE(0x30) compression helpers."""
from __future__ import annotations

from collections import defaultdict, deque


class CompressionError(ValueError):
    pass


def lz10_decompress(data: bytes) -> bytes:
    if len(data) < 4 or data[0] != 0x10:
        raise CompressionError("not an LZ10 stream")
    size = data[1] | (data[2] << 8) | (data[3] << 16)
    out = bytearray()
    pos = 4
    while len(out) < size:
        if pos >= len(data):
            raise CompressionError("truncated LZ10 flags")
        flags = data[pos]
        pos += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                if pos + 2 > len(data):
                    raise CompressionError("truncated LZ10 back-reference")
                b1, b2 = data[pos], data[pos + 1]
                pos += 2
                length = (b1 >> 4) + 3
                distance = (((b1 & 0x0F) << 8) | b2) + 1
                if distance > len(out):
                    raise CompressionError("invalid LZ10 distance")
                for _ in range(length):
                    out.append(out[-distance])
                    if len(out) >= size:
                        break
            else:
                if pos >= len(data):
                    raise CompressionError("truncated LZ10 literal")
                out.append(data[pos])
                pos += 1
    return bytes(out)


def lz10_compress(data: bytes) -> bytes:
    if len(data) > 0xFFFFFF:
        raise CompressionError("LZ10 input is too large")
    out = bytearray((0x10, len(data) & 0xFF, (len(data) >> 8) & 0xFF, (len(data) >> 16) & 0xFF))
    positions: dict[bytes, deque[int]] = defaultdict(deque)

    def add_position(index: int) -> None:
        if index + 2 >= len(data):
            return
        key = data[index : index + 3]
        q = positions[key]
        q.append(index)
        minimum = index - 0x1000
        while q and q[0] < minimum:
            q.popleft()
        while len(q) > 128:
            q.popleft()

    pos = 0
    while pos < len(data):
        flag_index = len(out)
        out.append(0)
        flags = 0
        tokens = bytearray()
        for bit in range(8):
            if pos >= len(data):
                break
            best_length = 0
            best_distance = 0
            if pos + 2 < len(data):
                key = data[pos : pos + 3]
                for candidate in reversed(positions.get(key, ())):
                    distance = pos - candidate
                    if distance <= 0 or distance > 0x1000:
                        continue
                    length = 3
                    max_length = min(18, len(data) - pos)
                    while length < max_length and data[candidate + length] == data[pos + length]:
                        length += 1
                    if length > best_length:
                        best_length = length
                        best_distance = distance
                        if length == max_length:
                            break
            if best_length >= 3:
                flags |= 0x80 >> bit
                disp = best_distance - 1
                tokens.append(((best_length - 3) << 4) | ((disp >> 8) & 0x0F))
                tokens.append(disp & 0xFF)
                consumed = best_length
            else:
                tokens.append(data[pos])
                consumed = 1
            for index in range(pos, pos + consumed):
                add_position(index)
            pos += consumed
        out[flag_index] = flags
        out += tokens
    return bytes(out)


def rl_decompress(data: bytes) -> bytes:
    if len(data) < 4 or data[0] != 0x30:
        raise CompressionError("not an RLE 0x30 stream")
    size = data[1] | (data[2] << 8) | (data[3] << 16)
    out = bytearray()
    pos = 4
    while len(out) < size:
        if pos >= len(data):
            raise CompressionError("truncated RLE control byte")
        control = data[pos]
        pos += 1
        if control & 0x80:
            length = (control & 0x7F) + 3
            if pos >= len(data):
                raise CompressionError("truncated RLE run")
            out.extend([data[pos]] * length)
            pos += 1
        else:
            length = (control & 0x7F) + 1
            if pos + length > len(data):
                raise CompressionError("truncated RLE literal run")
            out += data[pos : pos + length]
            pos += length
    return bytes(out[:size])


def rl_compress(data: bytes) -> bytes:
    if len(data) > 0xFFFFFF:
        raise CompressionError("RLE input is too large")
    out = bytearray((0x30, len(data) & 0xFF, (len(data) >> 8) & 0xFF, (len(data) >> 16) & 0xFF))
    pos = 0
    while pos < len(data):
        run = 1
        while pos + run < len(data) and data[pos + run] == data[pos] and run < 130:
            run += 1
        if run >= 3:
            out.append(0x80 | (run - 3))
            out.append(data[pos])
            pos += run
            continue

        literal_start = pos
        pos += 1
        while pos < len(data) and pos - literal_start < 128:
            lookahead = 1
            while pos + lookahead < len(data) and data[pos + lookahead] == data[pos] and lookahead < 3:
                lookahead += 1
            if lookahead >= 3:
                break
            pos += 1
        length = pos - literal_start
        out.append(length - 1)
        out += data[literal_start:pos]
    return bytes(out)
