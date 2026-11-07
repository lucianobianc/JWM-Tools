"""Run each real-JWM check in a process with isolated GTK/X11 state."""

import os
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(
    os.environ.get("JWM_REAL_TESTS") == "1",
    "Set JWM_REAL_TESTS=1 to compare pixels with JWM",
)
class RealJWMTests(unittest.TestCase):
    def check(self, name):
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("jwm_pixel_worker.py")),
                "RealJWMTests." + name,
                "-v",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_flat_focused(self):
        self.check("test_flat_focused")

    def test_flat_inactive(self):
        self.check("test_flat_inactive")

    def test_flat_maximized(self):
        self.check("test_flat_maximized")

    def test_motif_focused(self):
        self.check("test_motif_focused")

    def test_motif_inactive(self):
        self.check("test_motif_inactive")

    def test_motif_maximized(self):
        self.check("test_motif_maximized")

    def test_custom_order_small_title(self):
        self.check("test_custom_order_small_title")

    def test_large_motif_maximized(self):
        self.check("test_large_motif_maximized")
