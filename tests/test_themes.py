import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from jwm_style.themes import PRESETS, preset_values, StyleStore
from jwm_style.config import flatten, update_style


class ThemeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = StyleStore(self.temp.name)

    def test_all_34_presets_can_be_applied_to_empty_config(self):
        self.assertEqual(len(PRESETS), 34)
        for name in PRESETS:
            with self.subTest(name=name):
                text = "<JWM><!--do not lose--></JWM>"
                for (section, path), value in flatten(preset_values(name)).items():
                    text = update_style(text, section, path, value)
                self.assertIn("<!--do not lose-->", text)
                ET.fromstring(text)

    def test_save_reload_rename_delete_preserves_old_schema(self):
        values = preset_values("CDE Pastel")
        path = self.store.save("My theme", values)
        payload = json.loads(path.read_text())
        payload["legacyMetadata"] = "keep"
        path.write_text(json.dumps(payload))
        self.assertEqual(self.store.load()["My theme"][0], values)
        new = self.store.rename("My theme", "New theme")
        self.assertFalse(path.exists())
        self.assertEqual(json.loads(new.read_text())["legacyMetadata"], "keep")
        self.store.delete("New theme")
        self.assertEqual(self.store.load(), {})

    def test_slug_collision_and_builtin_names_rejected(self):
        self.store.save("A B", {})
        with self.assertRaises(ValueError):
            self.store.save("A-B", {})
        with self.assertRaises(ValueError):
            self.store.save("CDE Pastel", {})
        with self.assertRaises(ValueError):
            self.store.save("../escape", {})

    def test_rename_with_same_slug(self):
        path = self.store.save("A B", {})
        self.assertEqual(self.store.rename("A B", "A-B"), path)
        self.assertIn("A-B", self.store.load())

    def test_existing_legacy_json_and_malformed_files(self):
        base = Path(self.temp.name)
        (base / "old.json").write_text(
            json.dumps(
                {"name": "Legacy", "values": {"WindowStyle": {"Font": "Sans-12:bold"}}}
            )
        )
        (base / "bad.json").write_text("{")
        self.assertEqual(list(self.store.load()), ["Legacy"])
