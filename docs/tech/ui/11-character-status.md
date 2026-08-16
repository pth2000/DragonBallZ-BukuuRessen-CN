# 角色状态页招式

剧情路线角色状态页中的已获得招式名称。

```text
romdata/scene/common/cstatus_bg.bin
```

该包内含六种语言、15 条可用路线和 1 张未解锁占位页。

## 本地化范围

15 条剧情路线，共 76 个已获得的特殊能力、究极技和团队必杀技名称。

译名逐项复用剧情主表中的“获得招式”提示，确保剧情、状态页和[资料模式角色卡](12-character-data.md)中的同名招式保持一致。

以下内容保持原样：顶部 `Gokou / Gohan / Vegeta` 等英文或罗马字角色名、`Map Clear` 标题及路线进度、六边形图表、黄黑边框、灰色未解锁槽、未解锁的 `???` 页面，以及其他五种语言。

日版角色选择页和剧情头像名牌经逐项核对，本身即为英文或罗马字美术，按风格保留策略不予重绘。

## 排版

使用 Fusion Pixel Font 12px，固定写入原有的 16 像素高列表行。中文全角叹号在本页使用原界面风格的窄版叹号字形。

## 约束

除[通用约束](README.md#重绘约束)外，本界面追加以下检查：15 条路线的槽位与 76 项翻译数量完全匹配；每项中文名称均能放入原列表行；仅 30 个日文 NBFC/NBFS 条目及 `cstatus_bg.bin` 发生变化。

## 数据与构建

译文位于 `data/translation/ui_character_status_moves.tsv`。

```powershell
uv run python tools/build_character_status_moves.py
```

产物输出至 `build/ui_character_status_test/`，含 15 组日/英/中预览。
