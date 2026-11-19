#!/usr/bin/env python3
"""Mirror original Little Snitch packages explicitly linked by Objective Development."""

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import gzip
import hashlib
from html.parser import HTMLParser
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.error import HTTPError
from urllib.parse import unquote, urldefrag, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


REPO = "LOVECHEN/littlesnitch-release"
ORIGIN = "https://obdev.at"
CHECKSUMS = "SHA256SUMS.txt"
MIB = 1024 * 1024
MAX_PACKAGE = 512 * MIB
VERSION = r"\d+(?:\.\d+){1,3}"
MAC_NAME = re.compile(
    rf"LittleSnitch[-_](?P<version>{VERSION})(?:-(?P<channel>nightly|beta)-"
    r"\((?P<build>\d+)\))?\.dmg(?P<gzip>\.gz)?"
)
LINUX_ID = re.compile(rf"littlesnitch-(?P<version>{VERSION}(?:-pre\d+)?)"
                      r"\.hashes\.txt(?:\.sig\.github\.json)?")
LINUX_PACKAGES = (
    re.compile(rf"littlesnitch_(?P<version>{VERSION})(?:~(?P<pre>pre\d+))?_[\w-]+\.deb"),
    re.compile(rf"littlesnitch-(?P<version>{VERSION})(?:~(?P<pre>pre\d+))?-\d+\.[\w-]+\.rpm"),
    re.compile(rf"littlesnitch-(?P<version>{VERSION})(?P<pre>pre\d+)?-\d+-[\w-]+\.pkg\.tar\.zst"),
    re.compile(rf"littlesnitch-(?P<version>{VERSION})(?:-(?P<pre>pre\d+))?-[\w-]+\.tar\.gz"),
)


@dataclass(frozen=True)
class Source:
    platform: str
    channel: str
    path: str
    directory: str = ""
    notes: str = ""

    @property
    def url(self):
        return ORIGIN + "/products/" + self.path

    @property
    def prerelease(self):
        return self.channel in {"nightly", "beta", "prerelease"}

    @property
    def github_prerelease(self):
        # macOS previews use title labels so they appear in GitHub's default listing.
        return self.platform == "linux" and self.prerelease

    @property
    def latest(self):
        return (self.platform, self.channel) == ("mac", "stable")

    @property
    def prefix(self):
        return f"{self.platform}-{self.channel}"

    @property
    def download_paths(self):
        product = "littlesnitch" if self.platform == "mac" else "littlesnitch-linux"
        return tuple(f"{base}/{product}/{self.directory}"
                     for base in ("/downloads", "/ftp/pub/Products"))


SOURCES = (
    Source("mac", "stable", "littlesnitch/download.html",
           notes="littlesnitch/releasenotes.html"),
    Source("mac", "nightly", "littlesnitch/download-nightly.html", "nightly/",
           "littlesnitch/releasenotes.html"),
    Source("mac", "legacy", "littlesnitch/download-previous-versions.html", "legacy/"),
    Source("mac", "beta", "littlesnitch7-beta/index.html", "beta/",
           "littlesnitch7-beta/releasenotes.html"),
    Source("linux", "stable", "littlesnitch-linux/download.html"),
    Source("linux", "prerelease", "littlesnitch-linux/download-prerelease.html", "prerelease/"),
)


@dataclass(frozen=True)
class Asset:
    name: str
    url: str

    @property
    def published_name(self):
        return self.name.replace("(", "").replace(")", "").replace("~", "-")


@dataclass(frozen=True)
class Release:
    source: Source
    version: str
    assets: tuple
    build: str = ""

    @property
    def legacy_tag(self):
        return f"{self.source.prefix}-{self.version}" + (f"-{self.build}" if self.build else "")

    @property
    def tag(self):
        if self.source.platform != "mac":
            return self.legacy_tag
        # Put the numeric version before the channel in GitHub's native release list.
        parts = [int(part) for part in self.version.split(".")]
        parts += [0] * (3 - len(parts))
        if len(parts) == 4 and not parts[-1]:
            parts.pop()
        version = ".".join(f"{part:03d}" for part in parts)
        build = f"-{int(self.build):08d}" if self.build else ""
        return f"mac-v{version}-{self.source.channel}{build}"

    @property
    def title(self):
        product = "macOS" if self.source.platform == "mac" else "Linux"
        build = f" ({self.build})" if self.build else ""
        return f"Little Snitch for {product} {self.version}{build} · {self.source.channel.title()}"


