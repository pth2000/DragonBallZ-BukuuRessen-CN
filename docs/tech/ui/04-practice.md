# 练习模式

练习模式入口与 15 张教学章节说明。

```text
romdata/scene/common/prcselect.bin
romdata/scene/common/tutorial.bin
```

## 资源结构

`prcselect.bin` 包含练习模式入口的 3 张标签纹理，以及“自由练习”和“操作教学”两张说明背景。

`tutorial.bin` 包含 15 张章节说明：移动、攻击、防御、支援攻击、交替、气力、追踪冲刺、防护罩防御、投技、气弹、气弹反射、特殊能力、必杀技、必杀技对决和团队必杀技。

`tutorial.bin` 自身包含六种语言，不属于成对命名的 `JA/US` 资源，因此按文件名进行的区域审计不会发现它。构建器仅修改日文区域条目，英、法、德、意、西五组保持不变。

## 本地化范围

2 张练习选择说明与 15 张章节说明，共 17 项。

以下内容保持原样：`COURSE SELECT / Training / Tutorial` 大标题和选项标签的原始贴图、说明页顶部的黄字 `TRAINING / TUTORIAL` 图块、NBFP 与 NTFP 调色板。

## 排版

说明文本按可见笔画整体居中，块内各行左对齐。文本块锚点依据原版纹理校准至约 `(127, 103)`。

## 数据与构建

译文位于 `data/translation/ui_practice_explanations.tsv`。

```powershell
uv run python tools/build_practice_explanations.py
```

产物输出至 `build/ui_practice_test/`，包括测试 ROM、相对原版的 BPS、日/英/中三栏预览、两份重建资源和 `build_report.json`。

相对上一阶段的整合 ROM，仅 `prcselect.bin` 与 `tutorial.bin` 发生变化；相对原版 ROM，累计 7 个 NitroFS 文件发生变化。

原版纹理的日英对照可单独渲染，用于排版核对：

```powershell
uv run python tools/render_practice_ui.py    # build/practice_ui_audit/
```
