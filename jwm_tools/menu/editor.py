"""GTK tree editor for JWM menus."""

from pathlib import Path
import difflib
import shlex
import subprocess
import xml.etree.ElementTree as ET
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GLib, Gio
from .model import MenuDocument, Node, KINDS, TEXT_KINDS
from ..startup.editor import ApplicationDialog, StartupEditor
from ..iconpicker import choose_icon


def icon_pixbuf(name, size=22):
    if not name:
        return None
    try:
        path = Path(name).expanduser()
        if path.is_file():
            return GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), size, size, True)
        return Gtk.IconTheme.get_default().load_icon(name, size, 0)
    except (GLib.Error, OSError):
        return None


class EntryDialog(Gtk.Dialog):
    def __init__(self, parent, node=None):
        super().__init__(
            title="Edit menu entry" if node else "Add menu entry",
            transient_for=parent,
            modal=True,
        )
        self.node = node
        self.set_default_size(680, 0)
        self.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL, "Confirm", Gtk.ResponseType.OK
        )
        box = self.get_content_area()
        box.set_border_width(16)
        box.set_spacing(12)
        grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        box.add(grid)
        self.kind = Gtk.ComboBoxText()
        for kind in ("RootMenu",) if node and node.kind == "RootMenu" else KINDS:
            self.kind.append(kind, kind)
        self.kind.set_active_id(node.kind if node else "Program")
        self.kind.set_sensitive(node is None)
        self.label = Gtk.Entry()
        self.label.set_text(node.attrs.get("label", "") if node else "")
        self.label.set_hexpand(True)
        self.command = Gtk.Entry()
        self.command.set_text(node.value if node else "")
        self.command.set_placeholder_text("Command, without exec:")
        self.icon = Gtk.Entry()
        self.icon.set_text(node.attrs.get("icon", "") if node else "")
        self.icon.set_placeholder_text("Icon theme name or image file")
        self.image = Gtk.Image()
        iconrow = Gtk.Box(spacing=8)
        iconrow.pack_start(self.image, False, False, 0)
        iconrow.pack_start(self.icon, True, True, 0)
        browse = Gtk.Button(label="Choose icon…")
        browse.connect("clicked", self.choose_icon)
        iconrow.pack_start(browse, False, False, 0)
        self.tooltip = Gtk.Entry()
        self.tooltip.set_text(node.attrs.get("tooltip", "") if node else "")
        self.onroot = Gtk.Entry()
        self.onroot.set_text(node.attrs.get("onroot", "") if node else "")
        for row, (label, widget) in enumerate(
            (
                ("Type", self.kind),
                ("Label", self.label),
                ("Command / path", self.command),
                ("Icon", iconrow),
                ("Tooltip", self.tooltip),
                ("Root buttons", self.onroot),
            )
        ):
            grid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
            grid.attach(widget, 1, row, 1, 1)
        choices = Gtk.Box(spacing=8)
        self.app_button = Gtk.Button(label="Installed application…")
        self.app_button.connect("clicked", self.choose_application)
        choices.add(self.app_button)
        self.program_button = Gtk.Button(label="Program or script…")
        self.program_button.connect("clicked", self.choose_program)
        choices.add(self.program_button)
        grid.attach(choices, 1, 6, 1, 1)
        self.note = Gtk.Label(
            label="Saving does not launch menu commands. Unknown attributes are preserved.",
            xalign=0,
        )
        self.note.set_line_wrap(True)
        box.add(self.note)
        self.error = Gtk.Label(xalign=0)
        self.error.set_line_wrap(True)
        self.error.set_max_width_chars(80)
        box.add(self.error)
        self.kind.connect("changed", self.update_fields)
        self.icon.connect("changed", self.update_icon)
        self.update_fields()
        self.update_icon()
        self.show_all()

    def update_fields(self, *_):
        kind = self.kind.get_active_id()
        self.command.set_sensitive(kind in TEXT_KINDS)
        self.onroot.set_sensitive(kind == "RootMenu")
        self.app_button.set_sensitive(kind == "Program")
        self.program_button.set_sensitive(
            kind in ("Program", "Exit", "Dynamic", "Include")
        )
        self.command.set_placeholder_text(
            "File path, or exec:command for a dynamic Include"
            if kind == "Include"
            else "Command, without exec:"
        )

    def update_icon(self, *_):
        image = icon_pixbuf(self.icon.get_text().strip(), 32)
        if image:
            self.image.set_from_pixbuf(image)
        else:
            self.image.clear()

    def candidate(self):
        kind = self.kind.get_active_id()
        attrs = dict(self.node.attrs) if self.node else {}
        for key, widget in (
            ("label", self.label),
            ("icon", self.icon),
            ("tooltip", self.tooltip),
        ):
            value = widget.get_text().strip()
            if value:
                attrs[key] = value
            else:
                attrs.pop(key, None)
        if kind == "RootMenu":
            value = self.onroot.get_text().strip()
            if value:
                if not value.isdecimal() or "0" in value:
                    raise ValueError(
                        "Root buttons must be button numbers, for example 12."
                    )
                attrs["onroot"] = value
            else:
                attrs.pop("onroot", None)
        value = (
            self.command.get_text().strip()
            if kind in TEXT_KINDS
            else (self.node.value if self.node else "")
        )
        return kind, attrs, value

    def choose_path(self, title, image=False):
        chooser = Gtk.FileChooserDialog(
            title=title, transient_for=self, action=Gtk.FileChooserAction.OPEN
        )
        chooser.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL, "Select", Gtk.ResponseType.OK
        )
        chooser.set_local_only(True)
        chooser.set_show_hidden(True)
        if image:
            images = Gtk.FileFilter()
            images.set_name("Images")
            images.add_pixbuf_formats()
            chooser.add_filter(images)
            allfiles = Gtk.FileFilter()
            allfiles.set_name("All files")
            allfiles.add_pattern("*")
            chooser.add_filter(allfiles)
            preview = Gtk.Image()
            chooser.set_preview_widget(preview)

            def update_preview(dialog):
                filename = dialog.get_preview_filename()
                pixbuf = icon_pixbuf(filename, 128) if filename else None
                if pixbuf:
                    preview.set_from_pixbuf(pixbuf)
                dialog.set_preview_widget_active(bool(pixbuf))

            chooser.connect("update-preview", update_preview)
        try:
            return (
                chooser.get_filename() if chooser.run() == Gtk.ResponseType.OK else None
            )
        finally:
            chooser.destroy()

    def choose_icon(self, *_):
        value = choose_icon(self, self.icon.get_text())
        if value is not None:
            self.icon.set_text(value)

    def choose_program(self, *_):
        filename = self.choose_path(
            "Choose file"
            if self.kind.get_active_id() == "Include"
            else "Choose program or script"
        )
        if filename:
            self.command.set_text(
                filename
                if self.kind.get_active_id() == "Include"
                else shlex.quote(filename)
            )

    def choose_application(self, *_):
        dialog = ApplicationDialog(self)
        try:
            while dialog.run() == Gtk.ResponseType.OK:
                try:
                    command = dialog.command()
                    model, it = dialog.tree.get_selection().get_selected()
                    app = model[it][0]
                    self.label.set_text(app.get_display_name())
                    self.command.set_text(command)
                    icon = app.get_icon()
                    if isinstance(icon, Gio.ThemedIcon):
                        self.icon.set_text(icon.get_names()[0])
                    elif isinstance(icon, Gio.FileIcon):
                        self.icon.set_text(icon.get_file().get_path() or "")
                    else:
                        self.icon.set_text("")
                    break
                except ValueError as exc:
                    dialog.error.set_text(str(exc))
        finally:
            dialog.destroy()


