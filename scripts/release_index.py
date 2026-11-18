"""Render the README download index from published GitHub Release assets."""

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote

from scripts.mirror import (
    CHECKSUMS, REPO, SOURCES, VERSION, list_releases, preview_releases_url, version_key,
)


START = "<!-- release-index:start -->"
END = "<!-- release-index:end -->"
BASE = f"https://github.com/{REPO}/releases"
SOURCES_BY_PREFIX = {source.prefix: source for source in SOURCES}
TAG = re.compile(rf"(?P<prefix>mac|linux)-(?P<channel>[a-z]+)-(?P<version>{VERSION})"
                 r"(?:-(?P<suffix>pre\d+|\d+))?")
CHANNELS = {
    "stable": "Stable", "legacy": "Legacy", "beta": "Beta",
    "nightly": "Nightly", "prerelease": "Pre-release",
}


@dataclass(frozen=True)
class Entry:
    tag: str
    platform: str
    channel: str
    version: str
    build: str
    packages: tuple[str, ...]

    @property
    def sort_key(self):
        version, pre, build = version_key((self.version, self.build))
        return version + (0,) * (4 - len(version)), pre, not self.build, build, self.tag

    @property
    def display_version(self):
        return f"{self.version} ({self.build})" if self.build else self.version

    @property
    def release_url(self):
        return f"{BASE}/tag/{self.tag}"

    def asset_url(self, name):
        return f"{BASE}/download/{self.tag}/{quote(name, safe='')}"

    @property
    def download_links(self):
        if self.platform == "linux":
            return f"[Packages]({self.release_url})"
        return " · ".join(f"[{'DMG.gz' if name.endswith('.gz') else 'DMG'}]"
                          f"({self.asset_url(name)})" for name in self.packages)


def parse_release(item):
    tag = item["tag_name"]
    match = TAG.fullmatch(tag)
    if item["draft"] or not match:
        return None
    platform, channel, version, suffix = match.groups()
    source = SOURCES_BY_PREFIX.get(f"{platform}-{channel}")
    if not source or item["prerelease"] != source.prerelease:
        return None
    if channel in {"nightly", "beta"}:
        if not suffix or not suffix.isdigit():
            return None
        build = suffix
    elif channel == "prerelease":
        if not suffix or not suffix.startswith("pre"):
            return None
        version += "-" + suffix
        build = ""
    else:
        if suffix:
            return None
        build = ""

    assets = sorted(asset["name"] for asset in item["assets"] if asset["state"] == "uploaded")
    extensions = (".dmg", ".dmg.gz") if platform == "mac" else (".deb", ".rpm", ".tar.gz", ".pkg.tar.zst")
    packages = tuple(name for name in assets if name.endswith(extensions))
    if CHECKSUMS not in assets or not packages:
        return None
    return Entry(tag, platform, channel, version, build, packages)


def render(releases):
    entries = sorted((entry for item in releases if (entry := parse_release(item))),
                     key=lambda entry: entry.sort_key, reverse=True)
    if not entries:
        raise ValueError("No complete published releases; refusing to clear the index")

    lines = []
    shortcuts = []
    for channel, title in (("beta", "macOS 7 Beta"), ("nightly", "macOS Nightly")):
        latest = next((entry for entry in entries
                       if (entry.platform, entry.channel) == ("mac", channel)), None)
        shortcuts.append((channel, title, latest))

    for channel, title, latest in sorted(
        shortcuts, key=lambda shortcut: shortcut[2].sort_key if shortcut[2] else (), reverse=True
    ):
        source = SOURCES_BY_PREFIX[f"mac-{channel}"]
        lines += [f"## {title}", "", f"[官方下载页]({source.url})"]
        if latest:
            lines[-1] += (f" · [镜像 {latest.display_version}]({latest.release_url})"
                          f" · {latest.download_links} · [SHA-256]({latest.asset_url(CHECKSUMS)})")
        lines[-1] += f" · [GitHub 全部 {CHANNELS[channel]}]({preview_releases_url(CHANNELS[channel])})"
        lines.append("")

    lines += ["## 按版本下载", ""]
    for platform, title in (("mac", "macOS"), ("linux", "Linux")):
        lines += [f"### {title}", "",
                  "| Version | Channel | Download | Checksums |",
                  "|---|---|---|---|"]
        for entry in entries:
            if entry.platform == platform:
                lines += [f"| [{entry.display_version}]({entry.release_url}) | {CHANNELS[entry.channel]} | "
                          f"{entry.download_links} | [SHA-256]({entry.asset_url(CHECKSUMS)}) |"]
        lines.append("")
    return "\n".join(lines).rstrip()


def update_readme(text, releases):
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError("README must contain exactly one pair of release index markers")
    before, remaining = text.split(START, 1)
    if END not in remaining:
        raise ValueError("README release index markers are out of order")
    _, after = remaining.split(END, 1)
    return f"{before}{START}\n\n{render(releases)}\n\n{END}{after}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-stdin", action="store_true",
                        help="Read paginated release JSON from gh api --paginate --slurp")
    args = parser.parse_args()
    if args.from_stdin:
        releases = (item for page in json.load(sys.stdin) for item in page)
    else:
        releases = list_releases().values()
    readme = Path(__file__).resolve().parents[1] / "README.md"
    original = readme.read_text(encoding="utf-8")
    updated = update_readme(original, releases)
    if updated != original:
        readme.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
