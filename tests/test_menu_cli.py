from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch


class MenuCLITests(unittest.TestCase):
    def test_no_options_opens_editor_without_generating(self):
        with patch.object(sys, "argv", ["jwm_menu"]), patch(
            "jwm_tools.menu.editor.main"
        ) as editor, patch("jwm_tools.menu.generator.main") as generator:
            runpy.run_path(
                str(Path(__file__).resolve().parents[1] / "jwm_menu"),
                run_name="__main__",
            )
            editor.assert_called_once()
            generator.assert_not_called()

    def test_generate_is_explicit_and_does_not_open_editor(self):
        with patch.object(sys, "argv", ["jwm_menu", "--generate"]), patch(
            "jwm_tools.menu.editor.main"
        ) as editor, patch("jwm_tools.menu.generator.main") as generator:
            runpy.run_path(
                str(Path(__file__).resolve().parents[1] / "jwm_menu"),
                run_name="__main__",
            )
            generator.assert_called_once()
            editor.assert_not_called()
