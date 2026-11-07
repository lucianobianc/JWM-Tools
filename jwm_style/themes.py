"""Built-in palettes and backwards-compatible custom style storage."""

import os
import json
from pathlib import Path
from .colors import readable_text, contrast_ratio, mix, luminous_text, bevel
from .theme_profiles import HERITAGE

STYLES = [
    "WindowStyle",
    "TrayStyle",
    "TaskListStyle",
    "PagerStyle",
    "MenuStyle",
    "PopupStyle",
]
COLORS = ["Foreground", "Background"]
PRESETS = {
    "Graphite & Amber": {
        "base": "#35383B",
        "text": "#E5E1D8",
        "accent": "#D09A52",
        "accent_text": "#202124",
        "muted": "#B8B6AF",
        "dark": "#202124",
    },
    "Slate Lavender": {
        "base": "#343744",
        "text": "#E6E6ED",
        "accent": "#9295AD",
        "accent_text": "#161820",
        "muted": "#C5C3D4",
        "dark": "#242630",
    },
    "Classic Motif": {
        "base": "#444B50",
        "text": "#DFE4DF",
        "accent": "#829B9D",
        "accent_text": "#20282A",
        "muted": "#B8C5C2",
        "dark": "#292D30",
    },
    "Midnight Teal": {
        "base": "#293940",
        "text": "#DAE4E1",
        "accent": "#659A99",
        "accent_text": "#19252B",
        "muted": "#A5BDBB",
        "dark": "#19252B",
    },
}

# Each palette: dark, base, accent, muted, light. These are JWM adaptations,
# not exact historical color extractions.
COLLECTIONS = {
    "Original": {
        "Graphite & Amber": None,
        "Slate Lavender": None,
        "Classic Motif": None,
        "Midnight Teal": None,
    },
    "Heritage": {
        "Redmond": "#1746A0 #245EDC #5C91ED #A6CAF0 #ECE9D8",
        "Redmond Silver": "#53576F #8589A8 #B1B4CB #D7D9E5 #ECECF1",
        "Redmond Olive": "#40542D #66794A #91A477 #C8D3A7 #ECE9D8",
        "Mountain View": "#424A56 #4C719E #858F9B #B5B9BE #ECECEA",
        "Palo Alto": "#665D60 #B67D7B #D49A91 #D6C3BB #F0ECE5",
        "Santa Clara": "#574C8F #7972A7 #A5A0C3 #C7C5D6 #E3E2E9",
        "Austin": "#25256D #4545A2 #7979C0 #B6B6D5 #E3E3EB",
    },
    "Modern": {
        "Porcelain": "#374454 #CCD4DC #7998B5 #E9EAEB #F8F8F6",
        "Arctic": "#354C60 #B6D0DE #759EB8 #DFEAF0 #F5F9FB",
        "Linen": "#414944 #B9C4B0 #85988A #E9E1D1 #FAF6EC",
        "Wisteria": "#494156 #C9BBD9 #9884B7 #E8E1F1 #F8F6FB",
        "Seashell": "#594C58 #F0DDD7 #DCA99E #FBF6F0 #FBF6F0",
    },
    "Chromatic": {
        "Azure": "#284E78 #5F8FB8 #9FC1D5 #D6E5EC #F1F6F8",
        "Amethyst": "#51466E #8E7CAD #B9ACCC #E0D9E8 #F6F3F8",
        "Sage": "#405E51 #799B84 #AFC6AF #DCE6D7 #F4F6EE",
        "Coral": "#875B5A #C58C83 #E1B4A7 #F1DCD1 #FBF3E9",
        "Amber": "#70552F #B38A50 #D6B57D #EBDBC0 #FAF5EA",
        "Slate": "#35414F #697D8C #A1B0B9 #D6DEE0 #F3F5F4",
    },
    "Hacker": {
        "Phosphor": "#080F0B #12241A #57C776 #245A35 #B8F5C5",
        "Amber Terminal": "#17120A #302414 #D69A35 #70501F #F4D38B",
        "Cyberdeck": "#0A1018 #142A3B #37C6D0 #175D75 #B2F4F0",
        "Matrix": "#050A06 #102415 #39E75F #176C2E #B0FFBD",
        "Purple Haze": "#12101A #282039 #A16AE8 #593F85 #E0C8FF",
        "Red Alert": "#130D10 #302025 #D45B65 #702D37 #F3B2AA",
    },
    "Pastel Workstations": {
        "CDE Pastel": "#6D6489 #6D6489 #A79BC1 #D59B91 #E9DFC9",
        "Vintage Workstation": "#466C68 #466C68 #C78F8C #C6CCB5 #F0E5D2",
        "Orchid & Sage": "#665579 #665579 #A992B3 #A9BCA3 #F2E8D5",
        "Solaris Garden": "#514C75 #514C75 #7CA69A #D58E82 #EAE1CF",
        "Retro Pastel": "#47434F #47434F #D7A098 #A8C5B5 #E6DDD1",
        "Lavender & Copper": "#594B65 #594B65 #C98F7C #A5AD86 #E9DDC7",
    },
}