def official(url):
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.netloc.lower() in {"obdev.at", "www.obdev.at"}


class OfficialRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not official(newurl):
            raise ValueError(f"Unexpected redirect from {req.full_url}: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, path, limit):
    if not official(url):
        raise ValueError(f"Not an official URL: {url}")
    request = Request(url, headers={"User-Agent": "Little-Snitch-Release-Mirror/1.0"})
    for attempt in range(3):
        try:
            with build_opener(OfficialRedirects()).open(request, timeout=40) as response:
                total = 0
                digest = hashlib.sha256()
                expected = response.headers.get("Content-Length")
                if expected is not None and int(expected) > limit:
                    raise ValueError(f"Download too large: {url}")
                with path.open("wb") as output:
                    while chunk := response.read(MIB):
                        total += len(chunk)
                        if total > limit:
                            raise ValueError(f"Download too large: {url}")
                        output.write(chunk)
                        digest.update(chunk)
                if not total or (expected is not None and int(expected) != total):
                    raise OSError(f"Empty or incomplete download: {url}")
                return digest.hexdigest()
        except (OSError, HTTPException) as error:
            if attempt == 2 or (isinstance(error, HTTPError)
                                 and 400 <= error.code < 500 and error.code not in {408, 429}):
                raise
            time.sleep(2 ** attempt)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def linked_downloads(source, html):
    parser = Links()
    parser.feed(html)
    assets = {}
    for href in parser.hrefs:
        url, _ = urldefrag(urljoin(source.url, href))
        if not official(url):
            continue
        path = unquote(urlsplit(url).path)
        for directory in source.download_paths:
            if not path.startswith(directory):
                continue
            name = path.removeprefix(directory)
            if not re.fullmatch(r"[A-Za-z0-9_~().-]+", name) or not name.lower().startswith("littlesnitch"):
                continue
            assets.setdefault(name, Asset(name, url))
            break
    if not assets:
        raise ValueError(f"No official installer links found at {source.url}")
    return tuple(assets.values())


def linux_version(name):
    if match := LINUX_ID.fullmatch(name):
        return match["version"]
    for pattern in LINUX_PACKAGES:
        if match := pattern.fullmatch(name):
            return match["version"] + (f"-{match['pre']}" if match["pre"] else "")
    raise ValueError(f"Unrecognized Linux asset: {name}")


def discover(source, html):
    groups = defaultdict(list)
    for asset in linked_downloads(source, html):
        if source.platform == "mac":
            match = MAC_NAME.fullmatch(asset.name)
            channel = source.channel if source.channel in {"beta", "nightly"} else None
            if not match or match["channel"] != channel:
                raise ValueError(f"Unexpected {source.prefix} filename: {asset.name}")
            groups[match["version"], match["build"] or ""].append(asset)
        else:
            version = linux_version(asset.name)
            if ("-pre" in version) != source.prerelease:
                raise ValueError(f"Unexpected {source.prefix} version: {version}")
            groups[version, ""].append(asset)
    releases = []
    for (version, build), assets in sorted(groups.items(), key=lambda pair: version_key(pair[0])):
        names = {asset.name for asset in assets}
        if len({asset.published_name for asset in assets}) != len(assets):
            raise ValueError(f"GitHub filenames collide in {source.prefix}-{version}")
        if source.platform == "linux":
            manifest = f"littlesnitch-{version}.hashes.txt"
            metadata = {manifest, f"{manifest}.sig.github.json"}
            if not metadata < names:
                raise ValueError(f"Missing Linux packages, hash manifest or signature for {version}")
        releases.append(Release(source, version, tuple(assets), build))
    return releases


def version_key(version_build):
    version, build = version_build
    base, _, pre = version.partition("-pre")
    return tuple(map(int, base.split("."))), int(pre) if pre else sys.maxsize, int(build or 0)


def validate_dmg(path, compressed):
    if compressed:
        with gzip.open(path, "rb") as image:
            # Read through EOF to validate the gzip CRC, without expanding it to disk.
            total = 0
            tail = b""
            while chunk := image.read(MIB):
                total += len(chunk)
                if total > MAX_PACKAGE:
                    raise ValueError(f"Uncompressed DMG too large: {path.name}")
                tail = (tail + chunk)[-512:]
            magic = tail[:4] if len(tail) == 512 else b""
    else:
        with path.open("rb") as image:
            if path.stat().st_size < 512:
                raise ValueError(f"Short DMG: {path.name}")
            image.seek(-512, os.SEEK_END)
            magic = image.read(4)
    if magic != b"koly":
        raise ValueError(f"Not a UDIF disk image: {path.name}")


def parse_hashes(content):
    hashes = {}
    for match in re.finditer(r"(?m)^([a-fA-F0-9]{64})[ \t]+\*?([A-Za-z0-9_.~-]+)[ \t]*\r?$", content):
        value, name = match.groups()
        if name in hashes:
            raise ValueError(f"Duplicate upstream hash for {name}")
        hashes[name] = value.lower()
    if not hashes:
        raise ValueError("No SHA-256 entries in upstream manifest")
    return hashes


def save_assets(release, directory):
    upstream = None
    digests = {}
    assets = release.assets
    if release.source.platform == "linux":
        name = f"littlesnitch-{release.version}.hashes.txt"
        bundle = name + ".sig.github.json"
        metadata = {asset.name: asset for asset in assets if asset.name in {name, bundle}}
        for asset in metadata.values():
            digests[asset.published_name] = download(asset.url, directory / asset.published_name, MIB)
        subprocess.run(
            ["cosign", "verify-blob", "--bundle", str(directory / bundle),
             "--certificate-identity", "littlesnitch-linux@obdev.at",
             "--certificate-oidc-issuer", "https://github.com/login/oauth", str(directory / name)],
            check=True, timeout=180,
        )
        upstream = parse_hashes((directory / name).read_text(encoding="utf-8"))
        assets = tuple(asset for asset in assets if asset.name not in metadata)
        if set(upstream) != {asset.name for asset in assets}:
            raise ValueError(f"Official Linux links and signed package manifest differ for {release.tag}")

    def fetch(asset):
        file = directory / asset.published_name
        digest = download(asset.url, file, MAX_PACKAGE)
        if upstream is None:
            validate_dmg(file, compressed=asset.name.endswith(".gz"))
        elif digest != upstream[asset.name]:
            raise ValueError(f"Upstream SHA-256 mismatch for {asset.name}")
        return asset.published_name, digest

    with ThreadPoolExecutor(max_workers=4) as pool:
        digests.update(pool.map(fetch, assets))
    manifest = directory / CHECKSUMS
    manifest.write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(digests.items())),
                        encoding="ascii")
    digests[CHECKSUMS] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    return digests


