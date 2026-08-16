"""Build side-by-side language comparison strips from real ROM font pages.

Every panel is rendered through the game's own 2bpp font pages, so a strip shows
the actual glyphs, spacing and line breaks a player sees rather than a mock-up.

Japanese and Chinese text are read straight out of the two ROMs at the same
script location; English is supplied by the caller because regional scripts do
not share block or command numbering (see docs/tech/FORMATS.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .archive import PackedArchive
from .font import FontMapEntry, GameFont, find_font_map
from .nds import NDSRom
from .nitro_bg import decode_4bpp_linear, decode_bgr555_palette
from .preview import LINE_HEIGHT, raw_to_codes, render_lines, wrap_codes
from .script import ScriptFile

LABEL_WIDTH = 34
PANEL_GAP = 6
MARGIN = 8
LABEL_COLOR = 150
RULE_COLOR = 210


class ShowcaseError(ValueError):
    pass


@dataclass(frozen=True)
class RomFonts:
    """A ROM plus the font pages and code map needed to draw its own text."""

    rom: NDSRom
    font: GameFont
    entries: dict[int, FontMapEntry]
    scripts: PackedArchive

    @classmethod
    def load(cls, path: str | Path, script_path: str, font_path: str) -> RomFonts:
        rom = NDSRom.from_file(path)
        _, entries = find_font_map(rom.arm9())
        return cls(
            rom=rom,
            font=GameFont(rom.get_file(font_path)),
            entries={entry.code: entry for entry in entries},
            scripts=PackedArchive(rom.get_file(script_path)),
        )

    def raw_text(self, script_code: str, block: int, command: int, *, language: str = "jp") -> bytes:
        entry_name = f"script_{language}_{script_code}.bin"
        script = ScriptFile(self.scripts.unpack(entry_name))
        try:
            target = script.command(block, command)
        except IndexError as exc:
            raise ShowcaseError(
                f"{entry_name}: no command {command} in block {block}"
            ) from exc
        raw = script.raw_text(target)
        if raw is None:
            raise ShowcaseError(
                f"{entry_name}: command {command} in block {block} is not a text command"
            )
        return raw


@dataclass
class Panel:
    label: str
    lines: list[list[int]]
    fonts: RomFonts = field(repr=False)


def _panel_from_raw(label: str, raw: bytes, fonts: RomFonts, max_width: int) -> Panel:
    return Panel(label, wrap_codes(raw_to_codes(raw), fonts.entries, max_width), fonts)


def build_panels(
    original: RomFonts,
    patched: RomFonts,
    script_code: str,
    block: int,
    command: int,
    *,
    english: str | None = None,
    max_width: int = 24 * LINE_HEIGHT,
) -> list[Panel]:
    """Assemble the Japanese, English and Chinese panels for one story line."""
    panels = [
        _panel_from_raw(
            "JP", original.raw_text(script_code, block, command), original, max_width
        )
    ]
    if english:
        # The font maps 0x5C to ¥, so the only backslash allowed is the one that
        # starts a literal \n line break.
        if english.replace("\\n", "").count("\\"):
            raise ShowcaseError(
                f"english sample has a backslash outside a \\n line break: {english!r}"
            )
        panels.append(
            _panel_from_raw("EN", english.encode("ascii", errors="replace"), original, max_width)
        )
    panels.append(
        _panel_from_raw("CN", patched.raw_text(script_code, block, command), patched, max_width)
    )
    return panels


def render_texture(
    rom: NDSRom,
    archive_path: str,
    texture: str,
    palette: str,
    *,
    width: int = 256,
    scale: int = 2,
    transparent_index: int | None = 0,
    crop: bool = True,
):
    """Decode one linear 4bpp UI texture straight out of a ROM.

    The result is the artwork the game itself displays, so a texture pulled from
    a patched ROM is the finished Chinese screen rather than a mock-up. Index 0
    is the transparent colour in these textures; it is made transparent here so
    the card does not sit on a flat green field.
    """
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError("Pillow is required for showcase textures") from exc

    archive = PackedArchive(rom.get_file(archive_path))
    pixels = decode_4bpp_linear(archive.unpack(texture), width=width)
    colors = decode_bgr555_palette(archive.unpack(palette))
    image = Image.new("RGBA", (width, len(pixels)), (0, 0, 0, 0))
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            if value == transparent_index:
                continue
            red, green, blue = colors[value][:3]
            image.putpixel((x, y), (red, green, blue, 255))
    if crop:
        box = image.getbbox()
        if box:
            image = image.crop(box)
    if scale != 1:
        image = image.resize(
            (image.width * scale, image.height * scale), Image.Resampling.NEAREST
        )
    return image


def stack_textures(images, output: str | Path, *, labels=None, gap: int = 10, background=(24, 26, 32)):
    """Stack rendered textures vertically into one comparison sheet."""
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError("Pillow is required for showcase textures") from exc

    label_width = 34 if labels else 0
    width = max(image.width for image in images) + gap * 2 + label_width
    height = sum(image.height for image in images) + gap * (len(images) + 1)
    canvas = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(canvas)
    y = gap
    for index, image in enumerate(images):
        canvas.paste(image, (gap + label_width, y), image if image.mode == "RGBA" else None)
        if labels:
            draw.text((gap, y + image.height // 2 - 4), labels[index], fill=(150, 155, 165))
        y += image.height + gap
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return output


def _label_image(Image, ImageDraw, text: str, scale: int, background: int):
    """Draw a label at 1x and upscale it, so it keeps the same pixel look."""
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    left, top, right, bottom = probe.textbbox((0, 0), text)
    tile = Image.new("L", (max(1, right - left), max(1, bottom - top)), background)
    ImageDraw.Draw(tile).text((-left, -top), text, fill=LABEL_COLOR)
    factor = max(1, scale - 1)
    return tile.resize((tile.width * factor, tile.height * factor), Image.Resampling.NEAREST)


def render_strip(
    panels: list[Panel],
    output: str | Path,
    *,
    scale: int = 3,
    background: int = 255,
) -> Path:
    """Stack labelled panels vertically into a single comparison image."""
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError("Pillow is required for showcase strips") from exc

    if not panels:
        raise ShowcaseError("no panels to render")

    # Glyphs are scaled with nearest-neighbour to stay crisp; labels and rules are
    # drawn afterwards at final size so they do not turn into blocky pixels too.
    rendered = [
        render_lines(panel.lines, panel.fonts.font, panel.fonts.entries, scale=scale)
        for panel in panels
    ]
    body_width = max(image.width for image in rendered)
    label_width = LABEL_WIDTH * scale
    margin = MARGIN * scale
    gap = PANEL_GAP * scale
    width = margin + label_width + body_width + margin
    height = margin + sum(image.height for image in rendered) + gap * (len(panels) - 1) + margin

    canvas = Image.new("L", (width, height), background)
    draw = ImageDraw.Draw(canvas)
    y = margin
    for index, (panel, image) in enumerate(zip(panels, rendered)):
        if index:
            rule = y - gap // 2
            draw.line([(margin, rule), (width - margin, rule)], fill=RULE_COLOR)
        label = _label_image(Image, ImageDraw, panel.label, scale, background)
        canvas.paste(label, (margin, y + (image.height - label.height) // 2))
        canvas.paste(image, (margin + label_width, y))
        y += image.height + gap

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return output
