"""Cairo title decorations based on JWM v2.4.6 border.c and color.c."""

import math
import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Pango, PangoCairo
from .fonts import jwm_to_pango
from .buttons import button_layout, native_segments


def rgb(value, fallback="#808080"):
    rgba = Gdk.RGBA()
    if not rgba.parse(value or fallback):
        rgba.parse(fallback)
    return rgba.red, rgba.green, rgba.blue


def derived(value, up=True):
    factor = 371 if up else 141
    return tuple(min(255, (round(c * 255) * factor) >> 8) / 255 for c in rgb(value))


def lines(cr, segments, color, width=1):
    cr.save()
    cr.set_antialias(cairo.ANTIALIAS_NONE)
    cr.set_source_rgb(*color)
    cr.set_line_width(width)
    cr.set_line_cap(cairo.LINE_CAP_SQUARE)
    for x, y, x2, y2 in segments:
        cr.new_path()
        cr.move_to(x + 0.5, y + 0.5)
        cr.line_to(x2 + 0.5, y2 + 0.5)
        cr.stroke()
    cr.restore()


def fill(cr, x, y, w, h, value):
    # JWM accepts vertical a:b and horizontal a;b gradients.
    sep = ";" if ";" in value else ":" if ":" in value else None
    if sep:
        a, b = value.split(sep, 1)
        gradient = cairo.LinearGradient(
            x, y, x + w if sep == ";" else x, y + h if sep == ":" else y
        )
        gradient.add_color_stop_rgb(0, *rgb(a))
        gradient.add_color_stop_rgb(1, *rgb(b))
        cr.set_source(gradient)
    else:
        cr.set_source_rgb(*rgb(value))
    cr.rectangle(x, y, max(0, w), max(0, h))
    cr.fill()


def draw_text(cr, x, y, text, color, font="Sans-12", width=None):
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(jwm_to_pango(font))
    layout.set_text(text, -1)
    if width is not None:
        layout.set_width(max(0, int(width)) * Pango.SCALE)
        layout.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
    cr.set_source_rgb(*rgb(color))
    cr.move_to(x, y)
    PangoCairo.show_layout(cr, layout)
    return layout.get_pixel_size()


def font_height(cr, font):
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(jwm_to_pango(font))
    layout.set_text("Mg", -1)
    return layout.get_pixel_size()[1]


_IMAGE_CACHE = {}


def image(cr, path, x, y, size):
    try:
        from pathlib import Path

        stamp = Path(path).stat().st_mtime_ns
        key = (path, stamp, size)
        if key not in _IMAGE_CACHE:
            if len(_IMAGE_CACHE) > 64:
                _IMAGE_CACHE.clear()
            _IMAGE_CACHE[key] = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                path, size, size, True
            )
        pix = _IMAGE_CACHE[key]
        Gdk.cairo_set_source_pixbuf(
            cr, pix, x + (size - pix.get_width()) / 2, y + (size - pix.get_height()) / 2
        )
        cr.paint()
        return True
    except (OSError, GLib.Error, ValueError):
        return False


def motif_handles(cr, w, h, b, t, up, down):
    # DrawBorderHandles: outer bevels, inner client edges, and resize marks.
    north = t + b
    light = [
        (b, b, w - b - 1, b),
        (b, h - b, w - b, h - b),
        (1, 0, w - 1, 0),
        (1, 1, w - 2, 1),
        (b, b + 1, b, t + b - 1),
        (w - b, b, w - b, h - b),
        (b, b, b, b + t),
        (0, 0, 0, h - 1),
        (1, 1, 1, h - 2),
    ]
    dark = [
        (b + 1, north - 1, w - b - 1, north - 1),
        (b - 1, b - 1, w - b, b - 1),
        (0, h - 1, w, h - 1),
        (1, h - 2, w - 1, h - 2),
        (w - b - 1, b + 1, w - b - 1, north - 1),
        (b - 1, b, b - 1, h - b),
        (w - 1, 0, w - 1, h - 1),
        (w - 2, 1, w - 2, h - 2),
    ]
    lines(cr, light, up)
    lines(cr, dark, down)
    for offset, color in ((-1, down), (0, up)):
        q = t + b + offset
        r = w - t - b + offset
        s = h - t - b + offset
        lines(
            cr,
            [
                (q, 0, q, b),
                (0, q, b, q),
                (w - b, q, w, q),
                (r, 0, r, b),
                (0, s, b, s),
                (q, h - b, q, h),
                (w - b, s, w, s),
                (r, h - b, r, h),
            ],
            color,
        )


