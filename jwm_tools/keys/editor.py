"""GTK interface for keyboard and window-manager mouse bindings."""

import difflib
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk
from .model import (
    BindingDocument,
    Binding,
    ACTIONS,
    CONTEXTS,
    MODIFIERS,
    normalize_mask,
    mouse_label,
    validate,
)


def entry(text=""):
    widget = Gtk.Entry()
    widget.set_text(text)
    widget.set_hexpand(True)
    return widget


def combo(items, current):
    widget = Gtk.ComboBoxText()
    for key, label in items:
        widget.append(key, label)
    widget.set_active_id(current)
    return widget


def event_mask(state):
    flags = [
        ("C", Gdk.ModifierType.CONTROL_MASK),
        ("S", Gdk.ModifierType.SHIFT_MASK),
        ("A", Gdk.ModifierType.MOD1_MASK),
        ("3", Gdk.ModifierType.MOD3_MASK),
        ("4", Gdk.ModifierType.MOD4_MASK | Gdk.ModifierType.SUPER_MASK),
        ("5", Gdk.ModifierType.MOD5_MASK),
    ]
    return "".join(char for char, flag in flags if state & flag)


class BindingDialog(Gtk.Dialog):
    def __init__(self, parent, kind, binding=None):
        super().__init__(
            title=("Editar " if binding else "Adicionar ")
            + ("teclado" if kind == "Key" else "mouse"),
            transient_for=parent,
            modal=True,
        )
        self.kind = kind
        self.binding = binding
        self.set_default_size(570, 0)
        self.add_buttons(
            "Cancelar", Gtk.ResponseType.CANCEL, "Confirmar", Gtk.ResponseType.OK
        )
        self.set_default_response(Gtk.ResponseType.OK)
        self.grid = Gtk.Grid(column_spacing=12, row_spacing=12, margin=16)
        self.get_content_area().add(self.grid)
        attrs = binding.attrs if binding else {}
        try:
            mask = normalize_mask(attrs.get("mask", ""))
        except ValueError:
            mask = attrs.get("mask", "")
        self.modifiers = {}
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(4)
        for char, label in MODIFIERS.items():
            check = Gtk.CheckButton(label=label)
            check.set_active(char in mask)
            self.modifiers[char] = check
            flow.add(check)
        self.attach("Modificadores", flow, 0)
        if kind == "Key":
            self.mode = combo(
                [("key", "Nome X11"), ("keycode", "Keycode")],
                "key" if attrs.get("key") or not attrs.get("keycode") else "keycode",
            )
            self.trigger = entry(attrs.get("key") or attrs.get("keycode", ""))
            row = Gtk.Box(spacing=6)
            row.pack_start(self.trigger, True, True, 0)
            capture = Gtk.Button(label="Capturar…")
            capture.connect("clicked", self.capture_key)
            row.pack_start(capture, False, False, 0)
            self.attach("Identificação", self.mode, 1)
            self.attach("Tecla", row, 2)
            self.context = None
        else:
            self.mode = None
            self.context = combo(CONTEXTS.items(), attrs.get("context", "title"))
            self.trigger = Gtk.ComboBoxText.new_with_entry()
            self.trigger.set_hexpand(True)
            for code in (*range(1, 10), -1, -2, -3, 11, 22, 33):
                self.trigger.append(
                    str(code), str(code) + " — " + mouse_label(str(code))
                )
            code = attrs.get("button", "1")
            self.trigger.set_active_id(code)
            if self.trigger.get_active_id() is None:
                self.trigger.get_child().set_text(code)
            row = Gtk.Box(spacing=6)
            row.pack_start(self.trigger, True, True, 0)
            capture = Gtk.Button(label="Capturar…")
            capture.connect("clicked", self.capture_mouse)
            row.pack_start(capture, False, False, 0)
            self.attach("Contexto", self.context, 1)
            self.attach("Botão / evento", row, 2)
        self.action = Gtk.ComboBoxText.new_with_entry()
        for action in ("exec:", "root:1", *ACTIONS):
            self.action.append_text(action)
        self.action.get_child().set_text(
            binding.action if binding else "exec:" if kind == "Key" else "move"
        )
        self.action.set_hexpand(True)
        self.attach("Ação", self.action, 3)
        hint = Gtk.Label(
            label="Use exec:comando para executar um programa. A ação só será ativada pelo JWM depois de salvar e reiniciar.",
            xalign=0,
        )
        hint.set_line_wrap(True)
        hint.set_max_width_chars(60)
        self.grid.attach(hint, 0, 4, 2, 1)
        self.error = Gtk.Label(xalign=0)
        self.error.set_line_wrap(True)
        self.error.set_max_width_chars(60)
        self.grid.attach(self.error, 0, 5, 2, 1)
        self.show_all()

    def attach(self, label, widget, row):
        self.grid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
        self.grid.attach(widget, 1, row, 1, 1)

    def attributes(self):
        attrs = dict(self.binding.attrs) if self.binding else {}
        mask = "".join(
            char for char, widget in self.modifiers.items() if widget.get_active()
        )
        original = attrs.get("mask", "")
        try:
            same = normalize_mask(original) == mask
        except ValueError:
            same = False
        if not same:
            if mask:
                attrs["mask"] = mask
            else:
                attrs.pop("mask", None)
        if self.kind == "Key":
            mode = self.mode.get_active_id()
            attrs.pop("keycode" if mode == "key" else "key", None)
            attrs[mode] = self.trigger.get_text().strip()
        else:
            attrs["context"] = self.context.get_active_id() or ""
            attrs["button"] = (
                self.trigger.get_active_id()
                or self.trigger.get_child().get_text().split(" — ", 1)[0].strip()
            )
        return attrs

    def candidate(self):
        attrs = self.attributes()
        action = self.action.get_child().get_text().strip()
        candidate = Binding(
            self.binding.token if self.binding else "",
            self.kind,
            attrs,
            action,
            Path("."),
        )
        validate(candidate, self.binding)
        return candidate

    def set_modifiers(self, mask):
        for char, widget in self.modifiers.items():
            widget.set_active(char in mask)

    def capture_key_event(self, _dialog, event):
        name = Gdk.keyval_name(event.keyval)
        if (
            not name
            or name.startswith(
                ("Shift_", "Control_", "Alt_", "Super_", "Meta_", "Hyper_")
            )
            or name in ("Caps_Lock", "Num_Lock", "ISO_Level3_Shift")
        ):
            return True
        self.mode.set_active_id("key")
        self.trigger.set_text(name)
        self.set_modifiers(event_mask(event.state))
        _dialog.response(Gtk.ResponseType.OK)
        return True

    def capture_key(self, *_):
        dialog = Gtk.Dialog(title="Capturar tecla", transient_for=self, modal=True)
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        label = Gtk.Label(
            label="Pressione a combinação desejada.\nAtalhos globais podem ser interceptados pelo JWM.",
            margin=24,
        )
        dialog.get_content_area().add(label)
        dialog.connect("key-press-event", self.capture_key_event)
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def capture_mouse(self, *_):
        dialog = Gtk.Dialog(
            title="Capturar botão do mouse", transient_for=self, modal=True
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        box = dialog.get_content_area()
        box.set_border_width(16)
        box.set_spacing(12)
        mode = combo(
            [
                ("press", "Pressionar"),
                ("release", "Soltar"),
                ("double", "Duplo clique"),
            ],
            "press",
        )
        box.add(mode)
        area = Gtk.EventBox()
        area.add(
            Gtk.Label(label="Clique ou role aqui com o botão desejado.", margin=24)
        )
        area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.SCROLL_MASK)

        def selected(_area, event):
            scroll = {
                Gdk.ScrollDirection.UP: 4,
                Gdk.ScrollDirection.DOWN: 5,
                Gdk.ScrollDirection.LEFT: 6,
                Gdk.ScrollDirection.RIGHT: 7,
            }
            code = (
                scroll.get(event.direction)
                if event.type == Gdk.EventType.SCROLL
                else event.button
            )
            if not code:
                return True
            code = (
                -code
                if mode.get_active_id() == "release"
                else code * 11 if mode.get_active_id() == "double" else code
            )
            self.trigger.set_active_id(str(code))
            if self.trigger.get_active_id() is None:
                self.trigger.get_child().set_text(str(code))
            self.set_modifiers(event_mask(event.state))
            dialog.response(Gtk.ResponseType.OK)
            return True

        area.connect("button-press-event", selected)
        area.connect("scroll-event", selected)
        box.add(area)
        dialog.show_all()
        dialog.run()
        dialog.destroy()