def preview_releases_url(channel):
    return f"https://github.com/{REPO}/releases?q={channel}"


def preview_navigation():
    return (f"**预发布下载 / Pre-releases:** [macOS Beta]({preview_releases_url('Beta')}) · "
            f"[macOS Nightly]({preview_releases_url('Nightly')})")


def notes(release):
    source = release.source
    lines = [f"Original installers from [the official download page]({source.url}).", "",
             f"Verify mirrored files with `shasum -a 256 -c {CHECKSUMS}`.", ""]
    if source.notes:
        url = f"{ORIGIN}/products/{source.notes}"
        if release.build:
            url += f"#version-{release.build}"
        lines += [f"[Official release notes]({url})", ""]
    if source.latest:
        lines[:0] = [preview_navigation(), ""]
    if source.platform == "linux":
        lines += ["Linux package checksums were verified against the signed upstream manifest. "
                  "The original manifest and Sigstore bundle are included.", ""]
    if any(asset.name != asset.published_name for asset in release.assets):
        lines += ["GitHub-compatible filenames are used in the mirror. The original filenames "
                  "are shown below and the file contents are unchanged.", ""]
    lines.extend(f"- [`{asset.name}`](<{asset.url}>)" for asset in release.assets)
    return "\n".join(lines) + "\n"


