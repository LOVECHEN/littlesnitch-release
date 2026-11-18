# Little Snitch for macOS & Linux 官方安装包镜像

[GitHub Releases](https://github.com/LOVECHEN/littlesnitch-release/releases) · [English](#english)

自动归档 Objective Development 下载页公开提供的原始安装包，不修改包内容。每 6 小时检查一次，也可在 Actions 手动运行。安装包只放在 Releases，不进入 Git 历史。

| 平台 / 通道 | 官方来源 | 镜像 |
|---|---|---|
| macOS 正式版 | [Download](https://obdev.at/products/littlesnitch/download.html) | [最新正式版](https://github.com/LOVECHEN/littlesnitch-release/releases/latest) |
| macOS Nightly | [Nightly Builds](https://obdev.at/products/littlesnitch/download-nightly.html) | [Nightly Releases](https://github.com/LOVECHEN/littlesnitch-release/releases?q=mac-nightly-) |
| macOS 历史版本 | [Previous Versions](https://obdev.at/products/littlesnitch/download-previous-versions.html) | [Legacy Releases](https://github.com/LOVECHEN/littlesnitch-release/releases?q=mac-legacy-) |
| macOS 7 Beta | [Little Snitch 7 Beta](https://obdev.at/products/littlesnitch7-beta/index.html) | [Beta Releases](https://github.com/LOVECHEN/littlesnitch-release/releases?q=mac-beta-) |
| Linux 正式版 | [Download](https://obdev.at/products/littlesnitch-linux/download.html) | [Linux Stable](https://github.com/LOVECHEN/littlesnitch-release/releases?q=linux-stable-) |
| Linux 预发布 | [Pre-release Downloads](https://obdev.at/products/littlesnitch-linux/download-prerelease.html) | [Linux Pre-release](https://github.com/LOVECHEN/littlesnitch-release/releases?q=linux-prerelease-) |

macOS 保留官网 DMG 和早期 `.dmg.gz`。Linux 保留官网列出的所有架构和格式，包括 DEB、RPM、Arch 包和静态 tarball，以及官方哈希清单与原始 Sigstore 签名。历史版本只采集官网实际链接；不会推测未列出的下载地址。

每个 Release 附带使用下载文件名的 `SHA256SUMS.txt`，可用 `shasum -a 256 -c SHA256SUMS.txt` 校验。发布前先验证 Linux 官方哈希清单的 Sigstore 签名，再逐包比对 SHA-256。macOS 检查 DMG 格式并计算镜像 SHA-256，不将其标为官方校验值。

## English

An independent mirror of unmodified Little Snitch installers for macOS and Linux, sourced from the six official pages above. The scheduled workflow checks every six hours and archives only explicitly linked packages. Each release includes a SHA-256 manifest; Linux releases also retain and verify the upstream signed checksum manifest and Sigstore bundle. The repository's Latest release points to macOS Stable; use the channel links above for Linux and previews.
