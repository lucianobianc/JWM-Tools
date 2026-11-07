# jwm_startup

```sh
jwm_startup              # opens ~/.jwmrc
jwm_startup another.jwmrc
```

| Event | JWM tag | When it runs |
| --- | --- | --- |
| Session startup | `StartupCommand` | When a new session starts, without repeating on restart. |
| JWM restart | `RestartCommand` | When the JWM window manager restarts. |
| Shutdown | `ShutdownCommand` | When JWM exits without restarting. |

Enter a command, choose an installed application, or select a program or script.
Use the command directly, without `exec:`. Arguments and operators follow shell
syntax.

**Move up** and **Move down** change the selected entry's position in the XML,
within the same event. New and disabled entries can also be moved. Changes are
only written when you save. Moves cannot cross an `Include`; use **Open source**
to edit entries owned by another file.

JWM 2.4 calls each event's commands from bottom to top in the XML. Moving down
therefore makes a command get called earlier. Processes run asynchronously;
this does not guarantee that one application finishes or becomes ready before
the next. Use a script that waits for the required condition for dependencies.

Uncheck **Enabled** to disable an entry without deleting it. **View changes**
shows the XML before saving. Saving creates an `<filename>.bak` backup and does
not execute commands. External edits require reloading before saving.

Included entries are read-only until you open their source. Dynamic `exec:`
Includes are not executed. The editor manages JWM commands, not XDG autostart
entries or system services.

Disabled commands are stored in XML comments with a `jwm_startup:disabled` marker
and Base64 content. This preserves commands containing `--arguments` and their
original XML. Simple comments containing only a command tag are also recognized
as disabled entries.
