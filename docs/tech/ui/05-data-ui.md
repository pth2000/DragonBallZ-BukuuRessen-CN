# 资料模式界面

资料模式的 4 张帮助页与分类选择页。

```text
romdata/data/HelpJA.bin        帮助页，256×256 A3I5 线性纹理
romdata/data/DataSubScrJA.bin  分类页，4bpp NBFC/NBFS 背景
```

## 本地化范围

帮助页 4 张：必杀技（含连射型、蓄力型和究极必杀技）、特殊能力、支援角色、团队必杀技。

分类页包含“请选择要查看的项目”提示，以及必杀技、特殊能力、支援和团队必杀技四个分类项。

`CANCEL / EXIT` 等风格化英文按钮、图标和边框保持不变。

## 排版

帮助页正文与“请选择要查看的项目”使用 Fusion Pixel Font 12px，左对齐。

分类标题使用正格点黑 16 的原生 16px 简体点阵。分类标题在原版中即为大字号，缩放 12px 字形会产生明显的锯齿与断笔。

必杀技帮助页的三组标题与正文均自 `x=23` 起始，图标右缘至文字主体保留与日版一致的 3 像素净间距。

## 约束

除[通用约束](README.md#重绘约束)外，分类标题的重绘仅清除旧文字所使用的亮色像素，棕色框线作为受保护像素逐点校验。若按矩形整体清空，黑色清除区域会覆盖边框。

## 数据与构建

译文位于 `data/translation/ui_data_help.tsv` 和 `ui_data_menu.tsv`。

```powershell
uv run python tools/build_data_ui.py
```

产物输出至 `build/ui_data_test/`。

本阶段需额外指定字体：`--help-bdf` 与 `--menu-bdf` 使用 Fusion 12px，`--menu-label-font` 使用正格点黑 16。字体来源与许可见[第三方声明](../../../THIRD_PARTY_NOTICES.md)。
