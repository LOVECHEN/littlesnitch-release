from gzip import compress
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import mirror


MAC_STABLE, NIGHTLY, LEGACY, BETA, LINUX_STABLE, LINUX_PRE = mirror.SOURCES
PRE_FILES = (
    "littlesnitch_1.1.2~pre1_amd64.deb",
    "littlesnitch-1.1.2~pre1-1.riscv64.rpm",
    "littlesnitch-1.1.2pre1-1-ppc64le.pkg.tar.zst",
    "littlesnitch-1.1.2-pre1-arm64-linux-musl.tar.gz",
    "littlesnitch-1.1.2-pre1.hashes.txt",
    "littlesnitch-1.1.2-pre1.hashes.txt.sig.github.json",
)


def page(*urls):
    return "".join(f'<a href="{url}">Download</a>' for url in urls)


def linux_page(*names, directory="prerelease/"):
    return page(*(f"/downloads/littlesnitch-linux/{directory}{name}" for name in names))


class DiscoveryTest(unittest.TestCase):
    def test_mac_stable_absolute_and_same_page_duplicate(self):
        path = "/downloads/littlesnitch/LittleSnitch-6.5.dmg"
        [release] = mirror.discover(MAC_STABLE, page(path, mirror.ORIGIN + path,
                                                   "https://example.com" + path))
        self.assertEqual(release.tag, "mac-v006.005.000-stable")
        self.assertEqual(release.legacy_tag, "mac-stable-6.5")
        self.assertEqual(len(release.assets), 1)
        self.assertTrue(release.source.latest)

    def test_mac_build_tags(self):
        for source, version, build in ((NIGHTLY, "6.5.1", "7309"), (BETA, "7.0", "8020")):
            channel = source.channel
            path = f"/downloads/littlesnitch/{channel}/LittleSnitch-{version}-{channel}-%28{build}%29.dmg"
            [release] = mirror.discover(source, page(path))
            self.assertEqual(release.legacy_tag, f"mac-{channel}-{version}-{build}")
            self.assertTrue(release.source.prerelease)
            self.assertFalse(release.source.github_prerelease)
            self.assertEqual(release.assets[0].published_name, f"LittleSnitch-{version}-{channel}-{build}.dmg")

    def test_mac_tags_sort_by_version_before_channel(self):
        versions = [
            (BETA, "7.0", "8020"), (BETA, "7.0", "8013"),
            (NIGHTLY, "6.5.1", "7309"), (MAC_STABLE, "6.5", ""),
            (NIGHTLY, "6.5", "7300"), (MAC_STABLE, "6.4.1", ""),
        ]
        tags = [mirror.Release(source, version, (), build).tag for source, version, build in versions]
        self.assertEqual(tags, sorted(tags, reverse=True))
        self.assertGreater(mirror.Release(MAC_STABLE, "6.10", ()).tag,
                           mirror.Release(MAC_STABLE, "6.9", ()).tag)

    def test_mac_legacy_with_gzip(self):
        releases = mirror.discover(LEGACY, page(
            "/downloads/littlesnitch/legacy/LittleSnitch-3.8.2.dmg",
            "/downloads/littlesnitch/legacy/LittleSnitch_1.2.4.dmg.gz",
        ))
        self.assertEqual([r.version for r in releases], ["1.2.4", "3.8.2"])

    def test_linux_prerelease_groups_all_packaging_spellings(self):
        [release] = mirror.discover(LINUX_PRE, linux_page(*PRE_FILES, PRE_FILES[0]))
        self.assertEqual(release.tag, "linux-prerelease-1.1.2-pre1")
        self.assertTrue(release.source.github_prerelease)
        self.assertEqual(len(release.assets), 6)
        self.assertEqual(release.assets[0].published_name, "littlesnitch_1.1.2-pre1_amd64.deb")

    def test_linux_stable_packages_and_not_latest(self):
        [release] = mirror.discover(LINUX_STABLE, linux_page(
            "littlesnitch_1.1.1_arm64.deb", "littlesnitch-1.1.1.hashes.txt",
            "littlesnitch-1.1.1.hashes.txt.sig.github.json", directory=""))
        self.assertEqual(release.tag, "linux-stable-1.1.1")
        self.assertFalse(release.source.latest)
        self.assertFalse(release.source.prerelease)

    def test_missing_signature_refuses_to_group(self):
        with self.assertRaisesRegex(ValueError, "Missing Linux packages"):
            mirror.discover(LINUX_PRE, linux_page(*PRE_FILES[:-1]))

    def test_offsite_links_and_path_traversal_are_excluded(self):
        with self.assertRaisesRegex(ValueError, "No official installer links"):
            mirror.discover(MAC_STABLE, page(
                "https://obdev.at.example.com/downloads/littlesnitch/LittleSnitch-6.5.dmg",
                "https://obdev.at@example.com/downloads/littlesnitch/LittleSnitch-6.5.dmg",
                "http://obdev.at/downloads/littlesnitch/LittleSnitch-6.5.dmg",
                "/downloads/littlesnitch/%2E%2E%2FLittleSnitch-6.5.dmg",
            ))

    def test_redirect_policy(self):
        with self.assertRaisesRegex(ValueError, "Unexpected redirect"):
            mirror.OfficialRedirects().redirect_request(
                mirror.Request(MAC_STABLE.url), None, 302, "", {}, "https://example.com/")


