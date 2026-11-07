import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk
from jwm_tools.keys.editor import KeysEditor, BindingDialog


def pump():
    for _ in range(5):
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.01)


@unittest.skipUnless(os.environ.get("DISPLAY"), "GTK requires an X11 display")
class KeysUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.include = self.base / "included"
        self.include.write_text('<JWM><Key key="F8">exec:true</Key></JWM>')
        self.path = self.base / "jwmrc"
        self.original = f'<JWM><!--keep--><Key mask="A" key="F4" extra="keep">close</Key><Mouse context="title" button="11">maximize</Mouse><Include>{self.include}</Include></JWM>'
        self.path.write_text(self.original)
        self.errors = []
        hook = patch.object(sys, "excepthook", lambda *error: self.errors.append(error))
        hook.start()
        self.addCleanup(hook.stop)
        self.window = KeysEditor(self.path)
        self.window.show_all()
        pump()
        self.addCleanup(self.window.destroy)
        self.addCleanup(lambda: self.assertFalse(self.errors, str(self.errors)))

    def select(self, token):
        for row in self.window.filtered:
            if row[0].token == token:
                self.window.tree.get_selection().select_path(row.path)
                pump()
                return
        self.fail("Row not found: " + token)

    def test_lists_both_types_and_read_only_includes(self):
        self.assertEqual(len(self.window.store), 3)
        self.select("I0")
        self.assertFalse(self.window.edit_button.get_sensitive())
        self.assertFalse(self.window.remove_button.get_sensitive())
        self.assertTrue(self.window.source_button.get_sensitive())
        self.window.open_source()
        self.assertEqual(self.window.document.path, self.include)
        self.assertTrue(self.window.document.entries()[0].editable)

    def test_filter_by_type_and_search(self):
        self.window.kind_filter.set_active_id("Mouse")
        self.window.filtered.refilter()
        self.assertEqual(len(self.window.filtered), 1)
        self.window.kind_filter.set_active_id("all")
        # Search an action: a short key name can also occur in the random
        # temporary source path, which is intentionally searchable.
        self.window.search.set_text("exec:true")
        self.window.filtered.refilter()
        self.assertEqual(len(self.window.filtered), 1)
        self.assertEqual(next(iter(self.window.filtered))[0].attrs["key"], "F8")

    def test_keyboard_capture_and_save_preserves_unknown_attributes(self):
        binding = self.window.document.get("L0")
        form = BindingDialog(self.window, "Key", binding)
        try:
            capture = SimpleNamespace(
                response=lambda result: self.assertEqual(result, Gtk.ResponseType.OK)
            )
            form.capture_key_event(
                capture,
                SimpleNamespace(
                    keyval=Gdk.KEY_F9,
                    state=Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD4_MASK,
                ),
            )
            candidate = form.candidate()
            self.assertEqual(
                candidate.attrs, {"key": "F9", "mask": "C4", "extra": "keep"}
            )
            self.window.document.update(
                binding.token, candidate.attrs, candidate.action
            )
            self.window.refresh()
            self.assertEqual(self.path.read_text(), self.original)
            self.assertTrue(self.window.save())
            self.assertIn('key="F9"', self.path.read_text())
            self.assertIn('extra="keep"', self.path.read_text())
            self.assertEqual(
                self.path.with_name("jwmrc.bak").read_text(), self.original
            )
        finally:
            form.destroy()

    def test_keycode_mode_and_mouse_release_form(self):
        form = BindingDialog(self.window, "Key")
        try:
            form.mode.set_active_id("keycode")
            form.trigger.set_text("38")
            form.action.get_child().set_text("exec:true")
            self.assertEqual(form.candidate().attrs, {"keycode": "38"})
        finally:
            form.destroy()
        form = BindingDialog(self.window, "Mouse", self.window.document.get("L1"))
        try:
            form.context.set_active_id("root")
            form.trigger.set_active_id("-3")
            candidate = form.candidate()
            self.assertEqual(candidate.attrs, {"context": "root", "button": "-3"})
        finally:
            form.destroy()

    def test_conflict_visible_without_implicit_overwrite(self):
        self.window.document.add("Key", {"mask": "1", "key": "F4"}, "none")
        self.window.refresh()
        self.assertIn("conflicting", self.window.status.get_text())
        self.assertEqual(len(self.window.document.entries()), 4)
        self.assertEqual(self.path.read_text(), self.original)

    def test_external_change_save_error_keeps_pending_data(self):
        self.window.document.add("Key", {"key": "F10"}, "exec:true")
        self.path.write_text("<JWM><!--external--></JWM>")
        with patch.object(self.window, "message") as message:
            self.assertFalse(self.window.save())
            message.assert_called_once()
        self.assertTrue(self.window.document.dirty)
        self.assertEqual(self.path.read_text(), "<JWM><!--external--></JWM>")

    def test_discard_and_close_protect_pending_changes(self):
        self.window.document.add("Key", {"key": "F10"}, "exec:true")
        with patch.object(self.window, "confirm", return_value=False):
            self.assertFalse(self.window.can_discard())
            self.window.discard()
        self.assertTrue(self.window.document.dirty)
        with patch.object(self.window, "confirm", return_value=True):
            self.window.discard()
        self.assertFalse(self.window.document.dirty)
        self.assertEqual(self.path.read_text(), self.original)

    def test_restart_only_after_save_and_error_reported(self):
        self.window.document.add("Key", {"key": "F10"}, "exec:true")
        with patch("jwm_tools.keys.editor.subprocess.run") as run:
            run.return_value.returncode = 0
            self.window.apply()
            self.assertEqual(run.call_args.args[0], ["jwm", "-restart"])
        self.window.document.add("Key", {"key": "F11"}, "none")
        with patch(
            "jwm_tools.keys.editor.subprocess.run", side_effect=OSError("not running")
        ), patch.object(self.window, "message") as message:
            self.window.apply()
            self.assertIn("File saved", message.call_args.args[0])
        self.assertFalse(self.window.document.dirty)
