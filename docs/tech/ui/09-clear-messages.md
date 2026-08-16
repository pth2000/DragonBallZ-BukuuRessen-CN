# 解锁、通关与奖励通知

```text
romdata/scene/common/clearevent.bin
```

该包内含六种语言的通知正文，以及角色头像、窗口、龙珠图标和通关横幅。

## 本地化范围

14 张日文通知正文：

- DP 增加 1 点、2 点及达到上限；
- 困难、狂热等级解锁；
- MAXIMUM 课程与模式入口解锁；
- 魔人贝吉塔解锁，以及超级赛亚人贝吉塔的 R＋A 选择说明；
- 剧情、教学和 Z-BATTLE 的支援次数奖励。

另有 1 张独立的“DP 增加 1 点”1bpp 小提示纹理，合计 15 项。

## 保留的黄色横幅

日版的 8 张黄色横幅本身即为 `CONGRATULATIONS`、`ALL MAPS CLEAR`、`NOVICE RANK CLEAR` 等高度风格化英文，与海外版之间只存在时态和标点差异。这说明该部分在原版设计中就不属于本地化对象，因此按风格保留策略不予重绘。

角色头像、窗口、龙珠图标、调色板和其他语言组同样保持不变。

## 排版

正文使用 Fusion Pixel Font 12px。独立的 DP 小提示放大为 15px，以匹配原纹理的显示尺寸。文本块整体居中，块内多行左对齐。

## 数据与构建

译文位于 `data/translation/ui_clear_messages.tsv`。

```powershell
uv run python tools/build_clear_messages.py
```

产物输出至 `build/ui_clear_test/`，含 14 张正文、DP 小提示和保留英文横幅的对照预览。
