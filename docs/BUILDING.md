# 构建流程

## 准备源 ROM

构建需要一份自行准备的日版 Rev 0 备份。ROM 位置任意，命令行传入路径即可。

项目同时约定了一个默认位置：

```text
work/original/DBZ_Bukuu_Ressen_ADBJ_Rev0.nds
```

`render_*.py` 系列、`audit_regional_ui.py` 和 12 个界面构建器的 `--source-rom` 都以此为默认值，可省略路径参数；`build_release.py` 和 `inspect_rom.py` 仍需显式传入 ROM。

本文档其余示例中的 `<原版 ROM>` 均指该路径。

## 构建入口

完整构建使用以下命令，`<原版 ROM>` 替换为实际路径：

```powershell
uv run python tools/fetch_fonts.py
uv run python tools/build_release.py <原版 ROM>
```

该命令从干净原 ROM 开始，按“剧情字库 → 模式 → 选项 → 场景 → 练习 → 资料帮助 → 存档 → 地图标题 → 联机 → 通关通知 → MAXIMUM → 角色状态 → 角色资料卡”的固定顺序构建。最终从原 ROM 直接生成 BPS，并校验源、目标、补丁哈希及 BPS 回放。阶段 ROM、阶段补丁和预览默认在成功后删除。

## 验证源 ROM

构建前必须验证：

```text
ADBJ / Rev 0 / 64 MiB
SHA-256 a18a79f4da2bc3d836645714092ec7c8b38ad53160078e26b854329d7fc9923e
```

不同 dump、裁剪 ROM、已打补丁 ROM 和其他地区版均不受支持。

## 读取 NDS 文件系统

工具从 NDS 头部读取：

- FNT：文件名和目录树；
- FAT：每个文件在 ROM 中的起止地址。

关键资源：

```text
romdata/scene/script.bin
romdata/scene/font_jp.bin
```

替换资源时优先在原地址写入并修改 FAT 结束位置。如果资源超过原文件到下一文件之间的空间，构建器会把它搬到 ROM 尾部未使用区，并更新 FAT 起止地址。

## 维护翻译表

公开剧情表 `data/translation/story_zh.tsv` 只保留稳定 ID、脚本定位字段、opcode 和简体中文构建输入。界面表同样只保留资源定位字段及实际写入内容，避免把完整原文提取物或内部审校记录纳入发布源码。

日文脚本使用 Shift-JIS 风格编码；行内换行是字面量 `\n`，游戏脚本中对应字节 `5C 6E`。表格字段与编辑规则见 [TRANSLATION.md](TRANSLATION.md)。

## 编码与字形

简体字通过借用未使用的 Shift-JIS 编码槽写入，字形从开源像素字体导入为点阵。编码槽分配、字形来源、导入规则和缺字处理见[字库工作流](tech/FONTS.md)。

## 定长写回剧情

构建器不改变命令长度、剧情块起点或脚本总长度。

对每条译文：

1. 编码中文；
2. 检查是否超过文本容量；
3. 更新有效字节数字段；
4. 写入文字区域；
5. 剩余区域补零；
6. 保留其余指令数据和块偏移。

如果超长，构建器停止并报告，不会自动截断。

## 重压缩与重打包

- 修改后的剧情脚本使用 LZ10 重新压缩。
- 修改后的 NTFT 页使用 RLE 0x30 重新压缩。
- 未修改条目保留原压缩数据，减少差异和风险。
- 包条目的 packed size 和 relative offset 自动重算。

## 替换 NDS 文件

生成的新资源写入 ROM：

- 原位置容量充足：保持起始地址，仅更新 FAT 结束地址。
- 原位置容量不足：按对齐要求搬移至 ROM 尾部空白区，并更新 FAT 起止地址。

ROM 总容量保持 64 MiB。

## 生成 BPS

项目自带的 BPS 生成器使用：

- SourceRead；
- TargetRead；
- Source/Target/Patch CRC32。

生成后立即重新应用补丁，并与输出 ROM 逐字节比较。

## 验证

构建成功只说明结构约束成立，不代表显示正确。模拟器与真实硬件的验证范围见[测试规范](TESTING.md)。

## 构建角色资料卡

角色资料卡使用独立的 4bpp 线性 NTFT，不经过剧情字库。维护 `data/translation/ui_character_data.tsv` 后运行：

```powershell
uv run python tools/build_character_data.py
```

每次扩展角色时应检查日/英/中预览，并在模拟器中逐项翻页，重点确认长团队技名、按键图标前的留白、特殊能力说明和相邻角色切换。
