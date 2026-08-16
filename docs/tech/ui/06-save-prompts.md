# 存档提示

存档损坏与初始化提示。

```text
romdata/opening/OpnSaveLoadJA.bin
```

## 本地化范围

日版在两个重复状态中保存同一段提示，均已替换为：

```text
游戏数据已损坏。
将初始化游戏数据。
```

窗口美术与前三个动画状态保持不变。

该提示位于开机存档检查流程，因此两个重复状态必须同时更新。

## 数据与构建

译文位于 `data/translation/ui_save_prompts.tsv`。

```powershell
uv run python tools/build_save_prompts.py
```

产物输出至 `build/ui_save_test/`。该阶段的 ROM 与 BPS 包含构建链中位于其之前的全部改动。
