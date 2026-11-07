"""Opt-in pixel comparison against a real JWM 2.4.6 on its own X server.

JWM_REAL_TESTS=1 python3 -m unittest discover -s tests -p test_jwm_real.py -v
"""

import os
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from pathlib import Path
import re
import select
import subprocess
import tempfile
import time
import unittest
import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkX11", "3.0")
from gi.repository import Gtk, Gdk, GdkX11
from jwm_tools.style.render import draw_window
from jwm_tools.style.buttons import ButtonConfig, button_layout


def pump():
    for _ in range(15):
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.02)


@unittest.skipUnless(
    os.environ.get("JWM_REAL_TESTS") == "1",
    "Set JWM_REAL_TESTS=1 to compare pixels with JWM",
)
class RealJWMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name)
        read, write = os.pipe()
        cls.xlog = open(cls.base / "xvfb.log", "wb")
        cls.xvfb = subprocess.Popen(
            [
                "Xvfb",
                "-displayfd",
                str(write),
                "-screen",
                "0",
                "1024x768x24",
                "-nolisten",
                "tcp",
            ],
            pass_fds=(write,),
            stdout=cls.xlog,
            stderr=cls.xlog,
        )
        os.close(write)
        ready, _, _ = select.select([read], [], [], 10)
        if not ready:
            raise RuntimeError("Xvfb did not start")
        number = os.read(read, 50).decode().strip()
        os.close(read)
        cls.env = dict(os.environ, DISPLAY=":" + number)
        cls.display = Gdk.Display.open(":" + number)
        if cls.display is None:
            raise RuntimeError("Cannot connect to Xvfb")
        cls.artifacts = Path(
            os.environ.get("JWM_TEST_ARTIFACTS", str(cls.base / "artifacts"))
        )
        cls.artifacts.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.xvfb.terminate()
        cls.xvfb.wait(timeout=5)
        cls.xlog.close()
        cls.temp.cleanup()

    def compare(
        self, decorations, focused, maximized, title_height=24, border=4, order="timx"
    ):
        config = self.base / "jwmrc"
        config.write_text(
            f'<JWM><WindowStyle decorations="{decorations}"><Font>Sans-12</Font><Height>{title_height}</Height><Width>{border}</Width><Corner>0</Corner><Foreground>#eeeeee</Foreground><Background>#555555</Background><Active><Foreground>#ffffff</Foreground><Background>#336699</Background></Active></WindowStyle><TitleButtonOrder>{order}</TitleButtonOrder><FocusModel>click</FocusModel></JWM>'
        )
        log = open(self.base / "jwm.log", "wb")
        wm = subprocess.Popen(
            ["jwm", "-f", str(config)], env=self.env, stdout=log, stderr=log
        )
        window = None
        other = None
        try:
            pump()
            window = Gtk.Window(title="JWM comparison")
            window.set_screen(self.display.get_default_screen())
            window.set_default_size(360, 180)
            window.show_all()
            window.present()
            pump()
            if maximized:
                window.maximize()
                pump()
            if not focused:
                other = Gtk.Window(title="Focus target")
                other.set_screen(self.display.get_default_screen())
                other.set_default_size(100, 80)
                other.move(0, 600)
                other.show_all()
                other.present()
                pump()
            xid = window.get_window().get_xid()
            info = subprocess.check_output(
                ["xwininfo", "-id", str(xid), "-tree"], env=self.env, text=True
            )
            parent_id = int(
                re.search(r"Parent window id: (0x[0-9a-f]+)", info).group(1), 16
            )
            parent = GdkX11.X11Window.foreign_new_for_display(self.display, parent_id)
            geo = parent.get_geometry()
            w, h = geo.width, geo.height
            origin = parent.get_origin()
            actual = Gdk.pixbuf_get_from_window(
                self.display.get_default_screen().get_root_window(),
                origin[-2],
                origin[-1],
                w,
                h,
            )
            self.assertIsNotNone(actual)
            suffix = (
                f"{decorations}-"
                + ("focused" if focused else "inactive")
                + ("-maximized" if maximized else "")
            )
            actual.savev(str(self.artifacts / (suffix + "-jwm.png")), "png", [], [])
            expected = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
            values = {
                "WindowStyle": {
                    "Height": str(title_height),
                    "Width": str(border),
                    "Corner": "0",
                    "Font": "Sans-12",
                    "Foreground": "#eeeeee",
                    "Background": "#555555",
                    "Active": {"Foreground": "#ffffff", "Background": "#336699"},
                }
            }
            draw_window(
                cairo.Context(expected),
                0,
                0,
                w,
                h,
                focused,
                values,
                ButtonConfig(order=order, decorations=decorations),
                maximized,
                title="JWM comparison",
            )
            expected.write_to_png(str(self.artifacts / (suffix + "-preview.png")))
            expected.flush()
            data = expected.get_data()
            pixels = actual.get_pixels()
            fg = (255, 255, 255) if focused else (238, 238, 238)
            yoff = border - 1 if decorations == "motif" else 0
            for kind, x, _ in button_layout(order, w, title_height, border)[0]:
                # Compare glyph coverage, excluding separator and title pixels.
                a = set()
                b = set()
                for y in range(yoff + 3, yoff + title_height - 2):
                    for xx in range(int(x) + 3, int(x) + title_height - 2):
                        i = y * actual.get_rowstride() + xx * actual.get_n_channels()
                        if tuple(pixels[i : i + 3]) == fg:
                            a.add((xx - int(x), y - yoff))
                        j = y * expected.get_stride() + xx * 4
                        if tuple(data[j : j + 3][::-1]) == fg:
                            b.add((xx - int(x), y - yoff))
                self.assertTrue(a, f"{suffix} {kind}: real JWM glyph not found")
                self.assertEqual(
                    a,
                    b,
                    f"{suffix} {kind}: glyph coverage differs: real-only={a-b}, preview-only={b-a}",
                )
            self.assertIsNone(wm.poll())
        finally:
            if other:
                other.destroy()
            if window:
                window.destroy()
            pump()
            wm.terminate()
            wm.wait(timeout=5)
            log.close()

    def test_custom_order_small_title(self):
        self.compare("flat", True, False, 18, 2, "xmit")

    def test_large_motif_maximized(self):
        self.compare("motif", True, True, 32, 6, "timx")

    def test_flat_focused(self):
        self.compare("flat", True, False)

    def test_flat_inactive(self):
        self.compare("flat", False, False)

    def test_flat_maximized(self):
        self.compare("flat", True, True)

    def test_motif_focused(self):
        self.compare("motif", True, False)

    def test_motif_inactive(self):
        self.compare("motif", False, False)

    def test_motif_maximized(self):
        self.compare("motif", True, True)


if __name__ == "__main__":
    unittest.main()
