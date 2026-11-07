import os
from pathlib import Path
import select
import shlex
import subprocess
import tempfile
import time
import unittest
from jwm_tools.startup.model import StartupDocument


@unittest.skipUnless(os.environ.get("JWM_REAL_TESTS") == "1", "Set JWM_REAL_TESTS=1")
class StartupJWMTests(unittest.TestCase):
    def test_session_restart_shutdown_and_disabled_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            read_fd, write_fd = os.pipe()
            server = subprocess.Popen(
                [
                    "Xvfb",
                    "-displayfd",
                    str(write_fd),
                    "-screen",
                    "0",
                    "800x600x24",
                    "-nolisten",
                    "tcp",
                ],
                pass_fds=(write_fd,),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            os.close(write_fd)
            wm = None
            try:
                self.assertTrue(
                    select.select([read_fd], [], [], 10)[0], "Xvfb startup timeout"
                )
                display = ":" + os.read(read_fd, 32).decode().strip()
                env = dict(os.environ, DISPLAY=display)
                config = base / "jwmrc"
                log = base / "events"
                config.write_text("<JWM/>")
                doc = StartupDocument(config)
                for phase, event in [
                    ("StartupCommand", "start"),
                    ("RestartCommand", "restart"),
                    ("ShutdownCommand", "stop"),
                ]:
                    doc.add(phase, f"printf '{event}\\n' >> {shlex.quote(str(log))}")
                disabled = base / "must-not-exist"
                doc.add("StartupCommand", "touch " + shlex.quote(str(disabled)), False)
                doc.save()
                parsed = subprocess.run(
                    ["jwm", "-p", "-f", str(config)],
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(parsed.returncode, 0, parsed.stderr)
                self.assertFalse(log.exists())
                wm = subprocess.Popen(
                    ["jwm", "-f", str(config)],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                def wait_event(event):
                    deadline = time.monotonic() + 8
                    while time.monotonic() < deadline:
                        events = log.read_text().splitlines() if log.exists() else []
                        if event in events:
                            return events
                        time.sleep(0.03)
                    self.fail("Missing JWM lifecycle event: " + event)

                self.assertEqual(wait_event("start"), ["start"])
                subprocess.run(["jwm", "-restart"], env=env, check=True, timeout=3)
                self.assertEqual(wait_event("restart"), ["start", "restart"])
                subprocess.run(["jwm", "-exit"], env=env, check=True, timeout=3)
                self.assertEqual(wait_event("stop"), ["start", "restart", "stop"])
                wm.wait(timeout=5)
                self.assertFalse(disabled.exists())
            finally:
                os.close(read_fd)
                if wm is not None and wm.poll() is None:
                    wm.terminate()
                    wm.wait(timeout=5)
                server.terminate()
                server.wait(timeout=5)
