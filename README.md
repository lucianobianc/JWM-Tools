# JWM Tools

Tools for JWM on Linux/X11.

| Tool | Function | Usage |
| --- | --- | --- |
| `jwm_audio` | Master and application volume, output and microphone selection. | `jwm_audio` |
| `jwm_menu` | Edits the Start menu, submenus and icons; also generates application menus. | `jwm_menu` |
| `jwm_ram` | RAM, swap, CPU, temperature and battery indicators for the tray. | `jwm_ram --width 72 --height 30` |
| `jwm_style` | Edits JWM colors, fonts and decorations, with a preview and saved styles. | `jwm_style ~/.jwmrc` |
| `jwm_keys` | Edits keyboard shortcuts and mouse bindings, with file backups. | `jwm_keys ~/.jwmrc` |
| `jwm_startup` | Edits and reorders session startup, restart and shutdown commands. | `jwm_startup ~/.jwmrc` |

## Installation

Download the `.deb` from [Releases](https://github.com/lucianobianc/JWM-Tools/releases):

```sh
sudo apt install ./jwm-tools_0.1-1_all.deb
```

The package contains all six tools. Audio requires PulseAudio or PipeWire with PulseAudio support.

## From source

Download and extract GitHub's **Source code (tar.gz)** or **Source code (zip)**.
On Debian and derivatives, run these commands from the extracted directory:

```sh
sudo apt install python3 python3-gi python3-gi-cairo python3-cairo python3-tk python3-pulsectl gir1.2-gtk-3.0 libfontconfig1 jwm
python3 tools/install.py
```

Commands are installed in `~/.local/bin`, which must be in your `PATH`.
Run each command with `--help` for its options.

[Configuration and previous names](docs/usage.md) · [Style editor](docs/style.md) · [Menu editor](docs/menu.md) · [Binding editor](docs/keys.md) · [Session commands](docs/startup.md)

## Development

```sh
python3 tools/build_release.py
python3 -m unittest discover -s tests -v
```

Build artifacts are written to `dist/`. GUI tests require X11.
Tests against a real JWM session use `JWM_REAL_TESTS=1`, `Xvfb` and `xwininfo`.

License: [GPL v2](LICENSE).