class IntegrityTest(unittest.TestCase):
    def test_dmg_and_compressed_dmg(self):
        image = b"disk image contents" + b"koly" + bytes(508)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.dmg"
            path.write_bytes(image)
            mirror.validate_dmg(path, compressed=False)
            path.write_bytes(compress(image))
            mirror.validate_dmg(path, compressed=True)
            path.write_bytes(compress(image)[:-8])
            with self.assertRaises(EOFError):
                mirror.validate_dmg(path, compressed=True)
            path.write_bytes(b"<html>" * 150)
            with self.assertRaisesRegex(ValueError, "Not a UDIF"):
                mirror.validate_dmg(path, compressed=False)

    def test_hash_manifest_accepts_prose_but_refuses_duplicates(self):
        line = f"{'c' * 64}  {PRE_FILES[0]}"
        self.assertEqual(mirror.parse_hashes("Package hashes\n\n" + line), {PRE_FILES[0]: "c" * 64})
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            mirror.parse_hashes(f"{line}\n{line}")

    def test_linux_verifies_downloads_and_preserves_upstream_bytes(self):
        [release] = mirror.discover(LINUX_PRE, linux_page(*PRE_FILES))
        blobs = {name: name.encode() for name in PRE_FILES}
        blobs[PRE_FILES[-2]] = "".join(
            f"{sha256(blobs[name]).hexdigest()}  {name}\n" for name in PRE_FILES[:-2]
        ).encode()
        assets = {asset.url: asset.name for asset in release.assets}

        def download(url, path, _limit):
            content = blobs[assets[url]]
            path.write_bytes(content)
            return sha256(content).hexdigest()

        with TemporaryDirectory() as directory, patch.object(mirror, "download", download), \
                patch.object(mirror.subprocess, "run") as cosign:
            path = Path(directory)
            digests = mirror.save_assets(release, path)
            cosign.assert_called_once()
            self.assertEqual((path / PRE_FILES[-2]).read_bytes(), blobs[PRE_FILES[-2]])
            self.assertEqual(len(digests), len(PRE_FILES) + 1)
            blobs[PRE_FILES[0]] = b"invalid download"
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                mirror.save_assets(release, path)

    def test_upload_integrity_checks_asset_names_digests_and_state(self):
        uploaded = {"pkg": {"digest": "sha256:abc", "state": "uploaded"}}
        mirror.verify_uploaded("tag", {"pkg": "abc"}, uploaded)
        with self.assertRaisesRegex(ValueError, "wrong digest"):
            mirror.verify_uploaded("tag", {"pkg": "bad"}, uploaded)
        with self.assertRaisesRegex(ValueError, "filenames"):
            mirror.verify_uploaded("tag", {"renamed": "abc"}, uploaded)

    def test_release_notes_are_only_a_sorted_sha256_table(self):
        digests = {"z.dmg": "a" * 64, mirror.CHECKSUMS: "b" * 64, "a.dmg": "c" * 64}
        self.assertEqual(mirror.notes(digests), "\n".join([
            "| 文件名 | SHA-256 |",
            "|---|---|",
            f"| `a.dmg` | `{'c' * 64}` |",
            f"| `z.dmg` | `{'a' * 64}` |",
            "",
        ]))

    def test_complete_published_release_does_not_download_again(self):
        [release] = mirror.discover(
            MAC_STABLE, page("/downloads/littlesnitch/LittleSnitch-6.5.dmg"))
        previous = {"tag_name": release.legacy_tag, "draft": False, "prerelease": False, "assets": [
            {"name": name, "state": "uploaded", "digest": "sha256:abc"}
            for name in (mirror.CHECKSUMS, release.assets[0].published_name)
        ]}
        releases = {release.legacy_tag: previous}
        with patch.object(mirror, "save_assets") as save:
            mirror.publish(release, mirror.existing_release(release, releases), None)
            save.assert_not_called()
