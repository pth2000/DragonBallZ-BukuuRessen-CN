# 安装补丁

项目发布物是 BPS 差分补丁。安装时需要日版游戏和支持 BPS 格式的补丁工具。

## 准备源 ROM

补丁仅适用于日版 Rev 0：

```text
游戏代码   ADBJ
文件大小   67,108,864 字节（64 MiB）
SHA-256    a18a79f4da2bc3d836645714092ec7c8b38ad53160078e26b854329d7fc9923e
```

其他版本 ROM 均不兼容。

### 校验源文件

Windows PowerShell：

```powershell
Get-FileHash "DBZ_Bukuu_Ressen.nds" -Algorithm SHA256
```

macOS 或 Linux：

```bash
shasum -a 256 DBZ_Bukuu_Ressen.nds
```

输出须与上方 SHA-256 一致。

## 下载发布文件

从项目 Releases 页面下载：

```text
DBZ_Bukuu_Ressen_CN.bps
```

## 应用补丁

推荐使用 Floating IPS（flips）；beat、MultiPatch 等支持 BPS 的工具也可使用。

1. 打开补丁工具并选择 **Apply Patch**。
2. 选择下载的 `.bps` 文件。
3. 选择经过校验的源 `.nds` 文件。
4. 指定输出文件，例如 `DBZ_Bukuu_Ressen_CN.nds`。
5. 等待工具报告补丁应用成功。


## 运行

推荐使用 melonDS、DeSmuME 等模拟器进行测试。


## 常见问题

### 补丁工具报告源文件不匹配

确认所选文件是日版 Rev 0 的 `.nds`，而不是欧版、裁剪 ROM 或已修改 ROM。重新核对[源文件哈希](#校验源文件)。


### 部分内容仍为英文

这是项目的既定范围。标题、Logo、角色罗马字名牌、`ARTS / SPECIAL` 等栏目名和通关横幅在日版中属于英文美术，因此按原版保留；制作人员名单也不在本地化范围内。详见[项目状态](STATUS.md)。


## 反馈

请按[贡献指南](../CONTRIBUTING.md)提交 Issue，并注明路线或界面、复现步骤和测试环境。
