#!/usr/bin/env python3
"""Build source and architecture-independent Debian assets without root.

Only Python's standard library and dpkg-deb are required. The .deb contains
only the style editor; the source archive contains this repository's sources.
SOURCE_DATE_EPOCH controls reproducible timestamps.
"""
import argparse
from email.utils import formatdate
import gzip
import hashlib
import io
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ITEMS = (
    ".gitignore",
    "LICENSE",
    "README.md",
    "docs",
    "jwm-style-editor",
    "jwm_style",
    "tests",
    "tools",
    "packaging",
)


def source_files():
    result = []
    for name in SOURCE_ITEMS:
        path = ROOT / name
        if path.is_file():
            result.append(path)
        elif path.is_dir():
            result.extend(
                p
                for p in path.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
            )
    return sorted(result)


def epoch():
    if "SOURCE_DATE_EPOCH" in os.environ:
        return int(os.environ["SOURCE_DATE_EPOCH"])
    result = subprocess.run(
        ["git", "-C", str(ROOT), "log", "-1", "--format=%ct"],
        capture_output=True,
        text=True,
    )
    # Extracted source archives retain the entry point's normalized timestamp.
    return (
        int(result.stdout.strip())
        if result.returncode == 0
        else int((ROOT / "jwm-style-editor").stat().st_mtime)
    )


def write(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(mode)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    version = re.search(
        r'__version__\s*=\s*[\'"]([^\'"]+)',
        (ROOT / "jwm_style/__init__.py").read_text(),
    ).group(1)
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", version):
        raise SystemExit("Unsupported release version")
    timestamp = epoch()
    source = output / f"jwm-style-editor-{version}.tar.gz"
    deb = output / f"jwm-style-editor_{version}-1_all.deb"
    # Normalize gzip/tar metadata so repeated builds produce identical assets.
    with source.open("wb") as raw:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw, mtime=timestamp
        ) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for file in source_files():
                    entry = tarfile.TarInfo(
                        f"jwm-style-editor-{version}/{file.relative_to(ROOT)}"
                    )
                    data = file.read_bytes()
                    entry.size = len(data)
                    entry.mtime = timestamp
                    entry.mode = (
                        0o755
                        if file.name in ("jwm-style-editor", "build_release.py")
                        else 0o644
                    )
                    archive.addfile(entry, io.BytesIO(data))
    with tempfile.TemporaryDirectory(prefix="jwm-deb-", dir=output) as tmp:
        stage = Path(tmp)
        app = stage / "usr/share/jwm-style-editor"
        write(
            app / "jwm-style-editor",
            (ROOT / "jwm-style-editor")
            .read_bytes()
            .replace(b"#!/usr/bin/env python3", b"#!/usr/bin/python3", 1),
            0o755,
        )
        for file in sorted((ROOT / "jwm_style").glob("*.py")):
            write(app / "jwm_style" / file.name, file.read_bytes())
        (stage / "usr/bin").mkdir(parents=True)
        (stage / "usr/bin/jwm-style-editor").symlink_to(
            "../share/jwm-style-editor/jwm-style-editor"
        )
        write(
            stage / "usr/share/applications/jwm-style-editor.desktop",
            (ROOT / "packaging/jwm-style-editor.desktop").read_bytes(),
        )
        docs = stage / "usr/share/doc/jwm-style-editor"
        write(docs / "copyright", (ROOT / "packaging/copyright").read_bytes())
        write(
            docs / "README.md.gz",
            gzip.compress((ROOT / "README.md").read_bytes(), mtime=0),
        )
        changelog = (
            f"jwm-style-editor ({version}-1) unstable; urgency=medium\n\n"
            "  * Release the modular GTK 3 style editor with responsive layout,\n"
            "    native font selection and JWM 2.4.6 title decorations.\n\n"
            f" -- Luciano Biancardine <lucianobiancardine@gmail.com>  {formatdate(timestamp, usegmt=True)}\n"
        )
        write(docs / "changelog.Debian.gz", gzip.compress(changelog.encode(), mtime=0))
        checksums = []
        for file in sorted(stage.rglob("*")):
            if file.is_file() and not file.is_symlink():
                checksums.append(
                    hashlib.md5(file.read_bytes()).hexdigest()
                    + "  "
                    + str(file.relative_to(stage))
                )
        size = sum(
            (p.stat().st_size + 1023) // 1024 for p in stage.rglob("*") if p.is_file()
        )
        control = (ROOT / "packaging/control").read_text().replace("@VERSION@", version)
        control += f"Installed-Size: {size}\n"
        write(stage / "DEBIAN/control", control.encode())
        write(stage / "DEBIAN/md5sums", ("\n".join(checksums) + "\n").encode())
        for path in sorted(stage.rglob("*")):
            if path.is_dir():
                path.chmod(0o755)
            os.utime(path, (timestamp, timestamp), follow_symlinks=False)
        stage.chmod(0o755)
        subprocess.run(
            ["dpkg-deb", "--root-owner-group", "--build", str(stage), str(deb)],
            check=True,
            env=dict(os.environ, SOURCE_DATE_EPOCH=str(timestamp)),
        )
    sums = output / "SHA256SUMS"
    sums.write_text(
        "".join(
            hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
            for p in sorted((source, deb))
        )
    )
    for path in (source, deb, sums):
        print(path)


if __name__ == "__main__":
    main()
