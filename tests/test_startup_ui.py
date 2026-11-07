import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from jwm_tools.startup.editor import StartupEditor, CommandDialog, ApplicationDialog


@unittest.skipUnless(os.environ.get("DISPLAY"), "GTK requires X11")
class StartupUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "jwmrc"
        self.path.write_text(
            "<JWM><StartupCommand>jwm_audio</StartupCommand><RestartCommand>jwm_menu</RestartCommand></JWM>"
        )
        self.errors = []
        hook = patch.object(sys, "excepthook", lambda *args: self.errors.append(args))
        hook.start()
        self.addCleanup(hook.stop)
        self.addCleanup(lambda: self.assertFalse(self.errors, str(self.errors)))
        self.window = StartupEditor(self.path)
        self.window.show_all()
        self.addCleanup(self.window.destroy)

    def test_toggle_pending_then_save_and_restore(self):
        original = self.path.read_bytes()
        self.window.toggle(None, "0")
        self.assertFalse(self.window.document.get("L0").enabled)
        self.assertEqual(self.path.read_bytes(), original)
        self.window.save()
        self.assertFalse(self.window.document.get("L0").enabled)
        self.window.toggle(None, "0")
        self.window.save()
        self.assertEqual(self.path.read_bytes(), original)

    def test_filters(self):
        self.window.phase.set_active_id("RestartCommand")
        self.assertEqual(len(self.window.filtered), 1)
        self.window.phase.set_active_id("all")
        self.window.search.set_text("jwm_audio")
        self.window.refilter()
        self.assertEqual(len(self.window.filtered), 1)

    def test_dialog_lifecycle_hint_and_file_picker(self):
        dialog = CommandDialog(self.window)
        try:
            dialog.kind.set_active_id("ShutdownCommand")
            self.assertIn("encerrar", dialog.hint.get_text())
            with patch("jwm_tools.startup.editor.Gtk.FileChooserDialog") as factory:
                factory.return_value.run.return_value = Gtk.ResponseType.OK
                factory.return_value.get_filename.return_value = "/tmp/my script"
                dialog.choose_file()
                self.assertEqual(dialog.command.get_text(), "'/tmp/my script'")
        finally:
            dialog.destroy()

    def test_application_picker_and_selection_validation(self):
        dialog = ApplicationDialog(self.window)
        try:
            with self.assertRaises(ValueError):
                dialog.command()
        finally:
            dialog.destroy()

    def test_external_changes_reported_and_pending_kept(self):
        self.window.toggle(None, "0")
        self.path.write_text("<JWM/>")
        with patch.object(self.window, "message") as message:
            self.window.save()
            message.assert_called_once()
        self.assertTrue(self.window.document.dirty)
        self.assertEqual(self.path.read_text(), "<JWM/>")
