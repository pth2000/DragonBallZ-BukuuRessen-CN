"""End-to-end project builder."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .archive import PackedArchive
from .bps import apply_patch, create_patch
from .font import (
    FontError,
    FontMapEntry,
    GameFont,
    find_ark_glyph,
    find_font_map,
    load_bdf_masks,
    load_png_mask,
    shift_jis_code,
)
from .nds import NDSRom
from .script import apply_translation_rows


class BuildError(ValueError):
    pass


# Provenance labels for the `source` column of the custom glyph map. They are
# deliberately machine paths' opposite: stable across machines, and free of any
# local directory layout. Exact font versions live in THIRD_PARTY_NOTICES.md.
BASELINE_SOURCE = "font-baseline"
FALLBACK_SOURCE = "fusion-12px-zh_hans"


def ark_source_label(glyph_path: str | Path, size: int) -> str:
    """Describe an Ark Pixel Font glyph by size and regional variant."""
    stem = Path(glyph_path).stem
    variant = stem.split(" ", 1)[1] if " " in stem else "common"
    return f"ark-{size}px-{variant}"


@dataclass
class GlyphAssignment:
    character: str
    code: int
    slot_character: str
    entry: FontMapEntry
    source: str
    punctuation: bool = False


def read_tsv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: str | Path, rows: list[dict[str, object]], headers: list[str]) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def iter_text_characters(text: str):
    pos = 0
    while pos < len(text):
        if text.startswith("\\n", pos):
            yield "\\n"
            pos += 2
        else:
            yield text[pos]
            pos += 1


def is_cjk_ideograph(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
    )


def load_existing_assignments(path: str | Path, font_entries: dict[int, FontMapEntry]) -> dict[str, GlyphAssignment]:
    result: dict[str, GlyphAssignment] = {}
    for row in read_tsv(path):
        character = row["character"]
        code = int(row["code_hex"], 16)
        entry = font_entries.get(code)
        if entry is None:
            raise BuildError(f"custom glyph code {code:04X} is absent from ARM9 font map")
        result[character] = GlyphAssignment(
            character,
            code,
            row.get("native_slot_character", entry.native_character),
            entry,
            row.get("source", BASELINE_SOURCE),
            row.get("punctuation", "no").lower() == "yes",
        )
    return result


def load_slot_candidates(path: str | Path, font_entries: dict[int, FontMapEntry]) -> list[FontMapEntry]:
    rows = read_tsv(path)
    eligible = [
        row
        for row in rows
        if row.get("status") in {
            "legacy_reusable",
            "candidate_requires_test",
            "reusable_full_cn",
        }
    ]
    eligible.sort(key=lambda row: (int(row.get("priority", "999999")), int(row["code_hex"], 16)))
    return [font_entries[int(row["code_hex"], 16)] for row in eligible]


class TextEncoder:
    def __init__(self, font_entries: dict[int, FontMapEntry], assignments: dict[str, GlyphAssignment]):
        self.font_entries = font_entries
        self.assignments = assignments

    def native_code(self, character: str) -> int | None:
        try:
            code = shift_jis_code(character)
        except (UnicodeEncodeError, FontError):
            return None
        return code if code in self.font_entries else None

    def code_for(self, character: str) -> int | None:
        if character in self.assignments:
            return self.assignments[character].code
        return self.native_code(character)

    def encode(self, text: str) -> bytes:
        out = bytearray()
        for character in iter_text_characters(text):
            if character == "\\n":
                out += b"\\n"
                continue
            assignment = self.assignments.get(character)
            if assignment is not None:
                out += assignment.code.to_bytes(2, "big")
                continue
            try:
                raw = character.encode("shift_jis")
            except UnicodeEncodeError as exc:
                raise BuildError(f"no glyph assignment for {character} U+{ord(character):04X}") from exc
            code = raw[0] if len(raw) == 1 else int.from_bytes(raw, "big")
            if code not in self.font_entries:
                raise BuildError(
                    f"Shift-JIS code {code:04X} for {character!r} is not present in the game font map"
                )
            out += raw
        return bytes(out)


@dataclass
class BuildOptions:
    project_root: Path
    source_rom: Path
    output_rom: Path
    output_patch: Path
    translation_table: Path
    custom_glyph_map: Path | None = None
    ark_font_root: Path | None = None
    ark_size: int = 12
    fallback_bdf: Path | None = None
    update_map: bool = False


def build_project(options: BuildOptions) -> dict[str, object]:
    root = options.project_root
    config = json.loads((root / "project.json").read_text(encoding="utf-8"))
    source = options.source_rom.read_bytes()
    source_hash = hashlib.sha256(source).hexdigest()
    if source_hash != config["source_sha256"]:
        raise BuildError(
            "source ROM SHA-256 mismatch\n"
            f"expected: {config['source_sha256']}\n"
            f"actual:   {source_hash}"
        )
    source_rom = NDSRom(source)
    if source_rom.game_code != config["game_code"]:
        raise BuildError(f"game code mismatch: {source_rom.game_code}")

    baseline_patch = (root / config["baseline_patch"]).read_bytes()
    baseline = apply_patch(source, baseline_patch)
    baseline_hash = hashlib.sha256(baseline).hexdigest()
    if baseline_hash != config["baseline_target_sha256"]:
        raise BuildError("bundled font baseline patch failed its SHA-256 check")
    baseline_rom = NDSRom(baseline)

    font_map_offset, map_entries = find_font_map(source_rom.arm9())
    entries_by_code = {entry.code: entry for entry in map_entries}
    custom_map_path = options.custom_glyph_map or (root / config["custom_glyph_map"])
    assignments = load_existing_assignments(custom_map_path, entries_by_code)
    slot_plan = config.get("full_translation_slots", config["font_slots"])
    candidates = load_slot_candidates(root / slot_plan, entries_by_code)
    reserved_codes = {assignment.code for assignment in assignments.values()}
    candidates = [entry for entry in candidates if entry.code not in reserved_codes]

    rows = read_tsv(options.translation_table)
    translated_rows = [row for row in rows if row.get("简体中文", "")]
    required_characters: list[str] = []
    seen: set[str] = set()
    encoder = TextEncoder(entries_by_code, assignments)
    for row in translated_rows:
        for character in iter_text_characters(row["简体中文"]):
            if character == "\\n" or character in seen:
                continue
            seen.add(character)
            required_characters.append(character)

    # A slot that is still addressed through its native Shift-JIS code by any
    # translated text cannot be repurposed for a custom glyph.  In particular,
    # 0x97CA is the native slot for "量" and caused the v5 "力量 -> 力只"
    # regression when it was treated as reusable.
    required_native_codes = {
        code
        for character in required_characters
        if character not in assignments
        for code in [encoder.native_code(character)]
        if code is not None
    }
    enable_native_overrides = (
        options.ark_font_root is not None or options.fallback_bdf is not None
    )
    native_simplified_characters = (
        [
            character
            for character in required_characters
            if character not in assignments
            and encoder.native_code(character) is not None
            and is_cjk_ideograph(character)
        ]
        if enable_native_overrides
        else []
    )
    native_typography_characters = (
        [
            character
            for character in "”’"
            if character in seen
            and character not in assignments
            and encoder.native_code(character) is not None
        ]
        if enable_native_overrides
        else []
    )
    candidates = [entry for entry in candidates if entry.code not in required_native_codes]

    # Historical baseline assignments can collide with native characters introduced
    # by the full translation (for example, 寻 used the native 埋 slot).  Drop
    # those assignments so the custom character is allocated a new safe slot.
    conflicting_assignments = [
        assignment
        for assignment in assignments.values()
        if assignment.code in required_native_codes
    ]
    for assignment in conflicting_assignments:
        del assignments[assignment.character]
    encoder = TextEncoder(entries_by_code, assignments)

    missing_characters = [
        character
        for character in required_characters
        if encoder.code_for(character) is None
    ]
    required_character_set = set(required_characters)
    persisted_assignments_to_render = [
        assignment
        for assignment in assignments.values()
        if assignment.character in required_character_set
        and assignment.source != BASELINE_SOURCE
    ]
    fallback_masks = (
        load_bdf_masks(
            options.fallback_bdf,
            missing_characters
            + [assignment.character for assignment in persisted_assignments_to_render]
            + native_simplified_characters
            + native_typography_characters,
        )
        if options.fallback_bdf is not None
        else {}
    )

    baseline_font = GameFont(baseline_rom.get_file(config["font_path"]))
    source_font = GameFont(source_rom.get_file(config["font_path"]))
    assigned_codes = {assignment.code for assignment in assignments.values()}
    restored_native_codes = sorted(required_native_codes - assigned_codes)
    for code in restored_native_codes:
        # Most entries are already identical.  Copying all required native
        # rectangles is cheap and guarantees that stale baseline custom glyphs do
        # not survive after their mapping is moved elsewhere.
        baseline_font.copy_entry_from(source_font, entries_by_code[code])

    def load_custom_mask(character: str) -> tuple[list[list[bool]], str]:
        if options.ark_font_root is not None:
            try:
                glyph_path = find_ark_glyph(
                    options.ark_font_root, character, size=options.ark_size
                )
                return load_png_mask(glyph_path), ark_source_label(
                    glyph_path, options.ark_size
                )
            except FontError:
                pass
        mask = fallback_masks.get(character)
        if mask is not None:
            return mask, FALLBACK_SOURCE
        raise BuildError(
            f"no glyph source for {character} U+{ord(character):04X}; "
            "pass --ark-font-repo and, when needed, --fallback-bdf"
        )

    new_assignments: list[GlyphAssignment] = []
    for character in required_characters:
        if encoder.code_for(character) is not None:
            continue
        if not candidates:
            raise BuildError(f"no free candidate font slot remains for {character}")
        entry = candidates.pop(0)
        punctuation = character in "，。！？：；、“”‘’（）《》…"
        mask, glyph_source = load_custom_mask(character)
        baseline_font.import_mask(
            entry,
            mask,
            punctuation=punctuation,
            top_aligned=character in "“‘",
        )
        assignment = GlyphAssignment(
            character,
            entry.code,
            entry.native_character,
            entry,
            glyph_source,
            punctuation,
        )
        assignments[character] = assignment
        new_assignments.append(assignment)
        encoder = TextEncoder(entries_by_code, assignments)

    # Mappings persisted after a previous build are not present in the bundled
    # baseline font archive.  Redraw every required non-baseline assignment so rebuilding
    # from the same TSV and mapping remains deterministic.
    for assignment in persisted_assignments_to_render:
        mask, glyph_source = load_custom_mask(assignment.character)
        baseline_font.import_mask(
            assignment.entry,
            mask,
            punctuation=assignment.punctuation,
            top_aligned=assignment.character in "“‘",
        )
        assignment.source = glyph_source

    native_override_rows = []
    for character in native_simplified_characters:
        code = encoder.native_code(character)
        if code is None:
            raise BuildError(f"native code disappeared for {character!r}")
        mask, glyph_source = load_custom_mask(character)
        baseline_font.import_mask(entries_by_code[code], mask)
        native_override_rows.append(
            {
                "character": character,
                "unicode": f"U+{ord(character):04X}",
                "code_hex": f"{code:04X}",
                "kind": "simplified_han",
                "source": glyph_source,
            }
        )

    for character in native_typography_characters:
        code = encoder.native_code(character)
        if code is None:
            raise BuildError(f"native code disappeared for {character!r}")
        mask, glyph_source = load_custom_mask(character)
        baseline_font.import_mask(
            entries_by_code[code],
            mask,
            punctuation=True,
            top_aligned=True,
            left_aligned=True,
        )
        native_override_rows.append(
            {
                "character": character,
                "unicode": f"U+{ord(character):04X}",
                "code_hex": f"{code:04X}",
                "kind": "closing_quote",
                "source": glyph_source,
            }
        )

    # Rebuild scripts from the untouched Japanese source, not from the baseline.  This
    # makes the translation table the single source of truth.
    source_script_archive = PackedArchive(source_rom.get_file(config["script_path"]))
    by_script: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in translated_rows:
        by_script[row["脚本"]].append(row)
    script_report: list[dict[str, object]] = []
    for script_code, script_rows in sorted(by_script.items()):
        entry_name = f"script_jp_{script_code}.bin"
        original_script = source_script_archive.unpack(entry_name)
        rebuilt_script, report = apply_translation_rows(original_script, script_rows, encoder.encode)
        script_report.extend(report)
        if rebuilt_script != original_script:
            source_script_archive.replace_unpacked(entry_name, rebuilt_script)
    rebuilt_script_archive = source_script_archive.build()

    rebuilt_font_archive = baseline_font.build()

    output = NDSRom(source)
    script_entry = output.replace_file(config["script_path"], rebuilt_script_archive)
    font_entry = output.replace_file(config["font_path"], rebuilt_font_archive)
    output_bytes = bytes(output.data)
    options.output_rom.parent.mkdir(parents=True, exist_ok=True)
    options.output_rom.write_bytes(output_bytes)

    patch = create_patch(source, output_bytes, metadata=b"DBZ Bukuu Ressen CN project build")
    options.output_patch.parent.mkdir(parents=True, exist_ok=True)
    options.output_patch.write_bytes(patch)
    if apply_patch(source, patch) != output_bytes:
        raise BuildError("generated BPS patch failed round-trip validation")

    generated_map_rows = []
    for assignment in sorted(assignments.values(), key=lambda item: item.code):
        generated_map_rows.append(
            {
                "character": assignment.character,
                "unicode": f"U+{ord(assignment.character):04X}",
                "code_hex": f"{assignment.code:04X}",
                "native_slot_character": assignment.slot_character,
                "page": assignment.entry.page,
                "x0": assignment.entry.x0,
                "y0": assignment.entry.y0,
                "x1": assignment.entry.x1,
                "y1": assignment.entry.y1,
                "punctuation": "yes" if assignment.punctuation else "no",
                "source": assignment.source,
            }
        )
    map_output = options.output_rom.parent / "generated_custom_glyph_map.tsv"
    map_headers = [
        "character", "unicode", "code_hex", "native_slot_character", "page",
        "x0", "y0", "x1", "y1", "punctuation", "source",
    ]
    write_tsv(map_output, generated_map_rows, map_headers)
    if options.update_map and new_assignments:
        write_tsv(root / config["custom_glyph_map"], generated_map_rows, map_headers)

    budget_output = options.output_rom.parent / "text_budget_report.tsv"
    budget_headers = ["ID", "script", "block", "command", "used_bytes", "capacity_bytes", "remaining_bytes"]
    write_tsv(budget_output, script_report, budget_headers)

    native_override_output = options.output_rom.parent / "native_simplified_glyph_overrides.tsv"
    write_tsv(
        native_override_output,
        native_override_rows,
        ["character", "unicode", "code_hex", "kind", "source"],
    )

    result = {
        "source_sha256": source_hash,
        "output_sha256": hashlib.sha256(output_bytes).hexdigest(),
        "output_rom": str(options.output_rom),
        "output_patch": str(options.output_patch),
        "translated_rows": len(translated_rows),
        "unique_translation_characters": len(required_characters),
        "existing_custom_glyphs": len(assignments) - len(new_assignments),
        "new_custom_glyphs": len(new_assignments),
        "reassigned_conflicting_glyphs": [
            {
                "character": item.character,
                "old_code_hex": f"{item.code:04X}",
                "native_slot_character": item.slot_character,
            }
            for item in conflicting_assignments
        ],
        "restored_native_glyph_slots": len(restored_native_codes),
        "rendered_persisted_glyphs": len(persisted_assignments_to_render),
        "native_simplified_glyph_overrides": len(native_simplified_characters),
        "native_typography_overrides": native_typography_characters,
        "native_override_report": str(native_override_output),
        "new_assignments": [
            {"character": item.character, "code_hex": f"{item.code:04X}", "source": item.source}
            for item in new_assignments
        ],
        "font_map_offset": f"0x{font_map_offset:X}",
        "font_map_entries": len(map_entries),
        "script_archive_size": len(rebuilt_script_archive),
        "font_archive_size": len(rebuilt_font_archive),
        "script_rom_range": [script_entry.start, script_entry.end],
        "font_rom_range": [font_entry.start, font_entry.end],
        "budget_report": str(budget_output),
        "generated_map": str(map_output),
    }
    report_path = options.output_rom.parent / "build_report.json"
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
