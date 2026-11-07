import os
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(
    os.environ.get("JWM_REAL_TESTS") == "1",
    "Set JWM_REAL_TESTS=1 to exercise a private JWM session",
)
class RealBindingTests(unittest.TestCase):
    def test_saved_bindings_are_executed_by_jwm(self):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("keys_jwm_worker.py"))],
            capture_output=True,
            text=True,
            timeout=25,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
