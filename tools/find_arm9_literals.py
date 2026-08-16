#!/usr/bin/env python3
from __future__ import annotations

import argparse
import struct
from pathlib import Path

from _bootstrap import PROJECT_ROOT
from capstone import CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, Cs
from capstone.arm import ARM_OP_MEM, ARM_REG_PC


def scan(code: bytes, base: int, mode: int, low: int, high: int) -> list[str]:
    decoder = Cs(CS_ARCH_ARM, mode)
    decoder.detail = True
    decoder.skipdata = True
    results = []
    for instruction in decoder.disasm(code, base):
        if instruction.mnemonic != "ldr" or len(instruction.operands) < 2:
            continue
        operand = instruction.operands[1]
        if operand.type != ARM_OP_MEM or operand.mem.base != ARM_REG_PC:
            continue
        if mode == CS_MODE_ARM:
            literal_address = instruction.address + 8 + operand.mem.disp
        else:
            literal_address = ((instruction.address + 4) & ~3) + operand.mem.disp
        offset = literal_address - base
        if not 0 <= offset <= len(code) - 4:
            continue
        value = struct.unpack_from("<I", code, offset)[0]
        if low <= value < high:
            results.append(
                f"{instruction.address:08x} ({'ARM' if mode == CS_MODE_ARM else 'THUMB'}): "
                f"{instruction.mnemonic} {instruction.op_str}; [{literal_address:08x}]={value:08x}"
            )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Find ARM9 literal loads into an address range.")
    parser.add_argument("low", type=lambda value: int(value, 0))
    parser.add_argument("high", type=lambda value: int(value, 0))
    parser.add_argument(
        "--rom",
        type=Path,
        default=PROJECT_ROOT / "work/original/DBZ_Bukuu_Ressen_ADBJ_Rev0.nds",
    )
    args = parser.parse_args()

    data = args.rom.read_bytes()
    rom_offset, _, ram_address, size = struct.unpack_from("<IIII", data, 0x20)
    arm9 = data[rom_offset : rom_offset + size]
    results = scan(arm9, ram_address, CS_MODE_ARM, args.low, args.high)
    results += scan(arm9, ram_address, CS_MODE_THUMB, args.low, args.high)
    print("\n".join(results))


if __name__ == "__main__":
    main()
