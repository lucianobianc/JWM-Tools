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

**Generate from applications** replaces the selected menu's contents with installed
applications grouped by category. **Clear menu** removes its entries and submenus.
Select a submenu to limit either action to it. Both actions ask for confirmation
and remain pending until **Save**; **Discard** restores the loaded file. Included
files and unrelated JWM configuration are never cleared.

## Editing

Select a menu and use **Add entry** to add an application, submenu, separator,
Include or JWM action. Selecting a leaf adds the new entry after it. **Installed
application…** fills in its name, command and icon. **Program or script…** opens a
file chooser. Commands use shell syntax without an `exec:` prefix.

Enter an icon theme name or use **Choose image…** to select an image file with a
preview. The tree displays available icons. Icon files remain at their chosen
paths; they are not copied into the configuration.

**Move up / Move down** change sibling order. **Indent** puts an entry inside the
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

Static Includes appear as entries. Select one and use **Open Include** to edit
its file. Relative paths follow JWM's working directory. Dynamic Includes and
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
