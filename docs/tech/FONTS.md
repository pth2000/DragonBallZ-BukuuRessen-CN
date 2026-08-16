# 字库工作流

## 字库集成模型

游戏使用：

- 自定义 Shift-JIS 风格编码表；
- 6 页 2bpp NTFT 像素纹理；
- ARM9 中固定的编码到纹理矩形映射。

因此，每个实际使用的中文字符都必须转换为点阵，并写入可用编码槽。

## 字形来源

当前流程以方舟像素字体 12px PNG 为主要来源。

方舟缺少的简体字使用 Fusion Pixel Font 12px `zh_hans` BDF 回退。当前全文共有 32 个回退字形；Fusion Pixel Font 与方舟字体均使用 OFL-1.1。

BDF 读取必须同时处理全局 `FONTBOUNDINGBOX` 和单字 `BBX` 的纵向偏移。Fusion 中少数字形使用 `12×14, y=-3` 的扩展字框；加载器会按共同基线裁入 `12×12, y=-2` 字框，不应再使用逐字 `-1px` 偏移修正。

工程不包含字体文件。取得源码后目录应含：

```text
assets/glyphs/12/
```

构建器会递归寻找：

```text
<Unicode 十六进制> zh_cn.png
<Unicode 十六进制>.png
```

优先简体地区字形。

## 字形映射

```text
data/mapping/custom_glyph_map.tsv
```

每行表示：

```text
中文字符 → 被借用的 Shift-JIS 编码 → 字库页和矩形
```

例如 `只` 借用原“短”的槽 `925A`。编码只是在游戏内部作为索引，不表示翻译意义。

## 编码槽分配

候选清单：

```text
data/mapping/font_slots.tsv
```

当前稳定译文使用的确定性候选计划：

```text
data/mapping/full_cn_reusable_slots.tsv
```

状态：

- `custom_baseline`：当前已占用；
- `legacy_reusable`：基线字库中已被改过，但当前文本未使用，优先回收；
- `candidate_requires_test`：原剧情脚本未使用的 page 5 槽，可候选；
- `used_original_script`：日文剧情使用，不可覆盖；
- `reserved`：不自动分配；
- `reusable_full_cn`：针对当前 3,100 条中文译文扫描并排序的可回收槽。

未在剧情脚本中出现的槽仍可能被菜单、overlay 或硬编码文字使用。所有新槽都必须在游戏中验证。

## 导入规则

普通汉字：

- 目标矩形：15×15；
- 建议墨迹框：11×11；
- 左上偏移：`x=2, y=1`；
- 仅索引 1 为前景；
- 禁止灰度抗锯齿。

标点：

- 逗号、句号等按底部对齐；
- 引号、括号需要分别测试；
- 不应简单居中。

## 缺字处理

如果方舟 12px 没有某字：

1. 尝试方舟公共字形或 10/16px；
2. 尝试其他开放像素字体，只提取该字；
3. 手工绘制 11×11 PNG；
4. 调整译文，改用更清晰的同义词。

手工 PNG 只需透明背景和不透明前景。构建器会转为 1bpp 逻辑掩码再写入 2bpp 页面。

## 持久化新映射

首次构建不加 `--update-map`：

```powershell
uv run python tools/build_rom.py <原版 ROM> `
  --ark-font-repo work/vendor/ark-pixel-font `
  --fallback-bdf work/vendor/fusion-pixel-font/12px-monospaced-bdf-v2026.07.20/fusion-pixel-12px-monospaced-zh_hans.bdf
```

检查：

```text
build/generated_custom_glyph_map.tsv
build/build_report.json
```

确认编码和显示后，再使用 `--update-map` 写回项目配置，或手工合并。

## 字库容量

当前 ARM9 映射表共有 1,659 个字符槽。稳定译文包含 1,501 个唯一字符，其中 606 个使用原生编码，895 个使用自定义映射。候选计划提供 887 个可回收双字节槽，实际占用 858 个，保留 29 个余量；`8345` 和 `8B5B` 因可执行文件中的保守文本命中而排除。

映射计划绑定当前翻译 TSV 快照。新增用字前必须重新检查原生编码冲突和剩余槽位，不能直接复用旧的优先级结论。

后续扩充译文时仍应：

- 复用原生日文汉字；
- 统一术语，减少同义字；
- 避免生僻复杂字；
- 分批测试新槽是否影响其他界面。
