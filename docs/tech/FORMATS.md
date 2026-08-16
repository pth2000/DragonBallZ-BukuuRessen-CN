# 文件格式

## 多语言剧情包

日版 ROM 的 `romdata/scene/script.bin` 包含 96 个脚本：

```text
6 种语言 × 16 个脚本
```

语言代码：

```text
jp en fr ge it sp
```

脚本代码：

```text
gok goh crr pic veg trk gtk gnu frz drg egh cel bmr col brl tut
```

文本数量：

| 语言 | 记录数 |
|---|---:|
| jp | 3,100 |
| en | 3,046 |
| fr | 3,041 |
| ge | 3,043 |
| it | 3,042 |
| sp | 3,040 |

各地区脚本的剧情块和指令并非完全一致，不能按行号强制对齐。英文仅作为翻译参考，日文脚本是构建定位的基准。

## 包格式

剧情包和字库包共用 76 字节条目结构。首个 `u32` 的语义尚未完全确认，重打包时原样保留。

剧情包头部长度为 `0x1C88`，对应 96 条。

字库包头部长度为 `0x021C`，对应 7 条：

```text
font_jp_00.ntft
font_jp_01.ntft
font_jp_02.ntft
font_jp_03.ntft
font_jp_04.ntft
font_jp_05.ntft
font.pltt
```

## 剧情包结构

`script.bin` 使用游戏自定义资源包，头部布局为：

```text
0x00  u32  未知标志/包类型
0x04  u32  头部总长度
0x08  76 字节 × 文件数
```

文件数：

```text
(header_size - 8) / 76
```

每个条目：

```text
char name[64]
u32  unpacked_size
u32  packed_size
u32  relative_offset
```

数据区从 `header_size` 开始，剧情脚本采用 LZ10。

## 剧情脚本结构

脚本文件头：

```text
u16 data_start
u16 block_count
```

随后为 `block_count` 个剧情块记录：

```text
u32 event_id
u32 relative_offset_from_data_start
```

剧情块内是连续指令：

```text
u8 opcode
u8 total_command_length
... payload ...
```

文字指令：

| Opcode | payload 内文字起始位置 | 命令起点到文字起点 |
|---|---:|---:|
| `12` | 6 | 8 |
| `14` | 6 | 8 |
| `13` | 14 | 16 |
| `17` | 14 | 16 |

文字起点前两个字节是当前文字的**有效字节数**，小端 `u16`。写回中文时必须同时更新，否则可能出现截断、残字或剧情异常。

## 压缩

### LZ10

标准 Nintendo DS 类型 `0x10`：

```text
byte 0    0x10
byte 1-3  解压长度，24 位小端
```

剧情脚本采用该格式。

### RLE 0x30

标准 Nintendo DS 类型 `0x30`：

```text
byte 0    0x30
byte 1-3  解压长度，24 位小端
```

- 控制字节 bit7=1：重复 run，长度 `(control & 0x7F) + 3`，随后 1 字节值。
- bit7=0：原样 run，长度 `(control & 0x7F) + 1`，随后为数据。

字库 NTFT 和调色板条目采用该格式。

## 剧情脚本细节

### 固定布局策略

程序可能还存在未识别的内部位置引用、预读缓存或事件索引，因此稳定方案是：

- 不改变任何命令长度；
- 不改变块偏移；
- 不改变解压脚本长度；
- 只更新有效文字长度字段和文字区。

### 文字长度字段

文字起点前 2 字节为有效文字字节数。写入中文时必须把该字段更新为中文编码长度；若只覆盖文字而不更新长度，运行结果不可靠。

### 换行

脚本中是 ASCII 两字节：

```hex
5C 6E
```

即文本中的 `\n`。

## 字库结构

### 页面

6 个 NTFT 页，每页：

```text
256 × 256 像素
2 bpp
16,384 字节
```

像素数据是**线性行排列**：

```text
byte_offset = y * 64 + x // 4
bit_shift   = (x % 4) * 2
```

不是常见的 8×8 tile 顺序。按 tile 解码会让少量实际修改看起来散布到大量字形。

### 映射表

位于 ARM9 相对偏移：

```text
0xC8978
```

构建器使用签名自动查找，不完全依赖固定地址。

有效记录：1,659 条，随后有终止记录。

每条 12 字节：

```text
u16 page
u16 code        # Shift-JIS 风格，按数值升序
u16 x0
u16 y0
u16 x1
u16 y1
```

绝大多数日文双字节字形矩形为 15×15；ASCII 字符可为较窄矩形。

完整表在：

```text
data/mapping/arm9_font_map.tsv
```

构建器不读取这张表，它在运行时按签名从 ROM 中扫出映射；仓库内的副本仅供格式研究参考，可随时由自备 ROM 重新导出：

```powershell
uv run python tools/inspect_rom.py <原版 ROM> --dump-font-map
```

### 颜色索引

原字库主要使用：

```text
0 = 透明/背景
1 = 字形
```

索引 2/3 会因游戏调色板和混合方式产生杂点或重影，因此构建器只使用 0/1。

### 原生墨迹范围

多数日文字形的有效笔画大致在 15×15 区域中的：

```text
x = 2..12
y = 1..11
```

将 14×14 字形铺满区域会超过实际字符步进和行距，产生横向、纵向重叠。

## 自定义槽状态

当前稳定译文使用 895 个唯一自定义映射：36 个沿用基线字形，827 个由方舟 12px 重绘，32 个由 Fusion 12px 简体 BDF 回退。候选计划实际占用 858 槽，尚余 29 槽。

查看：

```text
data/mapping/custom_glyph_map.tsv
data/mapping/baseline_changed_slots.tsv
data/mapping/font_slots.tsv
data/mapping/full_cn_reusable_slots.tsv
```

`97CA` 是原生“量”的槽，不可用于自定义字形；当前“只”使用原生字符为“短”的 `925A` 槽。构建器会先恢复全部必需的原生槽，再把冲突的简体字迁移到确定性安全计划中的新槽。
