"""Custom Japanese font archive, ARM9 map, and Ark glyph import helpers."""
from __future__ import annotations

import struct
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .archive import PackedArchive


class FontError(ValueError):
    pass


UI_GLYPH_ALIASES = {"！": "!"}


@dataclass(frozen=True)
class FontMapEntry:
    index: int
    page: int
    code: int
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0 + 1

    @property
    def height(self) -> int:
        return self.y1 - self.y0 + 1

    @property
    def native_character(self) -> str:
        try:
            raw = bytes((self.code,)) if self.code <= 0xFF else self.code.to_bytes(2, "big")
            return raw.decode("shift_jis")
        except (UnicodeDecodeError, ValueError):
            return ""


def find_font_map(arm9: bytes) -> tuple[int, list[FontMapEntry]]:
    signature = struct.pack("<6H", 0, 0x21, 0, 0, 8, 14)
    search_pos = 0
    while True:
        start = arm9.find(signature, search_pos)
        if start < 0:
            break
        entries: list[FontMapEntry] = []
        pos = start
        previous_code = -1
        valid = True
        while pos + 12 <= len(arm9):
            page, code, x0, y0, x1, y1 = struct.unpack_from("<6H", arm9, pos)
            if page == 2 and code == 1 and x0 == y0 == x1 == y1 == 0:
                break
            if not (
                page <= 5
                and code > previous_code
                and x0 <= x1 <= 255
                and y0 <= y1 <= 255
                and x1 - x0 <= 15
                and y1 - y0 <= 15
            ):
                valid = False
                break
            entries.append(FontMapEntry(len(entries), page, code, x0, y0, x1, y1))
            previous_code = code
            pos += 12
        if valid and len(entries) > 1500:
            return start, entries
        search_pos = start + 1
    raise FontError("ARM9 font mapping table was not found")


def shift_jis_code(character: str) -> int:
    raw = character.encode("shift_jis")
    if len(raw) == 1:
        return raw[0]
    if len(raw) == 2:
        return int.from_bytes(raw, "big")
    raise FontError(f"unsupported Shift-JIS sequence for {character!r}")


class GameFont:
    PAGE_WIDTH = 256
    PAGE_HEIGHT = 256
    PAGE_BYTES = 0x4000

    def __init__(self, archive_data: bytes):
        self.archive = PackedArchive(archive_data)
        page_names = [name for name in self.archive.names() if name.endswith(".ntft")]
        if len(page_names) != 6:
            raise FontError(f"expected 6 NTFT pages, found {len(page_names)}")
        self.page_names = page_names
        self.pages = [bytearray(self.archive.unpack(name)) for name in page_names]
        for index, page in enumerate(self.pages):
            if len(page) != self.PAGE_BYTES:
                raise FontError(f"font page {index} has unexpected size {len(page)}")
        self.changed_pages: set[int] = set()

    @staticmethod
    def _offset(x: int, y: int) -> tuple[int, int]:
        if not (0 <= x < 256 and 0 <= y < 256):
            raise FontError(f"pixel coordinate out of range: {x}, {y}")
        byte_offset = y * 64 + x // 4
        shift = (x % 4) * 2
        return byte_offset, shift

    def get_pixel(self, page: int, x: int, y: int) -> int:
        offset, shift = self._offset(x, y)
        return (self.pages[page][offset] >> shift) & 3

    def set_pixel(self, page: int, x: int, y: int, value: int) -> None:
        if not 0 <= value <= 3:
            raise FontError("2bpp pixel must be 0..3")
        offset, shift = self._offset(x, y)
        mask = 3 << shift
        self.pages[page][offset] = (self.pages[page][offset] & ~mask) | (value << shift)
        self.changed_pages.add(page)

    def clear_entry(self, entry: FontMapEntry) -> None:
        for y in range(entry.y0, entry.y1 + 1):
            for x in range(entry.x0, entry.x1 + 1):
                self.set_pixel(entry.page, x, y, 0)

    def copy_entry_from(self, source: GameFont, entry: FontMapEntry) -> None:
        """Restore one mapped rectangle from another font with identical pages."""
        for y in range(entry.y0, entry.y1 + 1):
            for x in range(entry.x0, entry.x1 + 1):
                value = source.get_pixel(entry.page, x, y)
                if self.get_pixel(entry.page, x, y) != value:
                    self.set_pixel(entry.page, x, y, value)

    def import_mask(
        self,
        entry: FontMapEntry,
        mask: list[list[bool]],
        *,
        ink_x: int = 2,
        ink_y: int = 1,
        ink_width: int = 11,
        ink_height: int = 11,
        punctuation: bool = False,
        top_aligned: bool = False,
        left_aligned: bool = False,
    ) -> None:
        fitted = fit_mask(
            mask,
            ink_width,
            ink_height,
            punctuation=punctuation,
            top_aligned=top_aligned,
            left_aligned=left_aligned,
        )
        self.clear_entry(entry)
        for y, row in enumerate(fitted):
            for x, foreground in enumerate(row):
                if foreground:
                    px = entry.x0 + ink_x + x
                    py = entry.y0 + ink_y + y
                    if px <= entry.x1 and py <= entry.y1:
                        self.set_pixel(entry.page, px, py, 1)

    def build(self) -> bytes:
        for page in sorted(self.changed_pages):
            self.archive.replace_unpacked(self.page_names[page], bytes(self.pages[page]))
        return self.archive.build()


