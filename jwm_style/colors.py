"""sRGB luminance and text contrast, following WCAG 2 relative luminance.

These checks cover the palette's text/background pairs, not certification of
an entire desktop. Gradients are sampled to avoid testing just their endpoints.
"""

import re


def rgb(color):
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError(f"Expected an sRGB hex color: {color}")
    return tuple(int(color[i : i + 2], 16) / 255 for i in (1, 3, 5))


def luminance(color):
    values = [
        v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb(color)
    ]
    return sum(v * w for v, w in zip(values, (0.2126, 0.7152, 0.0722)))


def mix(first, second, amount):
    return "#" + "".join(
        f"{round((a*(1-amount)+b*amount)*255):02X}"
        for a, b in zip(rgb(first), rgb(second))
    )


def backgrounds(value):
    stops = re.split(r"[:;]", value)
    for first, second in zip(stops, stops[1:]):
        for i in range(17):
            yield mix(first, second, i / 16)
    if len(stops) == 1:
        yield value


def contrast_ratio(foreground, background):
    fg = luminance(foreground)
    return min(
        (max(fg, luminance(bg)) + 0.05) / (min(fg, luminance(bg)) + 0.05)
        for bg in backgrounds(background)
    )


def readable_text(background, preferred=None):
    if preferred and contrast_ratio(preferred, background) >= 4.5:
        return preferred
    best = max(("#000000", "#FFFFFF"), key=lambda c: contrast_ratio(c, background))
    if best == "#000000" and contrast_ratio("#202124", background) >= 4.5:
        return "#202124"
    return best


def luminous_text(accent, background):
    """Keep a terminal accent's hue, lifting it only as far as legibility needs."""
    for step in range(21):
        candidate = mix(accent, "#FFFFFF", step / 20)
        if contrast_ratio(candidate, background) >= 4.5:
            return candidate
    return readable_text(background)


def bevel(background):
    """JWM color.c's fixed-point shadow/highlight factors (down:up)."""
    base = next(backgrounds(background))
    channels = [round(v * 255) for v in rgb(base)]

    def shade(factor):
        return "#" + "".join(f"{min(255,(v*factor)>>8):02X}" for v in channels)

    return shade(141) + ":" + shade(371)
