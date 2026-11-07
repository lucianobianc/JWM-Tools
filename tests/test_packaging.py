"""Exercise the release archives and the installed Debian launcher layout."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

from jwm_style import __version__

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("dpkg-deb"), "Debian package tests need dpkg-deb")
class PackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name)
        cls.output = cls.base / "release"
        cls.env = dict(os.environ, SOURCE_DATE_EPOCH="1770000000")
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/build_release.py"),
                "--output",
                str(cls.output),
            ],
            check=True,
            env=cls.env,
            capture_output=True,
        )
        cls.deb = cls.output / f"jwm-style-editor_{__version__}-1_all.deb"
        cls.installed = cls.base / "installed"
        subprocess.run(
            ["dpkg-deb", "--extract", str(cls.deb), str(cls.installed)], check=True
        )

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_debian_metadata_and_launcher(self):
        metadata = subprocess.check_output(
            ["dpkg-deb", "--field", str(self.deb)], text=True
        )
        self.assertIn("Architecture: all", metadata)
        self.assertIn("python3-gi-cairo", metadata)
        self.assertIn("libfontconfig1", metadata)
        launcher = self.installed / "usr/bin/jwm-style-editor"
        self.assertTrue(launcher.is_symlink())
        self.assertTrue(launcher.resolve().is_relative_to(self.installed))
        self.assertTrue(os.access(launcher, os.X_OK))
        self.assertEqual(launcher.read_bytes().splitlines()[0], b"#!/usr/bin/python3")
        self.assertFalse((self.installed / "home").exists())
        self.assertFalse((self.installed / "etc").exists())
        self.assertTrue(
            (
                self.installed / "usr/share/jwm-style-editor/jwm_style/render.py"
            ).is_file()
        )

    @unittest.skipUnless(
        shutil.which("desktop-file-validate"), "Desktop validator unavailable"
    )
    def test_desktop_menu_entry(self):
        subprocess.run(
            [
                "desktop-file-validate",
                str(self.installed / "usr/share/applications/jwm-style-editor.desktop"),
            ],
            check=True,
        )

    def test_source_archive_includes_sources_tests_license_and_build(self):
        with tarfile.open(
            self.output / f"jwm-style-editor-{__version__}.tar.gz"
        ) as archive:
            members = archive.getmembers()
            files = {member.name for member in members}
            prefix = f"jwm-style-editor-{__version__}/"
            for name in (
                "LICENSE",
                "jwm-style-editor",
                "jwm_style/editor.py",
                "tests/test_config.py",
                "tools/build_release.py",
                "packaging/control",
            ):
                self.assertIn(prefix + name, files)
            self.assertFalse(any("__pycache__" in p or "/.git/" in p for p in files))
            self.assertTrue(
                all(
                    m.isfile() and m.uid == 0 and m.gid == 0 and m.mtime == 1770000000
                    for m in members
                )
            )

    def test_assets_are_reproducible_and_checksums_match(self):
        second = self.base / "second"
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/build_release.py"),
                "--output",
                str(second),
            ],
            check=True,
            env=self.env,
            capture_output=True,
        )
        for file in self.output.iterdir():
            self.assertEqual(
                file.read_bytes(), (second / file.name).read_bytes(), file.name
            )
        for line in (self.output / "SHA256SUMS").read_text().splitlines():
            expected, name = line.split("  ", 1)
            self.assertEqual(
                hashlib.sha256((self.output / name).read_bytes()).hexdigest(), expected
            )