def gh(*args, capture=False):
    return subprocess.run(["gh", *args], check=True, text=True, capture_output=capture,
                          timeout=300).stdout


def list_releases():
    data = json.loads(gh("api", "--paginate", "--slurp", f"repos/{REPO}/releases", capture=True))
    return {item["tag_name"]: item for page in data for item in page}


def existing_release(release, published):
    return published.get(release.tag, published.get(release.legacy_tag))


def release_assets(tag):
    result = json.loads(gh("release", "view", tag, "-R", REPO, "--json", "assets", capture=True))
    return {asset["name"]: asset for asset in result["assets"]}


def verify_uploaded(tag, digests, uploaded):
    if set(digests) != set(uploaded):
        raise ValueError(f"GitHub asset filenames do not match the expected names for {tag}")
    for name, digest in digests.items():
        asset = uploaded[name]
        if asset["state"] != "uploaded" or asset["digest"] != f"sha256:{digest}":
            raise ValueError(f"GitHub asset missing or has wrong digest: {tag}/{name}")


def publish(release, previous, directory):
    tag = previous["tag_name"] if previous else release.tag
    expected_names = {CHECKSUMS} | {asset.published_name for asset in release.assets}
    prerelease = release.source.github_prerelease
    if previous and not previous["draft"]:
        existing = {asset["name"] for asset in previous["assets"]
                    if asset["state"] == "uploaded" and (asset.get("digest") or "").startswith("sha256:")}
        if not expected_names <= existing or previous["prerelease"] != prerelease:
            raise ValueError(f"Unexpected files or metadata in existing release {tag}")
        print(f"Already published: {tag}", flush=True)
        return

    digests = save_assets(release, directory)
    if not previous:
        gh("release", "create", tag, "-R", REPO, "--draft", "--latest=false",
           f"--prerelease={str(prerelease).lower()}", "--title", release.title,
           "--notes", notes(release), "--target", os.environ["GITHUB_SHA"])
    uploaded = release_assets(tag)
    if not uploaded.keys() <= digests.keys():
        raise ValueError(f"Unexpected assets in existing draft {tag}")
    for name, asset in uploaded.items():
        verify_uploaded(tag, {name: digests[name]}, {name: asset})
    labels = {asset.published_name: asset.name for asset in release.assets
              if asset.published_name != asset.name}
    missing = [str(directory / name) + (f"#{labels[name]}" if name in labels else "")
               for name in sorted(digests.keys() - uploaded.keys())]
    if missing:
        gh("release", "upload", tag, "-R", REPO, *missing)
    verify_uploaded(tag, digests, release_assets(tag))
    gh("release", "edit", tag, "-R", REPO, "--draft=false",
       f"--latest={str(release.source.latest).lower()}",
       f"--prerelease={str(prerelease).lower()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("discover", "verify", "publish"))
    mode = parser.parse_args().mode
    published = list_releases() if mode == "publish" else {}
    errors = []
    with TemporaryDirectory(prefix="littlesnitch-mirror-") as temp:
        root = Path(temp)
        releases = []
        for source in SOURCES:
            try:
                html = root / "source.html"
                download(source.url, html, 4 * MIB)
                releases.extend(discover(source, html.read_text(encoding="utf-8")))
            except (OSError, ValueError, HTTPException) as error:
                errors.append(f"{source.prefix}: {error}")
        for release in releases:
            print(f"{release.tag}: {len(release.assets)} official files", flush=True)
            try:
                if mode == "discover":
                    for asset in release.assets:
                        print(f"  {asset.url}")
                    continue
                with TemporaryDirectory(dir=root) as temp_release:
                    if mode == "verify":
                        save_assets(release, Path(temp_release))
                    else:
                        publish(release, existing_release(release, published), Path(temp_release))
            except (OSError, EOFError, ValueError, KeyError, HTTPException, subprocess.SubprocessError) as error:
                errors.append(f"{release.tag}: {error}")
        print(f"Discovered {len(releases)} releases and {sum(len(r.assets) for r in releases)} official files.",
              flush=True)
    for error in errors:
        print(error, file=sys.stderr, flush=True)
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())
