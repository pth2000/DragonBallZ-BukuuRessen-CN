# 贡献指南

欢迎提交译文校对、术语修正、像素字形与界面排版、构建工具、测试和技术文档方面的改进。为便于审查和复现，请保持每个变更范围明确，并在提交前完成相应验证。

## 开发环境

需要 Python 3.10+、[uv](https://docs.astral.sh/uv/) 和 Git。

```powershell
uv sync --frozen
uvx ruff check src tools tests
uv run python -m unittest discover -s tests -v
uv run python tools/check_public_tree.py
uv run python tools/check_release_metadata.py
uv run python tools/check_glossary.py
```

以上五项检查与 CI 一致，均不需要 ROM。

完整构建需要自行准备 `project.json` 指定的日版 Rev 0 ROM，并下载经过版本锁定的字体。把 ROM 放在约定位置 `work/original/` 可让多数辅助工具省略路径参数，详见[构建流程](docs/BUILDING.md)：

```powershell
uv run python tools/fetch_fonts.py
uv run python tools/build_release.py <原版 ROM>
```

## 提交原则

- 一个 Pull Request 应集中解决一个明确问题。
- 保留既有文件格式、稳定 ID 和字段顺序，避免无关的批量格式化。
- 工具行为发生变化时，应补充或更新自动化测试。
- 影响最终 ROM 的变更必须报告源 ROM、输出 ROM 和 BPS 的 SHA-256。
- 像素界面变更必须注明页面、测试环境和修改理由，并提供必要的原版对照。

## 翻译变更

- 剧情译文位于 `data/translation/story_zh.tsv` 的 `简体中文` 列。
- 界面译文位于 `data/translation/ui_*.tsv`。
- TSV 使用 UTF-8 和 Tab 分隔；游戏内换行写成字面量 `\n`。
- 新译名应遵循[术语表](docs/GLOSSARY.md)和现有官方简体中文风格。
- 风格化英文、Logo、角色罗马字名和制作人员名单默认不修改。
- 新增字符时必须检查字形来源、编码槽和游戏内显示。

改动前后都应运行 `tools/check_translation.py`。它同时输出日文原文和字节余量，剧情文本采用定长写回，译文超出原命令预留空间会导致构建失败。

改动影响最终 ROM 时，完整构建会在哈希校验处中止——这是预期行为，因为记录的发布哈希只对应未修改的译文。用 `--allow-hash-change` 重新构建即可得到产物并打印新哈希，在 PR 中报告这两个值：

```powershell
uv run python tools/build_release.py <原版 ROM> --allow-hash-change
```

详细规则见[翻译规范](docs/TRANSLATION.md)。

## 文档变更

- 先说明用途和结论，再补充实现细节与背景。
- 面向玩家、贡献者和维护者的内容分别放入[文档索引](docs/README.md)对应分组。
- 正文使用简体中文和中文标点；命令、路径、字段名和代码标识符使用反引号。
- 技术文档记录稳定格式、约束和验证方式，不保留无助于复现的过程日志。
- 版本号和哈希以 `project.json` 为准，修改后运行 `tools/check_release_metadata.py`。
- 示例使用仓库相对路径或明确的占位符，不写入本机绝对路径。

## 提交前检查

```powershell
uvx ruff check src tools tests
uv run python -m unittest discover -s tests -v
uv run python tools/check_public_tree.py
uv run python tools/check_release_metadata.py
uv run python tools/check_glossary.py
```

若变更影响 ROM 输出，还应运行相关阶段构建；准备发布的变更必须执行完整发布构建和[测试规范](docs/TESTING.md)中的人工验证。

## 内容边界

Issue、Pull Request、提交记录和附件中不得包含：

- 原始或已打补丁的 ROM；
- 存档、Save State 或 ROM dump；
- 完整提取的游戏代码、文本、图像或音频；
- 未获许可再分发的完整字体；
- 私钥、访问令牌、本机用户名或无关的绝对路径。

复现问题时，请提供资源路径、界面名称、预期结果、实际结果和必要的工具输出，不要上传受版权保护的完整资源。

## 许可

提交代码即表示同意按 [MIT License](LICENSE) 提供有权许可的代码贡献。提交原创中文译文或项目文档即表示同意按 [LEGAL.md](LEGAL.md) 所述的 CC BY-NC-SA 4.0 条款提供相关内容。请勿提交无权再分发的第三方材料。
