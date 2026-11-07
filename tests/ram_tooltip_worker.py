"""Check tooltip stacking and focus in a private JWM session."""

import ctypes as C
import ctypes.util
import os
from pathlib import Path
import runpy
import select
import subprocess
import sys
import tempfile
import time
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    with tempfile.TemporaryDirectory() as tmp:
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
        wm = root = display = None
        x = C.CDLL(C.util.find_library("X11"))
        x.XOpenDisplay.argtypes = [C.c_char_p]
        x.XOpenDisplay.restype = C.c_void_p
        x.XDefaultRootWindow.argtypes = [C.c_void_p]
        x.XDefaultRootWindow.restype = C.c_ulong
        x.XQueryTree.argtypes = [
            C.c_void_p,
            C.c_ulong,
            C.POINTER(C.c_ulong),
            C.POINTER(C.c_ulong),
            C.POINTER(C.POINTER(C.c_ulong)),
            C.POINTER(C.c_uint),
        ]
        x.XFree.argtypes = [C.c_void_p]
        x.XGetInputFocus.argtypes = [
            C.c_void_p,
            C.POINTER(C.c_ulong),
            C.POINTER(C.c_int),
        ]
        x.XCloseDisplay.argtypes = [C.c_void_p]
        try:
            assert select.select([read_fd], [], [], 10)[0], "Xvfb timeout"
            os.environ["DISPLAY"] = ":" + os.read(read_fd, 32).decode().strip()
            config = Path(tmp) / "jwmrc"
            ready = Path(tmp) / "ready"
            config.write_text(
                f"<JWM><StartupCommand>touch {ready}</StartupCommand></JWM>"
            )
            wm = subprocess.Popen(
                ["jwm", "-f", str(config)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            assert ready.exists(), "JWM startup timeout"
            with patch.object(sys, "argv", ["jwm_ram"]), patch.object(
                tk.Misc, "mainloop"
            ):
                app = runpy.run_path(
                    str(Path(__file__).resolve().parents[1] / "jwm_ram")
                )
            root, tooltip = app["root"], app["tooltip"]
            root.geometry("+100+300")
            active = tk.Toplevel(root)
            active.title("Active application")
            active.geometry("650x500+0+0")

            def pump():
                for _ in range(15):
                    root.update()
                    time.sleep(0.01)

            pump()
            display = x.XOpenDisplay(None)
            assert display, "XOpenDisplay failed"
            xroot = x.XDefaultRootWindow(display)

            def tree(window):
                parent, root_id = C.c_ulong(), C.c_ulong()
                children, count = C.POINTER(C.c_ulong)(), C.c_uint()
                assert x.XQueryTree(
                    display,
                    window,
                    C.byref(root_id),
                    C.byref(parent),
                    C.byref(children),
                    C.byref(count),
                )
                result = [children[i] for i in range(count.value)]
                if children:
                    x.XFree(children)
                return parent.value, result

            def ancestor(window):
                while True:
                    parent, _ = tree(window)
                    if parent == xroot:
                        return window
                    window = parent

            def focus():
                window, revert = C.c_ulong(), C.c_int()
                x.XGetInputFocus(display, C.byref(window), C.byref(revert))
                return window.value

            for _ in range(2):
                active.lift()
                active.focus_force()
                pump()
                focused = focus()
                app["on_enter"](None)
                pump()
                stacking = tree(xroot)[1]
                assert stacking.index(ancestor(tooltip.winfo_id())) > stacking.index(
                    ancestor(active.winfo_id())
                ), "Tooltip is below the active application"
                assert focus() == focused, "Tooltip stole focus"
                app["on_leave"](None)
                pump()
                assert not tooltip.winfo_ismapped(), "Tooltip did not hide"
        finally:
            os.close(read_fd)
            if root is not None:
                root.destroy()
            if display:
                x.XCloseDisplay(display)
            if wm is not None and wm.poll() is None:
                wm.terminate()
                wm.wait(timeout=5)
            server.terminate()
            server.wait(timeout=5)


if __name__ == "__main__":
    main()
