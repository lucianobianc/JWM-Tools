"""Launch the actual monitor from Swallow and exercise repeated JWM restarts."""

import os
from pathlib import Path
import re
import select
import shlex
import subprocess
import sys
import tempfile
import time
from xml.sax.saxutils import escape


def main():
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
            assert select.select([read_fd], [], [], 10)[0], "Xvfb startup timed out"
            env = dict(os.environ, DISPLAY=":" + os.read(read_fd, 32).decode().strip())
            script = Path(__file__).resolve().parents[1] / "jwm_ram"
            log = base / "monitor.log"
            generations = base / "generations"
            command = f"echo $$ >> {shlex.quote(str(generations))}; exec {shlex.quote(sys.executable)} {shlex.quote(str(script))} --tooltip-fontsize 12 >>{shlex.quote(str(log))} 2>&1"
            config = base / "jwmrc"
            config.write_text(
                '<JWM><Tray x="0" y="-1" height="30"><Swallow name="jwm_ram" width="72" height="30">'
                + escape(command)
                + "</Swallow></Tray></JWM>"
            )
            wm = subprocess.Popen(
                ["jwm", "-f", str(config)],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            def wait_monitor(old=None):
                deadline = time.monotonic() + 8
                last = ""
                first_seen = None
                while time.monotonic() < deadline:
                    result = subprocess.run(
                        ["xwininfo", "-root", "-tree"],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=3,
                    )
                    last = result.stdout
                    pids = (
                        generations.read_text().splitlines()
                        if generations.exists()
                        else []
                    )
                    pid = pids[-1] if pids else None
                    if pid is None or pid == old:
                        time.sleep(0.03)
                        continue
                    for wid in re.findall(r'(0x[0-9a-f]+) "jwm_ram":', last):
                        info = subprocess.run(
                            ["xwininfo", "-id", wid],
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=3,
                        ).stdout
                        y = re.search(r"Absolute upper-left Y:\s*(\d+)", info)
                        if y and int(y.group(1)) >= 565:
                            if first_seen is None:
                                first_seen = time.monotonic()
                            if time.monotonic() - first_seen >= 0.3:
                                return pid
                    if not re.search(r"\"jwm_ram\"", last):
                        first_seen = None
                    time.sleep(0.03)
                raise AssertionError(
                    "Monitor missing from tray after restart\n"
                    + last
                    + "\n"
                    + (log.read_text() if log.exists() else "no log")
                )

            current = wait_monitor()
            for _ in range(3):
                subprocess.run(["jwm", "-restart"], env=env, check=True, timeout=3)
                current = wait_monitor(current)
            subprocess.run(["jwm", "-exit"], env=env, check=True, timeout=3)
            wm.wait(timeout=5)
        finally:
            os.close(read_fd)
            if wm is not None and wm.poll() is None:
                wm.terminate()
                wm.wait(timeout=5)
            server.terminate()
            server.wait(timeout=5)


if __name__ == "__main__":
    main()
