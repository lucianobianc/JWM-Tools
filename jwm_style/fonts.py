"""Fontconfig (JWM/Xft) ↔ Pango font chooser conversion.

Use Fontconfig's parser, including escaped family names, rather than splitting
names on spaces. Unedited font strings remain byte-for-byte unchanged in XML.
"""

import ctypes as C
import ctypes.util
import gi

gi.require_version("Pango", "1.0")
from gi.repository import Pango

fc = C.CDLL(ctypes.util.find_library("fontconfig"))
fc.FcNameParse.argtypes = [C.c_char_p]
fc.FcNameParse.restype = C.c_void_p
fc.FcPatternDestroy.argtypes = [C.c_void_p]
fc.FcPatternGetString.argtypes = [
    C.c_void_p,
    C.c_char_p,
    C.c_int,
    C.POINTER(C.c_char_p),
]
fc.FcPatternGetDouble.argtypes = [
    C.c_void_p,
    C.c_char_p,
    C.c_int,
    C.POINTER(C.c_double),
]
fc.FcPatternGetInteger.argtypes = [C.c_void_p, C.c_char_p, C.c_int, C.POINTER(C.c_int)]
WEIGHTS = [
    (0, 100),
    (40, 200),
    (50, 300),
    (55, 350),
    (75, 380),
    (80, 400),
    (100, 500),
    (180, 600),
    (200, 700),
    (205, 800),
    (210, 900),
    (215, 1000),
]


def jwm_to_pango(value):
    pattern = fc.FcNameParse((value or "Sans-12").encode())
    if not pattern:
        raise ValueError("Invalid Fontconfig font")
    try:
        desc = Pango.FontDescription()
        family = C.c_char_p()
        fc.FcPatternGetString(pattern, b"family", 0, C.byref(family))
        desc.set_family(family.value.decode() if family.value else "Sans")
        size = C.c_double(12)
        if fc.FcPatternGetDouble(pattern, b"size", 0, C.byref(size)) == 0:
            desc.set_size(round(size.value * Pango.SCALE))
        else:
            size = C.c_double(12)
            if fc.FcPatternGetDouble(pattern, b"pixelsize", 0, C.byref(size)) == 0:
                desc.set_absolute_size(size.value * Pango.SCALE)
            else:
                desc.set_size(12 * Pango.SCALE)
        weight = C.c_int(80)
        fc.FcPatternGetInteger(pattern, b"weight", 0, C.byref(weight))
        desc.set_weight(
            Pango.Weight(min(WEIGHTS, key=lambda pair: abs(pair[0] - weight.value))[1])
        )
        slant = C.c_int()
        fc.FcPatternGetInteger(pattern, b"slant", 0, C.byref(slant))
        desc.set_style(
            Pango.Style.ITALIC
            if slant.value == 100
            else Pango.Style.OBLIQUE if slant.value == 110 else Pango.Style.NORMAL
        )
        return desc
    finally:
        fc.FcPatternDestroy(pattern)


def pango_to_jwm(font, original=None):
    desc = (
        font
        if isinstance(font, Pango.FontDescription)
        else Pango.FontDescription.from_string(font)
    )
    family = desc.get_family() or "Sans"
    family = "".join("\\" + c if c in "\\-:," else c for c in family)
    size = f"{desc.get_size()/Pango.SCALE:g}"
    result = family + (
        ":pixelsize=" + size if desc.get_size_is_absolute() else "-" + size
    )
    weight = int(desc.get_weight())
    if weight != 400:
        names = {
            100: "thin",
            200: "extralight",
            300: "light",
            350: "demilight",
            380: "book",
            500: "medium",
            600: "demibold",
            700: "bold",
            800: "extrabold",
            900: "black",
            1000: "extrablack",
        }
        result += ":" + names.get(
            weight, "weight=" + str(min(WEIGHTS, key=lambda p: abs(p[1] - weight))[0])
        )
    if desc.get_style() != Pango.Style.NORMAL:
        result += ":italic" if desc.get_style() == Pango.Style.ITALIC else ":oblique"
    # Keep rendering hints from advanced configurations when choosing a font.
    if original:
        import re

        for item in re.split(r"(?<!\\):", original)[1:]:
            if "=" in item and item.split("=", 1)[0].lower() not in (
                "family",
                "style",
                "size",
                "pixelsize",
                "weight",
                "slant",
                "width",
            ):
                result += ":" + item
    return result
