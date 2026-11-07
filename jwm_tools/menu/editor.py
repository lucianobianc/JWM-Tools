"""GTK tree editor for JWM menus."""

from pathlib import Path
import difflib
import shlex
import subprocess
import xml.etree.ElementTree as ET
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Gio
from .model import (
    MenuDocument,
    Node,
    KINDS,
    TEXT_KINDS,
    save_documents,
    topmost_nodes,
    transfer_nodes,
)
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
            self.kind.append(
                kind,
                {
                    "Program": "Application",
                    "Menu": "Submenu",
                    "RootMenu": "Root menu",
                }.get(kind, kind),
            )
        self.kind.set_active_id(node.kind if node else "Program")
        self.kind.set_sensitive(node is None)
        self.label = Gtk.Entry()
        self.label.set_text(node.attrs.get("label", "") if node else "")
        self.label.set_hexpand(True)
        self.command = Gtk.Entry()
        self.command.set_text(node.value if node else "")
        self.command.set_placeholder_text("Command, without exec:")
        self.program_button = Gtk.Button(label="Choose file…")
        self.program_button.connect("clicked", self.choose_program)
        self.icon = Gtk.Entry()
        self.icon.set_text(node.attrs.get("icon", "") if node else "")
        self.icon.set_placeholder_text("Icon theme name or image file")
        browse = Gtk.Button(label="Choose icon…")
        browse.connect("clicked", self.choose_icon)
        self.tooltip = Gtk.Entry()
        self.tooltip.set_text(node.attrs.get("tooltip", "") if node else "")
        self.onroot = Gtk.Entry()
        self.onroot.set_text(node.attrs.get("onroot", "") if node else "")
        for row, (label, widget) in enumerate(
            (
                ("Type", self.kind),
                ("Label", self.label),
                ("Path", self.command),
                ("Icon", self.icon),
                ("Tooltip", self.tooltip),
                ("Root buttons", self.onroot),
            )
        ):
            grid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
            grid.attach(widget, 1, row, 1, 1)
        grid.attach(self.program_button, 2, 2, 1, 1)
        grid.attach(browse, 2, 3, 1, 1)
        self.icon.set_icon_activatable(Gtk.EntryIconPosition.SECONDARY, False)
        choices = Gtk.Box(spacing=8)
        self.app_button = Gtk.Button(label="Installed application…")
        self.app_button.connect("clicked", self.choose_application)
        choices.add(self.app_button)
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
        image = icon_pixbuf(self.icon.get_text().strip(), 22)
        self.icon.set_icon_from_pixbuf(Gtk.EntryIconPosition.SECONDARY, image)

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

    def __init__(self, path):
        super().__init__(title="jwm_menu — Menu editor")
        self.document = MenuDocument(path)
        self.documents = {self.document.path: self.document}
        self.origins = {}
        self.drag_nodes = []
        self.tree_states = {}
        self.tree_document_path = None
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
        self.store = Gtk.TreeStore(object, GdkPixbuf.Pixbuf, str, str, str, str)
        self.tree = Gtk.TreeView(model=self.store)
        self.tree.set_tooltip_column(5)
        self.tree.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        self.tree.connect("key-press-event", self.tree_key)
        targets = [
            Gtk.TargetEntry.new(
                "application/x-jwm-menu-entry", Gtk.TargetFlags.SAME_WIDGET, 0
            )
        ]
        self.tree.enable_model_drag_source(
            Gdk.ModifierType.BUTTON1_MASK, targets, Gdk.DragAction.MOVE
        )
        self.tree.enable_model_drag_dest(targets, Gdk.DragAction.MOVE)
        self.tree.connect(
            "drag-begin", lambda *_: setattr(self, "drag_nodes", self.selected_roots())
        )
        self.tree.connect(
            "drag-data-get",
            lambda _w, _c, data, _i, _t: data.set(
                data.get_target(), 8, b"jwm-menu-entry"
            ),
        )
        self.tree.connect("drag-motion", self.drag_motion)
        self.tree.connect("drag-drop", self.drag_drop)
        self.tree.connect(
            "drag-leave",
            lambda widget, *_: widget.set_drag_dest_row(
                None, Gtk.TreeViewDropPosition.BEFORE
            ),
        )
        self.tree.connect("drag-data-received", self.drop_received)
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
        for index, title in ((3, "Type"), (4, "Path"), (5, "Source file")):
            cell = Gtk.CellRendererText()
            cell.props.ellipsize = 3
            column = Gtk.TreeViewColumn(title, cell, text=index)
            column.set_resizable(True)
            column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            column.set_fixed_width({3: 120, 4: 280, 5: 150}[index])
            column.set_expand(index == 4)
            column.set_min_width(100)
            if index == 5:
                column.set_cell_data_func(
                    cell,
                    lambda _column, renderer, model, it, _data: renderer.set_property(
                        "text", Path(model[it][5]).name
                    ),
                )
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
            ("Edit", self.edit_selected),
            ("Delete", self.remove_selected),
            ("Move up", lambda *_: self.move(-1)),
            ("Move down", lambda *_: self.move(1)),
            ("Indent", self.indent),
            ("Outdent", self.outdent),
        ):
            mnemonic = {"Add entry": "_Add", "Edit": "_Edit", "Delete": "_Delete"}.get(
                label, label
            )
            button = Gtk.Button.new_with_mnemonic(mnemonic)
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
        self.tree.set_can_focus(True)
        self.connect("key-press-event", self.window_key)
        self.connect("delete-event", lambda *_: not self.can_discard())
        self.refresh()

    def selected_nodes(self):
        model, paths = self.tree.get_selection().get_selected_rows()
        return [model[path][0] for path in paths]

    def selected_roots(self):
        model, paths = self.tree.get_selection().get_selected_rows()
        indices = [tuple(path.get_indices()) for path in paths]
        return [
            model[path][0]
            for path, index in zip(paths, indices)
            if not any(
                len(other) < len(index) and index[: len(other)] == other
                for other in indices
            )
        ]

    def selected(self):
        nodes = self.selected_nodes()
        return nodes[0] if len(nodes) == 1 else None

    def owner(self, node):
        root = node
        while root.parent is not None:
            root = root.parent
        return next(
            document for document in self.documents.values() if document.root is root
        )

    def dirty_documents(self):
        return [document for document in self.documents.values() if document.dirty]

    def can_discard(self):
        return not self.dirty_documents() or self.confirm(
            "Discard unsaved changes in all edited menu files?"
        )

    def window_key(self, _widget, event):
        focus = self.get_focus()
        if isinstance(focus, (Gtk.Entry, Gtk.TextView)):
            return False
        return self.tree_key(self.tree, event)

    def tree_key(self, _widget, event):
        if event.state & (
            Gdk.ModifierType.CONTROL_MASK
            | Gdk.ModifierType.MOD1_MASK
            | Gdk.ModifierType.SUPER_MASK
        ):
            return False
        key = Gdk.keyval_to_lower(event.keyval)
        action = {
            Gdk.KEY_Delete: self.remove_selected,
            Gdk.KEY_KP_Delete: self.remove_selected,
            Gdk.KEY_d: self.remove_selected,
            Gdk.KEY_a: self.add_entry,
            Gdk.KEY_e: self.edit_selected,
            Gdk.KEY_F2: self.edit_selected,
        }.get(key)
        if action is None:
            return False
        action()
        return True

    def selection_changed(self):
        nodes = self.selected_nodes()
        node = nodes[0] if len(nodes) == 1 else None
        if not hasattr(self, "buttons"):
            return
        self.buttons["Edit"].set_sensitive(bool(node and node.editable))
        roots = self.selected_roots()
        self.buttons["Delete"].set_sensitive(
            bool(roots) and all(n.editable for n in roots)
        )
        for label in ("Move up", "Move down", "Indent", "Outdent"):
            self.buttons[label].set_sensitive(bool(node and node.editable))

    def drag_motion(self, widget, context, x, y, timestamp):
        hit = widget.get_dest_row_at_pos(x, y)
        if hit:
            widget.set_drag_dest_row(*hit)
        Gdk.drag_status(context, Gdk.DragAction.MOVE, timestamp)
        return True

    def drag_drop(self, widget, context, _x, _y, timestamp):
        target = widget.drag_dest_find_target(context, None)
        if target:
            widget.drag_get_data(context, target, timestamp)
            return True
        return False

    def include_container(self, node):
        path = self.owner(node).include_path(node)
        document = self.documents.get(path)
        if document is None:
            raise ValueError("This Include cannot be edited as a static menu.")
        roots = [n for n in document.roots() if n.kind == "RootMenu"]
        if len(roots) > 1:
            raise ValueError("Select the submenu inside this Include.")
        return roots[0] if roots else document.root

    def drop_received(self, widget, context, x, y, _data, _info, timestamp):
        hit = widget.get_dest_row_at_pos(x, y)
        success = False
        try:
            if not hit:
                parent, after = self.destination()
                index = (
                    len(parent.children)
                    if after is None
                    else parent.children.index(after) + 1
                )
            else:
                path, position = hit
                target = self.store[path][0]
                if position in (
                    Gtk.TreeViewDropPosition.INTO_OR_BEFORE,
                    Gtk.TreeViewDropPosition.INTO_OR_AFTER,
                ) and target.kind in ("RootMenu", "Menu", "Include"):
                    parent = (
                        self.include_container(target)
                        if target.kind == "Include"
                        else target
                    )
                    index = len(parent.children)
                else:
                    parent = target.parent
                    index = parent.children.index(target) + (
                        position
                        in (
                            Gtk.TreeViewDropPosition.AFTER,
                            Gtk.TreeViewDropPosition.INTO_OR_AFTER,
                        )
                    )
            moved = transfer_nodes(self.drag_nodes, parent, index, self.owner(parent))
            self.refresh(moved[0] if moved else None)
            success = bool(moved)
        except (ValueError, StopIteration) as exc:
            self.message(str(exc))
        finally:
            Gtk.drag_finish(context, success, False, timestamp)
            self.drag_nodes = []

    def refresh(self, selected=None, reset=False):
        def key(node, source):
            return (source, node.kind, node.span[:2] if node.span else id(node))

        expanded = set()
        if self.tree_document_path is not None:

            def remember(view, path, _data):
                row = self.store[path]
                expanded.add(key(row[0], row[5]))

            self.tree.map_expanded_rows(remember, None)
            self.tree_states[self.tree_document_path] = expanded
        restore = None if reset else self.tree_states.get(self.document.path)
        self.tree_document_path = self.document.path
        self.store.clear()
        self.origins = {}
        documents = self.documents
        warnings = []
        expand_paths = []
        selected_paths = []
        self.menu_roots = []

        def add(node, parent=None, document=None, stack=()):
            document = document or self.document
            foreign = document is not self.document
            if node.kind == "RootMenu":
                self.menu_roots.append(node)
            if foreign:
                self.origins[node] = document.path
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
                    node.kind + (" · included" if foreign else ""),
                    node.value,
                    str(document.path),
                ],
            )
            for child in node.children:
                add(child, it, document, stack)
            if node.kind == "Include":
                path = document.include_path(node)
                if path is not None:
                    if path in stack or path == document.path or len(stack) >= 16:
                        warnings.append(f"Include cycle/depth limit: {path}")
                    else:
                        try:
                            if not path.is_file():
                                raise OSError(f"File not found: {path}")
                            if path not in documents:
                                documents[path] = MenuDocument(path)
                            included = documents[path]
                            for child in included.roots():
                                add(child, it, included, (*stack, document.path))
                        except (OSError, ValueError, ET.ParseError) as exc:
                            warnings.append(f"Cannot read Include {path}: {exc}")
            if restore is not None and key(node, str(document.path)) in restore:
                expand_paths.append(self.store.get_path(it))
            if node is selected:
                path = self.store.get_path(it)
                selected_paths.append(path)

        for node in self.document.roots():
            add(node)
        if restore is None:
            self.tree.expand_all()
        else:
            for path in sorted(expand_paths, key=lambda p: p.get_depth()):
                self.tree.expand_row(path, False)
        for path in selected_paths:
            self.tree.expand_to_path(path)
            self.tree.get_selection().select_path(path)
        self.file_label.set_text(str(self.document.path))
        self.file_label.set_tooltip_text(str(self.document.path))
        dirty = self.dirty_documents()
        status = (
            f"Unsaved changes in {len(dirty)} {'file' if len(dirty) == 1 else 'files'}"
            if dirty
            else "No pending changes"
        )
        if self.document.path.name == ".jwm-menu":
            status += (
                " · Running the menu generator will replace manual edits to this file."
            )
        if warnings:
            status += "\n" + "\n".join(dict.fromkeys(warnings))
        self.status.set_text(status)
        self.status.set_line_wrap(True)
        self.status.set_max_width_chars(105)
        self.selection_changed()

    def destination(self):
        node = self.selected()
        if node and node.kind == "Include":
            return self.include_container(node), None
        if node and node.kind in ("RootMenu", "Menu"):
            return node, None
        if node:
            return node.parent, node
        roots = self.menu_roots
        return (roots[0] if roots else self.document.root), None

    def bulk_target(self):
        node = self.selected()
        if node and node.kind == "Include":
            path = self.owner(node).include_path(node)
            if path and path in self.documents:
                document = self.documents[path]
                roots = [n for n in document.roots() if n.kind == "RootMenu"]
                if len(roots) <= 1:
                    return roots[0] if roots else document.root
            self.message("This Include cannot be edited as a static menu.")
            return None
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
        target_document = self.owner(target)
        children = (
            list(target_document.roots())
            if target is target_document.root
            else list(target.children)
        )
        if not children:
            return
        if self.confirm(
            "Clear all entries in this menu, including submenus? This stays pending until you save. Other configuration and Include files are kept."
        ):
            for child in children:
                target.children.remove(child)
            self.refresh(target if target is not self.document.root else None)

    def generation_mode(self, count):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            text=f"Generate menu entries for {count} installed applications?",
        )
        dialog.format_secondary_text(
            "Add keeps the current entries, submenus and Includes. Replace removes this menu's current entries. Changes stay pending until you save."
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Replace menu contents", 2)
        dialog.add_button("Add to current menu", 1)
        dialog.set_default_response(1)
        try:
            response = dialog.run()
            return {1: "add", 2: "replace"}.get(response)
        finally:
            dialog.destroy()

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
            mode = self.generation_mode(count)
            if mode not in ("add", "replace"):
                return

            # Build and validate the replacement before changing the current tree.
            def build(element, parent):
                node = Node(
                    element.tag,
                    dict(element.attrib),
                    (element.text or "") if element.tag in TEXT_KINDS else "",
                    parent=parent,
                )
                self.owner(target).validate(node.kind, node.attrs, node.value)
                node.children = [build(child, node) for child in element]
                return node

            generated = [build(child, target) for child in tree]
            if mode == "add":
                target.children.extend(generated)
            elif target is self.owner(target).root:
                retained = [
                    n for n in target.children if n not in self.owner(target).roots()
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
                        self.owner(node).update(node, attrs, value)
                        selected = node
                    else:
                        parent, after = self.destination()
                        selected = self.owner(parent).add(
                            parent, kind, attrs, value, after
                        )
                    self.refresh(selected)
                    break
                except (ValueError, ET.ParseError) as exc:
                    dialog.error.set_text(str(exc))
        finally:
            dialog.destroy()

    def add_entry(self, *_):
        needs_root = (
            self.selected() is None
            and not self.menu_roots
            and (
                self.document.path.name == ".jwmrc"
                or any(n.kind not in KINDS for n in self.document.root.children)
                or (
                    not self.document.root.children
                    and self.document.path.name != ".jwm-menu"
                )
            )
        )
        if needs_root:
            self.add_root()
        else:
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
        dialog.set_title("Add root menu")
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
        nodes = topmost_nodes(self.selected_roots())
        if not nodes or any(not node.editable for node in nodes):
            return
        for node in nodes:
            self.owner(node).remove(node)
        self.refresh()

    def move(self, step):
        node = self.selected()
        if node and self.owner(node).move(node, step):
            self.refresh(node)

    def indent(self, *_):
        node = self.selected()
        if node and self.owner(node).indent(node):
            self.refresh(node)

    def outdent(self, *_):
        node = self.selected()
        if node and self.owner(node).outdent(node):
            self.refresh(node)

    def load(self, path):
        path = Path(path).expanduser().resolve()
        same_file = path == self.document.path
        if same_file and not self.can_discard():
            return False
        try:
            if same_file:
                document = MenuDocument(path)
                self.documents = {path: document}
            else:
                document = self.documents.get(path) or MenuDocument(path)
                self.documents[path] = document
        except (OSError, ValueError, ET.ParseError) as exc:
            self.message(str(exc))
            return False
        self.document = document
        self.refresh(reset=same_file)
        return True

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

    def discard(self, *_):
        if self.can_discard():
            self.document = MenuDocument(self.document.path)
            self.documents = {self.document.path: self.document}
            self.refresh(reset=True)

    def show_changes(self, *_):
        try:
            diff = "".join(
                "".join(
                    difflib.unified_diff(
                        document.text.splitlines(keepends=True),
                        document.preview().splitlines(keepends=True),
                        fromfile=str(document.path),
                        tofile=str(document.path) + " (changed)",
                    )
                )
                for document in self.dirty_documents()
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
            save_documents(list(self.documents.values()))
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
