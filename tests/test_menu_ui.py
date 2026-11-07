import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from jwm_tools.menu.editor import MenuEditor, EntryDialog


@unittest.skipUnless(os.environ.get("DISPLAY"), "GTK requires X11")
class MenuUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "jwmrc"
        self.xml = '<JWM><RootMenu onroot="12"><Menu label="Tools"/><Program label="One" icon="utilities-terminal">xterm</Program><Include>exec:false</Include></RootMenu></JWM>'
        self.path.write_text(self.xml)
        self.errors = []
        hook = patch.object(sys, "excepthook", lambda *args: self.errors.append(args))
        hook.start()
        self.addCleanup(hook.stop)
        self.addCleanup(lambda: self.assertFalse(self.errors, str(self.errors)))
        self.window = MenuEditor(self.path)
        self.window.show_all()
        self.addCleanup(self.window.destroy)

    def select(self, node):
        self.window.tree.get_selection().unselect_all()

        def visit(model, path, it, _):
            if model[it][0] is node:
                self.window.tree.expand_to_path(path)
                self.window.tree.get_selection().select_path(path)
                return True

        self.window.store.foreach(visit, None)

    def test_tree_reorder_and_indent_outdent_save(self):
        root = self.window.document.roots()[0]
        program = root.children[1]
        self.select(program)
        self.window.indent()
        self.assertIs(self.window.selected(), program)
        self.assertEqual(program.parent.kind, "Menu")
        self.window.outdent()
        self.window.move(-1)
        self.assertEqual(self.path.read_text(), self.xml)
        self.assertTrue(self.window.save())
        self.assertEqual(self.window.document.roots()[0].children[0].kind, "Program")
        self.assertEqual(self.path.with_name("jwmrc.bak").read_text(), self.xml)

    def test_icon_picker_is_file_dialog_and_cancel_preserves(self):
        dialog = EntryDialog(self.window)
        try:
            with patch(
                "jwm_tools.menu.editor.choose_icon", return_value="/tmp/my icon.svg"
            ) as picker:
                dialog.choose_icon()
                picker.assert_called_once_with(dialog, "")
                self.assertEqual(dialog.icon.get_text(), "/tmp/my icon.svg")
                self.assertIn("icon", dialog.candidate()[1])
            with patch("jwm_tools.menu.editor.choose_icon", return_value=None):
                dialog.choose_icon()
                self.assertEqual(dialog.icon.get_text(), "/tmp/my icon.svg")
            with patch("jwm_tools.menu.editor.choose_icon", return_value=""):
                dialog.choose_icon()
                self.assertNotIn("icon", dialog.candidate()[1])
        finally:
            dialog.destroy()

    def test_program_picker_quotes_path(self):
        dialog = EntryDialog(self.window)
        try:
            self.assertIs(
                dialog.command.get_parent(), dialog.program_button.get_parent()
            )
            with patch.object(dialog, "choose_path", return_value="/tmp/my program"):
                dialog.program_button.clicked()
                self.assertEqual(dialog.command.get_text(), "'/tmp/my program'")
            dialog.kind.set_active_id("Include")
            with patch.object(dialog, "choose_path", return_value="/tmp/my menu"):
                dialog.program_button.clicked()
                self.assertEqual(dialog.command.get_text(), "/tmp/my menu")
        finally:
            dialog.destroy()

    def test_application_picker_fills_label_and_command(self):
        dialog = EntryDialog(self.window)
        try:
            with patch("jwm_tools.menu.editor.ApplicationDialog") as factory:
                picker = factory.return_value
                picker.run.return_value = Gtk.ResponseType.OK
                picker.command.return_value = "xterm -e top"
                app = MagicMock()
                app.get_display_name.return_value = "System monitor"
                app.get_icon.return_value = None
                picker.tree.get_selection.return_value.get_selected.return_value = (
                    {0: [app]},
                    0,
                )
                dialog.choose_application()
                self.assertEqual(dialog.label.get_text(), "System monitor")
                self.assertEqual(dialog.command.get_text(), "xterm -e top")
                picker.destroy.assert_called_once()
        finally:
            dialog.destroy()

    def test_include_entries_are_editable_without_navigation_buttons(self):
        root = self.window.document.roots()[0]
        included = Path(self.temp.name) / "menu"
        included.write_text('<JWM><Program label="Included">true</Program></JWM>')
        self.window.document.update(root.children[2], {}, str(included))
        self.window.refresh()
        node = next(iter(self.window.origins))
        self.select(node)
        self.assertTrue(self.window.buttons["Edit"].get_sensitive())
        self.assertNotIn("Open source file", self.window.buttons)
        self.assertFalse(hasattr(self.window, "back_button"))
        self.assertNotIn("Add root menu", self.window.buttons)

    def test_external_change_save_error_and_discard_protection(self):
        root = self.window.document.roots()[0]
        self.window.document.remove(root.children[0])
        self.path.write_text("<JWM/>")
        with patch.object(self.window, "message") as message:
            self.assertFalse(self.window.save())
            message.assert_called_once()
        with patch.object(self.window, "confirm", return_value=False):
            self.window.discard()
        self.assertTrue(self.window.document.dirty)

    def test_clear_menu_pending_cancel_discard_and_preserve_config(self):
        self.path.write_text(
            self.xml.replace("</JWM>", '<Key key="F1">close</Key></JWM>')
        )
        self.window.load(self.path)
        original = self.path.read_bytes()
        with patch.object(self.window, "confirm", return_value=False):
            self.window.buttons["Clear menu"].clicked()
        self.assertFalse(self.window.document.dirty)
        with patch.object(self.window, "confirm", return_value=True):
            self.window.buttons["Clear menu"].clicked()
        self.assertEqual(self.window.document.roots()[0].children, [])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertIn('<Key key="F1">close</Key>', self.window.document.preview())
        with patch.object(self.window, "confirm", return_value=True):
            self.window.discard()
        self.assertFalse(self.window.document.dirty)

    def test_generation_targets_submenu_only_and_requires_save(self):
        import xml.etree.ElementTree as ET

        generated = ET.fromstring(
            '<JWM><Menu label="Utilities"><Program label="Fixture">true</Program></Menu></JWM>'
        )
        ET.indent(generated, space="    ")
        root = self.window.document.roots()[0]
        target = root.children[0]
        self.select(target)
        with patch(
            "jwm_tools.menu.generator.generate_tree", return_value=(generated, 1)
        ), patch.object(self.window, "generation_mode", return_value="replace"):
            self.window.buttons["Generate from applications"].clicked()
        self.assertEqual(target.children[0].children[0].value, "true")
        self.assertEqual(root.children[1].value, "xterm")
        self.assertEqual(self.path.read_text(), self.xml)
        self.assertTrue(self.window.save())
        self.assertIn("Fixture", self.path.read_text())

    def test_generation_cancel_and_empty_results_keep_menu(self):
        import xml.etree.ElementTree as ET

        generated = ET.fromstring('<JWM><Program label="Fixture">true</Program></JWM>')
        with patch(
            "jwm_tools.menu.generator.generate_tree", return_value=(generated, 1)
        ), patch.object(self.window, "generation_mode", return_value=None):
            self.window.generate_apps()
        self.assertFalse(self.window.document.dirty)
        with patch(
            "jwm_tools.menu.generator.generate_tree",
            return_value=(ET.Element("JWM"), 0),
        ), patch.object(self.window, "message") as message:
            self.window.generate_apps()
            message.assert_called_once()
        self.assertFalse(self.window.document.dirty)

    def test_actual_generation_with_indentation_can_be_confirmed_and_saved(self):
        from jwm_tools.menu import generator

        apps = Path(self.temp.name) / "apps"
        apps.mkdir()
        (apps / "fixture.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Fixture\nExec=/bin/true %f\nCategories=Utility;\n"
        )
        with patch.multiple(
            generator, HOME=Path(self.temp.name), SEARCH_PATHS=[apps]
        ), patch.object(
            self.window, "generation_mode", return_value="replace"
        ), patch.object(
            self.window, "message"
        ) as message:
            self.window.buttons["Generate from applications"].clicked()
            message.assert_not_called()
        root = self.window.document.roots()[0]
        self.assertEqual(root.children[0].attrs["label"], "Utilities")
        self.assertEqual(root.children[0].value, "")
        self.assertEqual(root.children[0].children[0].value, "/bin/true")
        self.assertEqual(self.path.read_text(), self.xml)
        self.assertTrue(self.window.save())
        self.assertIn("Fixture", self.path.read_text())
        self.assertEqual(self.path.with_name("jwmrc.bak").read_text(), self.xml)

    def test_add_generation_keeps_entries_and_include_until_save(self):
        import xml.etree.ElementTree as ET

        generated = ET.fromstring(
            '<JWM><Menu label="Generated"><Program label="New">new</Program></Menu></JWM>'
        )
        root = self.window.document.roots()[0]
        old = list(root.children)
        with patch(
            "jwm_tools.menu.generator.generate_tree", return_value=(generated, 1)
        ), patch.object(self.window, "generation_mode", return_value="add"):
            self.window.generate_apps()
        self.assertEqual(root.children[:3], old)
        self.assertEqual(root.children[-1].attrs["label"], "Generated")
        self.assertEqual(self.path.read_text(), self.xml)
        self.assertTrue(self.window.save())
        self.assertIn("exec:false", self.path.read_text())

    def test_static_include_entries_edit_their_source_in_place(self):
        included = Path(self.temp.name) / "included-menu"
        included.write_text(
            '<JWM><Menu label="Included"><Program label="Original">true</Program></Menu></JWM>'
        )
        self.path.write_text(
            f'<JWM><RootMenu onroot="12"><Include>{included}</Include></RootMenu><Key key="F1">close</Key></JWM>'
        )
        original = self.path.read_bytes()
        self.window.load(self.path)
        program = next(node for node in self.window.origins if node.kind == "Program")
        self.select(program)
        self.assertTrue(self.window.buttons["Edit"].get_sensitive())
        self.assertTrue(self.window.buttons["Delete"].get_sensitive())
        with patch.object(self.window, "edit_form") as form:
            self.window.edit_selected()
            local = form.call_args.args[0]
        self.assertEqual(self.window.document.path, self.path)
        self.assertIs(self.window.selected(), local)
        self.window.owner(local).update(
            local, {**local.attrs, "label": "Changed"}, "false"
        )
        self.assertTrue(self.window.save())
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.window.document.path, self.path)
        self.assertTrue(
            any(node.attrs.get("label") == "Changed" for node in self.window.origins)
        )

    def test_nested_include_cycle_missing_and_dynamic_are_safe(self):
        included = Path(self.temp.name) / "nested"
        marker = Path(self.temp.name) / "must-not-exist"
        included.write_text(
            f'<JWM><Program label="Nested">true</Program><Include>{self.path}</Include></JWM>'
        )
        self.path.write_text(
            f"<JWM><RootMenu><Include>{included}</Include><Include>{self.path.parent}/missing</Include><Include>exec:touch {marker}</Include></RootMenu></JWM>"
        )
        self.window.load(self.path)
        self.assertTrue(
            any(n.attrs.get("label") == "Nested" for n in self.window.origins)
        )
        self.assertIn("cycle", self.window.status.get_text())
        self.assertIn("Cannot read Include", self.window.status.get_text())
        self.assertFalse(marker.exists())
        self.assertFalse(self.window.document.dirty)

    def test_generation_prompt_has_add_replace_and_cancel(self):
        with patch("jwm_tools.menu.editor.Gtk.MessageDialog") as factory:
            dialog = factory.return_value
            dialog.run.return_value = 1
            self.assertEqual(self.window.generation_mode(5), "add")
            dialog.set_default_response.assert_called_with(1)
            dialog.run.return_value = 2
            self.assertEqual(self.window.generation_mode(5), "replace")
            dialog.run.return_value = Gtk.ResponseType.CANCEL
            self.assertIsNone(self.window.generation_mode(5))

    def test_collapsed_submenu_stays_closed_when_adding_elsewhere(self):
        root = self.window.document.roots()[0]
        menu = root.children[0]
        self.window.document.add(menu, "Program", {"label": "Nested"}, "true")
        self.window.refresh(menu)
        self.window.tree.expand_row(Gtk.TreePath.new_from_string("0:0"), False)
        self.window.tree.collapse_row(Gtk.TreePath.new_from_string("0:0"))
        self.assertFalse(
            self.window.tree.row_expanded(Gtk.TreePath.new_from_string("0:0"))
        )
        added = self.window.document.add(
            root, "Program", {"label": "Elsewhere"}, "false"
        )
        self.window.refresh(added)
        self.assertFalse(
            self.window.tree.row_expanded(Gtk.TreePath.new_from_string("0:0"))
        )
        self.assertIs(self.window.selected(), added)

    def test_entry_fields_are_aligned_with_inline_icon_preview(self):
        dialog = EntryDialog(self.window)
        try:
            dialog.icon.set_text("folder")
            for _ in range(10):
                while Gtk.events_pending():
                    Gtk.main_iteration_do(False)
            entries = (
                dialog.label,
                dialog.command,
                dialog.icon,
                dialog.tooltip,
                dialog.onroot,
            )
            allocations = [entry.get_allocation() for entry in entries]
            self.assertEqual(len({a.x for a in allocations}), 1)
            self.assertEqual(len({a.width for a in allocations}), 1)
            self.assertEqual(len({a.height for a in allocations}), 1)
        finally:
            dialog.destroy()

    def test_delete_included_entry_edits_source_pending_until_save(self):
        included = Path(self.temp.name) / "delete-source"
        included.write_text(
            '<JWM><Program label="Remove">true</Program><Program label="Keep">false</Program></JWM>'
        )
        self.path.write_text(
            f"<JWM><RootMenu><Include>{included}</Include></RootMenu></JWM>"
        )
        original = self.path.read_bytes()
        before = included.read_bytes()
        self.window.load(self.path)
        node = next(n for n in self.window.origins if n.attrs.get("label") == "Remove")
        self.select(node)
        self.assertTrue(self.window.buttons["Delete"].get_sensitive())
        with patch.object(self.window, "confirm") as confirm:
            self.window.buttons["Delete"].clicked()
            confirm.assert_not_called()
        self.assertEqual(self.window.document.path, self.path)
        self.assertEqual(included.read_bytes(), before)
        self.assertTrue(self.window.save())
        self.assertNotIn("Remove", included.read_text())
        self.assertIn("Keep", included.read_text())
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(
            included.with_name(included.name + ".bak").read_bytes(), before
        )

    def select_many(self, nodes):
        self.window.tree.get_selection().unselect_all()

        def visit(model, path, it, _):
            if model[it][0] in nodes:
                self.window.tree.expand_to_path(path)
                self.window.tree.get_selection().select_path(path)

        self.window.store.foreach(visit, None)

    def test_multi_delete_is_pending_and_never_asks_confirmation(self):
        root = self.window.document.roots()[0]
        nested = self.window.document.add(
            root.children[0], "Program", {"label": "Nested"}, "true"
        )
        self.window.refresh()
        self.select_many([root.children[0], nested, root.children[1]])
        with patch.object(self.window, "confirm") as confirm:
            self.window.remove_selected()
            confirm.assert_not_called()
        self.assertEqual([n.kind for n in root.children], ["Include"])
        self.assertEqual(self.path.read_text(), self.xml)
        self.assertTrue(self.window.save())
        self.assertNotIn("Nested", self.path.read_text())
        self.assertNotIn("xterm", self.path.read_text())

    def test_delete_multiple_source_files_in_place_and_save_both(self):
        included = Path(self.temp.name) / "multi-source"
        included.write_text('<JWM><Program label="Included">true</Program></JWM>')
        root = self.window.document.roots()[0]
        self.window.document.update(root.children[2], {}, str(included))
        self.window.save()
        original = self.path.read_bytes()
        root = self.window.document.roots()[0]
        foreign = next(n for n in self.window.origins if n.kind == "Program")
        self.select_many([root.children[1], foreign])
        self.window.buttons["Delete"].clicked()
        self.assertEqual(self.window.document.path, self.path)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertIn("Included", included.read_text())
        self.assertEqual(len(self.window.dirty_documents()), 2)
        self.assertTrue(self.window.save())
        self.assertNotIn("xterm", self.path.read_text())
        self.assertNotIn("Included", included.read_text())

    def test_drag_into_submenu_updates_model_and_keeps_selection(self):
        root = self.window.document.roots()[0]
        program = root.children[1]
        self.window.drag_nodes = [program]
        context = MagicMock()
        with patch.object(
            self.window.tree,
            "get_dest_row_at_pos",
            return_value=(
                Gtk.TreePath.new_from_string("0:0"),
                Gtk.TreeViewDropPosition.INTO_OR_AFTER,
            ),
        ), patch("jwm_tools.menu.editor.Gtk.drag_finish") as finish:
            self.window.drop_received(self.window.tree, context, 0, 0, None, 0, 1)
            finish.assert_called_once_with(context, True, False, 1)
        self.assertIs(program.parent, root.children[0])
        self.assertIs(self.window.selected(), program)
        self.assertEqual(self.path.read_text(), self.xml)
        self.assertTrue(self.window.save())
        self.assertEqual(
            self.window.document.roots()[0].children[0].children[0].value, "xterm"
        )

    def test_drag_to_included_submenu_preserves_commands_and_writes_both(self):
        included = Path(self.temp.name) / "drag-destination"
        included.write_text('<JWM><Menu label="Included"/></JWM>')
        root = self.window.document.roots()[0]
        self.window.document.update(root.children[2], {}, str(included))
        self.window.save()
        root = self.window.document.roots()[0]
        self.window.drag_nodes = [root.children[1]]
        context = MagicMock()
        with patch.object(
            self.window.tree,
            "get_dest_row_at_pos",
            return_value=(
                Gtk.TreePath.new_from_string("0:2:0"),
                Gtk.TreeViewDropPosition.INTO_OR_AFTER,
            ),
        ), patch("jwm_tools.menu.editor.Gtk.drag_finish") as finish:
            self.window.drop_received(self.window.tree, context, 0, 0, None, 0, 1)
            finish.assert_called_once_with(context, True, False, 1)
        self.assertEqual(len(self.window.dirty_documents()), 2)
        self.assertTrue(self.window.save())
        self.assertNotIn("xterm", self.path.read_text())
        self.assertIn("xterm", included.read_text())

    def test_shortcuts_and_mnemonics(self):
        from types import SimpleNamespace
        from gi.repository import Gdk

        for key, method in (
            (Gdk.KEY_a, "add_entry"),
            (Gdk.KEY_e, "edit_selected"),
            (Gdk.KEY_F2, "edit_selected"),
            (Gdk.KEY_d, "remove_selected"),
            (Gdk.KEY_Delete, "remove_selected"),
        ):
            with patch.object(self.window, method) as action:
                self.assertTrue(
                    self.window.tree_key(
                        self.window.tree, SimpleNamespace(keyval=key, state=0)
                    )
                )
                action.assert_called_once()
                self.assertEqual(
                    key == Gdk.KEY_a,
                    self.window.tree_key(
                        self.window.tree,
                        SimpleNamespace(
                            keyval=key, state=Gdk.ModifierType.CONTROL_MASK
                        ),
                    ),
                )
        self.assertTrue(self.window.buttons["Add entry"].get_use_underline())
        self.assertEqual(self.window.buttons["Add entry"].get_label(), "_Add")

    def test_add_creates_root_when_main_configuration_has_none(self):
        path = self.path.with_name(".jwmrc")
        path.write_text("<JWM><Tray/></JWM>")
        self.window.load(path)
        with patch.object(self.window, "add_root") as add_root, patch.object(
            self.window, "edit_form"
        ) as form:
            self.window.add_entry()
            add_root.assert_called_once()
            form.assert_not_called()
        self.assertNotIn("Add root menu", self.window.buttons)

    @unittest.skipUnless(
        os.environ.get("JWM_REAL_TESTS") == "1",
        "Set JWM_REAL_TESTS=1 for real X11 input",
    )
    def test_real_mouse_drag_moves_entry_into_submenu(self):
        root = self.window.document.roots()[0]
        node, target = root.children[1], root.children[0]
        self.real_mouse_drag("0:1", "0:0")
        self.assertIs(node.parent, target)
        self.assertEqual(self.path.read_text(), self.xml)

    def real_mouse_drag(self, source, destination, edge=False):
        import ctypes as C
        import ctypes.util
        import time

        x = C.CDLL(C.util.find_library("X11"))
        xt = C.CDLL(C.util.find_library("Xtst"))
        x.XOpenDisplay.argtypes = [C.c_char_p]
        x.XOpenDisplay.restype = C.c_void_p
        x.XFlush.argtypes = [C.c_void_p]
        x.XCloseDisplay.argtypes = [C.c_void_p]
        xt.XTestFakeMotionEvent.argtypes = [
            C.c_void_p,
            C.c_int,
            C.c_int,
            C.c_int,
            C.c_ulong,
        ]
        xt.XTestFakeButtonEvent.argtypes = [C.c_void_p, C.c_uint, C.c_int, C.c_ulong]
        display = x.XOpenDisplay(None)
        self.assertTrue(display)

        def pump(count=5):
            for _ in range(count):
                while Gtk.events_pending():
                    Gtk.main_iteration_do(False)
                time.sleep(0.01)

        self.window.present()
        pump()
        origin = self.window.tree.get_bin_window().get_origin()
        a = self.window.tree.get_background_area(
            Gtk.TreePath.new_from_string(source), None
        )
        b = self.window.tree.get_background_area(
            Gtk.TreePath.new_from_string(destination), None
        )
        sx, sy = origin[-2] + 150, origin[-1] + a.y + a.height // 2
        tx, ty = origin[-2] + 150, origin[-1] + b.y + b.height // 2

        if edge:
            ty = (
                self.window.tree.get_window().get_origin()[-1]
                + self.window.tree.get_allocated_height()
                - 4
            )

        def motion(px, py):
            xt.XTestFakeMotionEvent(display, -1, px, py, 0)
            x.XFlush(display)
            pump(3)

        try:
            motion(sx, sy)
            xt.XTestFakeButtonEvent(display, 1, True, 0)
            x.XFlush(display)
            pump(3)
            for i in range(1, 11):
                motion(sx + 30 * i // 10, sy + (ty - sy) * i // 10)
            motion(tx, ty)
            pump(60 if edge else 10)
            during = self.window.scroller.get_vadjustment().get_value()
            xt.XTestFakeButtonEvent(display, 1, False, 0)
            x.XFlush(display)
            pump(20)
            return during
        finally:
            xt.XTestFakeButtonEvent(display, 1, False, 0)
            x.XFlush(display)
            x.XCloseDisplay(display)

    def test_delete_include_and_preview_child_only_removes_reference(self):
        included = Path(self.temp.name) / "preserve-source"
        included.write_text('<JWM><Program label="Keep">true</Program></JWM>')
        original = included.read_bytes()
        root = self.window.document.roots()[0]
        self.window.document.update(root.children[2], {}, str(included))
        self.window.refresh()
        foreign = next(iter(self.window.origins))
        self.select_many([root.children[2], foreign])
        self.window.remove_selected()
        self.assertTrue(self.window.save())
        self.assertEqual(included.read_bytes(), original)
        self.assertNotIn(str(included), self.path.read_text())

    def test_add_uses_root_menu_from_an_include(self):
        included = Path(self.temp.name) / "root-menu-source"
        included.write_text(
            '<JWM><RootMenu onroot="12"><Program label="Existing">true</Program></RootMenu></JWM>'
        )
        path = self.path.with_name(".jwmrc")
        path.write_text(f"<JWM><Include>{included}</Include></JWM>")
        self.window.load(path)
        with patch.object(self.window, "edit_form") as form, patch.object(
            self.window, "add_root"
        ) as add_root:
            self.window.add_entry()
            form.assert_called_once()
            add_root.assert_not_called()
        parent, after = self.window.destination()
        self.assertEqual(parent.kind, "RootMenu")
        self.assertEqual(self.window.owner(parent).path, included)
        self.assertIsNone(after)

    def pump(self, count=10):
        import time

        for _ in range(count):
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
            time.sleep(0.01)

    def test_copy_paste_multiple_entries_preserves_source_and_xml(self):
        root = self.window.document.roots()[0]
        second = self.window.document.add(
            root, "Program", {"label": "Second", "icon": "folder"}, 'printf "a & b"'
        )
        self.window.refresh()
        self.select_many([root.children[1], second])
        self.window.copy_selection()
        self.select(root.children[0])
        self.window.paste_selection()
        pasted = root.children[0].children
        self.assertEqual([n.value for n in pasted], ["xterm", 'printf "a & b"'])
        self.assertIsNot(pasted[1], second)
        self.assertIn(second, root.children)
        self.assertEqual(self.path.read_text(), self.xml)
        self.assertTrue(self.window.save())
        self.assertIn("&amp;", self.path.read_text())

    def test_cut_paste_moves_selection_and_second_paste_copies(self):
        root = self.window.document.roots()[0]
        node = root.children[1]
        self.select(node)
        self.window.copy_selection(cut=True)
        self.assertIn(node, root.children)
        self.assertFalse(self.window.document.dirty)
        self.assertTrue(self.window.is_cut(node))
        self.select(root.children[0])
        self.window.paste_selection()
        self.assertIs(node.parent, root.children[0])
        self.assertFalse(self.window.cut_nodes)
        self.select(root.children[0])
        self.window.paste_selection()
        self.assertEqual(len(root.children[0].children), 2)
        self.assertIsNot(root.children[0].children[1], node)

    def test_cut_paste_between_includes_writes_both_sources(self):
        included = Path(self.temp.name) / "paste-target"
        included.write_text('<JWM><Menu label="Target"/></JWM>')
        root = self.window.document.roots()[0]
        self.window.document.update(root.children[2], {}, str(included))
        self.window.save()
        root = self.window.document.roots()[0]
        self.select(root.children[1])
        self.window.copy_selection(cut=True)
        target = next(n for n in self.window.origins if n.kind == "Menu")
        self.select(target)
        self.window.paste_selection()
        self.assertEqual(len(self.window.dirty_documents()), 2)
        self.assertTrue(self.window.save())
        self.assertNotIn("xterm", self.path.read_text())
        self.assertIn("xterm", included.read_text())

    def test_cut_cannot_paste_parent_into_itself_and_invalid_clipboard_is_ignored(self):
        from gi.repository import Gdk

        root = self.window.document.roots()[0]
        self.select(root.children[0])
        self.window.copy_selection(cut=True)
        with patch.object(self.window, "message") as message:
            self.window.paste_selection()
            message.assert_called_once()
        self.assertFalse(self.window.document.dirty)
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text("ordinary text", -1)
        with patch.object(self.window, "message") as message:
            self.window.paste_selection()
            message.assert_called_once()
        self.assertFalse(self.window.document.dirty)

    def test_undo_redo_delete_and_save_then_undo(self):
        root = self.window.document.roots()[0]
        self.select(root.children[1])
        self.window.remove_selected()
        self.assertTrue(self.window.document.dirty)
        self.window.undo()
        self.assertFalse(self.window.document.dirty)
        self.window.redo()
        self.assertTrue(self.window.document.dirty)
        self.assertTrue(self.window.save())
        self.window.undo()
        self.assertTrue(self.window.document.dirty)
        self.assertTrue(self.window.save())
        self.assertIn("xterm", self.path.read_text())

    def test_move_preserves_vertical_scroll_position(self):
        root = self.window.document.roots()[0]
        for i in range(100):
            self.window.document.add(root, "Program", {"label": f"Item {i:03}"}, "true")
        self.window.refresh()
        self.pump()
        adjustment = self.window.scroller.get_vadjustment()
        adjustment.set_value(1000)
        self.pump()
        node = root.children[45]
        self.select(node)
        before = adjustment.get_value()
        self.window.move(1)
        self.pump()
        self.assertGreater(before, 100)
        self.assertAlmostEqual(adjustment.get_value(), before, delta=2)

    def test_drag_scrolls_at_edges_and_stops_on_leave(self):
        root = self.window.document.roots()[0]
        for i in range(100):
            self.window.document.add(root, "Program", {"label": f"Long {i}"}, "true")
        self.window.refresh()
        self.pump()
        adjustment = self.window.scroller.get_vadjustment()
        with patch("jwm_tools.menu.editor.Gdk.drag_status"):
            self.window.drag_motion(
                self.window.tree,
                MagicMock(),
                100,
                self.window.tree.get_allocated_height() - 2,
                0,
            )
        self.pump(20)
        self.assertGreater(adjustment.get_value(), 0)
        self.window.drag_leave(self.window.tree)
        self.assertEqual(self.window.drag_scroll_id, 0)
        before = adjustment.get_value()
        self.pump()
        self.assertEqual(adjustment.get_value(), before)

    def test_control_shortcuts_and_text_fields_keep_native_editing(self):
        from types import SimpleNamespace
        from gi.repository import Gdk

        for key, method in (
            (Gdk.KEY_c, "copy_selection"),
            (Gdk.KEY_v, "paste_selection"),
            (Gdk.KEY_s, "save"),
            (Gdk.KEY_z, "undo"),
            (Gdk.KEY_y, "redo"),
        ):
            with patch.object(self.window, method) as action:
                self.assertTrue(
                    self.window.tree_key(
                        self.window.tree,
                        SimpleNamespace(
                            keyval=key, state=Gdk.ModifierType.CONTROL_MASK
                        ),
                    )
                )
                action.assert_called_once()
        field = Gtk.Entry()
        with patch.object(self.window, "get_focus", return_value=field), patch.object(
            self.window, "copy_selection"
        ) as copy:
            self.assertFalse(
                self.window.window_key(
                    self.window,
                    SimpleNamespace(
                        keyval=Gdk.KEY_c, state=Gdk.ModifierType.CONTROL_MASK
                    ),
                )
            )
            copy.assert_not_called()
        field.destroy()

    @unittest.skipUnless(
        os.environ.get("JWM_REAL_TESTS") == "1",
        "Set JWM_REAL_TESTS=1 for real X11 input",
    )
    def test_real_mouse_drag_moves_all_selected_entries_in_order(self):
        root = self.window.document.roots()[0]
        first = root.children[1]
        second = self.window.document.add(root, "Program", {"label": "Second"}, "false")
        self.window.refresh()
        self.select_many([first, second])
        self.real_mouse_drag("0:1", "0:0")
        self.assertEqual(root.children[0].children, [first, second])
        self.assertEqual(self.window.selected_nodes(), [first, second])

    @unittest.skipUnless(
        os.environ.get("JWM_REAL_TESTS") == "1",
        "Set JWM_REAL_TESTS=1 for real X11 input",
    )
    def test_real_mouse_drag_at_edge_scrolls_and_stops_after_drop(self):
        root = self.window.document.roots()[0]
        for i in range(100):
            self.window.document.add(root, "Program", {"label": f"Scroll {i}"}, "true")
        self.window.refresh()
        self.pump()
        self.assertGreater(self.real_mouse_drag("0:1", "0:0", edge=True), 30)
        self.assertEqual(self.window.drag_scroll_id, 0)

    def test_undo_cut_paste_across_sources_after_saving_restores_both_files(self):
        included = Path(self.temp.name) / "undo-target"
        included.write_text('<JWM><Menu label="Target"/></JWM>')
        root = self.window.document.roots()[0]
        self.window.document.update(root.children[2], {}, str(included))
        self.window.save()
        root = self.window.document.roots()[0]
        self.select(root.children[1])
        self.window.copy_selection(cut=True)
        self.select(next(n for n in self.window.origins if n.kind == "Menu"))
        self.window.paste_selection()
        self.assertTrue(self.window.save())
        self.assertNotIn("xterm", self.path.read_text())
        self.assertIn("xterm", included.read_text())
        self.window.undo()
        self.assertEqual(len(self.window.dirty_documents()), 2)
        self.assertTrue(self.window.save())
        self.assertIn("xterm", self.path.read_text())
        self.assertNotIn("xterm", included.read_text())
