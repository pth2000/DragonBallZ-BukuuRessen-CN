# 图片界面技术说明

剧情对白以文本数据存储在脚本中，并由游戏字库渲染。菜单、说明、标题和资料卡则在打包阶段预渲染为像素，运行时不存在可编辑的文字层，因此必须按纹理格式重绘。

本目录记录各界面的资源结构、像素布局、文字区域和构建约束。

## 界面一览

| # | 界面 | 资源 | 规模 |
| ---: | --- | --- | --- |
| 01 | [模式选择说明](01-mode-explanations.md) | `modeselect/ModeSelectSubScrExplanationJA.bin` | 9 项 |
| 02 | [选项说明](02-option-explanations.md) | `option/OptSubTxtJA.bin` | 6 项 |
| 03 | [场景选择说明](03-stage-explanations.md) | `stageselect/StageSelectSubScrBGJA.bin` | 16 项 |
| 04 | [练习模式](04-practice.md) | `scene/common/prcselect.bin`、`tutorial.bin` | 17 项 |
| 05 | [资料模式界面](05-data-ui.md) | `data/HelpJA.bin`、`DataSubScrJA.bin` | 帮助页 4 张 + 分类页 |
| 06 | [存档提示](06-save-prompts.md) | `opening/OpnSaveLoadJA.bin` | 1 段 × 2 状态 |
| 07 | [地图标题](07-map-titles.md) | `scene/maptitle_jp_tex.bin` | 232 个标题 / 66 张纹理 |
| 08 | [联机对战界面](08-versus.md) | `game/vsmode.bin` | 7 项 |
| 09 | [解锁与通关通知](09-clear-messages.md) | `scene/common/clearevent.bin` | 15 项 |
| 10 | [MAXIMUM 难度说明](10-maximum.md) | `scene/common/maxselect.bin` | 3 段 |
| 11 | [角色状态页招式](11-character-status.md) | `scene/common/cstatus_bg.bin` | 76 个招式名 |
| 12 | [资料模式角色卡](12-character-data.md) | `data/DataModeDataImage.bin` | 195 项 / 37 角色组 |

编号即构建顺序，每个阶段均在前一阶段的产物 ROM 上继续构建。哪些资源纳入汉化范围、哪些经审计后保留原样，见[界面资源盘点](resource-audit.md)。

## 资源形态

目标界面使用以下三种像素组织方式。

### NBFC / NBFP / NBFS 背景

01、02、03、04、08、09、10、11 均采用这一形式，由三个文件组成：

```text
*.nbfc   无文件头的 4bpp、8×8 字符图块
*.nbfp   16 色 BGR555 调色板
*.nbfs   32×32、每项 16 位的图块地图
```

图块地图记录每个位置对应的字符数据块，两者互相引用，因此修改文字时必须同时替换 `NBFC` 与 `NBFS`，只替换其一会导致错位。

此外，这类资源大多按界面状态重复五组，同名条目的解压内容相同。若只替换其中一组，界面在部分状态下仍会显示原始日文。

### 线性 NTFT 纹理

07 和 12 采用这一形式，为固定宽度的 4bpp 线性像素，偏移计算如下：

```text
byte_offset = y * (width // 2) + x // 2
```

它并非常见的 8×8 图块重排。若按图块顺序解码，原本集中于局部的修改会呈现为散布至整张纹理，容易被误判为修改范围失控。

### A3I5 纹理

05 的帮助页采用这一形式，256×256，每字节 5 位索引加 3 位 alpha。

三种格式的字节级定义见[资源格式](../FORMATS.md)。

## 排版规则

以下各条适用于全部界面，各页仅记录自身的例外。

正文统一使用 Fusion Pixel Font 12px 简体 BDF。唯一例外是资料模式的分类标题，该处使用正格点黑 16 的原生 16px 点阵，因为放大 12px 字形会产生锯齿与断笔。

文本块在目标区域内居中时，依据实际可见笔画的包围盒。字框含空白边与基线留白，按字框居中会产生可见偏移。块内各行共用同一条左边界。

中文全角 `！` 映射为原版窄体 UI 字形。全角标点在 16 像素行高内占用过多横向空间，且会使同一画面出现两套标点风格。

风格化的英文标题、Logo、罗马字人物名、按键图标与边框美术均不重绘，判定依据见[界面资源盘点](resource-audit.md)。

字形来源与编码槽分配见[字体工作流](../FONTS.md)。

## 重绘约束

纹理格式本身无法表达文字区域的语义，因此构建器通过显式断言限制修改范围。以下任一条件不成立时，构建立即中止：

1. **修改范围受限**。仅声明过的文字矩形允许变化，边框、图标与调色板逐点比对。
2. **回读一致**。重打包后解压回来的纹理内容，须与写入时逐像素相同。
3. **不影响其他文件**。相对上一阶段 ROM，仅本阶段的目标资源发生变化。
4. **补丁可还原**。相对原版 ROM 生成的 BPS，应用后须完整还原构建产物。
5. **不影响其他语言**。多语言资源包中的 `e/f/g/i/s` 五组保持原始解压内容。

各页的“约束”一节仅列出该界面追加的条件。

## 单独构建某个界面

正式构建见[构建与工作链](../../BUILDING.md)。调试时可单独构建单个界面，但构建器默认以**上一阶段的产物 ROM** 为基准，需先完成前序阶段。

```powershell
uv run python tools/build_map_titles.py
```

常用参数有三个：`--base-rom` 指定基准 ROM，`--source-rom` 指定原版 ROM（用于生成 BPS 和日文对照），`--output-dir` 指定输出位置。

每个构建器均产出测试 ROM、相对原版的 BPS、日/英/中三栏预览和一份构建报告。

## 构建器的结构

各阶段共享参数解析、ROM 校验、字形加载、资源写回、BPS 回放、文件差异检查和哈希记录。公共实现位于 [`src/dbzbr/uistage.py`](../../../src/dbzbr/uistage.py)，`tools/build_*.py` 仅保留各界面特有的像素处理逻辑。

改动构建器后，用 `tools/verify_stages.py` 确认输出与已知良好的基线逐字节一致。比对范围包括预览图。用法见[工具参考](../../TOOLS.md)。
