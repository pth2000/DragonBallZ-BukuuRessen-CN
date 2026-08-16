# 第三方组件说明

仓库不提交完整字体文件。`tools/fetch_fonts.py` 会将以下固定版本下载至被 Git 忽略的 `work/vendor/`。发布说明应保留相应署名和许可信息。

## Ark Pixel Font / 方舟像素字体

- 上游：[TakWolf/ark-pixel-font](https://github.com/TakWolf/ark-pixel-font)
- 固定提交：`417febb32c2d84d326e8f9f8f289da2122461a00`
- 用途：剧情字库的主要 12px 简体中文字形
- 许可：字形采用 SIL Open Font License 1.1；上游工具代码采用 MIT License

## Fusion Pixel Font / 缝合像素字体

- 上游：[TakWolf/fusion-pixel-font](https://github.com/TakWolf/fusion-pixel-font)
- 发布版本：`2026.07.20`
- 文件：`fusion-pixel-font-12px-monospaced-bdf-v2026.07.20.zip`
- ZIP SHA-256：`aea98326638e138de8583f0ae87db9eb722b9f44519361a32e0ee9577b3c6586`
- 使用的 BDF SHA-256：`8e4a12e821efad608bcb464d685ce50c70693f85a1e95dead9575e6cecafffc7`
- 用途：剧情缺字回退和 12px 图片界面正文
- 许可：SIL Open Font License 1.1，并包含上游发布包列出的来源许可

## ZhengGeDianHei-16 / 正格点黑 16

- 上游：[yzdnn/ZhengGeDianHei-16](https://github.com/yzdnn/ZhengGeDianHei-16)
- 发布版本：`v1.0.0`
- 文件：`ZhengGeDianHei-16.ttf`
- SHA-256：`ca9d5d362b589ef2743c500b3099bd09b11e63058b8f29d374f1f7e3e59d606c`
- 用途：资料模式 16px 分类标题
- 许可：SIL Open Font License 1.1

## Python 依赖

- [Pillow](https://python-pillow.org/)：按其上游许可证提供
- [Capstone](https://www.capstone-engine.org/)：按其上游许可证提供

精确解析版本记录在 `uv.lock`。项目不重新许可任何第三方组件；如本说明与上游许可文件存在差异，以上游许可文件为准。
