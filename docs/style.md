# jwm_style

Run `jwm_style ~/.jwmrc` to edit the current style. Changes appear in the preview
and are only written when you click **Apply and restart JWM**. **Discard changes**
restores the open file's values.

**Save style** stores a personal style. The selector lists the current
configuration and your saved styles, which can also be renamed or deleted.
There are no built-in presets or collections.

The editor changes selected XML values while preserving the rest of the file.
Before writing, it checks for external edits and creates a `.bak` backup.
Writes are atomic; symbolic links are resolved to their target file.

File Includes are read in JWM order. Relative paths follow the working directory.
Dynamic `exec:` Includes are not executed by the preview. Included files are never
changed implicitly. If a later Include overrides a local property, open that
file to edit it. Ambiguous blocks cannot be saved.

Fonts use the GTK chooser. Window decorations can be Flat or Motif.
The start menu button icon can be selected with a file picker.

The preview uses global button images, focus variants, `IconPath` and
`TitleButtonOrder`. Native button geometry follows
[JWM 2.4.6](https://github.com/joewing/jwm/blob/v2.4.6/src/border.c).
Window content is illustrative. Group rules, compositing, DPI and application
icons may produce differences on the real desktop.
