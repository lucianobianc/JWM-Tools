"""Storage for user-saved styles."""

import os
import json
from pathlib import Path

STYLES = [
    "WindowStyle",
    "TrayStyle",
    "TaskListStyle",
    "PagerStyle",
    "MenuStyle",
    "PopupStyle",
]
CURRENT_STYLE = "Current configuration"
# Preserve the directory used by previous versions.
CUSTOM_DIR = (
    Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    / "jwm-style-editor"
    / "styles"
)


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
            or name in (CURRENT_STYLE, "Custom (current configuration)")
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
