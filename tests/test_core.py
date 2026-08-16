from __future__ import annotations

import random
import tempfile
import unittest
from pathlib import Path

from dbzbr.bps import apply_patch, create_patch
from dbzbr.compression import lz10_compress, lz10_decompress, rl_compress, rl_decompress
from dbzbr.font import (
    FontMapEntry,
    centered_text_block_origin,
    fit_mask,
    load_bdf_masks,
    load_ui_bdf_masks,
    text_block_ink_bounds,
)
from dbzbr.nitro_bg import decode_4bpp_screen, encode_4bpp_screen
from dbzbr.preview import (
    SPACE_ADVANCE,
    SPACE_CODE,
    PreviewError,
    glyph_width,
    raw_to_codes,
    wrap_codes,
)


class CompressionTests(unittest.TestCase):
    def test_roundtrips(self):
        samples = [
            b"",
            b"A",
            b"ABC" * 200,
            b"\0" * 4096,
            bytes(range(256)) * 8,
            bytes(random.Random(1).randrange(256) for _ in range(4096)),
        ]
        for sample in samples:
            self.assertEqual(lz10_decompress(lz10_compress(sample)), sample)
            self.assertEqual(rl_decompress(rl_compress(sample)), sample)


class BPSTests(unittest.TestCase):
    def test_equal_and_changed_sizes(self):
        cases = [
            (b"abc", b"abc"),
            (b"abc", b"axc"),
            (b"abc", b"abcxyz"),
            (b"abcdef", b"ab"),
            (bytes(range(255)), bytes(range(254, -1, -1))),
        ]
        for source, target in cases:
            patch = create_patch(source, target, metadata=b"test")
            self.assertEqual(apply_patch(source, patch), target)


class FontTests(unittest.TestCase):
    def test_selected_bdf_glyph_loading(self):
        bdf = """STARTFONT 2.1
STARTCHAR u4E2D
ENCODING 20013
SWIDTH 1000 0
DWIDTH 4 0
BBX 4 2 0 0
BITMAP
90
60
ENDCHAR
ENDFONT
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.bdf"
            path.write_text(bdf, encoding="ascii")
            self.assertEqual(
                load_bdf_masks(path, ["中"])["中"],
                [[True, False, False, True], [False, True, True, False]],
            )

    def test_bdf_loading_accepts_utf8_properties_and_trailing_spaces(self):
        bdf = """STARTFONT 2.1
COPYRIGHT "Ælla"
STARTCHAR u4E2D
ENCODING 20013
SWIDTH 1000 0
DWIDTH 4 0
BBX 4 2 0 0
BITMAP 
90
60
ENDCHAR
ENDFONT
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.bdf"
            path.write_text(bdf, encoding="utf-8")
            self.assertEqual(
                load_bdf_masks(path, ["中"])["中"],
                [[True, False, False, True], [False, True, True, False]],
            )

    def test_bdf_glyphs_are_normalized_to_the_font_baseline(self):
        bdf = """STARTFONT 2.1
FONTBOUNDINGBOX 4 2 0 0
STARTCHAR u4E2D
ENCODING 20013
SWIDTH 1000 0
DWIDTH 4 0
BBX 4 4 0 -1
BITMAP
F0
90
60
F0
ENDCHAR
ENDFONT
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.bdf"
            path.write_text(bdf, encoding="ascii")
            self.assertEqual(
                load_bdf_masks(path, ["中"])["中"],
                [[True, False, False, True], [False, True, True, False]],
            )

    def test_ui_fullwidth_exclamation_uses_the_narrow_glyph(self):
        bdf = """STARTFONT 2.1
