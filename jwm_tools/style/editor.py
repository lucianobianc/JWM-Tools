"""GTK editor; configuration changes remain pending until explicitly applied."""

import sys
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk
from .themes import STYLES, CUSTOM_DIR, CURRENT_STYLE
from .config import flatten, set_nested, start_attributes, Configuration
from .fonts import jwm_to_pango, pango_to_jwm
from .preview import draw_preview
from .buttons import read_buttons
from .themes import StyleStore
from ..iconpicker import choose_icon


class Editor(Gtk.Window):
    def __init__(self, path):
        super().__init__(title="jwm_style")
        self.path = Path(path).expanduser().resolve()
        self.config = Configuration(self.path)
        self.buttons = read_buttons(self.config)
        self.values = self.config.values()
        self.store = StyleStore(CUSTOM_DIR)
        self.set_default_size(1050, 710)
        self.set_size_request(680, 480)
        self.set_border_width(12)
        self.original = self.path.read_bytes()
        self.text = self.original.decode("utf-8")
        ET.fromstring(self.text)
        self.pending = {}
        self.start_pending = {}
        self.loading = False
        self.custom = self.store.load()
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(outer)
        top = Gtk.Box(spacing=8)
        outer.pack_start(top, False, False, 0)
        top.pack_start(Gtk.Label(label="Style:"), False, False, 0)
        self.presets = Gtk.ComboBoxText()
        for cell in self.presets.get_cells():
            cell.set_property("ellipsize", 3)
            cell.set_property("width-chars", 18)
            cell.set_property("max-width-chars", 22)
        self.refresh_presets()
        self.presets.connect("changed", self.on_preset)
        top.pack_start(self.presets, True, True, 0)
        self.section = Gtk.ComboBoxText()
        for s in STYLES + ["Start Button"]:
            self.section.append_text(s)
        self.section.set_active(0)
        self.section.connect("changed", self.on_section)
        top.pack_start(self.section, False, False, 0)
        self.main_area = main_area = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        main_area.set_position(350)
        outer.pack_start(main_area, True, True, 0)
        self.scroller = scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_min_content_width(290)
        main_area.pack1(scroller, resize=False, shrink=False)
        self.grid = Gtk.Grid(column_spacing=10, row_spacing=12, margin=8)
        scroller.add(self.grid)
        preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=8)
        main_area.pack2(preview_box, resize=True, shrink=False)
        preview_header = Gtk.Box(spacing=8)
        preview_box.pack_start(preview_header, False, False, 0)
        preview_header.pack_start(Gtk.Label(label="Preview:"), False, False, 0)
        self.preview_mode = Gtk.ComboBoxText()
        self.preview_mode.append_text("Full desktop")
        self.preview_mode.append_text("Selected component")
        self.preview_mode.set_active(0)
        self.preview_mode.connect("changed", lambda *_: self.preview.queue_draw())
        preview_header.pack_start(self.preview_mode, True, True, 0)
        self.preview = Gtk.DrawingArea()
        self.preview.set_size_request(220, 150)
        self.preview.connect("draw", self.draw_preview)
        preview_box.pack_start(self.preview, True, True, 0)
        self.preview_maximized = Gtk.CheckButton(label="Maximized window")
        self.preview_maximized.connect("toggled", lambda *_: self.preview.queue_draw())
        preview_box.pack_start(self.preview_maximized, False, False, 0)
        note = Gtk.Label(label="JWM 2.4.6 preview. Includes are read only.", xalign=0)
        note.set_tooltip_text(
            "Button images use the global JWM settings and IconPath. Missing images use native button geometry."
        )
        note.set_line_wrap(True)
        note.set_max_width_chars(38)
        note.get_style_context().add_class("dim-label")
        preview_box.pack_start(note, False, False, 0)
        self.status = Gtk.Label(xalign=0)
        self.status.set_ellipsize(3)
        self.status.set_max_width_chars(70)
        self.notice = Gtk.Label(xalign=0)
        self.notice.set_line_wrap(True)
        self.notice.set_max_width_chars(70)
        self.notice.set_text("; ".join(self.buttons.warnings))
        self.notice.set_no_show_all(True)
        self.notice.set_visible(bool(self.buttons.warnings))
        outer.pack_start(self.notice, False, False, 0)
        outer.pack_start(self.status, False, False, 0)
        bottom = Gtk.FlowBox()
        bottom.set_selection_mode(Gtk.SelectionMode.NONE)
        bottom.set_max_children_per_line(5)
        bottom.set_min_children_per_line(1)
        bottom.set_column_spacing(8)
        bottom.set_row_spacing(6)
        outer.pack_start(bottom, False, False, 0)
        for label, callback in [
            ("Discard changes", self.on_reset),
            ("Rename style…", self.on_rename_style),
            ("Delete style", self.on_delete_style),
            ("Save style…", self.on_save_style),
            ("Apply and restart JWM", self.on_apply),
        ]:
            bottom.add(self.make_button(label, callback))
        self.detect_preset()
        self.on_section()

    def visible_presets(self):
        return [CURRENT_STYLE, *self.custom]

    def refresh_presets(self, selected=None):
        self.custom = self.store.load()
        self.presets.remove_all()
        choices = self.visible_presets()
        for name in choices:
            self.presets.append_text(name)
        self.presets.set_active(choices.index(selected) if selected in choices else 0)

    def detect_preset(self):
        actual = flatten(self.values)
        for name, (values, _) in self.custom.items():
            target = flatten(values)
            if target and all(
                actual.get(key) == value for key, value in target.items()
            ):
                self.loading = True
                self.refresh_presets(name)
                self.loading = False
                return

    def make_button(self, label, callback):
        b = Gtk.Button(label=label)
        b.connect("clicked", callback)
        return b

    def fields(self, section):
        fields = [("Foreground",), ("Background",)]
        fields += [("Font",)]
        if section in ("WindowStyle", "TrayStyle", "MenuStyle"):
            fields += [("Opacity",)]
        if section == "WindowStyle":
            fields += [("Width",), ("Height",), ("Corner",), ("@decorations",)]
        if section == "PagerStyle":
            fields += [("Text",)]
        if section in ("WindowStyle", "TaskListStyle", "PagerStyle", "MenuStyle"):
            fields += [("Active", "Foreground"), ("Active", "Background")]
        if section == "TaskListStyle":
            fields += [("Minimized", "Foreground"), ("Minimized", "Background")]
        return fields

    def current(self, section, path):
        return self.pending.get(
            (section, path), flatten(self.values).get((section, path))
        )

    def effective_values(self):
        import copy

        values = copy.deepcopy(self.values)
        for (section, path), value in self.pending.items():
            set_nested(values, section, path, value)
        return values

    @property
    def start_attributes(self):
        try:
            return start_attributes(self.text) or {}
        except ValueError:
            return {}

    def on_section(self, *_):
        self.loading = True
        for child in self.grid.get_children():
            self.grid.remove(child)
        section = self.section.get_active_text()
        if section == "Start Button":
            try:
                attrs = start_attributes(self.text)
            except ValueError as exc:
                attrs = None
                self.status.set_text(str(exc))
            if attrs is None:
                self.grid.attach(
                    Gtk.Label(
                        label="No unambiguous root-menu TrayButton found.", xalign=0
                    ),
                    0,
                    0,
                    2,
                    1,
                )
            else:
                for i, key in enumerate(("label", "icon", "tooltip")):
                    self.grid.attach(Gtk.Label(label=key.title(), xalign=0), 0, i, 1, 1)
                    entry = Gtk.Entry()
                    entry.set_width_chars(12)
                    entry.set_hexpand(True)
                    entry.set_text(self.start_pending.get(key, attrs.get(key, "")))
                    entry.connect("changed", self.on_start_entry, key)
                    if key == "icon":
                        row = Gtk.Box(spacing=6)
                        row.pack_start(entry, True, True, 0)
                        browse = Gtk.Button.new_from_icon_name(
                            "document-open-symbolic", Gtk.IconSize.BUTTON
                        )
                        browse.set_tooltip_text("Choose icon…")
                        browse.get_accessible().set_name("Choose icon")
                        browse.connect("clicked", self.on_choose_start_icon, entry)
                        row.pack_start(browse, False, False, 0)
                        self.grid.attach(row, 1, i, 1, 1)
                    else:
                        self.grid.attach(entry, 1, i, 1, 1)
            self.grid.show_all()
            self.loading = False
            self.update_status()
            self.preview.queue_draw()
            return
        for i, path in enumerate(self.fields(section)):
            key = (section, tuple(path))
            label = Gtk.Label(
                label="Decorations" if path == ("@decorations",) else " ".join(path),
                xalign=0,
            )
            label.set_line_wrap(True)
            label.set_max_width_chars(15)
            self.grid.attach(label, 0, i, 1, 1)
            value = self.current(section, tuple(path))
            if path == ("@decorations",):
                chooser = Gtk.ComboBoxText()
                chooser.append("motif", "Motif")
                chooser.append("flat", "Flat")
                chooser.set_active_id(value or self.buttons.decorations)
                chooser.connect("changed", self.on_decorations)
                self.grid.attach(chooser, 1, i, 1, 1)
            elif path[-1] in ("Foreground", "Background", "Text"):
                chooser = Gtk.ColorButton()
                rgba = Gdk.RGBA()
                rgba.parse(value if value and rgba.parse(value) else "#808080")
                chooser.set_rgba(rgba)
                chooser.props.use_alpha = False
                chooser.connect("color-set", self.on_color, key)
                self.grid.attach(chooser, 1, i, 1, 1)
            elif path[-1] == "Font":
                self.grid.attach(self.font_field(value, key), 1, i, 1, 1)
            else:
                entry = Gtk.Entry()
                entry.set_width_chars(12)
                entry.set_hexpand(True)
                entry.set_text(value or "")
                entry.connect("changed", self.on_entry, key)
                self.grid.attach(entry, 1, i, 1, 1)
        self.grid.show_all()
        self.loading = False
        self.update_status()
        self.preview.queue_draw()

    def font_field(self, value, key):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        button = Gtk.FontButton()
        button.set_title("Choose font")
        button.set_font_desc(jwm_to_pango(value))
        button.set_hexpand(True)
        box.pack_start(button, False, False, 0)

        def selected(chooser):
            if self.loading:
                return
            self.pending[key] = pango_to_jwm(
                chooser.get_font_desc(), self.current(*key)
            )
            self.update_status()
            self.preview.queue_draw()

        button.connect("font-set", selected)
        return box

    def on_choose_start_icon(self, button, entry):
        value = choose_icon(self, entry.get_text())
        if value is not None:
            entry.set_text(value)

    def on_start_entry(self, entry, key):
        if self.loading:
            return
        value = entry.get_text()
        try:
            original = (start_attributes(self.text) or {}).get(key, "")
        except ValueError:
            return
        if value != original:
            self.start_pending[key] = value
        else:
            self.start_pending.pop(key, None)
        self.update_status()
        self.preview.queue_draw()

    def on_decorations(self, chooser):
        if self.loading:
            return
        value = chooser.get_active_id()
        if value not in ("motif", "flat"):
            return
        key = ("WindowStyle", ("@decorations",))
        if value == self.buttons.decorations:
            self.pending.pop(key, None)
        else:
            self.pending[key] = value
        self.update_status()
        self.preview.queue_draw()

    def on_color(self, button, key):
        if not self.loading:
            c = button.get_rgba()
            self.pending[key] = "#%02X%02X%02X" % (
                round(c.red * 255),
                round(c.green * 255),
                round(c.blue * 255),
            )
            self.update_status()
            self.preview.queue_draw()

    def on_entry(self, entry, key):
        if not self.loading:
            value = entry.get_text().strip()
            if value:
                self.pending[key] = value
            else:
                self.pending.pop(key, None)
            self.update_status()
            self.preview.queue_draw()

    def on_preset(self, *_):
        if self.loading:
            return
        name = self.presets.get_active_text()
        self.pending.clear()
        self.start_pending.clear()
        values = self.custom[name][0] if name in self.custom else {}
        actual = flatten(self.values)
        self.pending.update(
            {k: v for k, v in flatten(values).items() if actual.get(k) != v}
        )
        self.on_section()

    def update_status(self):
        self.status.set_text(
            f"{self.path}  •  {len(self.pending) + len(self.start_pending)} pending properties"
        )

    def on_reset(self, *_):
        self.pending.clear()
        self.start_pending.clear()
        self.presets.set_active(0)
        self.on_section()

    def error(self, msg):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text="Could not save JWM configuration",
        )
        dialog.format_secondary_text(str(msg))
        dialog.run()
        dialog.destroy()

    def write(self):
        if not self.pending and not self.start_pending:
            return True
        try:
            self.text = self.config.commit(self.pending, self.start_pending)
            self.config = Configuration(self.path)
            self.values = self.config.values()
            self.buttons = read_buttons(self.config)
            self.original = self.path.read_bytes()
            self.pending.clear()
            self.start_pending.clear()
            self.loading = True
            self.refresh_presets()
            self.loading = False
            self.detect_preset()
            self.on_section()
            return True
        except (OSError, ValueError, ET.ParseError) as exc:
            self.error(exc)
            return False

    def on_save_style(self, *_):
        dialog = Gtk.Dialog(title="Save custom style", transient_for=self, flags=0)
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL, "Save style", Gtk.ResponseType.OK
        )
        area = dialog.get_content_area()
        area.set_spacing(8)
        area.set_border_width(12)
        area.pack_start(Gtk.Label(label="Style name:", xalign=0), False, False, 0)
        entry = Gtk.Entry()
        current_name = self.presets.get_active_text()
        if current_name in self.custom:
            entry.set_text(current_name)
        area.pack_start(entry, False, False, 0)
        dialog.show_all()
        response = dialog.run()
        name = entry.get_text().strip()
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        if not name or "/" in name or "\\" in name or name == CURRENT_STYLE:
            self.error("Choose a nonempty unique style name without path separators.")
            return
        try:
            values = self.effective_values()
            if name in self.custom:
                confirm = Gtk.MessageDialog(
                    transient_for=self,
                    message_type=Gtk.MessageType.QUESTION,
                    buttons=Gtk.ButtonsType.YES_NO,
                    text=f'Replace saved style "{name}"?',
                )
                response = confirm.run()
                confirm.destroy()
                if response != Gtk.ResponseType.YES:
                    return
            self.store.save(name, values, replace=name in self.custom)
            self.loading = True
            self.refresh_presets(name)
            self.loading = False
            self.update_status()
        except Exception as e:
            self.error(e)

    def on_rename_style(self, *_):
        name = self.presets.get_active_text()
        if name not in self.custom:
            self.error("Select a saved custom style to rename.")
            return
        dialog = Gtk.Dialog(title="Rename style", transient_for=self, flags=0)
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL, "Rename", Gtk.ResponseType.OK
        )
        entry = Gtk.Entry()
        entry.set_text(name)
        entry.set_margin_top(12)
        entry.set_margin_bottom(12)
        dialog.get_content_area().pack_start(entry, False, False, 0)
        dialog.show_all()
        response = dialog.run()
        new_name = entry.get_text().strip()
        dialog.destroy()
        if response != Gtk.ResponseType.OK or new_name == name:
            return
        if (
            not new_name
            or "/" in new_name
            or "\\" in new_name
            or new_name in self.custom
        ):
            self.error("Choose a unique style name without path separators.")
            return
        try:
            self.store.rename(name, new_name)
            self.loading = True
            self.refresh_presets(new_name)
            self.loading = False
            self.on_section()
        except Exception as e:
            self.error(e)

    def on_delete_style(self, *_):
        name = self.presets.get_active_text()
        if name not in self.custom:
            self.error("Select a saved custom style to delete.")
            return
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f'Delete saved style "{name}"?',
        )
        answer = dialog.run()
        dialog.destroy()
        if answer == Gtk.ResponseType.YES:
            try:
                self.store.delete(name)
                self.loading = True
                self.refresh_presets()
                self.loading = False
                self.on_section()
            except Exception as e:
                self.error(e)

    draw_preview = draw_preview

    def on_apply(self, *_):
        if self.write():
            try:
                result = subprocess.run(
                    ["jwm", "-restart"], capture_output=True, text=True, timeout=10
                )
                if result.returncode:
                    raise RuntimeError(
                        result.stderr or f"jwm exited with {result.returncode}"
                    )
            except Exception as e:
                self.error(f"Configuration saved, but restart failed: {e}")


def main():
    import argparse
    from .. import __version__

    parser = argparse.ArgumentParser(
        description="Edit JWM styles while preserving unrelated configuration."
    )
    parser.add_argument("configuration", nargs="?", default=str(Path.home() / ".jwmrc"))
    parser.add_argument(
        "--version", action="version", version="jwm_style " + __version__
    )
    args = parser.parse_args()
    path = Path(args.configuration).expanduser()
    if not path.is_file():
        sys.exit(f"File not found: {path}")
    try:
        app = Editor(path)
    except Exception as e:
        sys.exit(str(e))
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
