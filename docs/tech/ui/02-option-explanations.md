# 选项说明

选项菜单下屏的 6 项说明文本。

```text
romdata/option/OptSubTxtJA.bin
```

与[模式选择说明](01-mode-explanations.md)同构的 NBFC/NBFP/NBFS 背景资源，美版对应 `OptSubTxtUS.bin`。

## 本地化范围

6 项全部汉化：时间限制、游戏难度、伤害、背光灯、制作人员、选项模式。

带档位的说明保留原版的档位列举格式，用全角省略号连接：

```text
设置对战的时间限制。
ON……有时间限制
OFF……无时间限制
```

```text
调整游戏难度。
1……简单
2……普通
3……困难
```

## 排版

正文区域为 `(16, 68) – (240, 140)`，行高 15 像素，前景使用原调色板索引 7。定位方式与模式选择说明一致。

## 数据与构建

译文位于 `data/translation/ui_option_explanations.tsv`。

```powershell
uv run python tools/build_option_explanations.py
```

产物输出至 `build/ui_option_test/`。
