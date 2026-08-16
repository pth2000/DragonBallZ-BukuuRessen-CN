## 变更摘要

简述本次变更及其目的。

## 变更范围

- [ ] 翻译或术语
- [ ] 字形或界面排版
- [ ] 构建工具
- [ ] 测试
- [ ] 文档

## 验证

- [ ] `uvx ruff check src tools tests`
- [ ] `uv run python -m unittest discover -s tests -v`
- [ ] `uv run python tools/check_public_tree.py`
- [ ] `uv run python tools/check_release_metadata.py`
- [ ] `uv run python tools/check_glossary.py`
- [ ] 已完成受影响页面或路线的模拟器/实机检查（如适用）
- [ ] 已报告最终 ROM/BPS 哈希变化（如适用）

测试环境与结果：

## 内容与许可确认

- [ ] 本 PR 不包含 ROM、存档、Save State 或完整游戏资源。
- [ ] 本 PR 不包含无权再分发的字体或其他第三方内容。
- [ ] 我有权按项目许可提供本次贡献。
