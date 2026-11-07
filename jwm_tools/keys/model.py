"""Edit top-level Key/Mouse nodes without serializing the surrounding XML."""

from __future__ import annotations

from collections import defaultdict
import ctypes
import ctypes.util
from dataclasses import dataclass, replace
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from ..xmlutil import (
    Configuration,
    find_elements,
    save_atomic,
    patch_node,
    serialize,
    append_nodes,
)

CONTEXTS = {
    "root": "Desktop",
    "title": "Title",
    "border": "Border",
    "icon": "Window icon",
    "close": "Close",
    "maximize": "Maximize",
    "minimize": "Minimize",
}
MODIFIERS = {
    "C": "Ctrl",
    "S": "Shift",
    "A": "Alt",
    "2": "Mod2",
    "3": "Mod3",
    "4": "Super",
    "5": "Mod5",
}
ACTIONS = tuple(
    "at# center close ddesktop desktop# down escape exit fullscreen kill ldesktop left maxbottom maxbottomleft maxbottomright maxh maximize maxleft maxright maxtop maxtopleft maxtopright maxv minimize move next nextstacked none prev prevstacked rdesktop resize restart restore right select send# sendd sendl sendr sendu shade showdesktop showtray stick udesktop up window".split()
)
_X11 = None


def keysym(name):
    global _X11
    if _X11 is None:
        _X11 = ctypes.CDLL(ctypes.util.find_library("X11") or "libX11.so.6")
        _X11.XStringToKeysym.argtypes = [ctypes.c_char_p]
        _X11.XStringToKeysym.restype = ctypes.c_ulong
    return _X11.XStringToKeysym(name.encode("utf-8"))


def normalize_mask(mask):
    chars = set(mask.replace("1", "A"))
    if chars - set(MODIFIERS):
        raise ValueError("Valid modifiers: C, S, A (or 1), 2, 3, 4 and 5.")
    return "".join(char for char in MODIFIERS if char in chars)


