"""Shared scaffolding for the image-interface build stages.

Each stage in the release chain does the same things around its own pixel work:
parse the same five arguments, load and hash-check the two ROMs, load BDF glyph
masks, write the rebuilt resource, generate and round-trip a BPS, diff which
files changed, and record the same hashes in its report.

Only the pixel work in between is per-interface. That part stays in
``tools/build_*.py``; everything else lives here.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .archive import PackedArchive
from .bps import apply_patch, create_patch
from .font import load_ui_bdf_masks
from .nds import FileEntry, NDSRom
from .nitro_bg import decode_bgr555_palette

PREVIEW_BACKGROUND = (36, 39, 48, 255)
DEFAULT_BDF = (
    "work/vendor/fusion-pixel-font/12px-monospaced-bdf-v2026.07.20"
    "/fusion-pixel-12px-monospaced-zh_hans.bdf"
)
DEFAULT_SOURCE_ROM = "work/original/DBZ_Bukuu_Ressen_ADBJ_Rev0.nds"


class StageError(ValueError):
    pass


def read_rows(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_rows_by_id(path: Path, key: str = "id") -> dict[str, dict[str, str]]:
    return {row[key]: row for row in read_rows(path)}


def changed_entries(before: PackedArchive, after: PackedArchive) -> list[str]:
    """Names of archive entries whose decompressed contents differ."""
    if before.names() != after.names():
        raise StageError("archive entry order changed")
    return [
        old.name
        for old, new in zip(before.entries, after.entries)
        if before.decompress(old.packed_data) != after.decompress(new.packed_data)
    ]


def indexed_image(pixels: list[list[int]], palette_data: bytes):
    """Render indexed pixels with their palette; index 0 stays transparent."""
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError("Pillow is required for previews") from exc
    palette = decode_bgr555_palette(palette_data)
    image = Image.new("RGBA", (len(pixels[0]), len(pixels)), PREVIEW_BACKGROUND)
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            if value:
                image.putpixel((x, y), palette[value])
    return image


def load_masks(bdf: Path, characters: str) -> dict[str, list[list[bool]]]:
    """Load BDF glyph masks and fail loudly on anything the font cannot draw."""
    masks = load_ui_bdf_masks(bdf, characters)
    missing = sorted(set(characters) - set(masks))
    if missing:
        detail = ", ".join(f"{character} U+{ord(character):04X}" for character in missing)
        raise StageError(f"BDF is missing translated characters: {detail}")
    return masks


def add_stage_arguments(
    parser: argparse.ArgumentParser,
    *,
    project_root: Path,
    base_rom: str,
    table: str | None,
    output_dir: str,
    bdf: bool = True,
) -> argparse.ArgumentParser:
    """Add the arguments every stage accepts, with per-stage defaults.

    ``table`` and ``bdf`` are opt-out: the Data mode stage names its own tables
    and uses three separate fonts, so it declares them itself.
    """
    parser.add_argument("--base-rom", type=Path, default=project_root / base_rom)
    parser.add_argument("--source-rom", type=Path, default=project_root / DEFAULT_SOURCE_ROM)
    if table is not None:
        parser.add_argument("--table", type=Path, default=project_root / table)
    if bdf:
        parser.add_argument("--bdf", type=Path, default=project_root / DEFAULT_BDF)
    parser.add_argument("--output-dir", type=Path, default=project_root / output_dir)
    return parser


@dataclass
class Stage:
    """Both ROMs, verified, plus the glyph masks the stage will draw with."""

    args: argparse.Namespace
    project_root: Path
    source_bytes: bytes
    source_rom: NDSRom
    base_bytes: bytes
    base_rom: NDSRom
    masks: dict[str, list[list[bool]]] = field(default_factory=dict)

    def resource(self, path: str) -> PackedArchive:
        return PackedArchive(self.base_rom.get_file(path))

    def source_resource(self, path: str) -> PackedArchive:
        return PackedArchive(self.source_rom.get_file(path))


def load_stage(
    args: argparse.Namespace,
    project_root: Path,
    *,
    characters: str = "",
    bdf: Path | None = None,
) -> Stage:
    """Read both ROMs, verify the source hash, and load the glyph masks.

    The source hash check is what stops a stage from silently building on top of
    the wrong dump; every stage generates a BPS against this ROM.
    """
    source_bytes = Path(args.source_rom).read_bytes()
    source_rom = NDSRom(source_bytes)
    expected = json.loads((project_root / "project.json").read_text(encoding="utf-8"))[
        "source_sha256"
    ]
    if source_rom.sha256 != expected:
        raise StageError(
            f"source ROM hash mismatch\nexpected: {expected}\nactual:   {source_rom.sha256}"
        )
    base_bytes = Path(args.base_rom).read_bytes()

    masks = load_masks(bdf or args.bdf, characters) if characters else {}

    return Stage(
        args=args,
        project_root=project_root,
        source_bytes=source_bytes,
        source_rom=source_rom,
        base_bytes=base_bytes,
        base_rom=NDSRom(base_bytes),
        masks=masks,
    )


@dataclass
class StageOutput:
    output_bytes: bytes
    patch: bytes
    rom_path: Path
    patch_path: Path
    resource_paths: list[Path]
    replaced: list[FileEntry]
    changed_from_base: list[str]
    changed_from_source: list[str]

    def rom_range(self, path: str | None = None) -> list[int]:
        """Where a rebuilt resource landed in the output ROM."""
        entry = self.replaced[0] if path is None else self.by_path[path]
        return [entry.start, entry.end]

    @property
    def by_path(self) -> dict[str, FileEntry]:
        return {entry.path: entry for entry in self.replaced}

    def report_fields(self, base_bytes: bytes, bdf: Path) -> dict[str, object]:
        """The report keys every stage records, so they stay consistent."""
        return {
            "font": str(bdf),
            "base_rom_sha256": hashlib.sha256(base_bytes).hexdigest(),
            "output_rom_sha256": hashlib.sha256(self.output_bytes).hexdigest(),
            "patch_sha256": hashlib.sha256(self.patch).hexdigest(),
            "changed_from_base": self.changed_from_base,
            "changed_from_source": self.changed_from_source,
            "resource_rom_range": [
                [entry.start, entry.end] for entry in self.replaced
            ]
            if len(self.replaced) > 1
            else [self.replaced[0].start, self.replaced[0].end],
            "output_resource": [str(path) for path in self.resource_paths]
            if len(self.resource_paths) > 1
            else str(self.resource_paths[0]),
            "output_rom": str(self.rom_path),
            "output_patch": str(self.patch_path),
        }


def finish_stage(
    stage: Stage,
    resources: dict[str, bytes],
    *,
    rom_name: str,
    metadata: bytes,
    resource_names: dict[str, str],
    expect_changed: list[str] | None = None,
) -> StageOutput:
    """Write the rebuilt resources into the ROM and validate the result.

    ``resources`` maps a NitroFS path to its rebuilt bytes; ``resource_names``
    maps the same paths to the file names the stage dumps them under.
    """
    output_rom = NDSRom(stage.base_bytes)
    replaced = [output_rom.replace_file(path, data) for path, data in resources.items()]
    output_bytes = bytes(output_rom.data)

    output_dir = Path(stage.args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    resource_paths = []
    for path, data in resources.items():
        target = output_dir / resource_names[path]
        target.write_bytes(data)
        resource_paths.append(target)

    rom_path = output_dir / f"{rom_name}.nds"
    patch_path = output_dir / f"{rom_name}.bps"
    rom_path.write_bytes(output_bytes)
    patch = create_patch(stage.source_bytes, output_bytes, metadata=metadata)
    patch_path.write_bytes(patch)
    if apply_patch(stage.source_bytes, patch) != output_bytes:
        raise StageError("generated BPS patch failed round-trip validation")

    final_rom = NDSRom(output_bytes)
    changed_from_base = [
        entry.path
        for entry in stage.base_rom.list_files()
        if stage.base_rom.get_file(entry.path) != final_rom.get_file(entry.path)
    ]
    # "exactly these files changed" is a set comparison: NitroFS order need not
    # match the order the stage happened to rebuild them in.
    expected = set(expect_changed if expect_changed is not None else resources)
    if set(changed_from_base) != expected:
        raise StageError(
            f"unexpected changed ROM files: {sorted(changed_from_base)} "
            f"(expected {sorted(expected)})"
        )
    changed_from_source = [
        entry.path
        for entry in stage.source_rom.list_files()
        if stage.source_rom.get_file(entry.path) != final_rom.get_file(entry.path)
    ]

    return StageOutput(
        output_bytes=output_bytes,
        patch=patch,
        rom_path=rom_path,
        patch_path=patch_path,
        resource_paths=resource_paths,
        replaced=replaced,
        changed_from_base=changed_from_base,
        changed_from_source=changed_from_source,
    )


def write_report(stage: Stage, report: dict[str, object], name: str = "report.json") -> Path:
    path = Path(stage.args.output_dir) / name
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return path
