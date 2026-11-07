import os
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(os.environ.get("JWM_REAL_TESTS") == "1", "Set JWM_REAL_TESTS=1")
class RamTooltipTests(unittest.TestCase):
    def test_tooltip_is_above_active_window_without_taking_focus(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("ram_tooltip_worker.py"))],
            capture_output=True,
            text=True,
            timeout=25,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
