import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from jwm_tools.menu.editor import MenuEditor, EntryDialog


@unittest.skipUnless(os.environ.get("DISPLAY"), "GTK requires X11")
class MenuUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "jwmrc"
        self.xml = '<JWM><RootMenu onroot="12"><Menu label="Tools"/><Program label="One" icon="utilities-terminal">xterm</Program><Include>exec:false</Include></RootMenu></JWM>'
        self.path.write_text(self.xml)
        self.errors = []
        hook = patch.object(sys, "excepthook", lambda *args: self.errors.append(args))
        hook.start()
        self.addCleanup(hook.stop)
        self.addCleanup(lambda: self.assertFalse(self.errors, str(self.errors)))
        self.window = MenuEditor(self.path)
        self.window.show_all()
        self.addCleanup(self.window.destroy)

    def select(self, node):
        def visit(model, path, it, _):
            if model[it][0] is node:
                self.window.tree.get_selection().select_path(path)
                return True

        self.window.store.foreach(visit, None)

    def test_tree_reorder_and_indent_outdent_save(self):
        root = self.window.document.roots()[0]
        program = root.children[1]
        self.select(program)
        self.window.indent()
        self.assertIs(self.window.selected(), program)
        self.assertEqual(program.parent.kind, "Menu")
        self.window.outdent()
        self.window.move(-1)
        self.assertEqual(self.path.read_text(), self.xml)
        self.assertTrue(self.window.save())
        self.assertEqual(self.window.document.roots()[0].children[0].kind, "Program")
        self.assertEqual(self.path.with_name("jwmrc.bak").read_text(), self.xml)

    def test_icon_picker_is_file_dialog_and_cancel_preserves(self):
        dialog = EntryDialog(self.window)
        try:
            with patch(
                "jwm_tools.menu.editor.choose_icon", return_value="/tmp/my icon.svg"
            ) as picker:
                dialog.choose_icon()
                picker.assert_called_once_with(dialog, "")
                self.assertEqual(dialog.icon.get_text(), "/tmp/my icon.svg")
                self.assertIn("icon", dialog.candidate()[1])
            with patch("jwm_tools.menu.editor.choose_icon", return_value=None):
                dialog.choose_icon()
                self.assertEqual(dialog.icon.get_text(), "/tmp/my icon.svg")
            with patch("jwm_tools.menu.editor.choose_icon", return_value=""):
                dialog.choose_icon()
                self.assertNotIn("icon", dialog.candidate()[1])
        finally:
            dialog.destroy()

    def test_program_picker_quotes_path(self):
        dialog = EntryDialog(self.window)
        try:
            with patch.object(dialog, "choose_path", return_value="/tmp/my program"):
                dialog.choose_program()
                self.assertEqual(dialog.command.get_text(), "'/tmp/my program'")
            dialog.kind.set_active_id("Include")
            with patch.object(dialog, "choose_path", return_value="/tmp/my menu"):
                dialog.choose_program()
                self.assertEqual(dialog.command.get_text(), "/tmp/my menu")
        finally:
            dialog.destroy()

    def test_application_picker_fills_label_and_command(self):
        dialog = EntryDialog(self.window)
        try:
            with patch("jwm_tools.menu.editor.ApplicationDialog") as factory:
                picker = factory.return_value
                picker.run.return_value = Gtk.ResponseType.OK
                picker.command.return_value = "xterm -e top"
                app = MagicMock()
                app.get_display_name.return_value = "System monitor"
                app.get_icon.return_value = None
                picker.tree.get_selection.return_value.get_selected.return_value = (
                    {0: [app]},
                    0,
                )
                dialog.choose_application()
                self.assertEqual(dialog.label.get_text(), "System monitor")
                self.assertEqual(dialog.command.get_text(), "xterm -e top")
                picker.destroy.assert_called_once()
        finally:
            dialog.destroy()

    def test_include_button_and_open_source(self):
        root = self.window.document.roots()[0]
        self.select(root.children[2])
        self.assertFalse(self.window.buttons["Open Include"].get_sensitive())
        included = Path(self.temp.name) / "menu"
        included.write_text('<JWM><Program label="Included">true</Program></JWM>')
        self.window.document.update(root.children[2], {}, str(included))
        self.window.refresh(root.children[2])
        self.assertTrue(self.window.buttons["Open Include"].get_sensitive())
        with patch.object(self.window, "confirm", return_value=True):
            self.window.open_include()
        self.assertEqual(self.window.document.path, included)

    def test_external_change_save_error_and_discard_protection(self):
        root = self.window.document.roots()[0]
        self.window.document.remove(root.children[0])
        self.path.write_text("<JWM/>")
        with patch.object(self.window, "message") as message:
            self.assertFalse(self.window.save())
            message.assert_called_once()
        with patch.object(self.window, "confirm", return_value=False):
            self.window.discard()
        self.assertTrue(self.window.document.dirty)

    def test_clear_menu_pending_cancel_discard_and_preserve_config(self):
        self.path.write_text(
            self.xml.replace("</JWM>", '<Key key="F1">close</Key></JWM>')
        )
        self.window.load(self.path)
        original = self.path.read_bytes()
        with patch.object(self.window, "confirm", return_value=False):
            self.window.buttons["Clear menu"].clicked()
        self.assertFalse(self.window.document.dirty)
        with patch.object(self.window, "confirm", return_value=True):
            self.window.buttons["Clear menu"].clicked()
        self.assertEqual(self.window.document.roots()[0].children, [])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertIn('<Key key="F1">close</Key>', self.window.document.preview())
        with patch.object(self.window, "confirm", return_value=True):
            self.window.discard()
        self.assertFalse(self.window.document.dirty)

    def test_generation_targets_submenu_only_and_requires_save(self):
        import xml.etree.ElementTree as ET

        generated = ET.fromstring(
            '<JWM><Menu label="Utilities"><Program label="Fixture">true</Program></Menu></JWM>'
        )
        ET.indent(generated, space="    ")
        root = self.window.document.roots()[0]
        target = root.children[0]
        self.select(target)
        with patch(
            "jwm_tools.menu.generator.generate_tree", return_value=(generated, 1)
        ), patch.object(self.window, "confirm", return_value=True):
            self.window.buttons["Generate from applications"].clicked()
        self.assertEqual(target.children[0].children[0].value, "true")
        self.assertEqual(root.children[1].value, "xterm")
        self.assertEqual(self.path.read_text(), self.xml)
        self.assertTrue(self.window.save())
        self.assertIn("Fixture", self.path.read_text())

    def test_generation_cancel_and_empty_results_keep_menu(self):
        import xml.etree.ElementTree as ET

        generated = ET.fromstring('<JWM><Program label="Fixture">true</Program></JWM>')
        with patch(
            "jwm_tools.menu.generator.generate_tree", return_value=(generated, 1)
        ), patch.object(self.window, "confirm", return_value=False):
            self.window.generate_apps()
        self.assertFalse(self.window.document.dirty)
        with patch(
            "jwm_tools.menu.generator.generate_tree",
            return_value=(ET.Element("JWM"), 0),
        ), patch.object(self.window, "message") as message:
            self.window.generate_apps()
            message.assert_called_once()
        self.assertFalse(self.window.document.dirty)

    def test_actual_generation_with_indentation_can_be_confirmed_and_saved(self):
        from jwm_tools.menu import generator

        apps = Path(self.temp.name) / "apps"
        apps.mkdir()
        (apps / "fixture.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Fixture\nExec=/bin/true %f\nCategories=Utility;\n"
        )
        with patch.multiple(
            generator, HOME=Path(self.temp.name), SEARCH_PATHS=[apps]
        ), patch.object(self.window, "confirm", return_value=True), patch.object(
            self.window, "message"
        ) as message:
            self.window.buttons["Generate from applications"].clicked()
            message.assert_not_called()
        root = self.window.document.roots()[0]
        self.assertEqual(root.children[0].attrs["label"], "Utilities")
        self.assertEqual(root.children[0].value, "")
        self.assertEqual(root.children[0].children[0].value, "/bin/true")
        self.assertEqual(self.path.read_text(), self.xml)
        self.assertTrue(self.window.save())
        self.assertIn("Fixture", self.path.read_text())
        self.assertEqual(self.path.with_name("jwmrc.bak").read_text(), self.xml)
