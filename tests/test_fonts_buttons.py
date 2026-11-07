from pathlib import Path
import tempfile
import unittest
import gi

gi.require_version("Pango", "1.0")
from gi.repository import Pango
from jwm_tools.style.fonts import jwm_to_pango, pango_to_jwm
from jwm_tools.style.buttons import read_buttons, button_layout, native_segments
from jwm_tools.style.config import Configuration


class FontTests(unittest.TestCase):
    def test_family_spaces_bold_roundtrip(self):
        self.assertEqual(
            pango_to_jwm("JetBrains Mono Bold 12"), "JetBrains Mono-12:bold"
        )
        desc = jwm_to_pango("JetBrains Mono-12:bold")
        self.assertEqual(desc.get_family(), "JetBrains Mono")
        self.assertEqual(desc.get_weight(), Pango.Weight.BOLD)
        self.assertEqual(desc.get_size(), 12 * Pango.SCALE)

    def test_family_hyphen_italic_fractional_size(self):
        value = pango_to_jwm("My-Font Italic 10.5")
        desc = jwm_to_pango(value)
        self.assertEqual(desc.get_family(), "My-Font")
        self.assertEqual(desc.get_style(), Pango.Style.ITALIC)
        self.assertEqual(desc.get_size(), 10.5 * Pango.SCALE)

    def test_pixel_size_and_rendering_hints(self):
        desc = jwm_to_pango("Sans:pixelsize=18:weight=200:slant=110")
        self.assertTrue(desc.get_size_is_absolute())
        value = pango_to_jwm(desc, "Sans-12:antialias=false:hintstyle=hintslight")
        self.assertIn(":pixelsize=18", value)
        self.assertIn(":antialias=false:hintstyle=hintslight", value)
        self.assertEqual(jwm_to_pango(value).get_style(), Pango.Style.OBLIQUE)


class ButtonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_global_tags_includes_iconpaths_and_focus_states(self):
        icons = self.base / "icons"
        icons.mkdir()
        for name in ("close", "focus", "restore", "restore-focus"):
            (icons / (name + ".png")).write_bytes(b"fixture")
        (self.base / "buttons").write_text(
            "<JWM><ButtonClose>close</ButtonClose><ButtonCloseFocus>focus</ButtonCloseFocus><ButtonMaxActive>restore</ButtonMaxActive><ButtonMaxActiveFocus>restore-focus</ButtonMaxActiveFocus><TitleButtonOrder>xmitw</TitleButtonOrder></JWM>"
        )
        path = self.base / "jwmrc"
        path.write_text(
            '<JWM><Include>buttons</Include><IconPath>icons</IconPath><WindowStyle decorations="motif"><ButtonClose>wrong</ButtonClose></WindowStyle></JWM>'
        )
        result = read_buttons(Configuration(path, cwd=self.base))
        self.assertEqual(result.decorations, "motif")
        self.assertEqual(result.order, "xmitw")
        self.assertEqual(result.image("x", False), str(icons / "close.png"))
        self.assertEqual(result.image("x", True), str(icons / "focus.png"))
        self.assertEqual(
            result.image("m", True, True), str(icons / "restore-focus.png")
        )
        self.assertEqual(result.image("m", False, True), str(icons / "restore.png"))
        self.assertIsNone(result.image("m", True, False))

    def test_focus_falls_back_to_normal(self):
        path = self.base / "jwmrc"
        icon = self.base / "close.png"
        icon.touch()
        path.write_text(f"<JWM><ButtonClose>{icon}</ButtonClose></JWM>")
        self.assertEqual(read_buttons(Configuration(path)).image("x", True), str(icon))

    def test_title_order_default_and_custom(self):
        layout, left, right = button_layout("wtimx", 200, 20, 4)
        self.assertEqual(
            layout,
            [
                ("w", 4, "right"),
                ("x", 175, "left"),
                ("m", 155, "left"),
                ("i", 135, "left"),
            ],
        )
        self.assertEqual((left, right), (24, 136))
        layout, left, right = button_layout("xmitw", 200, 20, 4)
        self.assertEqual([b[0] for b in layout], list("xmiw"))
        self.assertTrue(all(0 <= x < 200 for _, x, _ in layout))

    def test_native_geometry_from_jwm_246(self):
        self.assertEqual(
            native_segments("x", 20), (2, [(7, 7, 14, 14), (14, 7, 7, 14)])
        )
        self.assertEqual(native_segments("i", 20), (2, [(7, 14, 14, 14)]))
        self.assertEqual(len(native_segments("m", 20, False)[1]), 5)
        self.assertEqual(len(native_segments("m", 20, True)[1]), 8)

    def test_extensionless_and_uppercase_icon_search(self):
        for filename in ("close", "close.JPEG"):
            with self.subTest(filename=filename):
                icon = self.base / filename
                icon.touch()
                path = self.base / "jwmrc"
                path.write_text(
                    f"<JWM><IconPath>{self.base}</IconPath><ButtonClose>close</ButtonClose></JWM>"
                )
                self.assertEqual(
                    read_buttons(Configuration(path)).image("x"), str(icon)
                )
                icon.unlink()
