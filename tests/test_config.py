from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch
from jwm_style.config import (
    update_style,
    start_attributes,
    update_start_attribute,
    Configuration,
    save_atomic,
)


class PatchingTests(unittest.TestCase):
    def test_changes_only_selected_value(self):
        text = """<?xml version="1.0"?>\r
<JWM>\r
  <!-- <WindowStyle><Foreground>ignore</Foreground></WindowStyle> -->\r
  <WindowStyle data="a > b">\r
    <Foreground>  old <!--keep--> </Foreground>\r
    <Background>#111111</Background>\r
  </WindowStyle>\r
  <Key key="F1">exec:foo &amp; bar</Key>\r
</JWM>"""
        changed = update_style(text, "WindowStyle", ("Foreground",), "new & value")
        self.assertEqual(
            changed, text.replace("  old <!--keep-->", "  new &amp; value <!--keep-->")
        )
        ET.fromstring(changed)

    def test_missing_property_group_section_and_empty_nodes(self):
        cases = [
            "<JWM/>",
            "<JWM><WindowStyle/></JWM>",
            "<JWM><WindowStyle><Active/></WindowStyle></JWM>",
            "<JWM><WindowStyle><Active><Foreground/></Active></WindowStyle></JWM>",
            "<JWM><WindowStyle><Active><Foreground></Foreground></Active></WindowStyle></JWM>",
        ]
        for text in cases:
            with self.subTest(text=text):
                result = update_style(
                    text, "WindowStyle", ("Active", "Foreground"), "#abcd12"
                )
                self.assertEqual(
                    ET.fromstring(result).findtext("WindowStyle/Active/Foreground"),
                    "#abcd12",
                )

    def test_missing_property_keeps_existing_bytes(self):
        text = (
            "<JWM>\n  <WindowStyle>\n    <Font>Sans-12</Font>\n  </WindowStyle>\n</JWM>"
        )
        result = update_style(text, "WindowStyle", ("Width",), "5")
        self.assertEqual(
            result,
            text.replace("  </WindowStyle>", "    <Width>5</Width>\n  </WindowStyle>"),
        )

    def test_duplicate_sections_groups_and_leaves_rejected(self):
        for inner in [
            "<WindowStyle/><WindowStyle/>",
            "<WindowStyle><Active/><Active/></WindowStyle>",
            "<WindowStyle><Active><Foreground>a</Foreground><Foreground>b</Foreground></Active></WindowStyle>",
        ]:
            with self.subTest(inner=inner), self.assertRaises(ValueError):
                update_style(
                    "<JWM>" + inner + "</JWM>",
                    "WindowStyle",
                    ("Active", "Foreground"),
                    "new",
                )

    def test_nested_sections_do_not_confuse_write_target(self):
        text = "<JWM><Other><WindowStyle><Foreground>leave</Foreground></WindowStyle></Other><WindowStyle><Foreground>old</Foreground></WindowStyle></JWM>"
        self.assertEqual(
            update_style(text, "WindowStyle", ("Foreground",), "new"),
            text.replace(">old<", ">new<"),
        )

    def test_cdata_rejected_as_unsafe_leaf(self):
        with self.assertRaises(ValueError):
            update_style(
                "<JWM><WindowStyle><Font><![CDATA[Sans-12]]></Font></WindowStyle></JWM>",
                "WindowStyle",
                ("Font",),
                "Sans-14",
            )

    def test_start_button_only_selected_attribute_changes(self):
        text = '<JWM><Tray><TrayButton label=\'A &amp; B\' icon="old" popup="keep">root:1</TrayButton><TrayButton>exec:other</TrayButton></Tray></JWM>'
        self.assertEqual(start_attributes(text)["label"], "A & B")
        result = update_start_attribute(text, "label", 'C "D" & E')
        self.assertEqual(result, text.replace("A &amp; B", "C &quot;D&quot; &amp; E"))
        self.assertEqual(start_attributes(result)["label"], 'C "D" & E')

    def test_ambiguous_start_button_rejected(self):
        with self.assertRaises(ValueError):
            start_attributes(
                "<JWM><Tray><TrayButton>root:1</TrayButton><TrayButton>root:2</TrayButton></Tray></JWM>"
            )


class FilesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.path = self.base / "jwmrc"
        self.original = b"<JWM><!--keep--><WindowStyle><Foreground>old</Foreground></WindowStyle></JWM>"
        self.path.write_bytes(self.original)
        self.pending = {("WindowStyle", ("Foreground",)): "new"}

    def test_backup_and_mode_and_atomic_replace(self):
        self.path.chmod(0o640)
        Configuration(self.path).commit(self.pending, {})
        self.assertEqual(self.path.with_name("jwmrc.bak").read_bytes(), self.original)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)
        self.assertIn(b">new<", self.path.read_bytes())
        self.assertEqual(list(self.base.glob(".jwmrc.*")), [])

    def test_external_change_aborts_without_backup(self):
        config = Configuration(self.path)
        self.path.write_bytes(b"<JWM/>")
        with self.assertRaises(ValueError):
            config.commit(self.pending, {})
        self.assertEqual(self.path.read_bytes(), b"<JWM/>")
        self.assertFalse(self.path.with_name("jwmrc.bak").exists())

    def test_atomic_failure_keeps_original_and_cleans_temp(self):
        with patch("jwm_style.config.os.replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                save_atomic(self.path, b"new")
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(list(self.base.glob(".jwmrc.*")), [])

    def test_static_include_order_and_override_without_touching_include(self):
        include = self.base / "styles.xml"
        include.write_text(
            "<JWM><WindowStyle><Foreground>included</Foreground><Width>8</Width></WindowStyle></JWM>"
        )
        self.path.write_text("<JWM><Include>styles.xml</Include></JWM>")
        before = include.read_bytes()
        config = Configuration(self.path, cwd=self.base)
        self.assertEqual(config.values()["WindowStyle"]["Foreground"], "included")
        config.commit(self.pending, {})
        self.assertEqual(include.read_bytes(), before)
        self.assertEqual(
            Configuration(self.path, cwd=self.base).values()["WindowStyle"][
                "Foreground"
            ],
            "new",
        )
        self.assertEqual(
            Configuration(self.path, cwd=self.base).values()["WindowStyle"]["Width"],
            "8",
        )

    def test_external_include_change_detected(self):
        include = self.base / "styles.xml"
        include.write_text("<JWM/>")
        self.path.write_text("<JWM><Include>styles.xml</Include></JWM>")
        config = Configuration(self.path, cwd=self.base)
        include.write_text("<JWM><!--new--></JWM>")
        with self.assertRaises(ValueError):
            config.commit(self.pending, {})

    def test_later_include_overrides_local_property(self):
        include = self.base / "styles.xml"
        include.write_text(
            "<JWM><WindowStyle><Foreground>later</Foreground></WindowStyle></JWM>"
        )
        self.path.write_text(
            "<JWM><WindowStyle><Foreground>first</Foreground></WindowStyle><Include>styles.xml</Include></JWM>"
        )
        config = Configuration(self.path, cwd=self.base)
        self.assertEqual(config.values()["WindowStyle"]["Foreground"], "later")
        with self.assertRaisesRegex(ValueError, "overridden"):
            config.commit(self.pending, {})

    def test_cycles_and_exec_include_never_executed(self):
        marker = self.base / "should-not-exist"
        self.path.write_text(
            f"<JWM><Include>jwmrc</Include><Include>exec:touch {marker}</Include></JWM>"
        )
        config = Configuration(self.path, cwd=self.base)
        self.assertEqual(len(config.warnings), 2)
        self.assertFalse(marker.exists())

    def test_duplicate_block_commit_does_not_write_anything(self):
        self.path.write_text("<JWM><WindowStyle/><WindowStyle/></JWM>")
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            Configuration(self.path).commit(self.pending, {})
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_numeric_values_do_not_replace_configuration(self):
        for key, value in [
            ("Width", "oops"),
            ("Width", "0"),
            ("Opacity", "NaN"),
            ("Height", "999"),
            ("Corner", "-1"),
        ]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                Configuration(self.path).commit({("WindowStyle", (key,)): value}, {})
            self.assertEqual(self.path.read_bytes(), self.original)

    def test_previously_missing_include_appears_before_save(self):
        self.path.write_text("<JWM><Include>missing.xml</Include></JWM>")
        config = Configuration(self.path, cwd=self.base)
        (self.base / "missing.xml").write_text("<JWM/>")
        with self.assertRaises(ValueError):
            config.commit(self.pending, {})
