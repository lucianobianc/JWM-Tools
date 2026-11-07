import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import cairo
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from jwm_tools.style.editor import Editor
from jwm_tools.style.themes import STYLES, CURRENT_STYLE
from jwm_tools.style.buttons import ButtonConfig
from jwm_tools.style.render import draw_window


def pump():
    for _ in range(10):
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.01)


@unittest.skipUnless(os.environ.get("DISPLAY"), "GTK tests require an X11 display")
class EditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "jwmrc"
        self.original = b'<JWM><!--keep--><WindowStyle decorations="motif"><Font>JetBrains Mono-12:bold</Font><Foreground>#ffffff</Foreground><Background>#555555</Background></WindowStyle><Tray><TrayButton label="Menu">root:1</TrayButton></Tray></JWM>'
        self.path.write_bytes(self.original)
        self.errors = []
        self.hook = patch.object(
            sys, "excepthook", lambda *error: self.errors.append(error)
        )
        self.hook.start()
        self.addCleanup(self.hook.stop)
        with patch(
            "jwm_tools.style.editor.CUSTOM_DIR", Path(self.temp.name) / "styles"
        ):
            self.editor = Editor(self.path)
        self.editor.show_all()
        pump()
        self.addCleanup(self.editor.destroy)
        self.addCleanup(lambda: self.assertEqual(self.errors, [], str(self.errors)))

    def test_layout_at_multiple_sizes_and_all_sections(self):
        for width, height in [(680, 480), (800, 600), (1050, 710), (1200, 800)]:
            self.editor.resize(width, height)
            pump()
            self.assertLessEqual(self.editor.get_allocated_width(), width)
            self.assertLessEqual(self.editor.get_allocated_height(), height)
            for i, section in enumerate(STYLES + ["Start Button"]):
                self.editor.section.set_active(i)
                pump()
                left = self.editor.scroller.translate_coordinates(self.editor, 0, 0)
                right = self.editor.preview.translate_coordinates(self.editor, 0, 0)
                self.assertGreaterEqual(
                    right[0], left[0] + self.editor.scroller.get_allocated_width()
                )
                self.assertFalse(self.editor.scroller.get_hscrollbar().get_mapped())
                self.assertGreater(self.editor.preview.get_allocated_width(), 0)
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_start_icon_file_selection_is_pending_until_apply(self):
        self.editor.section.set_active(len(STYLES))
        row = self.editor.grid.get_child_at(1, 1)
        entry, button = row.get_children()
        selected = str(Path(self.temp.name) / "Start & menu.png")
        Path(selected).touch()
        with patch(
            "jwm_tools.style.editor.choose_icon", return_value=selected
        ) as picker:
            button.emit("clicked")
            picker.assert_called_once()
        self.assertEqual(entry.get_text(), selected)
        self.assertEqual(self.editor.start_pending["icon"], selected)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertTrue(self.editor.write())
        from jwm_tools.style.config import start_attributes

        self.assertEqual(start_attributes(self.path.read_text())["icon"], selected)

    def test_cancelling_start_icon_selection_keeps_existing_value(self):
        self.editor.section.set_active(len(STYLES))
        entry, button = self.editor.grid.get_child_at(1, 1).get_children()
        entry.set_text("existing-icon")
        with patch("jwm_tools.style.editor.choose_icon", return_value=None):
            button.emit("clicked")
        self.assertEqual(entry.get_text(), "existing-icon")
        self.assertEqual(self.editor.start_pending["icon"], "existing-icon")
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_decorations_preview_and_save_only_selected_attribute(self):
        chooser = next(
            child
            for child in self.editor.grid.get_children()
            if isinstance(child, Gtk.ComboBoxText)
        )
        self.assertEqual(chooser.get_active_id(), "motif")
        chooser.set_active_id("flat")
        self.assertEqual(self.path.read_bytes(), self.original)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 600, 400)
        with patch("jwm_tools.style.preview.draw_window") as draw:
            self.editor.draw_preview(self.editor.preview, cairo.Context(surface))
            self.assertEqual(draw.call_args.args[7].decorations, "flat")
        self.assertTrue(self.editor.write())
        self.assertEqual(
            self.path.read_bytes(),
            self.original.replace(b'decorations="motif"', b'decorations="flat"'),
        )
        self.assertEqual(self.path.with_name("jwmrc.bak").read_bytes(), self.original)

    def test_discard_decorations_restores_original_style(self):
        chooser = next(
            child
            for child in self.editor.grid.get_children()
            if isinstance(child, Gtk.ComboBoxText)
        )
        chooser.set_active_id("flat")
        self.editor.on_reset()
        self.assertEqual(self.editor.pending, {})
        chooser = next(
            child
            for child in self.editor.grid.get_children()
            if isinstance(child, Gtk.ComboBoxText)
        )
        self.assertEqual(chooser.get_active_id(), "motif")
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_font_button_conversion_changes_pending_only(self):
        box = self.editor.grid.get_child_at(1, 2)
        button = next(
            child for child in box.get_children() if isinstance(child, Gtk.FontButton)
        )
        self.assertEqual(button.get_font_desc().get_family(), "JetBrains Mono")
        button.set_font_desc(
            Pango.FontDescription.from_string("DejaVu Sans Mono Bold 14")
        )
        button.emit("font-set")
        self.assertEqual(
            self.editor.pending[("WindowStyle", ("Font",))], "DejaVu Sans Mono-14:bold"
        )
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_no_builtins_and_current_configuration_renders_without_writing(self):
        self.assertEqual(self.editor.visible_presets(), [CURRENT_STYLE])
        self.assertFalse(hasattr(self.editor, "category"))
        for i in range(len(STYLES) + 1):
            self.editor.section.set_active(i)
            for mode in (0, 1):
                self.editor.preview_mode.set_active(mode)
                self.editor.preview_maximized.set_active(bool(mode))
                surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 600, 400)
                self.editor.draw_preview(self.editor.preview, cairo.Context(surface))
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertFalse(self.path.with_name("jwmrc.bak").exists())

    def test_saved_custom_style_can_be_selected_without_writing_jwmrc(self):
        self.editor.store.save(
            "Meu estilo",
            {"WindowStyle": {"Foreground": "#CCEEFF", "@decorations": "flat"}},
        )
        self.editor.refresh_presets()
        self.assertEqual(self.editor.visible_presets(), [CURRENT_STYLE, "Meu estilo"])
        self.editor.presets.set_active(1)
        self.assertEqual(
            self.editor.pending[("WindowStyle", ("Foreground",))], "#CCEEFF"
        )
        self.assertEqual(self.path.read_bytes(), self.original)
        self.editor.on_reset()
        self.assertEqual(self.editor.pending, {})
        self.assertEqual(self.editor.presets.get_active_text(), CURRENT_STYLE)

    def test_preview_clips_to_allocated_bounds(self):
        class Bounds:
            def get_allocated_width(self):
                return 200

            def get_allocated_height(self):
                return 120

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 300, 200)
        cr = cairo.Context(surface)
        cr.set_source_rgb(1, 0, 1)
        cr.paint()
        self.editor.draw_preview(Bounds(), cr)
        surface.flush()
        data = surface.get_data()
        stride = surface.get_stride()
        self.assertEqual(
            bytes(data[150 * stride + 250 * 4 : 150 * stride + 250 * 4 + 4]),
            b"\xff\x00\xff\xff",
        )

    def test_write_then_reopen_and_external_change_error(self):
        self.editor.pending[("WindowStyle", ("Width",))] = "7"
        self.assertTrue(self.editor.write())
        self.assertEqual(self.path.with_name("jwmrc.bak").read_bytes(), self.original)
        self.editor.pending[("WindowStyle", ("Width",))] = "8"
        self.path.write_text("<JWM/>")
        with patch.object(self.editor, "error") as error:
            self.assertFalse(self.editor.write())
            error.assert_called_once()
        self.assertEqual(self.path.read_text(), "<JWM/>")

    def test_apply_writes_then_requests_jwm_restart(self):
        self.editor.pending[("WindowStyle", ("Width",))] = "6"
        with patch("jwm_tools.style.editor.subprocess.run") as run:
            run.return_value.returncode = 0
            self.editor.on_apply()
            self.assertEqual(run.call_args.args[0], ["jwm", "-restart"])
            self.assertIn(b"<Width>6</Width>", self.path.read_bytes())

    def test_restart_failure_reports_saved_configuration(self):
        self.editor.pending[("WindowStyle", ("Width",))] = "6"
        with patch(
            "jwm_tools.style.editor.subprocess.run",
            side_effect=OSError("JWM unavailable"),
        ), patch.object(self.editor, "error") as error:
            self.editor.on_apply()
            self.assertIn(
                "Configuration saved, but restart failed", str(error.call_args)
            )
        self.assertIn(b"<Width>6</Width>", self.path.read_bytes())


