import unittest

from scripts import release_index as index


def release(tag, filename="LittleSnitch.dmg", *, draft=False, checksums=True):
    names = [filename, "SHA256SUMS.txt"] if checksums else [filename]
    return {
        "tag_name": tag,
        "draft": draft,
        "prerelease": any(f"-{channel}-" in tag for channel in ("beta", "nightly", "prerelease")),
        "assets": [{"name": name, "state": "uploaded"} for name in names],
    }


class ReleaseIndexTest(unittest.TestCase):
    def test_numeric_version_and_build_order(self):
        tags = (
            "mac-stable-6.9",
            "mac-beta-7.0-98",
            "mac-stable-6.10",
            "mac-beta-7.0-102",
            "mac-nightly-6.10-7309",
        )
        result = index.render(map(release, tags))
        table = result.split("### macOS", 1)[1]
        self.assertEqual(
            sorted(tags, key=table.index),
            ("mac-beta-7.0-102 mac-beta-7.0-98 mac-stable-6.10 "
             "mac-nightly-6.10-7309 mac-stable-6.9").split(),
        )
        self.assertIn("download-nightly.html", result)
        self.assertIn("mac-nightly-6.10-7309", result.split("## macOS 7 Beta", 1)[0])

    def test_linux_prereleases_sort_numerically_after_stable(self):
        tags = ("linux-prerelease-1.2.3-pre2", "linux-prerelease-1.2.3-pre10", "linux-stable-1.2.3")
        result = index.render(release(tag, "littlesnitch.deb") for tag in tags)
        self.assertEqual(sorted(tags, key=lambda tag: result.index(f"/tag/{tag})")), list(reversed(tags)))
        self.assertNotIn("/littlesnitch.deb", result)

    def test_drafts_incomplete_and_unrecognized_releases_are_omitted(self):
        entries = (
            release("mac-beta-7.0-8030", draft=True),
            release("mac-nightly-6.5.1-7310", checksums=False),
            release("mac-nightly-6.5.1-pre1"),
            release("linux-beta-7.0-8020"),
            release("mac-legacy-1.2.4", "LittleSnitch_1.2.4.dmg.gz"),
        )
        result = index.render(entries)
        for entry in entries[:-1]:
            self.assertNotIn(entry["tag_name"], result)
        self.assertIn("[DMG.gz]", result)

    def test_index_refresh_is_idempotent_and_retains_manual_sections(self):
        original = f"Header\n{index.START}\nold\n{index.END}\nFooter\n"
        entries = [release("mac-stable-6.5")]
        updated = index.update_readme(original, entries)
        self.assertTrue(updated.startswith(f"Header\n{index.START}"))
        self.assertTrue(updated.endswith(f"{index.END}\nFooter\n"))
        self.assertEqual(index.update_readme(updated, entries), updated)
        with self.assertRaisesRegex(ValueError, "No complete published releases"):
            index.update_readme(updated, [])
