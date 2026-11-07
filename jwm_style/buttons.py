"""Global title button configuration and native JWM 2.4.6 geometry.

Reference: joewing/jwm v2.4.6 src/border.c Draw*Button and settings.c
SetTitleButtonOrder. Focus and maximization are independent states.
"""

from dataclasses import dataclass, field
from pathlib import Path
import os
from .config import Configuration

BUTTON_TAGS = ("ButtonClose", "ButtonMin", "ButtonMax", "ButtonMaxActive", "ButtonMenu")
BUTTON_KEYS = tuple(tag + suffix for tag in BUTTON_TAGS for suffix in ("", "Focus"))


@dataclass
class ButtonConfig:
    order: str = "wtimx"
    decorations: str = "flat"
    images: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)

    def image(self, kind, focused=False, maximized=False):
        key = {
            "x": "ButtonClose",
            "i": "ButtonMin",
            "m": "ButtonMaxActive" if maximized else "ButtonMax",
            "w": "ButtonMenu",
        }[kind]
        return (self.images.get(key + "Focus") if focused else None) or self.images.get(
            key
        )


def read_buttons(config):
    result = ButtonConfig(warnings=list(config.warnings))
    paths = []
    names = {}
    for node, source in config.nodes:
        value = (node.text or "").strip()
        if node.tag == "TitleButtonOrder":
            result.order = "".join(c for c in value.lower() if c in "wtimx")[:9]
        elif node.tag == "IconPath":
            path = Path(os.path.expandvars(os.path.expanduser(value)))
            paths.append(path if path.is_absolute() else config.cwd / path)
        elif node.tag in BUTTON_KEYS or node.tag == "DefaultIcon":
            names[node.tag] = value
        elif node.tag == "WindowStyle" and node.get("decorations") in ("motif", "flat"):
            result.decorations = node.get("decorations")
    for key, name in names.items():
        expanded = Path(os.path.expandvars(os.path.expanduser(name)))
        # JWM searches absolute filenames or IconPath entries (not config dir).
        candidates = (
            [expanded] if expanded.is_absolute() else [p / expanded for p in paths]
        )
        for candidate in candidates:
            variants = [candidate]
            variants += [
                Path(str(candidate) + ext)
                for ext in (
                    ".png",
                    ".PNG",
                    ".svg",
                    ".SVG",
                    ".xpm",
                    ".XPM",
                    ".jpg",
                    ".JPG",
                    ".jpeg",
                    ".JPEG",
                    ".xbm",
                    ".XBM",
                )
            ]
            match = next((p for p in variants if p.is_file()), None)
            if match:
                result.images[key] = str(match)
                break
        else:
            if name:
                result.warnings.append(f"Button image not found: {name}")
    if "ButtonMenu" not in result.images and "DefaultIcon" in result.images:
        result.images["ButtonMenu"] = result.images["DefaultIcon"]
    return result


def title_button_images(text, config_path):
    return read_buttons(Configuration(config_path, text=text)).images


def button_layout(order, width, title_height, border=0):
    """Return (kind, x, separator side), title start/end, mirroring JWM."""
    left = border
    right = width - border
    index = order.find("t")
    left_items = order if index < 0 else order[:index]
    right_items = "" if index < 0 else order[index + 1 :]
    buttons = []
    for kind in left_items:
        if left + title_height >= width - border:
            break
        buttons.append((kind, left, "right"))
        left += title_height
    for kind in reversed(right_items):
        if kind == "t" or right - title_height < left:
            break
        right -= title_height
        buttons.append((kind, right - 1, "left"))
    return buttons, left, right


def native_segments(kind, height, maximized=False):
    """Integer X11 segment endpoints and stroke width from border.c."""
    size = (height + 2) // 3 + (2 if kind == "m" else 0)
    x = height // 2 - size // 2
    y = x
    x2 = x + size
    y2 = y + size
    if kind == "x":
        return 2, [(x, y, x2, y2), (x2, y, x, y2)]
    if kind == "i":
        return 2, [(x, y2, x2, y2)]
    if kind == "m":
        segments = [
            (x, y, x2, y),
            (x, y + 1, x2, y + 1),
            (x, y, x, y2),
            (x2, y, x2, y2),
            (x, y2, x2, y2),
        ]
        if maximized:
            x3 = x + size // 2
            y3 = y + size // 2
            segments += [(x, y3, x3, y3), (x, y3 + 1, x3, y3 + 1), (x3, y3, x3, y2)]
        return 1, segments
    return 1, []  # JWM menu uses an application/default icon, never a text glyph.