class RenderTests(unittest.TestCase):
    def test_native_buttons_have_distinct_maximized_state(self):
        surfaces = []
        for maximized in (False, True):
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 100)
            draw_window(
                cairo.Context(surface),
                0,
                0,
                200,
                100,
                True,
                {"WindowStyle": {"Height": "24"}},
                ButtonConfig(order="tm"),
                maximized,
            )
            surface.flush()
            surfaces.append(bytes(surface.get_data()))
        self.assertNotEqual(*surfaces)

    def test_configured_image_and_focus_override_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for i, color in enumerate([(1, 0, 0), (0, 1, 0)]):
                path = str(Path(tmp) / f"{i}.png")
                paths.append(path)
                s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 10, 10)
                c = cairo.Context(s)
                c.set_source_rgb(*color)
                c.paint()
                s.write_to_png(path)
            for focus, expected in [
                (False, b"\x00\x00\xff\xff"),
                (True, b"\x00\xff\x00\xff"),
            ]:
                surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 60)
                draw_window(
                    cairo.Context(surface),
                    0,
                    0,
                    100,
                    60,
                    focus,
                    {"WindowStyle": {"Height": "24", "Width": "4"}},
                    ButtonConfig(
                        order="tx",
                        images={"ButtonClose": paths[0], "ButtonCloseFocus": paths[1]},
                    ),
                )
                surface.flush()
                offset = 12 * surface.get_stride() + 83 * 4
                self.assertEqual(
                    bytes(surface.get_data()[offset : offset + 4]), expected
                )

    def test_corner_radius_clips_flat_and_motif(self):
        for decorations in ("flat", "motif"):
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 60)
            draw_window(
                cairo.Context(surface),
                0,
                0,
                100,
                60,
                True,
                {"WindowStyle": {"Corner": "8"}},
                ButtonConfig(decorations=decorations),
            )
            surface.flush()
            self.assertEqual(bytes(surface.get_data()[:4]), b"\x00\x00\x00\x00")
