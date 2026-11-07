# jwm_menu

```sh
jwm_menu                    # opens ~/.jwmrc, or ~/.jwm-menu if absent
jwm_menu /path/to/menu       # opens a configuration or menu fragment
jwm_menu --generate          # rebuilds ~/.jwm-menu without opening the GUI
```

## Editing

**Add** creates an application, submenu, separator, Include or JWM action. If the
main configuration has no root menu, Add creates that first. Included menu
fragments accept entries directly. Selecting a submenu adds inside it; selecting
an entry adds after it.

**Installed application…** fills in the name, command and icon. **Choose file…**
next to **Path** selects a program, script or Include file. Program paths are
quoted for the shell; Include paths are inserted directly. Commands use shell
syntax without an `exec:` prefix.

**Choose icon…** browses installed theme icons with search, category filters and
previews. It also accepts image files and can remove an icon. Selected icons are
stored as image file paths; files are not copied. The same picker is available
for the Start button in `jwm_style`.

## Selection and movement

Use Ctrl-click or Shift-click to select multiple entries. **Delete** removes the
selection without a confirmation dialog. Selecting a submenu and its children
removes that subtree once. Deleting an Include reference does not delete its
source file or implicitly remove entries inside that file.

Drag entries onto a submenu to move them inside it, or between rows to reorder.
Moves between included files remain pending in their respective source files.
A submenu cannot be moved into itself or one of its descendants. **Move up**,
**Move down**, **Indent** and **Outdent** remain available for a single entry.
Collapsed submenus stay collapsed when editing elsewhere.

| Shortcut | Action |
| --- | --- |
| A or Alt+A | Add |
| E, Alt+E or F2 | Edit |
| Delete, D or Alt+D | Delete selected entries |

Letter shortcuts apply in the menu editor, not in text fields. Underlined button
letters indicate Alt shortcuts; GTK may show the underline when Alt is pressed.

## Saving

All edits, deletions and moves remain pending until **Save**. **View changes**
shows the XML diff for every modified file. Saving checks all loaded source files
for external changes and creates `<filename>.bak` backups before writing. If a
write fails, earlier writes are rolled back when possible. **Save and restart
JWM** also requests a restart. **Discard** restores all loaded files after
confirmation.

Comments, unknown attributes and unrelated configuration are preserved. Unknown
elements appear read-only. Mixed-content action text may require editing in the
source file. The editor does not launch menu commands.

## Includes and generation

Static Includes expand in the same tree, including nested Includes. **Source
file** identifies where each entry is stored. Edit, add, delete or drag included
entries directly; Save writes their source files without navigating away.
Relative paths follow JWM's working directory. Missing files and Include cycles
are reported. Dynamic Includes and `Dynamic` commands are preserved without
execution, so their generated contents are not expanded.

**Generate from applications** asks whether to add to the selected menu or replace
its contents. Add keeps current entries and Includes; Replace rebuilds the
selected menu. **Clear menu** removes that menu's entries after confirmation.
These actions remain pending until saved.

The CLI generator replaces `~/.jwm-menu` and backs it up. If it runs automatically,
keep custom entries in another included file. Older startup commands that invoked
`jwm_menu` for generation must use `jwm_menu --generate`.