class KeysEditor(Gtk.Window):
    def __init__(self, path):
        super().__init__(title="jwm_keys")
        self.document = BindingDocument(path)
        self.set_default_size(1050, 620)
        self.set_size_request(680, 420)
        self.set_border_width(12)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(outer)
        header = Gtk.Box(spacing=8)
        outer.pack_start(header, False, False, 0)
        self.file_label = Gtk.Label(xalign=0)
        self.file_label.set_ellipsize(2)
        header.pack_start(self.file_label, True, True, 0)
        for label, callback in [
            ("Abrir…", self.open_file),
            ("Recarregar", self.reload_file),
        ]:
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            header.pack_start(button, False, False, 0)
        tools = Gtk.Box(spacing=8)
        outer.pack_start(tools, False, False, 0)
        self.kind_filter = combo(
            [("all", "Todos"), ("Key", "Teclado"), ("Mouse", "Mouse")], "all"
        )
        self.kind_filter.connect("changed", self.refilter)
        tools.pack_start(self.kind_filter, False, False, 0)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Buscar tecla, ação, contexto ou arquivo")
        self.search.connect("search-changed", self.refilter)
        tools.pack_start(self.search, True, True, 0)
        self.store = Gtk.ListStore(object, str, str, str, str, str, str, str)
        self.filtered = self.store.filter_new()
        self.filtered.set_visible_func(self.visible)
        self.tree = Gtk.TreeView(model=self.filtered)
        self.tree.set_tooltip_column(7)
        self.tree.set_headers_visible(True)
        for i, label in enumerate(
            ("Tipo", "Atalho", "Contexto", "Ação", "Arquivo", "Estado"), 1
        ):
            renderer = Gtk.CellRendererText()
            renderer.props.ellipsize = 3
            column = Gtk.TreeViewColumn(label, renderer, text=i)
            column.set_resizable(True)
            column.set_expand(i == 4)
            column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            column.set_fixed_width((75, 185, 130, 260, 170, 140)[i - 1])
            column.set_min_width(60)
            self.tree.append_column(column)
        self.tree.connect("row-activated", lambda *_: self.edit_selected())
        self.tree.get_selection().connect("changed", self.selection_changed)
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.tree)
        outer.pack_start(scroll, True, True, 0)
        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        self.status.set_max_width_chars(100)
        outer.pack_start(self.status, False, False, 0)
        buttons = Gtk.FlowBox()
        buttons.set_selection_mode(Gtk.SelectionMode.NONE)
        buttons.set_max_children_per_line(8)
        buttons.set_min_children_per_line(1)
        outer.pack_start(buttons, False, False, 0)
        for label, callback in [
            ("Novo teclado", lambda *_: self.edit_binding("Key")),
            ("Novo mouse", lambda *_: self.edit_binding("Mouse")),
            ("Editar", self.edit_selected),
            ("Excluir", self.remove_selected),
            ("Abrir origem", self.open_source),
            ("Descartar", self.discard),
            ("Ver alterações", self.show_changes),
            ("Salvar", self.save),
            ("Salvar e reiniciar JWM", self.apply),
        ]:
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            buttons.add(button)
            if label == "Editar":
                self.edit_button = button
            elif label == "Excluir":
                self.remove_button = button
            elif label == "Abrir origem":
                self.source_button = button
        self.connect("delete-event", lambda *_: not self.can_discard())
        self.refresh()

    def visible(self, model, iterator, _data=None):
        binding = model[iterator][0]
        if self.kind_filter.get_active_id() not in ("all", binding.kind):
            return False
        term = self.search.get_text().casefold().strip()
        return (
            not term
            or term
            in (
                " ".join(str(v) for v in model[iterator][1:])
                + " "
                + binding.attrs.get("context", "")
            ).casefold()
        )

    def refilter(self, *_):
        self.filtered.refilter()

    def selected(self):
        model, iterator = self.tree.get_selection().get_selected()
        return model[iterator][0] if iterator is not None else None

    def selection_changed(self, *_):
        selected = self.selected()
        self.edit_button.set_sensitive(bool(selected and selected.editable))
        self.remove_button.set_sensitive(bool(selected and selected.editable))
        self.source_button.set_sensitive(bool(selected and not selected.editable))

    def refresh(self, select=None):
        self.store.clear()
        conflicts = self.document.conflicts()
        for binding in self.document.entries():
            state = (
                "Incluído · leitura"
                if not binding.editable
                else (
                    "Novo"
                    if binding.span is None
                    else "Alterado" if binding.token in self.document.changes else ""
                )
            )
            if binding.token in conflicts:
                state = ("Conflito · " + state).rstrip(" ·")
            iterator = self.store.append(
                [
                    binding,
                    "Teclado" if binding.kind == "Key" else "Mouse",
                    binding.shortcut(),
                    CONTEXTS.get(binding.attrs.get("context"), ""),
                    binding.action,
                    binding.source.name,
                    state,
                    str(binding.source),
                ]
            )
            if select == binding.token:
                path = self.filtered.convert_child_path_to_path(
                    self.store.get_path(iterator)
                )
                if path is not None:
                    self.tree.get_selection().select_path(path)
        self.file_label.set_text(str(self.document.path))
        self.file_label.set_tooltip_text(str(self.document.path))
        changes = len(self.document.changes) + len(self.document.additions)
        message = (
            f"{len(self.document.entries())} vínculos · {changes} alterações pendentes"
        )
        if conflicts:
            message += f" · {len(conflicts)} vínculos em conflito (a última definição pode prevalecer)"
        if self.document.config.warnings:
            message += "\n" + "; ".join(self.document.config.warnings)
        self.status.set_text(message)
        self.selection_changed()

    def message(self, text, error=True):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR if error else Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.CLOSE,
            text=text,
        )
        dialog.run()
        dialog.destroy()

    def confirm(self, text):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=text,
        )
        dialog.set_default_response(Gtk.ResponseType.NO)
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.YES

    def can_discard(self):
        return not self.document.dirty or self.confirm(
            "Descartar as alterações não salvas?"
        )

    def edit_binding(self, kind, binding=None):
        dialog = BindingDialog(self, kind, binding)
        try:
            while dialog.run() == Gtk.ResponseType.OK:
                try:
                    candidate = dialog.candidate()
                    matches = self.document.conflicts(
                        candidate, binding.token if binding else None
                    )
                    if matches and not self.confirm(
                        "Essa combinação já aparece em outro vínculo. Manter as duas definições?"
                    ):
                        continue
                    if binding:
                        updated = self.document.update(
                            binding.token, candidate.attrs, candidate.action
                        )
                    else:
                        updated = self.document.add(
                            kind, candidate.attrs, candidate.action
                        )
                    self.refresh(updated.token)
                    break
                except (ValueError, OSError, ET.ParseError) as exc:
                    dialog.error.set_text(str(exc))
        finally:
            dialog.destroy()

    def edit_selected(self, *_):
        binding = self.selected()
        if binding and binding.editable:
            self.edit_binding(binding.kind, binding)

    def remove_selected(self, *_):
        binding = self.selected()
        if (
            binding
            and binding.editable
            and self.confirm("Excluir este vínculo? A exclusão será gravada ao salvar.")
        ):
            self.document.remove(binding.token)
            self.refresh()

    def open_source(self, *_):
        binding = self.selected()
        if binding and not binding.editable:
            self.load(binding.source)

    def load(self, path):
        if not self.can_discard():
            return
        try:
            self.document = BindingDocument(path)
        except (OSError, ValueError, ET.ParseError) as exc:
            self.message(str(exc))
            return
        self.refresh()

    def open_file(self, *_):
        dialog = Gtk.FileChooserDialog(
            title="Abrir configuração do JWM",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            "Cancelar", Gtk.ResponseType.CANCEL, "Abrir", Gtk.ResponseType.OK
        )
        dialog.set_filename(str(self.document.path))
        try:
            if dialog.run() == Gtk.ResponseType.OK and dialog.get_filename():
                self.load(dialog.get_filename())
        finally:
            dialog.destroy()

    def reload_file(self, *_):
        self.load(self.document.path)

    def discard(self, *_):
        if self.can_discard():
            self.document.reset()
            self.refresh()

    def show_changes(self, *_):
        try:
            diff = "".join(
                difflib.unified_diff(
                    self.document.original.decode("utf-8").splitlines(keepends=True),
                    self.document.preview().splitlines(keepends=True),
                    fromfile="Original",
                    tofile="Alterado",
                )
            )
        except (ValueError, ET.ParseError) as exc:
            self.message(str(exc))
            return
        dialog = Gtk.Dialog(title="Alterações no XML", transient_for=self, modal=True)
        dialog.set_default_size(800, 480)
        dialog.add_button("Fechar", Gtk.ResponseType.CLOSE)
        view = Gtk.TextView()
        view.set_editable(False)
        view.set_monospace(True)
        view.get_buffer().set_text(diff or "Nenhuma alteração.")
        scroll = Gtk.ScrolledWindow()
        scroll.add(view)
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
                raise RuntimeError(result.stderr or f"jwm retornou {result.returncode}")
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            self.message(
                "Arquivo salvo, mas não foi possível reiniciar o JWM:\n" + str(exc)
            )


def main():
    import argparse
    from .. import __version__

    parser = argparse.ArgumentParser(
        description="Edita vínculos de teclado e mouse do JWM."
    )
    parser.add_argument("configuration", nargs="?", default=str(Path.home() / ".jwmrc"))
    parser.add_argument(
        "--version", action="version", version="jwm_keys " + __version__
    )
    args = parser.parse_args()
    try:
        window = KeysEditor(args.configuration)
    except (OSError, ValueError, ET.ParseError) as exc:
        parser.exit(1, str(exc) + "\n")
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()
