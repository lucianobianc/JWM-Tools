"""GTK editor for JWM session lifecycle commands."""

import difflib
from pathlib import Path
import shlex
import xml.etree.ElementTree as ET
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, GLib
from .model import StartupDocument, PHASES, HINTS, desktop_command


def combo(items, current):
    widget = Gtk.ComboBoxText()
    for key, label in items:
        widget.append(key, label)
    widget.set_active_id(current)
    return widget


class ApplicationDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title="Escolher aplicativo", transient_for=parent, modal=True)
        self.set_default_size(680, 440)
        self.add_buttons(
            "Cancelar", Gtk.ResponseType.CANCEL, "Selecionar", Gtk.ResponseType.OK
        )
        box = self.get_content_area()
        box.set_spacing(10)
        box.set_border_width(12)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Buscar aplicativo")
        box.add(self.search)
        self.store = Gtk.ListStore(object, str, str)
        for app in sorted(
            Gio.AppInfo.get_all(), key=lambda app: app.get_display_name().casefold()
        ):
            if app.should_show() and app.get_commandline():
                self.store.append([app, app.get_display_name(), app.get_commandline()])
        self.filtered = self.store.filter_new()
        self.filtered.set_visible_func(
            lambda model, it, data: not self.search.get_text()
            or self.search.get_text().casefold()
            in (model[it][1] + " " + model[it][2]).casefold()
        )
        self.search.connect("search-changed", lambda *_: self.filtered.refilter())
        self.tree = Gtk.TreeView(model=self.filtered)
        for index, title in ((1, "Aplicativo"), (2, "Comando")):
            cell = Gtk.CellRendererText()
            cell.props.ellipsize = 3
            col = Gtk.TreeViewColumn(title, cell, text=index)
            col.set_expand(True)
            self.tree.append_column(col)
        self.tree.connect(
            "row-activated", lambda *_: self.response(Gtk.ResponseType.OK)
        )
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.tree)
        box.pack_start(scroll, True, True, 0)
        self.error = Gtk.Label(xalign=0)
        self.error.set_line_wrap(True)
        box.pack_start(self.error, False, False, 0)
        self.show_all()

    def command(self):
        model, it = self.tree.get_selection().get_selected()
        if it is None:
            raise ValueError("Selecione um aplicativo.")
        app = model[it][0]
        icon = app.get_icon()
        icon_name = ""
        if isinstance(icon, Gio.ThemedIcon):
            icon_name = icon.get_names()[0]
        elif isinstance(icon, Gio.FileIcon):
            icon_name = icon.get_file().get_path() or ""
        filename = app.get_filename() if hasattr(app, "get_filename") else ""
        command = desktop_command(
            app.get_commandline(), app.get_display_name(), icon_name, filename or ""
        )
        if hasattr(app, "get_boolean") and app.get_boolean("Terminal"):
            terminal = GLib.find_program_in_path(
                "x-terminal-emulator"
            ) or GLib.find_program_in_path("xterm")
            if not terminal:
                raise ValueError(
                    "Esse aplicativo precisa de terminal. Informe o comando com um terminal de sua escolha."
                )
            command = shlex.quote(terminal) + " -e " + command
        return command


class CommandDialog(Gtk.Dialog):
    def __init__(self, parent, current=None, kind="StartupCommand"):
        super().__init__(
            title="Editar comando" if current else "Adicionar comando",
            transient_for=parent,
            modal=True,
        )
        self.current = current
        self.set_default_size(650, 0)
        self.add_buttons(
            "Cancelar", Gtk.ResponseType.CANCEL, "Confirmar", Gtk.ResponseType.OK
        )
        box = self.get_content_area()
        box.set_spacing(12)
        box.set_border_width(16)
        grid = Gtk.Grid(column_spacing=12, row_spacing=12)
        box.add(grid)
        self.kind = combo(PHASES.items(), current.kind if current else kind)
        grid.attach(Gtk.Label(label="Quando executar", xalign=0), 0, 0, 1, 1)
        grid.attach(self.kind, 1, 0, 1, 1)
        self.command = Gtk.Entry()
        self.command.set_text(current.command if current else "")
        self.command.set_hexpand(True)
        self.command.set_placeholder_text(
            "Ex.: jwm_audio ou picom --config ~/.config/picom.conf"
        )
        grid.attach(Gtk.Label(label="Comando", xalign=0), 0, 1, 1, 1)
        grid.attach(self.command, 1, 1, 1, 1)
        choose = Gtk.Box(spacing=8)
        for label, callback in [
            ("Aplicativo instalado…", self.choose_application),
            ("Programa ou script…", self.choose_file),
        ]:
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            choose.pack_start(button, False, False, 0)
        grid.attach(choose, 1, 2, 1, 1)
        self.enabled = Gtk.CheckButton(label="Ativado")
        self.enabled.set_active(current.enabled if current else True)
        grid.attach(self.enabled, 1, 3, 1, 1)
        self.hint = Gtk.Label(xalign=0)
        self.hint.set_line_wrap(True)
        self.hint.set_max_width_chars(75)
        box.add(self.hint)
        self.kind.connect("changed", self.update_hint)
        self.update_hint()
        note = Gtk.Label(
            label="Use o comando direto, sem exec:. Revise os argumentos antes de confirmar.",
            xalign=0,
        )
        note.set_line_wrap(True)
        box.add(note)
        self.error = Gtk.Label(xalign=0)
        self.error.set_line_wrap(True)
        self.error.set_max_width_chars(75)
        box.add(self.error)
        self.show_all()

    def update_hint(self, *_):
        self.hint.set_text(HINTS[self.kind.get_active_id()])

    def choose_file(self, *_):
        dialog = Gtk.FileChooserDialog(
            title="Escolher programa ou script",
            transient_for=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            "Cancelar", Gtk.ResponseType.CANCEL, "Selecionar", Gtk.ResponseType.OK
        )
        dialog.set_local_only(True)
        dialog.set_show_hidden(True)
        dialog.set_current_folder("/usr/bin")
        try:
            if dialog.run() == Gtk.ResponseType.OK and dialog.get_filename():
                self.command.set_text(shlex.quote(dialog.get_filename()))
        finally:
            dialog.destroy()

    def choose_application(self, *_):
        dialog = ApplicationDialog(self)
        try:
            while dialog.run() == Gtk.ResponseType.OK:
                try:
                    self.command.set_text(dialog.command())
                    break
                except ValueError as exc:
                    dialog.error.set_text(str(exc))
        finally:
            dialog.destroy()