class MenuEditor(Gtk.Window):
    message = StartupEditor.message
    confirm = StartupEditor.confirm
    can_discard = StartupEditor.can_discard

    def __init__(self, path):
        super().__init__(title="jwm_menu — Menu editor")
        self.document = MenuDocument(path)
        self.set_default_size(1080, 650)
        self.set_size_request(720, 480)
        self.set_border_width(12)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(box)
        header = Gtk.Box(spacing=8)
        self.file_label = Gtk.Label(xalign=0)
        self.file_label.set_ellipsize(2)
        header.pack_start(self.file_label, True, True, 0)
        for label, callback in (
            ("Open…", self.open_file),
            ("Reload", lambda *_: self.load(self.document.path)),
        ):
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            header.add(button)
        box.pack_start(header, False, False, 0)
        self.store = Gtk.TreeStore(object, GdkPixbuf.Pixbuf, str, str, str)
        self.tree = Gtk.TreeView(model=self.store)
        self.tree.set_tooltip_column(4)
        column = Gtk.TreeViewColumn("Menu entry")
        icon = Gtk.CellRendererPixbuf()
        column.pack_start(icon, False)
        column.add_attribute(icon, "pixbuf", 1)
        text = Gtk.CellRendererText()
        text.props.ellipsize = 3
        column.pack_start(text, True)
        column.add_attribute(text, "text", 2)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        column.set_fixed_width(400)
        column.set_resizable(True)
        self.tree.append_column(column)
        for index, title in ((3, "Type"), (4, "Command / path")):
            cell = Gtk.CellRendererText()
            cell.props.ellipsize = 3
            column = Gtk.TreeViewColumn(title, cell, text=index)
            column.set_resizable(True)
            column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            column.set_fixed_width(130 if index == 3 else 380)
            column.set_expand(index == 4)
            column.set_min_width(100)
            self.tree.append_column(column)
        self.tree.connect("row-activated", lambda *_: self.edit_selected())
        self.tree.get_selection().connect(
            "changed", lambda *_: self.selection_changed()
        )
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.tree)
        box.pack_start(scroll, True, True, 0)
        actions = Gtk.FlowBox()
        actions.set_selection_mode(Gtk.SelectionMode.NONE)
        actions.set_max_children_per_line(9)
        self.buttons = {}
        for label, callback in (
            ("Add entry", self.add_entry),
            ("Add root menu", self.add_root),
            ("Edit", self.edit_selected),
            ("Delete", self.remove_selected),
            ("Move up", lambda *_: self.move(-1)),
            ("Move down", lambda *_: self.move(1)),
            ("Indent", self.indent),
            ("Outdent", self.outdent),
            ("Open Include", self.open_include),
        ):
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            actions.add(button)
            self.buttons[label] = button
        box.pack_start(actions, False, False, 0)
        bulk = Gtk.Box(spacing=8)
        for label, callback in (
            ("Generate from applications", self.generate_apps),
            ("Clear menu", self.clear_menu),
        ):
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            bulk.pack_start(button, False, False, 0)
            self.buttons[label] = button
        box.pack_start(bulk, False, False, 0)
        note = Gtk.Label(
            label="Menu entries appear from top to bottom. Dynamic menus and Includes are never executed by the editor.",
            xalign=0,
        )
        note.set_line_wrap(True)
        box.pack_start(note, False, False, 0)
        self.status = Gtk.Label(xalign=0)
        box.pack_start(self.status, False, False, 0)
        footer = Gtk.Box(spacing=8)
        for label, callback in (
            ("Discard", self.discard),
            ("View changes", self.show_changes),
            ("Save", self.save),
            ("Save and restart JWM", self.apply),
        ):
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            footer.pack_start(button, True, True, 0)
        box.pack_start(footer, False, False, 0)
        self.connect("delete-event", lambda *_: not self.can_discard())
        self.refresh()

    def selected(self):
        model, it = self.tree.get_selection().get_selected()
        return model[it][0] if it is not None else None

    def selection_changed(self):
        node = self.selected()
        if not hasattr(self, "buttons"):
            return
        editable = bool(node and node.editable)
        for label in ("Edit", "Delete", "Move up", "Move down", "Indent", "Outdent"):
            self.buttons[label].set_sensitive(editable)
        self.buttons["Open Include"].set_sensitive(
            bool(node and self.document.include_path(node))
        )

    def refresh(self, selected=None):
        self.store.clear()

        def add(node, parent=None):
            label = (
                node.label
                if node.kind != "RootMenu"
                else (node.attrs.get("label") or "Root menu")
                + " · buttons "
                + node.attrs.get("onroot", "default")
            )
            it = self.store.append(
                parent,
                [
                    node,
                    icon_pixbuf(node.attrs.get("icon")),
                    label,
                    node.kind,
                    node.value,
                ],
            )
            for child in node.children:
                add(child, it)
            if node is selected:
                path = self.store.get_path(it)
                self.tree.expand_to_path(path)
                self.tree.get_selection().select_path(path)

        for node in self.document.roots():
            add(node)
        self.tree.expand_all()
        self.file_label.set_text(str(self.document.path))
        self.file_label.set_tooltip_text(str(self.document.path))
        status = "Unsaved changes" if self.document.dirty else "No pending changes"
        if self.document.path.name == ".jwm-menu":
            status += (
                " · Running the menu generator will replace manual edits to this file."
            )
        self.status.set_text(status)
        self.selection_changed()

    def destination(self):
        node = self.selected()
        if node and node.kind in ("RootMenu", "Menu"):
            return node, None
        if node:
            return node.parent, node
        roots = [n for n in self.document.roots() if n.kind == "RootMenu"]
        return (roots[0] if roots else self.document.root), None

    def bulk_target(self):
        node = self.selected()
        if node:
            return node if node.kind in ("RootMenu", "Menu") else node.parent
        roots = [n for n in self.document.roots() if n.kind == "RootMenu"]
        if len(roots) > 1:
            self.message("Select the root menu or submenu to change.")
            return None
        if not roots and (
            self.document.path.name == ".jwmrc"
            or any(n.kind not in KINDS for n in self.document.root.children)
        ):
            self.message(
                "Add or select a root menu first. Other configuration will be kept."
            )
            return None
        return roots[0] if roots else self.document.root

    def clear_menu(self, *_):
        target = self.bulk_target()
        if target is None:
            return
        children = (
            list(target.children)
            if target is not self.document.root
            else list(self.document.roots())
        )
        if not children:
            return
        if self.confirm(
            "Clear all entries in this menu, including submenus? This stays pending until you save. Other configuration and Include files are kept."
        ):
            for child in children:
                target.children.remove(child)
            self.refresh(target if target is not self.document.root else None)

    def generate_apps(self, *_):
        target = self.bulk_target()
        if target is None:
            return
        from .generator import generate_tree

        try:
            tree, count = generate_tree()
            if not count:
                self.message("No installed applications were found. The menu was kept.")
                return
            if not self.confirm(
                f"Replace this menu's entries with {count} installed applications? This stays pending until you save. Include files are kept."
            ):
                return

            # Build and validate the replacement before changing the current tree.
            def build(element, parent):
                node = Node(
                    element.tag,
                    dict(element.attrib),
                    (element.text or "") if element.tag in TEXT_KINDS else "",
                    parent=parent,
                )
                self.document.validate(node.kind, node.attrs, node.value)
                node.children = [build(child, node) for child in element]
                return node

            generated = [build(child, target) for child in tree]
            if target is self.document.root:
                retained = [
                    n for n in target.children if n not in self.document.roots()
                ]
                target.children = retained + generated
            else:
                target.children = generated
            self.refresh(target if target is not self.document.root else None)
        except (OSError, ValueError, ET.ParseError) as exc:
            self.message(str(exc))

    def edit_form(self, node=None):
        dialog = EntryDialog(self, node)
        try:
            while dialog.run() == Gtk.ResponseType.OK:
                try:
                    kind, attrs, value = dialog.candidate()
                    if node:
                        self.document.update(node, attrs, value)
                        selected = node
                    else:
                        parent, after = self.destination()
                        selected = self.document.add(parent, kind, attrs, value, after)
                    self.refresh(selected)
                    break
                except (ValueError, ET.ParseError) as exc:
                    dialog.error.set_text(str(exc))
        finally:
            dialog.destroy()

    def add_entry(self, *_):
        self.edit_form()

    def add_root(self, *_):
        used = set(
            "".join(
                n.attrs.get("onroot", "123")
                for n in self.document.roots()
                if n.kind == "RootMenu"
            )
        )
        buttons = next((str(n) for n in range(1, 10) if str(n) not in used), "")
        dialog = EntryDialog(self, Node("RootMenu", {"onroot": buttons}))
        try:
            while dialog.run() == Gtk.ResponseType.OK:
                try:
                    kind, attrs, value = dialog.candidate()
                    node = self.document.add(self.document.root, kind, attrs, value)
                    self.refresh(node)
                    break
                except ValueError as exc:
                    dialog.error.set_text(str(exc))
        finally:
            dialog.destroy()

    def edit_selected(self, *_):
        node = self.selected()
        if node and node.editable:
            self.edit_form(node)

    def remove_selected(self, *_):
        node = self.selected()
        if (
            node
            and node.editable
            and self.confirm(
                "Delete this entry and any submenu contents? Changes are written when you save."
            )
        ):
            self.document.remove(node)
            self.refresh()

    def move(self, step):
        node = self.selected()
        if node and self.document.move(node, step):
            self.refresh(node)

    def indent(self, *_):
        node = self.selected()
        if node and self.document.indent(node):
            self.refresh(node)

    def outdent(self, *_):
        node = self.selected()
        if node and self.document.outdent(node):
            self.refresh(node)

    def load(self, path):
        if not self.can_discard():
            return
        try:
            document = MenuDocument(path)
        except (OSError, ValueError, ET.ParseError) as exc:
            self.message(str(exc))
            return
        self.document = document
        self.refresh()

    def open_file(self, *_):
        chooser = Gtk.FileChooserDialog(
            title="Open JWM menu or configuration",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        chooser.add_buttons(
            "Cancel", Gtk.ResponseType.CANCEL, "Open", Gtk.ResponseType.OK
        )
        chooser.set_show_hidden(True)
        try:
            if chooser.run() == Gtk.ResponseType.OK and chooser.get_filename():
                self.load(chooser.get_filename())
        finally:
            chooser.destroy()

    def open_include(self, *_):
        node = self.selected()
        path = self.document.include_path(node) if node else None
        if path:
            self.load(path)

    def discard(self, *_):
        if self.can_discard():
            self.document = MenuDocument(self.document.path)
            self.refresh()

    def show_changes(self, *_):
        try:
            diff = "".join(
                difflib.unified_diff(
                    self.document.text.splitlines(keepends=True),
                    self.document.preview().splitlines(keepends=True),
                    fromfile="Original",
                    tofile="Changed",
                )
            )
        except (ValueError, ET.ParseError) as exc:
            self.message(str(exc))
            return
        dialog = Gtk.Dialog(title="XML changes", transient_for=self, modal=True)
        dialog.set_default_size(800, 480)
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        text = Gtk.TextView(editable=False, monospace=True)
        text.get_buffer().set_text(diff or "No changes.")
        scroll = Gtk.ScrolledWindow()
        scroll.add(text)
        dialog.get_content_area().add(scroll)
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def save(self, *_):
        try:
            self.document.save()
        except (OSError, ValueError, ET.ParseError) as exc:
            self.message(str(exc))
            return False
        self.refresh()
        return True

    def apply(self, *_):
        if not self.save():
            return
        try:
            result = subprocess.run(
                ["jwm", "-restart"], capture_output=True, text=True, timeout=10
            )
            if result.returncode:
                raise RuntimeError(result.stderr or f"jwm returned {result.returncode}")
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            self.message("File saved, but JWM could not be restarted:\n" + str(exc))


def main(path):
    try:
        window = MenuEditor(path)
    except (OSError, ValueError, ET.ParseError) as exc:
        raise SystemExit(str(exc))
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()
