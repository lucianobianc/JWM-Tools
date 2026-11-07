from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from jwm_tools.startup.model import StartupDocument, desktop_command


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "jwmrc"

    def document(self, xml="<JWM/>"):
        self.path.write_bytes(xml.encode())
        return StartupDocument(self.path)

    def test_top_level_only_and_disabled_comments(self):
        doc = self.document(
            "<JWM><StartupCommand>one</StartupCommand><Group><StartupCommand>nested</StartupCommand></Group><!-- <RestartCommand>two</RestartCommand> --><!-- example --></JWM>"
        )
        self.assertEqual(
            [(c.command, c.enabled) for c in doc.entries()],
            [("one", True), ("two", False)],
        )

    def test_edit_preserves_other_bytes_and_backup(self):
        xml = "<JWM>\r\n<!--áé--><StartupCommand extra='keep'> old <!--note--></StartupCommand>\r\n<Key key=\"F1\">close</Key></JWM>"
        doc = self.document(xml)
        doc.update("L0", "StartupCommand", "new & safe", True)
        doc.save()
        self.assertEqual(
            self.path.read_bytes().decode(), xml.replace(" old ", " new &amp; safe ")
        )
        self.assertEqual(self.path.with_name("jwmrc.bak").read_bytes(), xml.encode())

    def test_disable_and_restore_exact_xml(self):
        for inner in [
            "cmd --flag &amp;&amp; other <!--keep-->",
            "<![CDATA[cmd --flag && other]]>",
        ]:
            xml = (
                '<JWM>\r\n<!--á--><StartupCommand extra="x">'
                + inner
                + "</StartupCommand>\r\n</JWM>"
            )
            doc = self.document(xml)
            c = doc.get("L0")
            doc.update(c.token, c.kind, c.command, False)
            doc.save()
            self.assertFalse(doc.get("L0").enabled)
            self.assertIn("jwm_startup:disabled", self.path.read_text())
            c = doc.get("L0")
            doc.update(c.token, c.kind, c.command, True)
            doc.save()
            self.assertEqual(self.path.read_bytes().decode(), xml)

    def test_change_phase_and_edit_disabled(self):
        doc = self.document("<JWM><!-- <StartupCommand>old</StartupCommand> --></JWM>")
        doc.update("L0", "ShutdownCommand", "new", False)
        doc.save()
        c = doc.get("L0")
        self.assertEqual(
            (c.kind, c.command, c.enabled), ("ShutdownCommand", "new", False)
        )
        doc.update("L0", c.kind, c.command, True)
        self.assertIn("<ShutdownCommand>new</ShutdownCommand>", doc.preview())

    def test_add_remove_and_reset(self):
        doc = self.document()
        a = doc.add("StartupCommand", "one")
        doc.remove(a.token)
        self.assertFalse(doc.dirty)
        doc.add("RestartCommand", "two", False)
        doc.save()
        self.assertFalse(doc.get("L0").enabled)
        doc.remove("L0")
        self.assertNotIn("disabled", doc.preview())
        doc.reset()
        self.assertFalse(doc.dirty)

    def test_includes_are_readonly_and_external_changes_block_save(self):
        inc = self.path.with_name("include")
        inc.write_text("<JWM><StartupCommand>included</StartupCommand></JWM>")
        doc = self.document(f"<JWM><Include>{inc}</Include></JWM>")
        self.assertFalse(doc.get("I0").editable)
        with self.assertRaises(ValueError):
            doc.remove("I0")
        doc.add("StartupCommand", "new")
        inc.write_text("<JWM/>")
        with self.assertRaises(ValueError):
            doc.save()
        self.assertTrue(doc.dirty)

    def test_external_main_change_is_preserved(self):
        doc = self.document()
        doc.add("StartupCommand", "new")
        self.path.write_text("<JWM><!--external--></JWM>")
        with self.assertRaises(ValueError):
            doc.save()
        self.assertIn("external", self.path.read_text())

    def test_atomic_failure_preserves_original(self):
        doc = self.document()
        doc.add("StartupCommand", "new")
        with patch("jwm_tools.startup.model.save_atomic", side_effect=OSError("full")):
            with self.assertRaises(OSError):
                doc.save()
        self.assertEqual(self.path.read_text(), "<JWM/>")

    def test_invalid_marker_and_unrelated_comments_preserved(self):
        xml = "<JWM><!-- jwm_startup:disabled invalid! --><!-- tutorial <StartupCommand>x</StartupCommand> --></JWM>"
        doc = self.document(xml)
        self.assertTrue(doc.warnings)
        self.assertFalse(doc.entries())
        self.assertEqual(doc.preview(), xml)

    def test_duplicates_only_same_enabled_phase(self):
        doc = self.document()
        a = doc.add("StartupCommand", "one")
        b = doc.add("StartupCommand", "one")
        doc.add("RestartCommand", "one")
        doc.add("StartupCommand", "one", False)
        self.assertEqual(doc.duplicates(), {a.token, b.token})

    def test_validation(self):
        doc = self.document()
        for command in ["", "exec:foo", "one\ntwo", "\x00"]:
            with self.assertRaises(ValueError):
                doc.add("StartupCommand", command)
        with self.assertRaises(ValueError):
            doc.add("Unknown", "foo")

    def test_desktop_fields_are_quoted_not_executed(self):
        self.assertEqual(
            desktop_command(
                "app %U %i --name=%c %%", name="A; touch nope", icon="icon"
            ),
            "app --icon icon '--name=A; touch nope' %",
        )
        self.assertEqual(
            desktop_command('app "%k"', filename="/a b/app.desktop"),
            "app '/a b/app.desktop'",
        )
        with self.assertRaises(ValueError):
            desktop_command("app %X")

    def test_move_preserves_xml_and_reversing_move_clears_dirty(self):
        xml = '<JWM>\r\n<StartupCommand extra="1">one</StartupCommand><!--keep--><Key key="F1">close</Key><RestartCommand>restart</RestartCommand><StartupCommand extra="2">two</StartupCommand></JWM>'
        doc = self.document(xml)
        self.assertTrue(doc.move("L2", -1))
        self.assertEqual([c.command for c in doc.entries()], ["two", "restart", "one"])
        self.assertTrue(doc.dirty)
        self.assertIn('<!--keep--><Key key="F1">close</Key>', doc.preview())
        self.assertTrue(doc.move("L2", 1))
        self.assertFalse(doc.dirty)
        self.assertEqual(doc.preview(), xml)

    def test_move_save_reload_with_new_disabled_and_edited(self):
        doc = self.document(
            "<JWM><StartupCommand>one</StartupCommand><StartupCommand>two</StartupCommand></JWM>"
        )
        new = doc.add("StartupCommand", "three", False)
        doc.move(new.token, -1)
        doc.move(new.token, -1)
        doc.update("L1", "StartupCommand", "edited", True)
        doc.save()
        self.assertEqual(
            [(c.command, c.enabled) for c in doc.entries()],
            [("three", False), ("one", True), ("edited", True)],
        )
        self.assertFalse(doc.dirty)
        doc.remove("L1")
        doc.move("L2", -1)
        doc.save()
        self.assertEqual([c.command for c in doc.entries()], ["edited", "three"])

    def test_move_bounds_includes_and_readonly(self):
        inc = self.path.with_name("include")
        inc.write_text("<JWM><StartupCommand>included</StartupCommand></JWM>")
        doc = self.document(
            f"<JWM><StartupCommand>one</StartupCommand><Include>{inc}</Include><StartupCommand>two</StartupCommand></JWM>"
        )
        self.assertFalse(doc.move("L0", -1))
        self.assertFalse(doc.move("L1", 1))
        self.assertFalse(doc.move("L0", 1))
        self.assertFalse(doc.move("I0", -1))
        self.assertFalse(doc.dirty)
