#!/usr/bin/env python3
"""Install the commands in the user directory."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from jwm_tools import COMMANDS


def install(prefix):
    prefix = prefix.expanduser().resolve()
    app = prefix / "share/jwm-tools"
    bin_dir = prefix / "bin"
    marker = app / "install.json"
    if app.is_symlink() or (app.exists() and not marker.is_file()):
        raise ValueError(
            f"Existing directory does not belong to this installation: {app}"
        )
    for command in COMMANDS:
        link = bin_dir / command
        if link.exists() or link.is_symlink():
            if not link.is_symlink() or link.resolve() != app / command:
                raise ValueError(f"Existing command will not be replaced: {link}")
    app.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        ROOT / "jwm_tools",
        app / "jwm_tools",
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    for command in COMMANDS:
        shutil.copyfile(ROOT / command, app / command)
        (app / command).chmod(0o755)
        link = bin_dir / command
        if not link.is_symlink():
            link.symlink_to(app / command)
    marker.write_text(json.dumps({"commands": list(COMMANDS)}) + "\n")
    print(f"Commands installed in {bin_dir}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, default=Path.home() / ".local")
    args = parser.parse_args()
    try:
        install(args.prefix)
    except (OSError, ValueError) as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
