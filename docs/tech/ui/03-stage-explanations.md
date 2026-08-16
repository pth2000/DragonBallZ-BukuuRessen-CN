# 场景选择说明

16 个对战场景的名称与说明。

```text
romdata/stageselect/StageSelectSubScrBGJA.bin
```

## 资源结构

16 个场景各含 NBFC、NBFP、NBFS 三部分，并按游戏状态重复五组，共 240 个压缩条目。

## 本地化范围

16 个场景的名称和说明全部汉化。

## 排版

场景名称沿用原界面的左对齐位置，在标题黑条内按可见笔画垂直居中，笔画中心与原版同为 `y=32`。

说明文本按可见笔画整体居中、块内各行左对齐。说明的中心线依据 16 张原版纹理统一校准至 `y=104`，对应实机上棕色说明框的中心。

标题使用原调色板索引 4，说明使用索引 1。

## 约束

除[通用约束](README.md#重绘约束)外，重建时仅替换各场景的 NBFC 与 NBFS，全部 NBFP 调色板保持不变。

## 数据与构建

译文位于 `data/translation/ui_stage_explanations.tsv`。

```powershell
uv run python tools/build_stage_explanations.py
```

产物输出至 `build/ui_stage_test/`，包括测试 ROM、相对原版的 BPS、单项日/英/中预览、总览图和构建校验报告。
