# 界面资源审计

日版 ROM 中包含 23 组成对的 `JA/US` 区域界面资源。审计逐组比较条目名、日美版像素和图块格式，以确定本地化范围。

仅本地化日版资源中的功能性日文。日版原生使用的英文或罗马字美术按设计保留，以维持原版视觉语言。

按文件名配对只能覆盖部分资源。`game/vsmode.bin` 将六种语言保存在同一个包内，没有独立的 `JA/US` 文件名，因此不在这 23 组之列，需要逐条检查包内条目名后缀才能发现。

## 已本地化

| 资源 | 内容 | 保留部分 |
| --- | --- | --- |
| `modeselect/ModeSelectSubScrExplanationJA.bin` | 9 项模式说明 | 英文标题 |
| `option/OptSubTxtJA.bin` | 6 项选项说明 | 选项标签 |
| `stageselect/StageSelectSubScrBGJA.bin` | 16 张场景名称与说明 | 场景大标题 |
| `scene/common/prcselect.bin` | 2 张练习选择说明 | `COURSE SELECT / Training / Tutorial` 标签 |
| `scene/common/tutorial.bin` | 15 张教学章节说明 | 黄字 `TRAINING / TUTORIAL` |
| `data/HelpJA.bin` | 4 张帮助页 | 原图标 |
| `data/DataSubScrJA.bin` | 资料模式提示与分类项 | `CANCEL / EXIT` 按钮 |
| `opening/OpnSaveLoadJA.bin` | 存档损坏与初始化提示 | 窗口边框、其他动画状态 |
| `scene/maptitle_jp_tex.bin` | 19 条路线、232 个标题 | 方块图标、分隔线、空槽、占位标题 |
| `game/vsmode.bin` | 3 段联机说明 + 4 项连接提示 | `VS BATTLE` 标题、连接图标 |
| `scene/common/clearevent.bin` | 14 张通知正文 + 1 张 DP 小提示 | 黄色通关横幅 |
| `scene/common/maxselect.bin` | 3 段难度说明 | `NOVICE / HARD / MANIA RANK` 黄字标题 |
| `scene/common/cstatus_bg.bin` | 15 条路线的 76 个招式名 | 角色名、`Map Clear`、图表、未解锁槽 |
| `data/DataModeDataImage.bin` | 37 个角色组、195 项资料卡 | 英文栏目、罗马字名、能量值、按键图标 |

各资源的结构与重绘细节见对应页面，入口在[本目录索引](README.md)。

## 已审计并保留

**`scene/common/pausemenu.bin`**　14 张剧情与教学暂停页的日版和英文版资源逐字节相同，内容为 `Pause Menu / Continue / Return to...` 等风格化英文。日版从未本地化过这部分。

**`game/result.bin`**　只有 `e/f/g/i/s` 五组地区资源，不存在日文组。结果、难度和按钮均为原版风格化英文美术。

**角色选择确认与取消、模式与场景大标题、选项标签**　日美版解压条目逐项相同，属于英文按钮或标题美术。

**角色选择名称与剧情头像名牌**　日版资源本身使用 `Gokou / Vegeta / Piccolo` 等英文或罗马字，属于角色名牌美术。

**制作人员名单**　不在本地化计划内。

## 复现方法

```powershell
uv run python tools/audit_regional_ui.py     # build/regional_ui_audit.json
uv run python tools/render_regional_nb.py    # NBFC/NBFS 背景预览
uv run python tools/render_regional_nt.py    # NTFT 纹理预览
```

两个渲染工具均输出至 `build/regional_ui_previews/`，可用于逐组核对日美版差异。

## 未纳入范围

角色选择中的其他动态文字与状态提示、许可画面等低优先级资源目前保持原样，后续计划见[路线图](../../ROADMAP.md)。
