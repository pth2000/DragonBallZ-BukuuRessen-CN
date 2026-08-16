"""Optional integration test.

Set DBZ_BUKUU_ROM to the exact original ADBJ ROM path before running.
No ROM is bundled with the project.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from dbzbr.archive import PackedArchive
from dbzbr.bps import apply_patch
from dbzbr.build import BuildOptions, build_project, read_tsv, write_tsv
from dbzbr.nds import NDSRom

ROOT = Path(__file__).resolve().parents[1]
BASELINE_TRANSLATIONS = {
    "1857": r"在与前来寻找龙珠的贝吉塔交战时，\n悟空的伙伴们接连负伤倒下。",
    "1858": r"悟空和比克\n与拥有可怕力量的贝吉塔对峙。",
    "1859": r"悟空\n好强大的气……\n这种家伙要是在地球上，\n地球会被毁掉的。",
    "1860": r"悟空\n界王拳两倍……\n不，只能提升到三倍了。",
    "1861": r"比克\n界王拳吗……\n居然学会了这么棘手的招式……\n不过我也开发了新招。",
    "1862": r"比克\n这招集气需要时间。\n你先和他战斗，\n把他的注意力引开。",
    "1863": r"贝吉塔\n你们在商量什么？\n区区下级战士，\n不可能打得过超级精英的我。",
    "1864": r"悟空\n明明是这种时候，\n我却兴奋起来了……！",
}


@unittest.skipUnless(os.environ.get("DBZ_BUKUU_ROM"), "DBZ_BUKUU_ROM is not set")
class RomIntegrationTests(unittest.TestCase):
    def test_initial_translation_matches_baseline_decompressed_resources(self):
        source_path = Path(os.environ["DBZ_BUKUU_ROM"])
        config = json.loads((ROOT / "project.json").read_text(encoding="utf-8"))
        source = source_path.read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), config["source_sha256"])
        baseline = apply_patch(source, (ROOT / config["baseline_patch"]).read_bytes())
        baseline_rom = NDSRom(baseline)
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            output = directory / "build.nds"
            patch = directory / "build.bps"
            baseline_translation = directory / "baseline_translation.tsv"
            baseline_mapping = directory / "baseline_custom_glyph_map.tsv"
            translation_rows = []
            for source_row in read_tsv(ROOT / config["translation_table"]):
                if source_row["ID"] not in BASELINE_TRANSLATIONS:
                    continue
                row = dict(source_row)
                row["简体中文"] = BASELINE_TRANSLATIONS[row["ID"]]
                translation_rows.append(row)
            self.assertEqual(len(translation_rows), 8)
            write_tsv(baseline_translation, translation_rows, list(translation_rows[0]))
            mapping_rows = []
            for slot in read_tsv(ROOT / "data/mapping/baseline_changed_slots.tsv"):
                if slot["status"] != "custom_active":
                    continue
                character = slot["assigned_character"]
                mapping_rows.append(
                    {
                        "character": character,
                        "unicode": f"U+{ord(character):04X}",
                        "code_hex": slot["code_hex"],
                        "native_slot_character": slot["native_slot_character"],
                        "page": slot["page"],
                        "x0": slot["x0"],
                        "y0": slot["y0"],
                        "x1": slot["x1"],
                        "y1": slot["y1"],
                        "punctuation": "yes" if character in "，。！？：；、“”‘’（）《》—…" else "no",
                        "source": "font-baseline",
                    }
                )
            self.assertEqual(len(mapping_rows), 44)
            write_tsv(baseline_mapping, mapping_rows, list(mapping_rows[0]))
            build_project(
                BuildOptions(
                    project_root=ROOT,
                    source_rom=source_path,
                    output_rom=output,
                    output_patch=patch,
                    translation_table=baseline_translation,
                    custom_glyph_map=baseline_mapping,
                )
            )
            built = NDSRom.from_file(output)
            self.assertEqual(
                built.get_file(config["font_path"]), baseline_rom.get_file(config["font_path"])
            )
            left = PackedArchive(built.get_file(config["script_path"]))
            right = PackedArchive(baseline_rom.get_file(config["script_path"]))
            self.assertEqual(left.names(), right.names())
            for name in left.names():
                self.assertEqual(left.unpack(name), right.unpack(name), name)


if __name__ == "__main__":
    unittest.main()
