import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from jwm_tools.menu.model import MenuDocument


@unittest.skipUnless(os.environ.get("JWM_REAL_TESTS") == "1", "Set JWM_REAL_TESTS=1")
class MenuJWMTests(unittest.TestCase):
    def test_edited_tree_icons_and_static_include_parse_in_jwm(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path = base / "jwmrc"
            icon = base / "icon.xpm"
            icon.write_text(
                '/* XPM */\nstatic char * icon[] = {"2 2 2 1", "a c #00ff00", "b c #000000", "ab", "ba"};\n'
            )
            included = base / "menu"
            included.write_text('<JWM><Program label="Included">true</Program></JWM>')
            doc = MenuDocument(path)
            root = doc.add(
                doc.root,
                "RootMenu",
                {"onroot": "12", "label": "Start", "labeled": "true"},
            )
            doc.add(root, "Menu", {"label": "Tools", "icon": str(icon)})
            program = doc.add(
                root, "Program", {"label": "Terminal", "icon": str(icon)}, "xterm"
            )
            self.assertTrue(doc.indent(program))
            doc.add(root, "Include", value=str(included))
            doc.add(root, "Separator")
            doc.add(root, "Restart", {"label": "Restart JWM"})
            doc.add(root, "Exit", {"label": "Exit", "confirm": "true"})
            doc.save()
            result = subprocess.run(
                ["jwm", "-p", "-f", str(path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("invalid", result.stderr.lower())
            self.assertEqual(
                MenuDocument(path).roots()[0].children[0].children[0].value, "xterm"
            )
