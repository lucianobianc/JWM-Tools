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

from jwm_tools import __version__

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
        cls.deb = cls.output / f"jwm-tools_{__version__}-1_all.deb"
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
        self.assertIn("python3-tk", metadata)
        self.assertIn("python3-pulsectl", metadata)
        self.assertIn("Conflicts: jwm-style-editor", metadata)
        for command in (
            "jwm_audio",
            "jwm_menu",
            "jwm_ram",
            "jwm_style",
            "jwm_keys",
            "jwm_startup",
        ):
            launcher = self.installed / "usr/bin" / command
            self.assertTrue(launcher.is_symlink())
            self.assertTrue(os.access(launcher, os.X_OK))
            self.assertTrue(launcher.resolve().is_relative_to(self.installed))
        launcher = self.installed / "usr/bin/jwm_style"
        self.assertTrue(launcher.is_symlink())
        self.assertTrue(launcher.resolve().is_relative_to(self.installed))
        self.assertTrue(os.access(launcher, os.X_OK))
        self.assertEqual(launcher.read_bytes().splitlines()[0], b"#!/usr/bin/python3")
        self.assertFalse((self.installed / "home").exists())
        self.assertFalse((self.installed / "etc").exists())
        self.assertTrue(
            (self.installed / "usr/share/jwm-tools/jwm_tools/style/render.py").is_file()
        )

    @unittest.skipUnless(
        shutil.which("desktop-file-validate"), "Desktop validator unavailable"
    )
    def test_desktop_menu_entry(self):
        for desktop in (self.installed / "usr/share/applications").glob("*.desktop"):
            subprocess.run(["desktop-file-validate", str(desktop)], check=True)

    def test_source_archive_includes_sources_tests_license_and_build(self):
        with tarfile.open(self.output / f"jwm-tools-{__version__}.tar.gz") as archive:
            members = archive.getmembers()
            files = {member.name for member in members}
            prefix = f"jwm-tools-{__version__}/"
            for name in (
                "LICENSE",
                "jwm_audio",
                "jwm_menu",
                "jwm_ram",
                "jwm_style",
                "jwm_keys",
                "jwm_startup",
                "jwm_tools/startup/editor.py",
                "jwm_tools/style/editor.py",
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

    def test_all_packaged_commands_report_version_outside_checkout(self):
        for command in (
            "jwm_audio",
            "jwm_menu",
            "jwm_ram",
            "jwm_style",
            "jwm_keys",
            "jwm_startup",
        ):
            with self.subTest(command=command):
                result = subprocess.run(
                    [str(self.installed / "usr/bin" / command), "--version"],
                    cwd=self.base,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertEqual(result.stdout.strip(), command + " " + __version__)

    def test_packaged_menu_generates_a_desktop_entry(self):
        import xml.etree.ElementTree as ET

        home = self.base / "menu-home"
        apps = home / "share/applications"
        apps.mkdir(parents=True, exist_ok=True)
        (apps / "fixture.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Menu fixture\nExec=/bin/true %f\nCategories=Utility;\n"
        )
        env = dict(os.environ, HOME=str(home), XDG_DATA_DIRS=str(home / "share"))
        subprocess.run(
            [str(self.installed / "usr/bin/jwm_menu"), "--generate"],
            env=env,
            cwd=self.base,
            check=True,
            capture_output=True,
        )
        programs = ET.parse(home / ".jwm-menu").findall(".//Program")
        self.assertTrue(
            any(
                p.get("label") == "Menu fixture" and p.text == "/bin/true"
                for p in programs
            )
        )

    def test_source_install_is_repeatable_and_all_commands_work(self):
        prefix = self.base / "local"
        for _ in range(2):
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/install.py"),
                    "--prefix",
                    str(prefix),
                ],
                check=True,
                capture_output=True,
            )
        for command in (
            "jwm_audio",
            "jwm_menu",
            "jwm_ram",
            "jwm_style",
            "jwm_keys",
            "jwm_startup",
        ):
            result = subprocess.run(
                [str(prefix / "bin" / command), "--version"],
                cwd=self.base,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.stdout.strip(), command + " " + __version__)

        for command in (
            "jwm_audio",
            "jwm_menu",
            "jwm_ram",
            "jwm_style",
            "jwm_keys",
            "jwm_startup",
        ):
            desktop = prefix / "share/applications" / (command + ".desktop")
            self.assertIn("Categories=Utility;", desktop.read_text())
        self.assertIn(
            "Exec=jwm_menu\n",
            (prefix / "share/applications/jwm_menu.desktop").read_text(),
        )

    def test_source_install_refuses_to_overwrite_an_unrelated_command(self):
        prefix = self.base / "occupied"
        (prefix / "bin").mkdir(parents=True)
        original = prefix / "bin/jwm_menu"
        original.write_text("user command")
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/install.py"), "--prefix", str(prefix)],
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(original.read_text(), "user command")
        self.assertFalse((prefix / "share").exists())

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