def validate(binding, previous=None):
    attrs = binding.attrs
    normalize_mask(attrs.get("mask", ""))
    if binding.kind == "Key":
        key, code = attrs.get("key", ""), attrs.get("keycode", "")
        if bool(key) == bool(code):
            raise ValueError("Enter either a key or a keycode, not both.")
        if code:
            if not code.isdecimal() or not 8 <= int(code) <= 255:
                raise ValueError("X11 keycodes must be between 8 and 255.")
        else:
            if key.count("#") > 1:
                raise ValueError("Use only one # in a key sequence.")
            names = (
                [key.replace("#", str(n)) for n in range(1, 10)]
                if "#" in key
                else [key]
            )
            if any(not keysym(name) for name in names):
                raise ValueError("Invalid X11 key name: " + key)
            if "#" in key and binding.action not in ("desktop#", "send#", "at#"):
                raise ValueError("Keys containing # require desktop#, send# or at#.")
    elif binding.kind == "Mouse":
        try:
            button = int(attrs.get("button", ""))
        except ValueError:
            raise ValueError("Enter a numeric button code.") from None
        valid_button = (
            -255 <= button <= -1
            or 1 <= button <= 255
            or (button > 255 and button % 11 == 0 and button // 11 <= 255)
        )
        if not valid_button:
            raise ValueError("Invalid button code.")
        if attrs.get("context") not in CONTEXTS:
            raise ValueError("Choose a valid mouse context.")
    else:
        raise ValueError("Invalid binding type.")
    action = binding.action
    if not action:
        raise ValueError("Enter an action.")
    if previous is not None and previous.action == action:
        return
    if "\n" in action or "\r" in action:
        raise ValueError("Enter the action on a single line.")
    if action in ACTIONS:
        return
    if action.startswith("exec:") and action[5:].strip():
        return
    if action.startswith("root:") and action[5:].strip():
        return
    if re.fullmatch(r"resize:[nsew]+", action):
        return
    raise ValueError("Invalid action. Use a JWM action or exec:command.")


@dataclass
class Binding:
    token: str
    kind: str
    attrs: dict
    action: str
    source: Path
    span: tuple | None = None
    editable: bool = True

    def signatures(self):
        try:
            mask = normalize_mask(self.attrs.get("mask", ""))
        except ValueError:
            mask = self.attrs.get("mask", "")
        if self.kind == "Mouse":
            return [
                (
                    self.kind,
                    mask,
                    self.attrs.get("context"),
                    str(int(self.attrs.get("button", "0") or 0)),
                )
            ]
        if self.attrs.get("key"):
            key = self.attrs["key"]
            names = (
                [key.replace("#", str(n)) for n in range(1, 10)]
                if "#" in key
                else [key]
            )
            return [
                (
                    "Key",
                    mask,
                    "key",
                    keysym(k.lower() if len(k) == 1 and k.isalpha() else k),
                )
                for k in names
            ]
        return [("Key", mask, "keycode", str(int(self.attrs.get("keycode", "0") or 0)))]

    def shortcut(self):
        try:
            mask = normalize_mask(self.attrs.get("mask", ""))
        except ValueError:
            mask = self.attrs.get("mask", "")
        mods = [MODIFIERS.get(c, c) for c in mask]
        value = (
            self.attrs.get("key") or "keycode " + self.attrs.get("keycode", "")
            if self.kind == "Key"
            else mouse_label(self.attrs.get("button", ""))
        )
        return "+".join([*mods, value])


def mouse_label(code):
    names = {
        1: "Left",
        2: "Middle",
        3: "Right",
        4: "Scroll up",
        5: "Scroll down",
        6: "Scroll left",
        7: "Scroll right",
        8: "Back",
        9: "Forward",
    }
    try:
        value = int(code)
    except ValueError:
        return code
    if value < 0:
        return "Release " + names.get(-value, str(-value)).lower()
    if value % 11 == 0 and value // 11 in names:
        return "Double " + names[value // 11].lower()
    return names.get(value, "Button " + str(value))


def read_bindings(path, data, editable):
    text = data.decode("utf-8")
    root = ET.fromstring(text)
    if root.tag != "JWM":
        return []
    spans = sorted(
        [
            (*span, kind)
            for kind in ("Key", "Mouse")
            for span in find_elements(text, kind)
            if span[4] == 1
        ]
    )
    result = []
    for i, span in enumerate(spans):
        a, b, cs, ce, depth, kind = span
        node = ET.fromstring(text[a:b])
        result.append(
            Binding(
                str(i),
                kind,
                dict(node.attrib),
                "".join(node.itertext()).strip(),
                path,
                (a, b, cs, ce, depth),
                editable,
            )
        )
    return result


class BindingDocument:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        self.config = Configuration(self.path)
        self.original = self.config.snapshots[self.path]
        self.local = read_bindings(self.path, self.original, True)
        for i, binding in enumerate(self.local):
            binding.token = "L" + str(i)
        self.included = []
        for path, data in self.config.snapshots.items():
            if path == self.path or data is None:
                continue
            try:
                items = read_bindings(path, data, False)
            except (ET.ParseError, UnicodeError, ValueError):
                continue
            for item in items:
                item.token = "I" + str(len(self.included))
                self.included.append(item)
        self.changes = {}
        self.additions = []
        self.next_id = 0

    @property
    def dirty(self):
        return bool(self.changes or self.additions)

    def entries(self):
        return (
            [
                self.changes.get(b.token, b)
                for b in self.local
                if self.changes.get(b.token, b) is not None
            ]
            + self.additions
            + self.included
        )

    def get(self, token):
        return next(b for b in self.entries() if b.token == token)

    def add(self, kind, attrs, action):
        binding = Binding("N" + str(self.next_id), kind, dict(attrs), action, self.path)
        validate(binding)
        self.next_id += 1
        self.additions.append(binding)
        return binding

    def update(self, token, attrs, action):
        current = self.get(token)
        if not current.editable:
            raise ValueError("Open the source file to edit this binding.")
        candidate = replace(current, attrs=dict(attrs), action=action)
        validate(candidate, current)
        if token.startswith("N"):
            self.additions = [
                candidate if b.token == token else b for b in self.additions
            ]
        else:
            original = next(b for b in self.local if b.token == token)
            if (
                candidate.attrs == original.attrs
                and candidate.action == original.action
            ):
                self.changes.pop(token, None)
            else:
                self.changes[token] = candidate
        return candidate

    def remove(self, token):
        binding = self.get(token)
        if not binding.editable:
            raise ValueError("Open the source file to delete this binding.")
        if token.startswith("N"):
            self.additions = [b for b in self.additions if b.token != token]
        else:
            self.changes[token] = None

    def reset(self):
        self.changes.clear()
        self.additions.clear()

    def conflicts(self, candidate=None, exclude=None):
        groups = defaultdict(list)
        for binding in self.entries():
            if binding.token != exclude:
                try:
                    signatures = binding.signatures()
                except (ValueError, OSError):
                    continue
                for signature in signatures:
                    groups[signature].append(binding)
        if candidate is not None:
            matches = {
                b.token: b
                for sig in candidate.signatures()
                for b in groups.get(sig, [])
            }
            return list(matches.values())
        return {b.token for group in groups.values() if len(group) > 1 for b in group}

    def preview(self):
        text = self.original.decode("utf-8")
        for original in reversed(self.local):
            if original.token not in self.changes:
                continue
            changed = self.changes[original.token]
            replacement = "" if changed is None else patch_node(text, changed, original)
            a, b = original.span[:2]
            text = text[:a] + replacement + text[b:]
        text = append_nodes(text, [serialize(b) for b in self.additions])
        ET.fromstring(text)
        return text

    def save(self):
        if not self.config.unchanged():
            raise ValueError(
                "The configuration or an Include changed on disk. Reload before saving."
            )
        data = self.preview().encode("utf-8")
        if data != self.original:
            if not self.config.unchanged():
                raise ValueError(
                    "The configuration changed while preparing the changes."
                )
            save_atomic(self.path.with_name(self.path.name + ".bak"), self.original)
            save_atomic(self.path, data)
        self.__init__(self.path)
