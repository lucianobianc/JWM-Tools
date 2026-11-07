"""Browse theme icons and return a JWM-readable image file."""

from pathlib import Path
import os
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GLib


class IconPicker(Gtk.Dialog):
    PAGE_SIZE = 96

    def __init__(self, parent, current="", theme=None):
        super().__init__(title="Choose icon", transient_for=parent, modal=True)
        self.set_default_size(780, 600)
        self.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL, "Select icon", Gtk.ResponseType.OK
        )
        self.set_response_sensitive(Gtk.ResponseType.OK, False)
        self.theme = theme or Gtk.IconTheme.get_default()
        self.selection = None
        self.pending = 0
        self.offset = 0
        self.names = []
        box = self.get_content_area()
        box.set_border_width(12)
        box.set_spacing(10)
        controls = Gtk.Box(spacing=8)
        self.context = Gtk.ComboBoxText()
        self.context.append("", "All categories")
        for context in sorted(self.theme.list_contexts() or []):
            self.context.append(context, context)
        self.context.set_active_id("")
        controls.pack_start(self.context, False, False, 0)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Search icons: folder, terminal, audio…")
        controls.pack_start(self.search, True, True, 0)
        box.pack_start(controls, False, False, 0)
        self.symbolic = Gtk.CheckButton(label="Include symbolic icons")
        box.pack_start(self.symbolic, False, False, 0)
        self.store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)
        self.view = Gtk.IconView.new_with_model(self.store)
        self.view.set_pixbuf_column(0)
        self.view.set_text_column(1)
        self.view.set_tooltip_column(1)
        self.view.set_item_width(112)
        self.view.set_margin(8)
        self.view.set_row_spacing(12)
        self.view.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.view.connect("selection-changed", self.selected)
        self.view.connect("item-activated", self.activate)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.view)
        box.pack_start(scroll, True, True, 0)
        paging = Gtk.Box(spacing=8)
        self.status = Gtk.Label(xalign=0)
        paging.pack_start(self.status, True, True, 0)
        self.more = Gtk.Button(label="Load more")
        self.more.connect("clicked", lambda *_: self.load_more())
        paging.pack_end(self.more, False, False, 0)
        box.pack_start(paging, False, False, 0)
        selection = Gtk.Box(spacing=12)
        self.preview = Gtk.Image()
        self.preview.set_size_request(72, 72)
        selection.pack_start(self.preview, False, False, 0)
        self.name = Gtk.Label(
            label="Choose an icon from the grid or an image file.", xalign=0
        )
        self.name.set_line_wrap(True)
        self.name.set_max_width_chars(65)
        selection.pack_start(self.name, True, True, 0)
        box.pack_start(selection, False, False, 0)
        files = Gtk.Box(spacing=8)
        for label, callback in (
            ("Choose image file…", self.choose_file),
            ("Remove icon", self.remove_icon),
        ):
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            files.add(button)
        box.pack_start(files, False, False, 0)
        self.error = Gtk.Label(xalign=0)
        self.error.set_line_wrap(True)
        box.pack_start(self.error, False, False, 0)
        self.search.connect("search-changed", self.reload)
        self.context.connect("changed", self.reload)
        self.symbolic.connect("toggled", self.reload)
        self.connect("destroy", self.stop_loading)
        path = Path(os.path.expandvars(current)).expanduser() if current else None
        if path and path.is_file():
            self.select_file(str(path), path.name)
        elif current:
            info = self.theme.lookup_icon(current, 64, 0)
            if info and info.get_filename():
                self.select_file(info.get_filename(), current)
        self.reload()
        self.show_all()

    def stop_loading(self, *_):
        if self.pending:
            GLib.source_remove(self.pending)
            self.pending = 0

    def reload(self, *_):
        self.stop_loading()
        self.store.clear()
        term = self.search.get_text().strip().casefold().replace("_", "-")
        terms = term.replace(" ", "-").split("-") if term else []
        names = set(self.theme.list_icons(self.context.get_active_id() or None) or [])
        self.names = sorted(
            name
            for name in names
            if (self.symbolic.get_active() or not name.endswith("-symbolic"))
            and all(word in name.casefold() for word in terms)
        )
        self.offset = 0
        self.load_more()

    def load_more(self):
        if self.pending:
            return
        self.batch_end = min(self.offset + self.PAGE_SIZE, len(self.names))
        self.more.set_sensitive(False)
        self.pending = GLib.idle_add(self.fill_batch)

    def fill_batch(self):
        for _ in range(8):
            if self.offset >= self.batch_end:
                self.pending = 0
                self.more.set_sensitive(self.offset < len(self.names))
                text = f"{len(self.store)} icons shown"
                if self.offset < len(self.names):
                    text += f" · {len(self.names) - self.offset} more matches"
                if not len(self.store):
                    text = "No matching image files. Try another category or choose an image file."
                self.status.set_text(text)
                return False
            name = self.names[self.offset]
            self.offset += 1
            info = self.theme.lookup_icon(name, 48, 0)
            filename = info.get_filename() if info else None
            if not filename or not Path(filename).is_file():
                continue
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(filename, 48, 48, True)
                self.store.append([pixbuf, name, filename])
            except GLib.Error:
                continue
        return True

    def select_file(self, filename, name=None):
        try:
            path = Path(filename).expanduser().resolve()
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), 64, 64, True)
        except (OSError, GLib.Error) as exc:
            self.error.set_text(str(exc))
            return False
        self.selection = str(path)
        self.preview.set_from_pixbuf(pixbuf)
        self.name.set_text(name or path.name)
        self.name.set_tooltip_text(str(path))
        self.error.set_text("")
        self.set_response_sensitive(Gtk.ResponseType.OK, True)
        return True

    def selected(self, *_):
        paths = self.view.get_selected_items()
        if paths:
            row = self.store[paths[0]]
            self.select_file(row[2], row[1])

    def activate(self, _view, path):
        row = self.store[path]
        if self.select_file(row[2], row[1]):
            self.response(Gtk.ResponseType.OK)

    def remove_icon(self, *_):
        self.view.unselect_all()
        self.selection = ""
        self.preview.clear()
        self.name.set_text("No icon")
        self.name.set_tooltip_text(None)
        self.error.set_text("")
        self.set_response_sensitive(Gtk.ResponseType.OK, True)

    def choose_file(self, *_):
        dialog = Gtk.FileChooserDialog(
            title="Choose icon image",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL, "Select", Gtk.ResponseType.OK
        )
        dialog.set_local_only(True)
        images = Gtk.FileFilter()
        images.set_name("Images")
        images.add_pixbuf_formats()
        dialog.add_filter(images)
        if self.selection:
            dialog.set_filename(self.selection)
        try:
            if dialog.run() == Gtk.ResponseType.OK and dialog.get_filename():
                if self.select_file(dialog.get_filename()):
                    self.view.unselect_all()
        finally:
            dialog.destroy()


def choose_icon(parent, current=""):
    dialog = IconPicker(parent, current)
    try:
        return dialog.selection if dialog.run() == Gtk.ResponseType.OK else None
    finally:
        dialog.destroy()