STARTCHAR exclamation
ENCODING 33
SWIDTH 500 0
DWIDTH 2 0
BBX 2 2 0 0
BITMAP
80
80
ENDCHAR
STARTCHAR fullwidth-exclamation
ENCODING 65281
SWIDTH 1000 0
DWIDTH 4 0
BBX 4 2 0 0
BITMAP
F0
F0
ENDCHAR
ENDFONT
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.bdf"
            path.write_text(bdf, encoding="ascii")
            self.assertEqual(
                load_ui_bdf_masks(path, ["！"])["！"],
                [[True, False], [True, False]],
            )

    def test_opening_punctuation_can_be_top_aligned(self):
        source = [
            [False, True, False],
            [True, False, True],
        ]
        fitted = fit_mask(
            source, 7, 7, punctuation=True, top_aligned=True
        )
        points = [
            (x, y)
            for y, row in enumerate(fitted)
            for x, value in enumerate(row)
            if value
        ]
        self.assertEqual(min(y for _, y in points), 0)
        self.assertEqual(max(x for x, _ in points), 5)

    def test_closing_punctuation_can_be_top_left_aligned(self):
        source = [
            [True, False, True],
            [False, True, False],
        ]
        fitted = fit_mask(
            source,
            7,
            7,
            punctuation=True,
            top_aligned=True,
            left_aligned=True,
        )
        points = [
            (x, y)
            for y, row in enumerate(fitted)
            for x, value in enumerate(row)
            if value
        ]
        self.assertEqual(min(x for x, _ in points), 1)
        self.assertEqual(min(y for _, y in points), 0)

    def test_em_dash_can_be_vertically_centered(self):
        source = [[True] * 11]
        fitted = fit_mask(source, 11, 11)
        ink_rows = [index for index, row in enumerate(fitted) if any(row)]
        self.assertEqual(ink_rows, [5])

    def test_text_block_centering_uses_visible_ink(self):
        masks = {
            "甲": [
                [False, False, False, False],
                [True, True, True, False],
                [True, False, True, False],
                [False, False, False, False],
            ],
            "乙": [
                [False, False, False, False],
                [False, True, True, False],
                [False, True, False, False],
                [False, False, False, False],
            ],
        }
        lines = ["甲乙", "甲"]
        self.assertEqual(text_block_ink_bounds(lines, masks, 5), (0, 1, 7, 8))
        self.assertEqual(
            centered_text_block_origin((10, 20, 30, 40), lines, masks, 5),
            (16, 25),
        )


class NitroBackgroundTests(unittest.TestCase):
    def test_4bpp_screen_roundtrip(self):
        pixels = [[0] * 256 for _ in range(256)]
        for y in range(17, 31):
            for x in range(23, 49):
                pixels[y][x] = (x + y) % 8
        characters, screen = encode_4bpp_screen(pixels)
        self.assertEqual(decode_4bpp_screen(characters, screen), pixels)

    def test_4bpp_192px_screen_roundtrip(self):
        pixels = [[0] * 256 for _ in range(192)]
        for y in range(71, 95):
            for x in range(35, 87):
                pixels[y][x] = (x * 3 + y) % 8
        characters, screen = encode_4bpp_screen(pixels)
        self.assertEqual(len(screen), 1536)
        self.assertEqual(decode_4bpp_screen(characters, screen), pixels)


class PreviewLayoutTests(unittest.TestCase):
    """Glyph advance follows the mapped rectangle, not a fixed full-width grid."""

    def setUp(self):
        # Single-byte glyphs are uniformly 9px wide in the ARM9 map; double-byte
        # ideographs are 15px.
        self.entries = {
            0x41: FontMapEntry(0, 0, 0x41, 0, 0, 8, 14),
            0x42: FontMapEntry(1, 0, 0x42, 9, 0, 17, 14),
            0x889F: FontMapEntry(2, 1, 0x889F, 0, 0, 14, 14),
        }

    def test_ascii_advances_by_its_own_width(self):
        self.assertEqual(glyph_width(0x41, self.entries), 9)
        self.assertEqual(glyph_width(0x889F, self.entries), 15)

    def test_space_advances_without_a_mapped_rectangle(self):
        self.assertNotIn(SPACE_CODE, self.entries)
        self.assertEqual(glyph_width(SPACE_CODE, self.entries), SPACE_ADVANCE)

    def test_unmapped_code_is_rejected(self):
        with self.assertRaises(PreviewError):
            glyph_width(0x9999, self.entries)

    def test_wrapping_uses_real_widths(self):
        # Six 9px glyphs fit in 54px; a seventh does not.
        lines = wrap_codes([0x41] * 7, self.entries, 54)
        self.assertEqual([len(line) for line in lines], [6, 1])

    def test_explicit_break_starts_a_new_line(self):
        lines = wrap_codes([0x41, None, 0x42], self.entries, 900)
        self.assertEqual(lines, [[0x41], [0x42]])

    def test_wrapped_line_does_not_start_with_a_space(self):
        lines = wrap_codes([0x41] * 6 + [SPACE_CODE, 0x42], self.entries, 54)
        self.assertEqual(lines, [[0x41] * 6, [0x42]])

    def test_raw_text_decodes_two_byte_codes_and_literal_breaks(self):
        # 5C 6E is the in-game line break, not 0A.
        raw = bytes([0x88, 0x9F, 0x5C, 0x6E, 0x41])
        self.assertEqual(raw_to_codes(raw), [0x889F, None, 0x41])


if __name__ == "__main__":
    unittest.main()
