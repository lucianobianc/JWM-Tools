"""Exercise saved keyboard and mouse bindings on a private Xvfb/JWM server."""

import ctypes as C
import ctypes.util
import os
from pathlib import Path
import select
import shlex
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jwm_tools.keys.model import BindingDocument, keysym


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        with (base / "server.log").open("wb") as xlog, (base / "jwm.log").open(
            "wb"
        ) as wlog:
            read, write = os.pipe()
            xvfb = subprocess.Popen(
                [
                    "Xvfb",
                    "-displayfd",
                    str(write),
                    "-screen",
                    "0",
                    "1024x768x24",
                    "-nolisten",
                    "tcp",
                ],
                pass_fds=(write,),
                stdout=xlog,
                stderr=xlog,
            )
            os.close(write)
            wm = None
            display = None
            x = C.CDLL(C.util.find_library("X11"))
            xt = C.CDLL(C.util.find_library("Xtst"))
            x.XOpenDisplay.argtypes = [C.c_char_p]
            x.XOpenDisplay.restype = C.c_void_p
            x.XCloseDisplay.argtypes = [C.c_void_p]
            x.XKeysymToKeycode.argtypes = [C.c_void_p, C.c_ulong]
            x.XKeysymToKeycode.restype = C.c_ubyte
            x.XDefaultRootWindow.argtypes = [C.c_void_p]
            x.XDefaultRootWindow.restype = C.c_ulong
            x.XSetInputFocus.argtypes = [C.c_void_p, C.c_ulong, C.c_int, C.c_ulong]
            x.XWarpPointer.argtypes = [
                C.c_void_p,
                C.c_ulong,
                C.c_ulong,
                C.c_int,
                C.c_int,
                C.c_uint,
                C.c_uint,
                C.c_int,
                C.c_int,
            ]
            x.XSync.argtypes = [C.c_void_p, C.c_int]
            xt.XTestFakeKeyEvent.argtypes = [C.c_void_p, C.c_uint, C.c_int, C.c_ulong]
            xt.XTestFakeButtonEvent.argtypes = [
                C.c_void_p,
                C.c_uint,
                C.c_int,
                C.c_ulong,
            ]
            try:
                ready, _, _ = select.select([read], [], [], 10)
                assert ready, "Xvfb startup timed out"
                number = os.read(read, 50).decode().strip()
                os.close(read)
                address = ":" + number
                display = x.XOpenDisplay(address.encode())
                assert display, "Cannot connect to isolated X server"
                env = dict(os.environ, DISPLAY=address)
                config = base / "jwmrc"
                config.write_text(
                    '<JWM><!--keep--><RootMenu onroot="3"><Program label="Terminal">true</Program></RootMenu></JWM>'
                )
                doc = BindingDocument(config)
                markers = {
                    name: base / name
                    for name in ("key", "keycode", "press", "release", "double")
                }
                action = lambda name: "exec:/usr/bin/touch " + shlex.quote(
                    str(markers[name])
                )
                doc.add("Key", {"mask": "CS", "key": "F9"}, action("key"))
                doc.add(
                    "Key",
                    {
                        "mask": "C",
                        "keycode": str(x.XKeysymToKeycode(display, keysym("F10"))),
                    },
                    action("keycode"),
                )
                for code, name in [("1", "press"), ("-1", "release"), ("11", "double")]:
                    doc.add("Mouse", {"context": "root", "button": code}, action(name))
                doc.save()
                checked = subprocess.run(
                    ["jwm", "-p", "-f", str(config)],
                    env=env,
                    capture_output=True,
                    text=True,
                )
                assert checked.returncode == 0 and not checked.stderr, checked.stderr
                wm = subprocess.Popen(
                    ["jwm", "-f", str(config)], env=env, stdout=wlog, stderr=wlog
                )
                time.sleep(0.5)
                assert wm.poll() is None, (base / "jwm.log").read_text()
                root = x.XDefaultRootWindow(display)
                x.XSetInputFocus(display, root, 1, 0)
                x.XWarpPointer(display, 0, root, 0, 0, 0, 0, 200, 200)
                x.XSync(display, False)

                def chord(names):
                    codes = [
                        x.XKeysymToKeycode(display, keysym(name)) for name in names
                    ]
                    assert all(codes)
                    for code in codes:
                        xt.XTestFakeKeyEvent(display, code, True, 30)
                    for code in reversed(codes):
                        xt.XTestFakeKeyEvent(display, code, False, 30)
                    x.XSync(display, False)

                chord(["Control_L", "Shift_L", "F9"])
                chord(["Control_L", "F10"])
                for _ in range(2):
                    xt.XTestFakeButtonEvent(display, 1, True, 50)
                    xt.XTestFakeButtonEvent(display, 1, False, 50)
                x.XSync(display, False)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and not all(
                    p.exists() for p in markers.values()
                ):
                    time.sleep(0.05)
                missing = [name for name, path in markers.items() if not path.exists()]
                assert not missing, (missing, (base / "jwm.log").read_text())
                assert "<!--keep-->" in config.read_text()
                print(
                    "PASS: real JWM executed saved keysym, keycode, mouse press/release and double-click bindings"
                )
            finally:
                if display:
                    x.XCloseDisplay(display)
                if wm:
                    wm.terminate()
                    wm.wait(timeout=5)
                xvfb.terminate()
                xvfb.wait(timeout=5)


if __name__ == "__main__":
    main()