def _bounding_box(mask: list[list[bool]]) -> tuple[int, int, int, int] | None:
    points = [(x, y) for y, row in enumerate(mask) for x, value in enumerate(row) if value]
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def text_block_ink_bounds(
    lines: Iterable[str],
    masks: dict[str, list[list[bool]]],
    line_height: int,
) -> tuple[int, int, int, int] | None:
    """Return the visible-ink bounds of a left-aligned multiline text block."""
    bounds: tuple[int, int, int, int] | None = None
    for line_index, line in enumerate(lines):
        cursor_x = 0
        cursor_y = line_index * line_height
        for character in line:
            mask = masks[character]
            glyph_bounds = _bounding_box(mask)
            if glyph_bounds is not None:
                gx0, gy0, gx1, gy1 = glyph_bounds
                placed = (
                    cursor_x + gx0,
                    cursor_y + gy0,
                    cursor_x + gx1,
                    cursor_y + gy1,
                )
                if bounds is None:
                    bounds = placed
                else:
                    bounds = (
                        min(bounds[0], placed[0]),
                        min(bounds[1], placed[1]),
                        max(bounds[2], placed[2]),
                        max(bounds[3], placed[3]),
                    )
            cursor_x += len(mask[0]) if mask else 0
    return bounds


def centered_text_block_origin(
    rect: tuple[int, int, int, int],
    lines: Iterable[str],
    masks: dict[str, list[list[bool]]],
    line_height: int,
) -> tuple[int, int]:
    """Place visible ink at the center of ``rect`` while retaining left alignment."""
    materialized_lines = list(lines)
    bounds = text_block_ink_bounds(materialized_lines, masks, line_height)
    x0, y0, x1, y1 = rect
    if bounds is None:
        return x0 + (x1 - x0) // 2, y0 + (y1 - y0) // 2
    ink_x0, ink_y0, ink_x1, ink_y1 = bounds
    ink_width = ink_x1 - ink_x0
    ink_height = ink_y1 - ink_y0
    if ink_width > x1 - x0 or ink_height > y1 - y0:
        raise FontError("visible text block does not fit the selected rectangle")
    visible_x = x0 + (x1 - x0 - ink_width) // 2
    visible_y = y0 + (y1 - y0 - ink_height) // 2
    return visible_x - ink_x0, visible_y - ink_y0


