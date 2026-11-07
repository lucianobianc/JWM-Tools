import unittest
from jwm_style.colors import contrast_ratio, luminance, readable_text
from jwm_style.themes import COLLECTIONS, PRESETS, PRESET_METADATA, preset_values
from jwm_style.config import property_values, update_style, flatten


class ColorTests(unittest.TestCase):
    def test_wcag_reference_values(self):
        self.assertAlmostEqual(contrast_ratio("#000000", "#FFFFFF"), 21)
        self.assertAlmostEqual(luminance("#808080"), 0.2158605, places=6)
        self.assertEqual(readable_text("#808080"), "#000000")
        self.assertGreaterEqual(
            contrast_ratio(readable_text("#808080"), "#808080"), 4.5
        )

    def test_gradients_are_not_judged_by_one_endpoint(self):
        bg = "#0054E3;#1B6AE8"
        self.assertGreaterEqual(contrast_ratio(readable_text(bg), bg), 4.5)
        self.assertLess(contrast_ratio("#FFFFFF", "#000000;#FFFFFF"), 1.01)


class PaletteRoleTests(unittest.TestCase):
    def test_all_text_pairs_meet_normal_text_contrast(self):
        for name in PRESETS:
            for section, fields in preset_values(name).items():
                for state, values in [("normal", fields)] + [
                    (key, fields[key])
                    for key in ("Active", "Minimized")
                    if key in fields
                ]:
                    with self.subTest(theme=name, section=section, state=state):
                        self.assertGreaterEqual(
                            contrast_ratio(values["Foreground"], values["Background"]),
                            4.5,
                        )
                if section == "PagerStyle":
                    for bg in (fields["Background"], fields["Active"]["Background"]):
                        self.assertGreaterEqual(
                            contrast_ratio(fields["Text"], bg), 4.5, name
                        )

    def test_hacker_keeps_dark_surfaces_and_colored_terminal_text(self):
        for name in COLLECTIONS["Hacker"]:
            values = preset_values(name)
            for section in ("WindowStyle", "TrayStyle", "MenuStyle", "PopupStyle"):
                self.assertLess(luminance(values[section]["Background"]), 0.06, name)
            self.assertLess(
                luminance(values["WindowStyle"]["Active"]["Background"]), 0.06, name
            )
            self.assertNotEqual(
                values["WindowStyle"]["Active"]["Foreground"], "#FFFFFF", name
            )
            self.assertEqual(values["WindowStyle"]["@decorations"], "flat")
            self.assertEqual(values["WindowStyle"]["Font"], "Monospace-10")
            self.assertEqual(
                values["MenuStyle"]["Active"]["Background"], PRESETS[name]["accent"]
            )

    def test_historical_roles_are_not_one_shared_palette(self):
        luna = preset_values("Redmond")
        self.assertEqual(luna["MenuStyle"]["Background"], "#FFFFFF")
        self.assertEqual(luna["TaskListStyle"]["Background"], "#ECE9D8")
        self.assertEqual(luna["TrayStyle"]["Background"], "#245EDC")
        self.assertNotEqual(
            luna["WindowStyle"]["Active"]["Background"], luna["MenuStyle"]["Background"]
        )
        self.assertEqual(
            preset_values("Mountain View")["WindowStyle"]["Active"]["Background"],
            "#A59F80",
        )
        self.assertEqual(
            preset_values("Palo Alto")["WindowStyle"]["Active"]["Background"], "#FACE9D"
        )
        self.assertEqual(
            preset_values("Santa Clara")["WindowStyle"]["Active"]["Background"],
            "#EDA870",
        )
        self.assertEqual(
            preset_values("Austin")["WindowStyle"]["Active"]["Background"], "#000080"
        )

    def test_decorations_are_consistent_and_supported(self):
        for name in PRESETS:
            values = preset_values(name)
            expected = (
                "motif"
                if name == "Classic Motif"
                or PRESET_METADATA[name]["category"] == "Pastel Workstations"
                or name in ("Mountain View", "Palo Alto", "Santa Clara", "Austin")
                else "flat"
            )
            for section in ("WindowStyle", "TrayStyle", "TaskListStyle", "MenuStyle"):
                self.assertEqual(values[section]["@decorations"], expected, name)
            for section in ("PagerStyle", "PopupStyle"):
                self.assertNotIn("@decorations", values[section])

    def test_light_menu_surface_is_used_for_modern_and_chromatic(self):
        for category in ("Modern", "Chromatic", "Pastel Workstations"):
            for name in COLLECTIONS[category]:
                values = preset_values(name)
                self.assertEqual(
                    values["MenuStyle"]["Background"], PRESETS[name]["light"]
                )
                self.assertNotEqual(
                    values["WindowStyle"]["Active"]["Background"],
                    values["MenuStyle"]["Background"],
                )

    def test_switching_away_from_hacker_resets_window_outline(self):
        text = '<JWM><!--keep--><Key key="F1">exec:xterm</Key></JWM>'
        for name in ("Matrix", "Porcelain"):
            values = preset_values(name)
            for (section, path), value in flatten(values).items():
                text = update_style(text, section, path, value)
        self.assertEqual(
            property_values(text)["WindowStyle"]["Outline"],
            preset_values("Porcelain")["WindowStyle"]["Outline"],
        )
        self.assertEqual(
            property_values(text)["WindowStyle"]["Active"]["Outline"],
            preset_values("Porcelain")["WindowStyle"]["Active"]["Outline"],
        )
        self.assertIn('<!--keep--><Key key="F1">exec:xterm</Key>', text)

    def test_patching_component_decoration_preserves_other_attributes(self):
        for section in ("TrayStyle", "TaskListStyle", "MenuStyle"):
            text = f"<JWM><!--keep--><{section} decorations = 'motif' custom=\"keep\"><Background>#abcdef</Background></{section}></JWM>"
            self.assertEqual(
                update_style(text, section, ("@decorations",), "flat"),
                text.replace("'motif'", "'flat'"),
            )
            self.assertEqual(property_values(text)[section]["@decorations"], "motif")
        with self.assertRaises(ValueError):
            update_style("<JWM/>", "PopupStyle", ("@decorations",), "motif")
