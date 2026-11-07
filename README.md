# JWM-Tools

Tools that make it easier to use and configure JWM.

## JWM Style Editor 0.8

A Python/GTK 3 editor with 34 built-in palettes, custom styles, and a live Cairo
preview. The property panel and preview resize independently. Font fields use a native GTK font chooser. WindowStyle offers a Motif/Flat
decoration selector that updates the preview before applying changes.

On Debian, the editor uses `python3-gi`, `python3-gi-cairo`, `python3-cairo`,
`python3-tk` (for `jwm-ram`), `gir1.2-gtk-3.0`, and `libfontconfig1`.
JWM 2.4.6 is the reference version. The editor has no resident service.

```sh
/usr/bin/python3 jwm-style-editor ~/.jwmrc
/usr/bin/python3 jwm-style-editor --version
```

Keep the `jwm_style/` directory beside `jwm-style-editor` when copying the tool.
The entry point remains the same; the implementation is now separated into
configuration, themes/storage, font conversion, button configuration, rendering,
and GTK interface modules.

### Saving and preserving configuration

Selecting a preset, changing controls, and using the preview do **not** write the
configuration. **Save style…** saves a reusable custom style; **Apply and restart
JWM** explicitly writes the selected properties and requests `jwm -restart`.
Custom JSON styles remain compatible with the previous format and location:
`$XDG_CONFIG_HOME/jwm-style-editor/styles/` (default `~/.config/...`).

The editor patches the selected XML values rather than serializing the whole
file. Comments, unrelated tags, attributes, whitespace, and line endings remain
intact. Missing properties and groups can be inserted. Before replacing the
configuration atomically, the editor checks for external changes and saves the
previous bytes to `<filename>.bak`. The target's file permissions are preserved.
A symlink passed as the configuration path is resolved to its target.

Static `Include` files are read in JWM order for the effective preview. Relative
paths follow JWM's process working directory; use absolute paths or `~/...` when
launching JWM and the editor from different directories. Includes are never
modified implicitly. If the opened file has no local style block, applying a
property adds a local override after its includes. If a later include overrides
an existing local property, the editor asks you to open that included file
explicitly. Duplicate write targets are rejected; the editor does not guess which
block to modify. Changes to any observed include invalidate the save snapshot.

`Include` commands beginning with `exec:` are **not executed** by the preview.
Missing includes, cycles, and unresolved image paths produce a visible notice;
those configurations may have an incomplete preview. Start Button editing still
requires one unambiguous local `TrayButton` whose action is `root:N`.

### Preview and JWM compatibility

The window preview reads global `ButtonClose`, `ButtonMin`, `ButtonMax`,
`ButtonMaxActive`, and `ButtonMenu`, with their `Focus` variants, plus `DefaultIcon`,
`IconPath`, and `TitleButtonOrder` (default `wtimx`). Focus and maximization are
separate states. Missing focus images fall back to normal images, then to native
geometry. The maximization checkbox shows the restore button.

Native minimize, maximize, restore, and close geometry follows JWM **v2.4.6**
[`src/border.c`](https://github.com/joewing/jwm/blob/v2.4.6/src/border.c).
Motif bevels and resize marks use its border geometry; light and dark colors use
the fixed-point factors in
[`src/color.c`](https://github.com/joewing/jwm/blob/v2.4.6/src/color.c).
The window title uses Pango and the configured Fontconfig font; title height,
border width, corner radius, focus colors, outlines, and background gradients
are reflected in the preview. The font chooser converts, for example,
`JetBrains Mono Bold 12` to `JetBrains Mono-12:bold`.

The preview is a scaled illustration: application content, tray/menu layout, and
application-provided window icons are samples. It does not simulate all JWM
`Group` rules, screen DPI settings, compositor opacity, or dynamic includes.
Native button glyphs are pixel-compared against a real JWM; the entire desktop
is not claimed to be a pixel-identical screenshot.

### Theme references and contrast

Built-in presets now assign colors separately to titles, panels, menus and
selection. Heritage follows the named Windows XP, IRIX, VUE, CDE and OS/2
references; Hacker keeps dark surfaces with restrained luminous accents.
Generated text pairs target at least 4.5:1 contrast. Hover over the preset
selector to see its reference. See [the palette review](docs/themes.md) for
sources, component roles and fidelity limits. Existing custom styles are not
rewritten when opening the editor.

### Tests

The test suite uses the standard library's `unittest`. Core XML and theme tests
can run without an X server. GTK tests need an X11 display; the optional real-JWM
checks additionally need `jwm`, `Xvfb`, and `xwininfo`.

```sh
/usr/bin/python3 -m unittest discover -s tests -v
JWM_REAL_TESTS=1 /usr/bin/python3 -m unittest discover -s tests -v
```

Real-JWM checks start their own isolated X server and window manager. They compare
native glyph pixels in Flat/Motif, active/inactive/maximized states, custom button
order, and different title/border sizes. Set `JWM_TEST_ARTIFACTS` to a writable
folder to retain real/preview PNG pairs. GTK tests check the layout from 680×480
to 1200×800, clipping, font selection, all presets, and saving behavior.

In the prepared Codex cloud environment:

```sh
bash /workspace/jwm-env/start-services
source /workspace/jwm-env/session
cd /workspace/JWM-Tools
JWM_REAL_TESTS=1 /usr/bin/python3 -m unittest discover -s tests -v
```

## Other tools

- `jwm-menu-gen`: generate `~/.jwm-menu` from desktop application entries.
- `jwm-ram`: Tk indicators for Linux RAM, swap, CPU, temperature, and battery.
- `audiotray`: GTK 3 PulseAudio/PipeWire tray mixer; additionally requires
  `python3-pulsectl` and a running PulseAudio-compatible server.

## Debian package and source releases

The `jwm-style-editor` Debian package installs only the style editor, with a menu
entry under Settings. Its Python/GTK/Cairo, Fontconfig and JWM dependencies are
declared in the package; the other tools remain available in the source checkout.
The package does not change your `~/.jwmrc` or start a background service.

```sh
sudo apt install ./jwm-style-editor_0.8-1_all.deb
jwm-style-editor --version
```

To build the architecture-independent package and source archive without root:

```sh
python3 tools/build_release.py
cd dist
sha256sum -c SHA256SUMS
```

The build needs Python 3 and `dpkg-deb`. It includes no vendored dependencies or
local configuration. Set `SOURCE_DATE_EPOCH` to reproduce artifact timestamps;
by default it uses the latest Git commit timestamp. Release assets are
`jwm-style-editor-0.8.tar.gz`, `jwm-style-editor_0.8-1_all.deb`, and `SHA256SUMS`.
