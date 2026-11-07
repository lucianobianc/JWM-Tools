"""Named component roles for historical JWM adaptations.

Sources and the distinction between original palette data and recreations are
recorded in docs/themes.md. No original window assets or fonts are bundled.
"""

CDE_SOURCE = "https://github.com/cdesktopenv/cde/blob/d35c607e3a722201c6cd3213491a9483d40ef13e/cde/programs/palettes/Broica.dp"
VUE_SOURCE = "https://github.com/NsCDE/NsCDE/blob/2d26bbece7e9c0dbee31bfe23ebfc1e1c88792bd/data/palettes/BroicaVUE.dp"
SGI_SOURCE = "https://github.com/jujum4n/sgi-enhanced/tree/b7a02161f8e13da639d2ecff5735436c9f447d67"
XP_SOURCE = "https://github.com/B00merang-Project/Windows-XP/tree/7637830906823af40a3cd7e7079be753d8b7d679"

HERITAGE = {
    "Redmond": {
        "reference": "Windows XP / Luna Blue",
        "source": XP_SOURCE,
        "description": "Blue caption and panel, cream controls, white menus and blue selection.",
        "surface": "#ECE9D8",
        "panel": "#245EDC",
        "menu": "#FFFFFF",
        "title": "#5972AA",
        "title_active": "#0054E3;#1B6AE8",
        "selection": "#1466C9",
        "tooltip": "#FFFFE1",
        "decorations": "flat",
    },
    "Redmond Silver": {
        "reference": "Windows XP / Luna Metallic",
        "source": XP_SOURCE,
        "description": "Silver-lavender surfaces and captions; blue menu selection.",
        "surface": "#E6E6ED",
        "panel": "#D4D2DF",
        "menu": "#FFFFFF",
        "title": "#DADAE2",
        "title_active": "#B8B6C9",
        "selection": "#316AC5",
        "tooltip": "#FFFFE1",
        "decorations": "flat",
    },
    "Redmond Olive": {
        "reference": "Windows XP / Luna Homestead",
        "source": XP_SOURCE,
        "description": "Olive captions and panel, cream controls and sage selection.",
        "surface": "#ECE9D8",
        "panel": "#6D7B43",
        "menu": "#FFFFFF",
        "title": "#D5D8C5",
        "title_active": "#5F6B39",
        "selection": "#94B06F",
        "tooltip": "#FFFFE1",
        "decorations": "flat",
    },
    "Mountain View": {
        "reference": "SGI IRIX / Indigo Magic (brown-grey recreation)",
        "source": SGI_SOURCE,
        "description": "Warm grey active caption, neutral inactive frame and raised grey controls.",
        "surface": "#C6C6C6",
        "panel": "#B7B7B7",
        "menu": "#C6C6C6",
        "title": "#808080",
        "title_active": "#A59F80",
        "selection": "#606A80",
        "tooltip": "#FFFFDE",
        "decorations": "motif",
    },
    "Palo Alto": {
        "reference": "HP VUE / BroicaVUE palette adaptation",
        "source": VUE_SOURCE,
        "description": "Peach active caption, slate inactive caption and mauve panels with rose menus.",
        "surface": "#847982",
        "panel": "#847982",
        "menu": "#B19F98",
        "title": "#6D7A85",
        "title_active": "#FACE9D",
        "selection": "#956970",
        "tooltip": "#B18F90",
        "decorations": "motif",
    },
    "Santa Clara": {
        "reference": "Solaris / CDE, Broica palette adaptation",
        "source": CDE_SOURCE,
        "description": "Apricot active caption, neutral inactive caption, sand panels and rose menus.",
        "surface": "#C6B2A8",
        "panel": "#C6B2A8",
        "menu": "#B7878D",
        "title": "#999999",
        "title_active": "#EDA870",
        "selection": "#4992A7",
        "tooltip": "#938EAB",
        "decorations": "motif",
    },
    "Austin": {
        "reference": "OS/2 Presentation Manager / Warp-inspired",
        "source": "",
        "description": "Navy active caption and selection, grey controls and inactive caption.",
        "surface": "#C0C0C0",
        "panel": "#C0C0C0",
        "menu": "#C0C0C0",
        "title": "#808080",
        "title_active": "#000080",
        "selection": "#000080",
        "tooltip": "#FFFFE1",
        "decorations": "motif",
    },
}
