"""Render text through the game's real font pages for visual inspection."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from .build import TextEncoder, iter_text_characters
from .font import FontMapEntry, GameFont

LINE_HEIGHT = 15

# 0x20 has no rectangle in the ARM9 font map: every mapped single-byte glyph is
# 9px wide, and the game advances past a space without drawing anything.
SPACE_CODE = 0x20
SPACE_ADVANCE = 9


class PreviewError(ValueError):
    pass


def glyph_width(code: int, entries_by_code: dict[int, FontMapEntry]) -> int:
    if code == SPACE_CODE:
        return SPACE_ADVANCE
    entry = entries_by_code.get(code)
    if entry is None:
        raise PreviewError(f"code {code:04X} is absent from the font map")
    return entry.width


def _require_pillow():
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError("Pillow is required for previews") from exc
    return Image


def wrap_codes(codes: Iterable[int], entries_by_code: dict[int, FontMapEntry], max_width: int) -> list[list[int]]:
    """Break a stream of code units into lines that fit within max_width pixels.

    ``None`` acts as an explicit line break.
    """
    lines: list[list[int]] = [[]]
    used = 0
    for code in codes:
        if code is None:
            lines.append([])
            used = 0
            continue
        advance = glyph_width(code, entries_by_code)
        if used and used + advance > max_width:
            lines.append([])
            used = 0
            if code == SPACE_CODE:
                continue
        lines[-1].append(code)
        used += advance
    if len(lines) > 1 and not lines[-1]:
        lines.pop()
    return lines


def render_lines(
    lines: Sequence[Sequence[int]],
    font: GameFont,
    entries_by_code: dict[int, FontMapEntry],
    *,
    scale: int = 3,
    foreground: int = 0,
    background: int = 255,
):
    """Draw pre-wrapped lines of code units and return a PIL image.

    Each glyph advances by its own mapped width, so proportional ASCII renders
    the way the game draws it rather than on a fixed full-width grid.
    """
    Image = _require_pillow()
    widths = [sum(glyph_width(code, entries_by_code) for code in line) for line in lines]
    width = max(widths, default=1) or 1
    height = max(1, len(lines)) * LINE_HEIGHT
    image = Image.new("L", (width, height), background)
    for line_index, line in enumerate(lines):
        pen = 0
        for code in line:
            if code == SPACE_CODE:
                pen += SPACE_ADVANCE
                continue
            entry = entries_by_code[code]
            for y in range(entry.height):
                for x in range(entry.width):
                    if font.get_pixel(entry.page, entry.x0 + x, entry.y0 + y):
                        image.putpixel((pen + x, line_index * LINE_HEIGHT + y), foreground)
            pen += entry.width
    if scale != 1:
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    return image


def text_to_codes(text: str, encoder: TextEncoder) -> list[int | None]:
    """Convert authored translation text into code units, with None for breaks."""
    codes: list[int | None] = []
    for token in iter_text_characters(text):
        if token == "\\n":
            codes.append(None)
            continue
        code = encoder.code_for(token)
        if code is None:
            raise PreviewError(f"no code for {token!r}")
        codes.append(code)
    return codes


def raw_to_codes(raw: bytes) -> list[int | None]:
    """Convert a raw in-game text field into code units, with None for breaks.

    In-game line breaks are the two ASCII bytes ``5C 6E``, not ``0A``.
    """
    codes: list[int | None] = []
    pos = 0
    while pos < len(raw):
        first = raw[pos]
        if first == 0x5C and pos + 1 < len(raw) and raw[pos + 1] == 0x6E:
            codes.append(None)
            pos += 2
            continue
        if (0x81 <= first <= 0x9F or 0xE0 <= first <= 0xFC) and pos + 1 < len(raw):
            codes.append((first << 8) | raw[pos + 1])
            pos += 2
            continue
        codes.append(first)
        pos += 1
    return codes


def render_text(
    text: str,
    encoder: TextEncoder,
    font: GameFont,
    entries_by_code: dict[int, FontMapEntry],
    output: str | Path,
    *,
    max_columns: int = 24,
    scale: int = 3,
    foreground: int = 0,
    background: int = 255,
) -> None:
    codes = text_to_codes(text, encoder)
    lines = wrap_codes(codes, entries_by_code, max_columns * LINE_HEIGHT)
    image = render_lines(
        lines, font, entries_by_code, scale=scale, foreground=foreground, background=background
    )
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
