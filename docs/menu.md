# jwm_menu

```sh
jwm_menu                        # graphical editor
jwm_menu ~/.jwmrc               # edit a specific configuration
jwm_menu ~/.jwm-menu            # edit a menu fragment
jwm_menu --generate             # rebuild ~/.jwm-menu from installed applications
```

The editor opens `~/.jwmrc` by default, falling back to `~/.jwm-menu` if no main
configuration exists. New files are only created when saved. The desktop launcher
opens the editor. Running `jwm_menu` without options opens the editor. `--edit` remains an alias.

**Generate from applications** asks whether to **Add to current menu** or
**Replace menu contents**. Add keeps existing entries, submenus and Includes,
and appends installed applications grouped by category. Replace rebuilds the
selected menu. Cancel leaves it unchanged. **Clear menu** removes its entries and submenus.
Select a submenu to limit either action to it. Generation and clearing ask for confirmation
and remain pending until **Save**; **Discard** restores the loaded file. Included
files and unrelated JWM configuration are never cleared.

## Editing

Select a menu and use **Add entry** to add an application, submenu, separator,
Include or JWM action. Selecting a leaf adds the new entry after it. **Installed
application…** fills in its name, command and icon. **Choose file…** next to
**Path** opens a file chooser. Program paths are quoted for the shell;
Include paths are inserted directly. Commands use shell syntax without an `exec:`
prefix.

Use **Choose icon…** to browse the installed theme in a visual grid, search by
name and filter by category. **Load more** shows further matches. Symbolic icons
are optional. **Choose image file…** selects a custom image; **Remove icon** clears
it. The same picker is available for the Start button in `jwm_style`.

Selections store the resolved image file path so JWM can find the icon without
extra `IconPath` configuration. Files remain at those paths and are not copied;
removing a theme package may therefore remove an icon used by the menu. You can
also enter an icon name or image path manually. The tree displays available icons.

**Move up / Move down** change sibling order. Collapsed submenus stay collapsed when other entries are
added or edited. **Indent** puts an entry inside the
preceding submenu. **Outdent** moves it after its containing submenu. JWM menus
follow top-to-bottom order. **Add root menu** creates a separate `RootMenu`, whose
**Root buttons** field selects its desktop mouse buttons.

**View changes** shows the XML diff. **Save** creates a `<filename>.bak` backup and
writes atomically; **Save and restart JWM** also requests a restart. **Discard**
reloads the file after confirmation. Commands are never launched by the editor.

Unknown attributes, comments and unrelated configuration are preserved. Unknown
elements appear read-only inside menus. Mixed-content action text must be edited
in the source file if it cannot be safely patched. External edits require reload
before saving.

## Includes and generated menus

Static Includes expand in the tree, including nested Includes. **Source file**
shows where each entry is defined. **Edit** or **Delete** on an included entry opens its source
file and selects that entry. Deletion asks for confirmation and remains pending
until that file is saved. Save there, then use **Back** to return
to the parent menu. **Open source file** also navigates to the defining file.
Moving included entries requires opening that file first.

Relative paths follow JWM's working directory. Missing files, Include cycles and
depth limits are reported without changing the configuration. Dynamic Includes and
`Dynamic` menu commands are preserved without execution; their generated contents
are not expanded in the editor.

Generation replaces `~/.jwm-menu` with the installed application list and creates
a backup. If you run the generator at session startup, keep your custom entries
in `~/.jwmrc` or a different included file to avoid replacing manual edits.

To use a standalone menu fragment:

```xml
<RootMenu onroot="12">
    <Include>~/.jwm-menu</Include>
</RootMenu>
```

If an older session command invokes `jwm_menu` for automatic generation, change it
to `jwm_menu --generate`. The command without options now opens the GUI.