PRESET_METADATA = {}


for category, items in COLLECTIONS.items():
    for name, swatches in items.items():
        PRESET_METADATA[name] = {
            "category": category,
            "description": category + " palette adapted for JWM.",
            "reference": "Original palette; no historical reproduction claimed.",
        }
        if swatches is None:
            continue
        dark, base, accent, muted, light = swatches.split()
        PRESETS[name] = {
            "base": base,
            "text": readable_text(base),
            "accent": accent,
            "accent_text": readable_text(accent),
            "muted": muted,
            "dark": dark,
            "light": light,
        }

for name, profile in HERITAGE.items():
    PRESET_METADATA[name].update(
        {key: profile[key] for key in ("description", "reference", "source")}
    )
for name in COLLECTIONS["Pastel Workstations"]:
    PRESET_METADATA[name].update(
        reference="CDE/Motif workstation-inspired original palette",
        description="Pastel captions, neutral light menus and raised workstation controls. Not a stock CDE palette.",
    )
for name in COLLECTIONS["Hacker"]:
    PRESET_METADATA[name].update(
        reference="Terminal-inspired original palette",
        description="Dark surfaces, luminous text and restrained neon selection accents.",
    )


def theme_roles(name):
    """Assign colors to UI roles instead of applying one accent everywhere."""
    p = PRESETS[name]
    category = PRESET_METADATA[name]["category"]
    light = p.get("light", p["muted"])
    roles = dict(
        surface=p["base"],
        panel=p["base"],
        menu=light,
        title=p["muted"],
        title_active=p["accent"],
        selection=p["accent"],
        tooltip=light,
        decorations="flat",
        width="2",
        corner="4",
    )
    if category == "Heritage":
        roles.update(HERITAGE[name])
        roles.update(
            width="4" if roles["decorations"] == "motif" else "3",
            corner="0" if roles["decorations"] == "motif" else "4",
        )
    elif category == "Hacker":
        roles.update(
            surface=p["base"],
            panel=p["dark"],
            menu=p["dark"],
            title=p["dark"],
            title_active=p["base"],
            selection=p["accent"],
            tooltip=p["dark"],
            title_ink=light,
            active_ink=luminous_text(p["accent"], p["base"]),
            panel_ink=luminous_text(p["accent"], p["dark"]),
            menu_ink=luminous_text(p["accent"], p["dark"]),
            tooltip_ink=light,
            corner="0",
        )
        if name == "Phosphor":
            # Try a brighter focused caption without changing the surfaces.
            roles["active_ink"] = light
            roles["title_ink"] = luminous_text(p["accent"], p["dark"])
    elif category == "Pastel Workstations":
        roles.update(
            title=p["muted"],
            menu=light,
            selection=p["base"],
            decorations="motif",
            width="4",
            corner="0",
        )
    elif category == "Chromatic":
        roles.update(
            title=mix(p["muted"], light, 0.3),
            title_active=p["dark"],
            selection=p["base"],
        )
    elif category == "Modern":
        roles.update(title=mix(p["base"], light, 0.5), selection=p["dark"])
    else:
        # Preserve the original collection's dark surfaces and familiar accents.
        roles.update(menu=p["base"], tooltip=p["muted"])
        if name == "Classic Motif":
            roles.update(decorations="motif", width="4", corner="0")
    return roles


