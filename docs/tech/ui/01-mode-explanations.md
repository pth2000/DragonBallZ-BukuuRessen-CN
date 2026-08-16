# 模式选择说明

模式选择下屏的 9 项说明文本。

```text
romdata/modeselect/ModeSelectSubScrExplanationJA.bin
```

## 资源结构

该包共有 150 个压缩条目：9 项说明各含 NBFC、NBFP、NBFS 三部分，并按界面状态重复五组。同名条目的解压内容相同，因此重打包时必须整组替换同名的 `NBFC` 与 `NBFS`，否则界面在部分状态下仍显示原始日文。

## 本地化范围

9 项全部汉化：`Z-BATTLE`、`STORY MODE`、`VS BATTLE`、`MAXIMUM`、`???`、`FREE BATTLE`、`PRACTICE`、`DATA FILE`、`OPTION`。

标题本身为英文图像，保持不变，仅替换日文说明正文。以 `STORY MODE` 为例：

```text
体验各角色专属的故事。
既有忠于原作的剧情，
也有角色强化等原创IF故事，
内容丰富多彩！
```

## 排版

按整段多行文本的可见笔画包围盒在正文区域内水平、垂直居中，块内各行共用同一条左边界。

该定位方式是图片界面的通用规则，详见[排版规则](README.md#排版规则)。

## 数据与构建

译文位于 `data/translation/ui_mode_explanations.tsv`。

```powershell
uv run python tools/build_mode_explanations.py
```

产物输出至 `build/ui_mode_test/`。默认批量重建 9 项，传入 `--entry story` 可只构建单项。

构建器会重新解码修改后的图块、确认调色板与 ROM 中其余文件未变，并生成相对原版 ROM 的完整 BPS 及日/英/中三栏预览。
