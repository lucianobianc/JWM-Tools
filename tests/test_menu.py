from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from jwm_tools.menu.model import MenuDocument


class MenuTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "jwmrc"

    def document(
        self,
        xml='<JWM><RootMenu onroot="12"><Program label="One">one</Program><Menu label="Tools"><Program label="Two">two</Program></Menu><Separator/><Restart label="Restart"/></RootMenu><Key key="F1">close</Key></JWM>',
    ):
        self.path.write_bytes(xml.encode())
        return MenuDocument(self.path)

    def test_unmodified_roundtrip_and_roots(self):
        doc = self.document()
        self.assertEqual([n.kind for n in doc.roots()], ["RootMenu"])
        self.assertEqual(doc.preview().encode(), self.path.read_bytes())
        self.assertFalse(doc.dirty)

    def test_edit_preserves_quotes_comments_crlf_and_other_config(self):
        xml = "<JWM>\r\n<!--á--><RootMenu onroot='12'><Program label='Old' extra=\"keep\"> old <!--keep--></Program></RootMenu>\r\n<Key key=\"F1\">close</Key></JWM>"
        doc = self.document(xml)
        node = doc.roots()[0].children[0]
        doc.update(
            node,
            {**node.attrs, "label": "New", "icon": "/path/a & b.png"},
            "new && true",
        )
        expected = (
            xml.replace("label='Old'", "label='New'")
            .replace('extra="keep"', 'extra="keep" icon="/path/a &amp; b.png"')
            .replace(" old ", " new &amp;&amp; true ")
        )
        self.assertEqual(doc.preview(), expected)
        doc.save()
        self.assertEqual(self.path.read_bytes().decode(), expected)
        self.assertEqual(self.path.with_name("jwmrc.bak").read_bytes().decode(), xml)

    def test_move_indent_outdent_and_save(self):
        doc = self.document()
        root = doc.roots()[0]
        one, tools = root.children[:2]
        self.assertTrue(doc.move(one, 1))
        self.assertTrue(doc.indent(one))
        self.assertIs(one.parent, tools)
        self.assertTrue(doc.outdent(one))
        self.assertIs(one.parent, root)
        doc.save()
        root = doc.roots()[0]
        self.assertEqual(
            [n.kind for n in root.children], ["Menu", "Program", "Separator", "Restart"]
        )
        self.assertEqual(root.children[0].children[0].value, "two")

    def test_add_remove_nested_empty_and_fragment(self):
        doc = self.document("<JWM/>")
        menu = doc.add(doc.root, "Menu", {"label": "Tools"})
        program = doc.add(menu, "Program", {"label": "Terminal"}, "xterm")
        doc.add(menu, "Separator")
        doc.remove(program)
        doc.save()
        self.assertEqual(doc.roots()[0].children[0].kind, "Separator")
        self.assertFalse(doc.dirty)

    def test_unknown_elements_are_preserved_not_editable(self):
        xml = '<JWM><RootMenu><Future attr="v"><Nested/></Future><Program label="One">one</Program></RootMenu><Tray height="30"/></JWM>'
        doc = self.document(xml)
        root = doc.roots()[0]
        self.assertFalse(root.children[0].editable)
        with self.assertRaises(ValueError):
            doc.remove(root.children[0])
        doc.update(root.children[1], {"label": "Changed"}, "one")
        self.assertEqual(doc.preview(), xml.replace('label="One"', 'label="Changed"'))

    def test_add_root_and_guard_config_sections(self):
        doc = self.document('<JWM><Tray/><Key key="F1">close</Key></JWM>')
        root = doc.add(doc.root, "RootMenu", {"onroot": "12"})
        self.assertFalse(doc.move(root, -1))
        with self.assertRaises(ValueError):
            doc.add(doc.root, "Program", {"label": "Wrong place"}, "true")
        doc.add(root, "Program", {"label": "Right place"}, "true")
        self.assertIn("<Tray/>", doc.preview())

    def test_static_include_resolves_without_running_dynamic(self):
        marker = self.path.with_name("must-not-exist")
        doc = self.document(
            f'<JWM><RootMenu><Include>exec:touch {marker}</Include><Dynamic label="Dynamic">touch {marker}</Dynamic><Include>~/menu.xml</Include></RootMenu></JWM>'
        )
        a, _, b = doc.roots()[0].children
        self.assertIsNone(doc.include_path(a))
        self.assertEqual(doc.include_path(b), Path.home() / "menu.xml")
        self.assertFalse(marker.exists())
        self.assertFalse(doc.dirty)

    def test_external_change_blocks_save(self):
        doc = self.document()
        doc.remove(doc.roots()[0].children[0])
        self.path.write_text("<JWM><!--external--></JWM>")
        with self.assertRaises(ValueError):
            doc.save()
        self.assertIn("external", self.path.read_text())
        self.assertTrue(doc.dirty)

    def test_atomic_failure_preserves_original(self):
        doc = self.document()
        original = self.path.read_bytes()
        doc.remove(doc.roots()[0].children[0])
        with patch(
            "jwm_tools.menu.model.save_atomic", side_effect=OSError("disk full")
        ):
            with self.assertRaises(OSError):
                doc.save()
        self.assertEqual(self.path.read_bytes(), original)

    def test_symlink_and_new_file(self):
        doc = MenuDocument(self.path)
        self.assertFalse(self.path.exists())
        doc.add(doc.root, "Program", {"label": "One"}, "one")
        doc.save()
        link = self.path.with_name("link")
        link.symlink_to(self.path)
        doc = MenuDocument(link)
        doc.update(doc.roots()[0], {"label": "Changed"}, "two")
        doc.save()
        self.assertTrue(link.is_symlink())
        self.assertIn("Changed", self.path.read_text())

    def test_validation_and_failed_mixed_edit_leave_document_unchanged(self):
        doc = self.document(
            '<JWM><Program label="One"><![CDATA[one && true]]></Program></JWM>'
        )
        node = doc.roots()[0]
        with self.assertRaises(ValueError):
            doc.update(node, {"label": "Changed"}, "new")
        self.assertFalse(doc.dirty)
        for kind, attrs, value in [
            ("Program", {}, "one"),
            ("Include", {}, ""),
            ("Program", {"label": "One"}, "exec:one"),
            ("Program", {"label": "One"}, "\x01"),
        ]:
            with self.assertRaises(ValueError):
                doc.add(doc.root, kind, attrs, value)
        self.assertFalse(doc.dirty)

    def test_remove_menu_preserves_other_menu(self):
        doc = self.document(
            '<JWM><RootMenu onroot="1"><Menu label="One"><Program label="x">x</Program></Menu></RootMenu><RootMenu onroot="2"><Restart/></RootMenu></JWM>'
        )
        doc.remove(doc.roots()[0])
        self.assertEqual(
            ET.fromstring(doc.preview()).find("RootMenu").get("onroot"), "2"
        )

    def test_generator_backs_up_manual_edits_without_executing_programs(self):
        from jwm_tools.menu import generator

        apps = self.path.parent / "apps"
        apps.mkdir()
        marker = self.path.parent / "must-not-exist"
        (apps / "test.desktop").write_text(
            f"[Desktop Entry]\nType=Application\nName=Fixture\nExec=touch {marker}\nCategories=Utility;\n"
        )
        self.path.write_text("<JWM><!--manual--></JWM>")
        with patch.multiple(
            generator, HOME=self.path.parent, OUTPUT=self.path, SEARCH_PATHS=[apps]
        ):
            generator.main()
        self.assertEqual(
            self.path.with_name("jwmrc.bak").read_text(), "<JWM><!--manual--></JWM>"
        )
        self.assertEqual(ET.parse(self.path).find(".//Program").get("label"), "Fixture")
        self.assertFalse(marker.exists())

    def test_suite_launchers_are_generated_under_utilities(self):
        import shutil
        from jwm_tools import COMMANDS
        from jwm_tools.menu import generator

        apps = self.path.parent / "suite-apps"
        apps.mkdir()
        packaging = Path(__file__).resolve().parents[1] / "packaging"
        for desktop in packaging.glob("jwm_*.desktop"):
            shutil.copyfile(desktop, apps / desktop.name)
        with patch.multiple(generator, HOME=self.path.parent, SEARCH_PATHS=[apps]):
            tree, count = generator.generate_tree()
        utilities = tree.find("Menu[@label='Utilities']")
        self.assertIsNotNone(utilities)
        self.assertEqual(
            {p.get("label") for p in utilities.findall("Program")}, set(COMMANDS)
        )
        self.assertEqual(count, len(COMMANDS))
        menu = utilities.find("Program[@label='jwm_menu']")
        self.assertEqual(menu.text, "jwm_menu")

    def test_drag_across_documents_preserves_raw_xml_and_backups(self):
        from jwm_tools.menu.model import transfer_nodes, save_documents

        source = self.document(
            '<JWM><Menu label="One"><Program extra=\'keep\' label="Item"> old <!--note--></Program></Menu></JWM>'
        )
        destination_path = self.path.with_name("destination")
        destination_path.write_text('<JWM><Menu label="Two"/></JWM>')
        destination = MenuDocument(destination_path)
        original_source = self.path.read_bytes()
        original_destination = destination_path.read_bytes()
        node = source.roots()[0].children[0]
        transfer_nodes([node], destination.roots()[0], 0, destination)
        self.assertNotIn("<Program", source.preview())
        self.assertIn(
            "<Program extra='keep' label=\"Item\"> old <!--note--></Program>",
            destination.preview(),
        )
        save_documents([source, destination])
        self.assertNotIn("<Program", self.path.read_text())
        self.assertIn("<!--note-->", destination_path.read_text())
        self.assertEqual(self.path.with_name("jwmrc.bak").read_bytes(), original_source)
        self.assertEqual(
            destination_path.with_name("destination.bak").read_bytes(),
            original_destination,
        )

    def test_drag_rejects_cycle_before_mutating_tree(self):
        from jwm_tools.menu.model import transfer_nodes

        doc = self.document(
            '<JWM><Menu label="Parent"><Menu label="Child"/></Menu></JWM>'
        )
        parent = doc.roots()[0]
        child = parent.children[0]
        with self.assertRaises(ValueError):
            transfer_nodes([parent], child, 0, doc)
        self.assertFalse(doc.dirty)

    def test_multi_file_save_rolls_back_on_second_file_failure(self):
        from jwm_tools.menu import model

        first = self.document('<JWM><Program label="One">one</Program></JWM>')
        second_path = self.path.with_name("second")
        second_path.write_text('<JWM><Program label="Two">two</Program></JWM>')
        second = MenuDocument(second_path)
        originals = {d.path: d.path.read_bytes() for d in (first, second)}
        first.update(first.roots()[0], {"label": "Changed"}, "one")
        second.update(second.roots()[0], {"label": "Changed"}, "two")
        real_save = model.save_atomic

        def fail(path, data):
            if path == second_path:
                raise OSError("disk full")
            return real_save(path, data)

        with patch("jwm_tools.menu.model.save_atomic", side_effect=fail):
            with self.assertRaises(OSError):
                model.save_documents([first, second])
        for path, data in originals.items():
            self.assertEqual(path.read_bytes(), data)
        self.assertTrue(first.dirty)
        self.assertTrue(second.dirty)