def draw_window(cr, x, y, w, h, focused, values, buttons, maximized=False, title=None):
    fields = values.get("WindowStyle", {})
    active = fields.get("Active", {}) if focused else {}
    bg = active.get("Background", fields.get("Background", "#555555"))
    fg = active.get("Foreground", fields.get("Foreground", "#FFFFFF"))
    font = fields.get("Font") or "Sans-12"

    def number(key, default, minimum, maximum):
        try:
            return max(minimum, min(maximum, int(fields.get(key, default))))
        except (ValueError, TypeError):
            return default

    b = number("Width", 5, 1, 128)
    t = number("Height", 0, 0, 256) or font_height(cr, font) + 4
    radius = number("Corner", 4, 0, min(w, h) // 2)
    motif = buttons.decorations == "motif"
    north = t + b if motif else t
    outline = active.get("Outline", fields.get("Outline", ""))
    colors = outline.replace(";", ":").split(":") if outline else []
    # ParseGradient Outline maps the first color to down, second to up.
    down = rgb(colors[0]) if colors else derived(bg.split(":")[0].split(";")[0], False)
    up = rgb(colors[-1]) if colors else derived(bg.split(":")[0].split(";")[0], True)
    cr.save()
    cr.translate(x, y)
    cr.rectangle(0, 0, w, h)
    cr.clip()
    if radius:
        cr.new_path()
        for cx, cy, a1, a2 in (
            (w - radius, radius, -math.pi / 2, 0),
            (w - radius, h - radius, 0, math.pi / 2),
            (radius, h - radius, math.pi / 2, math.pi),
            (radius, radius, math.pi, math.pi * 1.5),
        ):
            cr.arc(cx, cy, radius, a1, a2)
        cr.close_path()
        cr.clip()
    # Inactive opacity concerns client content, not JWM's title decorations.
    fill(cr, 0, 0, w, h, bg.split(":")[-1].split(";")[-1])
    fill(cr, 0, 0, w, north, bg)
    fill(cr, b, north, w - 2 * b, h - north - b, "#25272B" if focused else "#484B4D")
    layout, left, right = button_layout(buttons.order, w, t, b)
    yoff = b - 1 if motif else 0
    for kind, bx, side in layout:
        if motif:
            sx = bx if side == "left" else bx + t - 1
            lines(cr, [(sx, b - 1, sx, b - 1 + t)], down)
            lines(cr, [(sx + 1, b - 1, sx + 1, b - 1 + t)], up)
        key = {
            "x": "ButtonClose",
            "i": "ButtonMin",
            "m": "ButtonMaxActive" if maximized else "ButtonMax",
            "w": "ButtonMenu",
        }[kind]
        candidates = [buttons.images.get(key + "Focus")] if focused else []
        candidates.append(buttons.images.get(key))
        if any(
            path and image(cr, path, bx + 2, yoff + 2, max(1, t - 2))
            for path in candidates
        ):
            continue
        if kind == "w":
            # icon.c GetDefaultIcon: an 8×8 monochrome box with a 1px inset.
            size = max(1, t - 2)
            cr.save()
            cr.translate(bx + 1, yoff + 2)
            cr.scale(size / 8, size / 8)
            cr.set_antialias(cairo.ANTIALIAS_NONE)
            cr.set_source_rgb(*rgb(fg))
            for iy in range(1, 7):
                for ix in range(1, 7):
                    if ix in (1, 6) or iy in (1, 6):
                        cr.rectangle(ix, iy, 1, 1)
            cr.fill()
            cr.restore()
            continue
        width, segments = native_segments(kind, t, maximized)
        lines(
            cr,
            [(a + bx, c + yoff, d + bx, e + yoff) for a, c, d, e in segments],
            rgb(fg),
            width,
        )
    if motif:
        left += 4
        right -= 4
    if left < right:
        draw_text(
            cr,
            left,
            yoff + (t - font_height(cr, font)) // 2,
            title
            or (
                "Maximized window"
                if maximized
                else "Active window" if focused else "Inactive window"
            ),
            fg,
            font,
            right - left,
        )
    if motif:
        motif_handles(cr, w, h, b, t, up, down)
    else:
        cr.set_source_rgb(*down)
        cr.set_line_width(1)
        if radius:
            cr.new_path()
            for cx, cy, a1, a2 in (
                (w - radius - 0.5, radius + 0.5, -math.pi / 2, 0),
                (w - radius - 0.5, h - radius - 0.5, 0, math.pi / 2),
                (radius + 0.5, h - radius - 0.5, math.pi / 2, math.pi),
                (radius + 0.5, radius + 0.5, math.pi, math.pi * 1.5),
            ):
                cr.arc(cx, cy, max(0, radius - 0.5), a1, a2)
            cr.close_path()
            cr.stroke()
        else:
            cr.rectangle(0.5, 0.5, w - 1, h - 1)
            cr.stroke()
    cr.restore()
    return b, t, north
