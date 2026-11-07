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
            swallow = "--swallow" in sys.argv
            tray = (
                '<Tray x="0" y="-1" height="30"><Swallow name="jwm_ram" width="72" height="30"/></Tray>'
                if swallow
                else ""
            )
            config.write_text(
                f"<JWM><StartupCommand>touch {ready}</StartupCommand>{tray}</JWM>"
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
            ram_args = ["jwm_ram", "--ramfg", "#123456", "--tooltip-fontsize", "12"] + (
                ["--no-swap"] if swallow else []
            )
            with patch.object(sys, "argv", ram_args), patch.object(tk.Misc, "mainloop"):
                app = runpy.run_path(
                    str(Path(__file__).resolve().parents[1] / "jwm_ram")
                )
            root, tooltip = app["root"], app["tooltip"]
            rows = app["tooltip_rows"]
            assert set(rows) == set(app["visible"])
            for name, label in rows.items():
                assert label.cget("foreground") == getattr(app["args"], name + "fg")
                assert label.cget("font") == str(app["tooltip_font"])
            assert rows["ram"].cget("foreground") == "#123456"
            assert app["uptime_label"].cget("foreground") == app["args"].tooltip_fg
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

            if swallow:
                # Tk's wrapper must be a direct child of the tray. A decorated
                # application would instead have a JWM frame between it and root.
                wrapper = tree(root.winfo_id())[0]
                tray_window = tree(wrapper)[0]
                assert (
                    tree(tray_window)[0] == xroot
                ), "Monitor is not embedded in the tray"
                assert tray_window != xroot, "Monitor is still a top-level window"
                assert 0 < root.winfo_width() <= 72 and 0 < root.winfo_height() <= 30
                assert (
                    root.winfo_rooty() >= root.winfo_screenheight() - 30
                ), "Monitor is outside the bottom tray"

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
