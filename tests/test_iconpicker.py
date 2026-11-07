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
from gi.repository import Gtk, GdkPixbuf
from jwm_tools.iconpicker import IconPicker, choose_icon


def pump(picker):
    deadline = time.monotonic() + 3
    while picker.pending and time.monotonic() < deadline:
        Gtk.main_iteration_do(False)
    if picker.pending:
        raise AssertionError("Icon picker did not finish loading")


@unittest.skipUnless(os.environ.get("DISPLAY"), "GTK requires X11")
class IconPickerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.image = Path(self.temp.name) / "test icon.png"
        pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 16, 16)
        pixbuf.fill(0x36A269FF)
        pixbuf.savev(str(self.image), "png", [], [])
        self.errors = []
        hook = patch.object(sys, "excepthook", lambda *args: self.errors.append(args))
        hook.start()
        self.addCleanup(hook.stop)
        self.addCleanup(lambda: self.assertFalse(self.errors, str(self.errors)))
        self.names = [f"app-{i:03}" for i in range(120)] + [
            "folder",
            "audio-symbolic",
            "resource-only",
        ]
        self.theme = SimpleNamespace(
            list_contexts=lambda: ["Applications", "Places"],
            list_icons=lambda context: (
                ["folder"] if context == "Places" else self.names
            ),
            lookup_icon=lambda name, size, flags: SimpleNamespace(
                get_filename=lambda: (
                    "/not/a/real/file" if name == "resource-only" else str(self.image)
                )
            ),
        )
        self.picker = IconPicker(None, theme=self.theme)
        self.addCleanup(self.picker.destroy)
        pump(self.picker)

    def test_browsing_pagination_and_selection_returns_actual_file(self):
        self.assertEqual(len(self.picker.store), 96)
        self.picker.more.clicked()
        pump(self.picker)
        self.assertEqual(len(self.picker.store), 121)
        self.picker.view.select_path(Gtk.TreePath.new_from_string("0"))
        self.assertEqual(self.picker.selection, str(self.image))
        self.assertIsNotNone(self.picker.preview.get_pixbuf())
        self.assertTrue(
            self.picker.get_widget_for_response(Gtk.ResponseType.OK).get_sensitive()
        )

    def test_category_search_and_symbolic_filter(self):
        self.picker.context.set_active_id("Places")
        pump(self.picker)
        self.assertEqual([row[1] for row in self.picker.store], ["folder"])
        self.picker.context.set_active_id("")
        self.picker.search.set_text("audio")
        self.picker.reload()
        pump(self.picker)
        self.assertFalse(len(self.picker.store))
        self.picker.symbolic.set_active(True)
        pump(self.picker)
        self.assertEqual([row[1] for row in self.picker.store], ["audio-symbolic"])

    def test_file_picker_cancel_and_invalid_image_preserve_selection(self):
        with patch("jwm_tools.iconpicker.Gtk.FileChooserDialog") as factory:
            factory.return_value.run.return_value = Gtk.ResponseType.OK
            factory.return_value.get_filename.return_value = str(self.image)
            self.picker.choose_file()
            self.assertEqual(self.picker.selection, str(self.image))
            factory.return_value.run.return_value = Gtk.ResponseType.CANCEL
            self.picker.choose_file()
            self.assertEqual(self.picker.selection, str(self.image))
        bad = Path(self.temp.name) / "bad.png"
        bad.write_text("not an image")
        self.assertFalse(self.picker.select_file(str(bad)))
        self.assertEqual(self.picker.selection, str(self.image))
        self.assertTrue(self.picker.error.get_text())

    def test_remove_icon_is_explicit_empty_selection(self):
        self.picker.select_file(str(self.image))
        self.picker.remove_icon()
        self.assertEqual(self.picker.selection, "")
        self.assertIsNone(self.picker.preview.get_pixbuf())

    def test_cancel_helper_does_not_return_pending_selection(self):
        with patch("jwm_tools.iconpicker.IconPicker") as factory:
            factory.return_value.run.return_value = Gtk.ResponseType.CANCEL
            factory.return_value.selection = str(self.image)
            self.assertIsNone(choose_icon(None, "existing"))
            factory.return_value.destroy.assert_called_once()

    def test_destroy_cancels_loading(self):
        self.picker.reload()
        self.assertTrue(self.picker.pending)
        self.picker.destroy()
        self.assertEqual(self.picker.pending, 0)
