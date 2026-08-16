# MAXIMUM 难度说明

```text
romdata/scene/common/maxselect.bin
```

该包内含六种语言的等级标题、说明页和课程选择贴图。

## 本地化范围

3 段难度说明：

| 等级 | 说明 |
| --- | --- |
| `NOVICE RANK` | MAXIMUM 模式的入门等级 |
| `HARD RANK` | 面向高手、难度有所提升 |
| `MANIA RANK` | 面向高手、难度设定得更高 |

黄字 `NOVICE RANK / HARD RANK / MANIA RANK` 属于原版风格化标题美术，保持不变。其他五种语言、课程标题、光标、调色板和非目标图块同样保持原样。

MAXIMUM 的 60 个挑战标题不在本阶段，属于[地图标题](07-map-titles.md)。

## 排版

三张日文说明正文使用 Fusion Pixel Font 12px 重绘，按可见笔画整体居中、块内多行左对齐。正文区域为 `(24, 80) – (232, 128)`，前景使用原调色板索引 7。

## 数据与构建

译文位于 `data/translation/ui_maximum_explanations.tsv`。

```powershell
uv run python tools/build_maximum_explanations.py
```

产物输出至 `build/ui_maximum_test/`，含日/英/中三栏预览。