def preset_values(name):
    p = PRESETS[name]
    r = theme_roles(name)

    def pair(background, preferred=None):
        return {
            "Foreground": readable_text(background, preferred),
            "Background": background,
        }

    result = {section: pair(r["surface"], p["text"]) for section in STYLES}
    result["WindowStyle"] = pair(r["title"], r.get("title_ink"))
    result["WindowStyle"].update(
        {
            "@decorations": r["decorations"],
            "Width": r["width"],
            "Height": "0",
            "Outline": bevel(r["title"]),
            "Corner": r["corner"],
            "Active": pair(r["title_active"], r.get("active_ink", p["accent_text"])),
        }
    )
    result["WindowStyle"]["Active"]["Outline"] = bevel(r["title_active"])
    if PRESET_METADATA[name]["category"] == "Hacker":
        result["WindowStyle"]["Outline"] = p["muted"]
        result["WindowStyle"]["Active"]["Outline"] = p["accent"]
    result["TrayStyle"] = pair(r["panel"], r.get("panel_ink"))
    result["TaskListStyle"]["Active"] = pair(r["selection"])
    # A minimized task stays readable but does not compete with the active task.
    result["TaskListStyle"]["Minimized"] = pair(mix(r["surface"], r["panel"], 0.5))
    result["MenuStyle"] = pair(r["menu"], r.get("menu_ink"))
    result["MenuStyle"]["Active"] = pair(r["selection"])
    result["PopupStyle"] = pair(r["tooltip"], r.get("tooltip_ink"))
    pager_active = mix(r["surface"], r["selection"], 0.18)
    pager_text = readable_text(r["surface"] + ";" + pager_active)
    if contrast_ratio(pager_text, r["surface"] + ";" + pager_active) < 4.5:
        pager_active = r["surface"]
        pager_text = readable_text(pager_active)
    result["PagerStyle"] = dict(
        pair(r["surface"]), Text=pager_text, Active=pair(pager_active)
    )
    for section in ("WindowStyle", "TrayStyle", "TaskListStyle", "MenuStyle"):
        result[section]["@decorations"] = r["decorations"]
    # Portable family aliases; historical fonts and bitmaps are not bundled.
    for section in STYLES:
        result[section]["Font"] = (
            "Monospace-10"
            if PRESET_METADATA[name]["category"] == "Hacker"
            else "Sans-10"
        )
    if PRESET_METADATA[name]["category"] != "Hacker":
        result["WindowStyle"]["Font"] = "Sans-10:bold"
    return result


CUSTOM_DIR = (
    Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    / "jwm-style-editor"
    / "styles"
)


def custom_styles():
    return StyleStore(CUSTOM_DIR).load()


class StyleStore:
    """Custom JSON styles; accept the existing schema and protect name collisions."""

    def __init__(self, directory):
        self.directory = Path(directory)

    def load(self):
        result = {}
        if self.directory.is_dir():
            for path in sorted(self.directory.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if (
                        isinstance(data, dict)
                        and isinstance(data.get("name"), str)
                        and isinstance(data.get("values"), dict)
                    ):
                        result[data["name"]] = (data["values"], path)
                except (OSError, ValueError, TypeError):
                    continue
        return result

    def _name(self, name):
        import re

        if (
            not name.strip()
            or name in PRESETS
            or name == "Custom (current configuration)"
            or any(c in name for c in "/\\\x00")
        ):
            raise ValueError(
                "Choose a unique nonempty style name without path separators."
            )
        filename = re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-") or "style"
        return self.directory / (filename + ".json")

    def save(self, name, values, replace=False):
        from .config import save_atomic

        styles = self.load()
        target = self._name(name)
        if name in styles:
            if not replace:
                raise ValueError("Style already exists.")
            target = styles[name][1]
        elif target.exists():
            raise ValueError("Style filename already exists.")
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "name": name,
            "category": "Custom",
            "description": "",
            "values": values,
        }
        save_atomic(
            target, (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode()
        )
        return target

    def rename(self, old, new):
        from .config import save_atomic

        styles = self.load()
        if old not in styles:
            raise ValueError("Style not found.")
        target = self._name(new)
        if new in styles and new != old:
            raise ValueError("Style already exists.")
        source = styles[old][1]
        if target.exists() and target != source:
            raise ValueError("Style filename already exists.")
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["name"] = new
        save_atomic(
            target, (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode()
        )
        if source != target:
            source.unlink()
        return target

    def delete(self, name):
        styles = self.load()
        if name not in styles:
            raise ValueError("Style not found.")
        styles[name][1].unlink()
