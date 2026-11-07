# jwm_keys

```sh
jwm_keys              # opens ~/.jwmrc
jwm_keys another.jwmrc
```

The list shows `Key` and `Mouse` bindings, with search and type filters.
Use **New keyboard binding** or **New mouse binding** to add an entry; select a
row to edit or delete it. **Capture** identifies the key or button received by
the window. JWM global shortcuts may intercept capture; enter the modifiers and
key manually in that case.

Changes remain pending. **View changes** shows the XML diff; **Save** writes the
file, and **Save and restart JWM** also requests a window manager restart.
**Discard** restores the loaded values.

Saving preserves comments, formatting, unknown attributes and other settings.
The previous file is backed up as `<filename>.bak`. External changes to the open
file or its Includes require reloading before saving. Mixed-content or CDATA
actions can have their attributes edited, but changing their action text requires
editing the source file.

## Keyboard

Accepts X11 names such as `Return`, `F4` or `XF86AudioRaiseVolume`, and keycodes
from 8 to 255. Modifiers are Ctrl (`C`), Shift (`S`), Alt (`A` or `1`), Super
(`4`) and Mod2/3/5. A `#` key template can be used with `desktop#`, `send#` and `at#`.

## Mouse

Contexts include desktop (`root`), title bar (`title`), border (`border`), window
icon (`icon`), and close, maximize and minimize buttons. Press uses the button's
number; release uses its negative. In JWM 2.4.6, double click multiplies the button
by 11: left = 11, middle = 22, right = 33.

Scrolling uses buttons 4/5 and horizontal scrolling uses 6/7. On the desktop,
buttons assigned to `RootMenu onroot` may take precedence. Mouse bindings within
application content are outside this editor's scope.

## Actions and Includes

Choose a JWM action such as `close`, `maximize`, `move`, `resize` or `root:1`.
To start a program, use `exec:command`. The editor does not execute these actions
when opening or editing a file.

Static Includes are read; included bindings are read-only in the list.
**Open source file** opens that file for explicit editing. Dynamic `exec:` Includes
are not executed. Relative paths follow JWM's working directory.

Repeated combinations are flagged. Conflict checks consider modifiers, key names,
`#` expansion, keycodes and mouse context/event. They do not resolve every mapping
between keycodes and symbolic names across X11 layouts.

Syntax reference: JWM 2.4.6, `src/parse.c`, `src/binding.c` and `src/event.c`.