class StartupEditor(Gtk.Window):
    def __init__(self, path):
        super().__init__(title="jwm_startup")
        self.document = StartupDocument(path)
        self.set_default_size(1050, 620)
        self.set_size_request(680, 440)
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
            ("Recarregar", lambda *_: self.load(self.document.path)),
        ]:
            button = Gtk.Button(label=label)
            button.connect("clicked", callback)
            header.pack_start(button, False, False, 0)
        controls = Gtk.Box(spacing=8)
        outer.pack_start(controls, False, False, 0)
        self.phase = combo([("all", "Todos"), *PHASES.items()], "all")
        self.phase.connect("changed", self.refilter)
        controls.pack_start(self.phase, False, False, 0)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Buscar comando ou arquivo")
        self.search.connect("search-changed", self.refilter)
        controls.pack_start(self.search, True, True, 0)
        self.store = Gtk.ListStore(object, bool, str, str, str, str, bool, str)
        self.filtered = self.store.filter_new()
        self.filtered.set_visible_func(self.visible)
        self.tree = Gtk.TreeView(model=self.filtered)
        self.tree.set_tooltip_column(7)
        toggle = Gtk.CellRendererToggle()
        toggle.connect("toggled", self.toggle)
        col = Gtk.TreeViewColumn("Ativo", toggle, active=1, activatable=6)
        col.set_fixed_width(55)
        self.tree.append_column(col)
        for index, title, width in (
            (2, "Momento", 155),
            (3, "Comando", 400),
            (4, "Arquivo", 170),
            (5, "Estado", 145),
        ):
            cell = Gtk.CellRendererText()
            cell.props.ellipsize = 3
            col = Gtk.TreeViewColumn(title, cell, text=index)
            col.set_resizable(True)
            col.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            col.set_fixed_width(width)
            col.set_expand(index == 3)
            self.tree.append_column(col)
        self.tree.connect("row-activated", lambda *_: self.edit_selected())
        self.tree.get_selection().connect("changed", self.selection_changed)
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.tree)
        outer.pack_start(scroll, True, True, 0)
        self.explanation = Gtk.Label(xalign=0)
        self.explanation.set_line_wrap(True)
        self.explanation.set_max_width_chars(105)
        outer.pack_start(self.explanation, False, False, 0)
        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        self.status.set_max_width_chars(105)
        outer.pack_start(self.status, False, False, 0)
        buttons = Gtk.FlowBox()
        buttons.set_selection_mode(Gtk.SelectionMode.NONE)
        buttons.set_max_children_per_line(7)
        buttons.set_min_children_per_line(1)
        outer.pack_start(buttons, False, False, 0)
        for label, callback in [
            ("Adicionar", self.add_command),
            ("Editar", self.edit_selected),
            ("Excluir", self.remove_selected),
            ("Abrir origem", self.open_source),
            ("Descartar", self.discard),
            ("Ver alterações", self.show_changes),
            ("Salvar", self.save),
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

    def visible(self, model, it, _data=None):
        command = model[it][0]
        if self.phase.get_active_id() not in ("all", command.kind):
            return False
        term = self.search.get_text().strip().casefold()
        return (
            not term or term in (command.command + " " + str(command.source)).casefold()
        )

    def refilter(self, *_):
        self.filtered.refilter()
        self.update_explanation()

    def selected(self):
        model, it = self.tree.get_selection().get_selected()
        return model[it][0] if it is not None else None

    def selection_changed(self, *_):
        command = self.selected()
        self.edit_button.set_sensitive(bool(command and command.editable))
        self.remove_button.set_sensitive(bool(command and command.editable))
        self.source_button.set_sensitive(bool(command and not command.editable))
        self.update_explanation()

    def update_explanation(self):
        command = self.selected() if hasattr(self, "tree") else None
        kind = command.kind if command else self.phase.get_active_id()
        if hasattr(self, "explanation"):
            self.explanation.set_text(
                HINTS.get(
                    kind,
                    "Salvar não executa comandos. Eles serão usados no próximo evento correspondente do JWM.",
                )
            )

    def refresh(self, select=None):
        self.store.clear()
        duplicates = self.document.duplicates()
        for command in self.document.entries():
            state = (
                "Incluído · leitura"
                if not command.editable
                else (
                    "Novo"
                    if command.span is None
                    else "Alterado" if command.token in self.document.changes else ""
                )
            )
            if command.token in duplicates:
                state = ("Repetido · " + state).rstrip(" ·")
            it = self.store.append(
                [
                    command,
                    command.enabled,
                    PHASES[command.kind],
                    command.command,
                    command.source.name,
                    state,
                    command.editable,
                    str(command.source),
                ]
            )
            if select == command.token:
                path = self.filtered.convert_child_path_to_path(self.store.get_path(it))
                if path is not None:
                    self.tree.get_selection().select_path(path)
        self.file_label.set_text(str(self.document.path))
        self.file_label.set_tooltip_text(str(self.document.path))
        text = f"{len(self.document.entries())} comandos · {len(self.document.changes)+len(self.document.additions)} alterações pendentes"
        if duplicates:
            text += " · Há comandos repetidos no mesmo momento"
        if self.document.warnings:
            text += "\n" + "; ".join(self.document.warnings)
        self.status.set_text(text)
        self.selection_changed()

    def message(self, text):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
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
        result = dialog.run()
        dialog.destroy()
        return result == Gtk.ResponseType.YES

    def can_discard(self):
        return not self.document.dirty or self.confirm(
            "Descartar as alterações não salvas?"
        )

    def toggle(self, _renderer, path):
        command = self.filtered[path][0]
        if not command.editable:
            return
        try:
            self.document.update(
                command.token, command.kind, command.command, not command.enabled
            )
            self.refresh(command.token)
        except ValueError as exc:
            self.message(str(exc))

    def add_command(self, *_):
        kind = self.phase.get_active_id()
        self.edit_command(kind=kind if kind in PHASES else "StartupCommand")

    def edit_command(self, command=None, kind="StartupCommand"):
        dialog = CommandDialog(self, command, kind)
        try:
            while dialog.run() == Gtk.ResponseType.OK:
                try:
                    phase = dialog.kind.get_active_id()
                    text = dialog.command.get_text().strip()
                    enabled = dialog.enabled.get_active()
                    from .model import Command, validate

                    candidate = Command(
                        "", phase, text, self.document.path, {}, enabled
                    )
                    validate(candidate, command)
                    if self.document.duplicates(
                        candidate, command.token if command else None
                    ) and not self.confirm(
                        "Esse comando já está ativado no mesmo momento. Manter a repetição?"
                    ):
                        continue
                    updated = (
                        self.document.update(command.token, phase, text, enabled)
                        if command
                        else self.document.add(phase, text, enabled)
                    )
                    self.refresh(updated.token)
                    break
                except (ValueError, ET.ParseError) as exc:
                    dialog.error.set_text(str(exc))
        finally:
            dialog.destroy()

    def edit_selected(self, *_):
        command = self.selected()
        if command and command.editable:
            self.edit_command(command)

    def remove_selected(self, *_):
        command = self.selected()
        if (
            command
            and command.editable
            and self.confirm("Excluir este comando? A exclusão será gravada ao salvar.")
        ):
            self.document.remove(command.token)
            self.refresh()

    def open_source(self, *_):
        command = self.selected()
        if command and not command.editable:
            self.load(command.source)

    def load(self, path):
        if not self.can_discard():
            return
        try:
            self.document = StartupDocument(path)
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
        dialog.set_show_hidden(True)
        dialog.set_filename(str(self.document.path))
        try:
            if dialog.run() == Gtk.ResponseType.OK and dialog.get_filename():
                self.load(dialog.get_filename())
        finally:
            dialog.destroy()

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


def main():
    import argparse
    from .. import __version__

    parser = argparse.ArgumentParser(
        description="Edita comandos de início, reinício e encerramento do JWM."
    )
    parser.add_argument("configuration", nargs="?", default=str(Path.home() / ".jwmrc"))
    parser.add_argument(
        "--version", action="version", version="jwm_startup " + __version__
    )
    args = parser.parse_args()
    try:
        window = StartupEditor(args.configuration)
    except (OSError, ValueError, ET.ParseError) as exc:
        parser.exit(1, str(exc) + "\n")
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()
