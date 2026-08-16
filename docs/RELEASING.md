# 发布流程

仓库本身不维护版本号，发布通过 GitHub Release 进行。补丁与哈希的唯一配置源为 `project.json`。

## 准备环境

```powershell
uv sync --frozen
uv run python tools/fetch_fonts.py
uvx ruff check src tools tests
uv run python -m unittest discover -s tests -v
uv run python tools/check_public_tree.py
uv run python tools/check_release_metadata.py
uv run python tools/check_glossary.py
```

确认源 ROM 的游戏代码、容量和 SHA-256 与 `project.json` 完全一致。

## 构建发布产物

```powershell
uv run python tools/build_release.py <原版 ROM>
```

构建器依次执行剧情、字库和全部界面阶段，生成本地测试 ROM，再从源 ROM 直接生成 BPS。阶段预览、ROM 和补丁默认在成功后删除；需要诊断时使用 `--keep-intermediates`。

## 译文改动后更新哈希

任何改变最终 ROM 的译文或资源改动都会改变目标 ROM 与补丁哈希。此时构建器会在哈希校验处中止并给出实际值，据此更新 `project.json` 的 `release_target_sha256` 和 `release_patch_sha256`，再重新构建确认通过。

`tools/check_release_metadata.py` 会检查文档中记录的哈希是否与 `project.json` 一致。

## 验证

- `dist/release_manifest.json` 中的源 ROM、目标 ROM 和 BPS 哈希与 `project.json` 一致。
- `tools/apply_bps.py` 能从干净源 ROM 回放 BPS，并得到预期目标 SHA-256。
- [测试规范](TESTING.md)中的模拟器验证已完成。
- 正式发布至少完成一次真实硬件或烧录卡验证。
- `tools/check_public_tree.py`、`tools/check_release_metadata.py` 和 `tools/check_glossary.py` 均通过。

## 创建 GitHub Release

版本号由 Release 标签确定，仓库内不记录。Release 附件仅包含：

```text
DBZ_Bukuu_Ressen_CN.bps
SHA256SUMS.txt
release_manifest.json
```

不得上传 `.nds`、存档、完整字体、完整提取资源或阶段补丁。Release 说明至少应包含：

- 主要变更；
- 支持的源 ROM 版本及 SHA-256；
- 目标 ROM 与 BPS 的 SHA-256；
- 已知问题和测试环境；
- 第三方字体署名。
