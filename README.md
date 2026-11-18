# Little Snitch for macOS & Linux 官方安装包镜像

[GitHub Releases](https://github.com/LOVECHEN/littlesnitch-release/releases) · [English](#english)

自动归档 Objective Development 下载页公开提供的原始安装包，不修改包内容。每 6 小时检查一次，也可在 Actions 手动运行。安装包只放在 Releases，不进入 Git 历史。

## macOS 7 Beta

| 版本 | 安装包 | 校验 |
|---|---|---|
| [Beta 5（8020）](https://github.com/LOVECHEN/littlesnitch-release/releases/tag/mac-beta-7.0-8020) | [下载 DMG](https://github.com/LOVECHEN/littlesnitch-release/releases/download/mac-beta-7.0-8020/LittleSnitch-7.0-beta-8020.dmg) | [SHA-256](https://github.com/LOVECHEN/littlesnitch-release/releases/download/mac-beta-7.0-8020/SHA256SUMS.txt) |
| [Beta 1（8013）](https://github.com/LOVECHEN/littlesnitch-release/releases/tag/mac-beta-7.0-8013) | [下载 DMG](https://github.com/LOVECHEN/littlesnitch-release/releases/download/mac-beta-7.0-8013/LittleSnitch-7.0-beta-8013.dmg) | [SHA-256](https://github.com/LOVECHEN/littlesnitch-release/releases/download/mac-beta-7.0-8013/SHA256SUMS.txt) |

Beta 标记为预发布，不会出现在指向 macOS 正式版的 Latest 入口。其他构建见 [Beta Releases](https://github.com/LOVECHEN/littlesnitch-release/releases?q=mac-beta-)。

## 下载来源

| 平台 / 通道 | 官方来源 | 镜像 |
|---|---|---|
| macOS 正式版 | [Download](https://obdev.at/products/littlesnitch/download.html) | [最新正式版](https://github.com/LOVECHEN/littlesnitch-release/releases/latest) |
| macOS Nightly | [Nightly Builds](https://obdev.at/products/littlesnitch/download-nightly.html) | [Nightly Releases](https://github.com/LOVECHEN/littlesnitch-release/releases?q=mac-nightly-) |
| macOS 历史版本 | [Previous Versions](https://obdev.at/products/littlesnitch/download-previous-versions.html) | [Legacy Releases](https://github.com/LOVECHEN/littlesnitch-release/releases?q=mac-legacy-) |
| macOS 7 Beta | [Little Snitch 7 Beta](https://obdev.at/products/littlesnitch7-beta/index.html) | [Beta 直达下载](#macos-7-beta) |
| Linux 正式版 | [Download](https://obdev.at/products/littlesnitch-linux/download.html) | [Linux Stable](https://github.com/LOVECHEN/littlesnitch-release/releases?q=linux-stable-) |
| Linux 预发布 | [Pre-release Downloads](https://obdev.at/products/littlesnitch-linux/download-prerelease.html) | [Linux Pre-release](https://github.com/LOVECHEN/littlesnitch-release/releases?q=linux-prerelease-) |

macOS 保留官网 DMG 和早期 `.dmg.gz`。Linux 保留官网列出的所有架构和格式，包括 DEB、RPM、Arch 包和静态 tarball，以及官方哈希清单与原始 Sigstore 签名。自动归档只采集官网实际链接，不推测下载地址。

另外，[6.3.3](https://github.com/LOVECHEN/littlesnitch-release/releases/tag/mac-stable-6.3.3)、[6.4.1](https://github.com/LOVECHEN/littlesnitch-release/releases/tag/mac-stable-6.4.1)、[6.5 Nightly（7300）](https://github.com/LOVECHEN/littlesnitch-release/releases/tag/mac-nightly-6.5-7300) 和 [7 Beta 1（8013）](https://github.com/LOVECHEN/littlesnitch-release/releases/tag/mac-beta-7.0-8013) 由此前从官网下载的本地备份补录。文件没有修改，发布前均通过 Objective Development 签名校验；Release 注明了来源。

每个 Release 附带使用下载文件名的 `SHA256SUMS.txt`，可用 `shasum -a 256 -c SHA256SUMS.txt` 校验。发布前先验证 Linux 官方哈希清单的 Sigstore 签名，再逐包比对 SHA-256。macOS 检查 DMG 格式并计算镜像 SHA-256，不将其标为官方校验值。

## English

An independent mirror of unmodified Little Snitch installers for macOS and Linux. The scheduled workflow checks six official download pages every six hours. Four older macOS builds were backfilled from locally preserved official downloads after verifying the vendor signature; their release notes identify this provenance. Each release includes a SHA-256 manifest. Linux releases also retain and verify the upstream signed manifest and Sigstore bundle. Latest points to macOS Stable; use the [Beta download table](#macos-7-beta) for Beta DMGs.
