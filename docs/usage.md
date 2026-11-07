# Configuration

## jwm_audio

Run `jwm_audio` in a session with a system tray and PulseAudio, or PipeWire with
`pipewire-pulse`. Click the icon for quick volume control; use **Open mixer** to
adjust individual applications.

## jwm_menu

Run `jwm_menu` to update `~/.jwm-menu`. Include it in the JWM menu:

```xml
<RootMenu>
    <Include>~/.jwm-menu</Include>
</RootMenu>
```

## jwm_ram

To place the resource indicator in the JWM tray:

```xml
<Tray>
    <Swallow name="jwm_ram" width="72" height="30">jwm_ram --width 72 --height 30</Swallow>
</Tray>
```

## jwm_style

Run `jwm_style ~/.jwmrc`. The editor uses the open configuration and styles you
save; it has no built-in presets. See [Style editor](style.md).

## jwm_keys

Run `jwm_keys` to edit keyboard and mouse bindings in `~/.jwmrc`, or pass another
configuration file. Included entries display their source file.
See [Binding editor](keys.md).

## jwm_startup

Run `jwm_startup` to edit and reorder session commands in `~/.jwmrc`, or pass
another configuration file. See [Session commands](startup.md).

## Previous names

| Previous | Current |
| --- | --- |
| `audiotray` | `jwm_audio` |
| `jwm-menu-gen` | `jwm_menu` |
| `jwm-ram` | `jwm_ram` |
| `jwm-style-editor` | `jwm_style` |

Update shortcuts, startup commands and `Swallow` names. The menu remains at
`~/.jwm-menu`. Personal styles remain at `~/.config/jwm-style-editor/styles/`,
or the equivalent path under `XDG_CONFIG_HOME`.

The `jwm-tools` Debian package replaces the old `jwm-style-editor` package.
All six tools use English, including GTK stock labels. This does not translate
user-provided commands, filenames, device descriptions or saved style names.