def _resize_nearest(mask: list[list[bool]], width: int, height: int) -> list[list[bool]]:
    source_height = len(mask)
    source_width = len(mask[0]) if source_height else 0
    if not source_width or not source_height:
        return [[False] * width for _ in range(height)]
    return [
        [mask[min(source_height - 1, y * source_height // height)][min(source_width - 1, x * source_width // width)] for x in range(width)]
        for y in range(height)
    ]


def fit_mask(
    mask: list[list[bool]],
    width: int,
    height: int,
    *,
    punctuation: bool = False,
    top_aligned: bool = False,
    left_aligned: bool = False,
) -> list[list[bool]]:
    bbox = _bounding_box(mask)
    canvas = [[False] * width for _ in range(height)]
    if bbox is None:
        return canvas
    x0, y0, x1, y1 = bbox
    cropped = [row[x0:x1] for row in mask[y0:y1]]
    source_width = x1 - x0
    source_height = y1 - y0
    scale = min(1.0, width / source_width, height / source_height)
    target_width = max(1, round(source_width * scale))
    target_height = max(1, round(source_height * scale))
    if target_width != source_width or target_height != source_height:
        cropped = _resize_nearest(cropped, target_width, target_height)
    if punctuation:
        offset_x = min(1, width - target_width) if left_aligned else max(0, width - target_width - 1)
        offset_y = 0 if top_aligned else max(0, height - target_height)
    else:
        offset_x = (width - target_width) // 2
        offset_y = (height - target_height) // 2
    for y in range(target_height):
        for x in range(target_width):
            if cropped[y][x]:
                canvas[offset_y + y][offset_x + x] = True
    return canvas


def find_ark_glyph(ark_root: str | Path, character: str, *, size: int = 12, locale: str = "zh_cn") -> Path:
    root = Path(ark_root)
    codepoint = f"{ord(character):04X}"
    base = root / "assets" / "glyphs" / str(size)
    if not base.exists():
        raise FontError(f"Ark glyph directory not found: {base}")
    candidates = list(base.rglob(f"{codepoint}*.png"))
    if not candidates:
        raise FontError(f"Ark Pixel Font has no {size}px glyph for {character} U+{codepoint}")

    def priority(path: Path) -> tuple[int, int, str]:
        name = path.stem
        if name == f"{codepoint} {locale}":
            rank = 0
        elif name == codepoint:
            rank = 1
        elif locale in name:
            rank = 2
        else:
            rank = 3
        return rank, len(path.parts), str(path)

    return sorted(candidates, key=priority)[0]


def load_png_mask(path: str | Path) -> list[list[bool]]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise FontError("Pillow is required for PNG glyph import: pip install Pillow") from exc
    image = Image.open(path).convert("RGBA")
    pixels = list(image.getdata())
    has_transparency = any(alpha < 255 for _, _, _, alpha in pixels)
    mask: list[list[bool]] = []
    for y in range(image.height):
        row: list[bool] = []
        for x in range(image.width):
            red, green, blue, alpha = image.getpixel((x, y))
            if has_transparency:
                row.append(alpha > 0)
            else:
                row.append((red + green + blue) / 3 < 128)
        mask.append(row)
    return mask


def load_bdf_masks(path: str | Path, characters: Iterable[str]) -> dict[str, list[list[bool]]]:
    """Load selected Unicode glyph masks from a text BDF in one pass."""
    requested = {ord(character): character for character in characters}
    result: dict[str, list[list[bool]]] = {}
    if not requested:
        return result

    font_height: int | None = None
    font_y_offset = 0
    encoding: int | None = None
    width = height = 0
    glyph_y_offset = 0
    bitmap_rows: list[str] | None = None
    # BDF control records are ASCII, but some fonts (including GNU Unifont)
    # include UTF-8 contributor names in comments or properties.  Replacing
    # non-ASCII bytes is safe because those lines are not parsed as glyph data.
    with Path(path).open("r", encoding="ascii", errors="replace") as handle:
        for raw_line in handle:
            # Some generators emit trailing spaces after records such as
            # ``BITMAP``; whitespace is not meaningful in BDF control lines.
            line = raw_line.strip()
            if line.startswith("FONTBOUNDINGBOX "):
                _, _, raw_height, _, raw_y_offset = line.split()[:5]
                font_height = int(raw_height)
                font_y_offset = int(raw_y_offset)
            elif line.startswith("ENCODING "):
                encoding = int(line.split()[1])
            elif line.startswith("BBX "):
                width, height, _, glyph_y_offset = map(int, line.split()[1:5])
            elif line == "BITMAP":
                bitmap_rows = []
            elif line == "ENDCHAR":
                if encoding in requested and bitmap_rows is not None:
                    if len(bitmap_rows) != height:
                        raise FontError(
                            f"BDF glyph U+{encoding:04X} has {len(bitmap_rows)} rows, expected {height}"
                        )
                    mask: list[list[bool]] = []
                    for row_text in bitmap_rows:
                        bit_count = len(row_text) * 4
                        value = int(row_text, 16)
                        mask.append(
                            [bool(value & (1 << (bit_count - 1 - x))) for x in range(width)]
                        )
                    if font_height is not None:
                        # BDF bitmap rows are stored top-to-bottom, while BBX
                        # offsets are measured from the baseline.  Normalize
                        # every glyph into the font-wide vertical cell so
                        # oversize fallback glyphs do not render lower than
                        # ordinary glyphs that share the same baseline.
                        target = [[False] * width for _ in range(font_height)]
                        target_y = (
                            font_y_offset
                            + font_height
                            - glyph_y_offset
                            - height
                        )
                        for source_y, source_row in enumerate(mask):
                            canvas_y = target_y + source_y
                            if 0 <= canvas_y < font_height:
                                target[canvas_y] = source_row
                        mask = target
                    result[requested[encoding]] = mask
                encoding = None
                width = height = 0
                glyph_y_offset = 0
                bitmap_rows = None
            elif bitmap_rows is not None:
                bitmap_rows.append(line)
    return result


def ui_glyph_character(character: str) -> str:
    """Return the shared display glyph used by localized bitmap interfaces."""
    return UI_GLYPH_ALIASES.get(character, character)


def load_ui_bdf_masks(
    path: str | Path, characters: Iterable[str]
) -> dict[str, list[list[bool]]]:
    """Load UI glyphs with shared punctuation aliases and BDF baseline handling."""
    requested = list(dict.fromkeys(characters))
    display_characters = [ui_glyph_character(character) for character in requested]
    display_masks = load_bdf_masks(path, display_characters)
    return {
        character: display_masks[display]
        for character, display in zip(requested, display_characters)
        if display in display_masks
    }
