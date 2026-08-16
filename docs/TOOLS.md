# 工具参考

所有命令均从项目根目录执行。

常用入口：

| 任务 | 命令 |
| --- | --- |
| 完整发布构建 | `uv run python tools/build_release.py <rom>` |
| 下载固定版本字体 | `uv run python tools/fetch_fonts.py` |
| 运行核心测试 | `uv run python -m unittest discover -s tests -v` |
| 检查公开目录 | `uv run python tools/check_public_tree.py` |
| 检查发布元数据 | `uv run python tools/check_release_metadata.py` |
| 检查术语一致性 | `uv run python tools/check_glossary.py` |

所有中文图片界面通过共享 BDF UI 加载器绘字。加载器会按 BDF 的全局字框与单字 `BBX` 偏移统一纵向基线，并将中文全角 `！` 映射为 6px 窄体 UI 字形；各界面构建器不再维护单字基线或感叹号补丁。

## `tools/build_release.py`

完整正式构建入口：

```powershell
uv run python tools/build_release.py <原版 ROM>
```

它按固定顺序调用剧情和全部界面构建器，输出本地最终 ROM、正式 BPS、`SHA256SUMS.txt` 和发布清单。默认删除阶段产物；调试时使用 `--keep-intermediates`。字体可用 `tools/fetch_fonts.py` 准备。

## `tools/fetch_fonts.py`

下载并校验 `THIRD_PARTY_NOTICES.md` 指定版本的 Ark、Fusion 和正格点黑字体：

```powershell
uv run python tools/fetch_fonts.py
```

所有文件写入被 Git 忽略的 `work/vendor/`。

## `tools/check_public_tree.py`

检查源码范围内是否残留 ROM、缓存、完整提取物、旧快照、异常大文件，以及本机文件系统路径（盘符、`/home/`、`/Users/`）：

```powershell
uv run python tools/check_public_tree.py
```

## `tools/check_glossary.py`

校验[术语表](GLOSSARY.md)与翻译表的一致性：同一原名没有多个译名、表中译名仍出现在翻译数据里、角色名嵌在招式名内部时写法一致。

```powershell
uv run python tools/check_glossary.py
```

## `tools/check_release_metadata.py`

校验 README、安装文档、项目状态和 `dist/` 补丁中的文件名与哈希是否与 `project.json` 一致：

```powershell
uv run python tools/check_release_metadata.py
```

## `tools/verify_stages.py`

改动界面构建器后，确认输出与已知良好的基线逐字节一致。先做一次完整构建并保留中间产物，记录各阶段哈希，之后即可单独重跑任意阶段比对：

```powershell
uv run python tools/build_release.py <原版 ROM> `
  --output-root build/baseline --dist-dir build/baseline/dist --keep-intermediates
uv run python tools/verify_stages.py --record
uv run python tools/verify_stages.py                 # 全部阶段
uv run python tools/verify_stages.py maximum data    # 指定阶段
```

比对范围包括 ROM、阶段资源、构建报告和预览图。

## `tools/render_showcase.py`

生成[成果展示](SHOWCASE.md)使用的日/英/中对照图，包括剧情文本条和图片界面纹理：

```powershell
uv run python tools/render_showcase.py
```

## `tools/prepare_baseline.py`

将项目自带的字库基线 BPS 应用到原始 ROM。

```powershell
uv run python tools/prepare_baseline.py original.nds
```

可指定输出：

```powershell
uv run python tools/prepare_baseline.py original.nds --output work/baseline.nds
```

## `tools/extract_all.py`

提取 96 个脚本和六语言文本。

```powershell
uv run python tools/extract_all.py original.nds work/extracted
```

输出：

```text
scripts_decompressed/
plain_text/
multilingual_raw_text.tsv
extraction_report.json
```

## `tools/check_translation.py`

在构建前检查译文，同时输出校对用的日中对照。

```powershell
uv run python tools/check_translation.py <原版 ROM>
```

报告写入 `build/translation_check.tsv`，逐条给出字节容量、实际用量、剩余量、缺字状态，以及从所给 ROM 中读出的日文原文。公开翻译表不含原文，这是校对时获取对照的方式。

可用 `--translation` 指定其他译文表，`--output` 指定报告位置。

## `tools/build_rom.py`

完整构建：

```powershell
uv run python tools/build_rom.py original.nds
```

新增字形：

```powershell
uv run python tools/build_rom.py original.nds --ark-font-repo work/vendor/ark-pixel-font
```

常用选项：

```text
--translation PATH
--ark-font-repo PATH
--ark-size 10|12|16
--output PATH
--patch PATH
--update-map
```

`--update-map` 会把新分配的编码写回项目的 `custom_glyph_map.tsv`。建议先不使用，检查 `build/generated_custom_glyph_map.tsv` 后再决定是否提交。

## `tools/preview_text.py`

使用 ROM 中的真实字库渲染文本：

```powershell
uv run python tools/preview_text.py build/DBZ_Bukuu_Ressen_CN.nds `
  "悟空\n好强大的气……" `
  --map build/generated_custom_glyph_map.tsv
```

输出：

```text
build/text_preview.png
```

选项：

```text
--columns N
--scale N
--output PATH
--map PATH
```

## `tools/inspect_rom.py`

查看 ROM 版本、脚本包条目、字库包和 ARM9 映射。加 `--dump-font-map` 可将映射表导出为 TSV：

```powershell
uv run python tools/inspect_rom.py original.nds
uv run python tools/inspect_rom.py original.nds --dump-font-map
```

## `tools/apply_bps.py`

纯 Python 应用 BPS：

```powershell
uv run python tools/apply_bps.py original.nds patch.bps output.nds
```

## `tools/make_bps.py`

从两个文件生成 BPS：

```powershell
uv run python tools/make_bps.py original.nds translated.nds output.bps
```

项目生成器只使用 SourceRead 和 TargetRead，因此补丁不一定是理论最小，但稳定、可校验。

## 界面构建器

12 个界面各有一个构建器和若干渲染工具。它们的命令、输入表和输出目录记录在对应的界面页中，与该界面的资源结构写在一处：[图片界面](tech/ui/README.md)。

正式构建由 `build_release.py` 按固定顺序调用全部界面构建器，通常无需单独运行。
## 快捷脚本

`scripts/` 提供常用命令的轻量包装。脚本会先切换到仓库根目录，再调用对应的 Python 工具。

| 操作 | Windows | Linux / macOS |
| --- | --- | --- |
| 检查 uv 并同步依赖 | `scripts\setup_windows.bat` | `scripts/setup_unix.sh` |
| 完整发布构建 | `scripts\build_release.bat <rom>` | `scripts/build_release.sh <rom>` |
| 构建前检查译文 | `scripts\check_translation.bat <rom>` | `scripts/check_translation.sh <rom>` |

`<rom>` 为日版源 ROM 路径。包装脚本不增加构建逻辑，与对应的 `uv run python tools/...` 命令等价。

## 可选外部工具

- Floating IPS：图形界面应用 BPS。
- melonDS：主要测试模拟器。
- DeSmuME：第二模拟器交叉验证。
- NitroPaint：处理 NCGR/NCLR/NSCR/NCER/NFTR 和图片资源。
- Tinke/TinkeDSi：浏览 NDS ROM 文件树和常见资源。
- NitroPacker：通用 NDS 拆包/重打包。
- Kuriimu2：若后续要制作专用文本插件，可作为 UI 框架。

本项目的剧情和字库是自定义格式，通用工具不能直接代替这里的 Python 转换层。
