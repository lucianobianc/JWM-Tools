from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch
from jwm_tools.keys.model import (
    BindingDocument,
    Binding,
    validate,
    normalize_mask,
    mouse_label,
)


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.path = self.base / "jwmrc"
        self.text = """<?xml version="1.0"?>\r
<JWM>\r
  <!-- <Key key="F1">ignored</Key> -->\r
  <Key mask = 'A' key="F4" extra="a &amp; b">  close <!--keep--> </Key>\r
  <Mouse context="title" button="11">maximize</Mouse>\r
  <WindowStyle><Font>Sans-12</Font></WindowStyle>\r
  <Tray><TrayButton><Button mask="1">exec:keep</Button></TrayButton></Tray>\r
</JWM>"""
        self.path.write_bytes(self.text.encode())
        self.doc = BindingDocument(self.path)

    def test_reads_only_actual_top_level_bindings(self):
        self.assertEqual(
            [(b.kind, b.action) for b in self.doc.entries()],
            [("Key", "close"), ("Mouse", "maximize")],
        )
        self.assertFalse(self.doc.dirty)
        self.doc.save()
        self.assertEqual(self.path.read_bytes(), self.text.encode())
        self.assertFalse(self.path.with_name("jwmrc.bak").exists())

    def test_changes_only_selected_attribute(self):
        b = self.doc.entries()[0]
        attrs = dict(b.attrs, key="F3")
        self.doc.update(b.token, attrs, b.action)
        self.assertEqual(self.doc.preview(), self.text.replace('key="F4"', 'key="F3"'))
        self.doc.save()
        self.assertEqual(
            self.path.with_name("jwmrc.bak").read_bytes(), self.text.encode()
        )
        self.assertFalse(self.doc.dirty)

    def test_action_escapes_xml_without_changing_comments(self):
        b = self.doc.entries()[0]
        self.doc.update(b.token, b.attrs, 'exec:printf "a & b"')
        expected = self.text.replace(
            "  close <!--keep-->", '  exec:printf "a &amp; b" <!--keep-->'
        )
        self.assertEqual(self.doc.preview(), expected)
        self.assertEqual(
            ET.fromstring(expected).findtext("Key").strip(), 'exec:printf "a & b"'
        )

    def test_multiple_edits_and_deletion_keep_offsets_and_unrelated_xml(self):
        key, mouse = self.doc.entries()
        self.doc.update(key.token, dict(key.attrs, key="F2"), key.action)
        self.doc.remove(mouse.token)
        expected = self.text.replace('key="F4"', 'key="F2"').replace(
            '<Mouse context="title" button="11">maximize</Mouse>', ""
        )
        self.assertEqual(self.doc.preview(), expected)

    def test_adds_both_types_with_crlf_and_no_fake_xml_entities(self):
        self.doc.add("Key", {"mask": "C4", "key": "Return"}, "exec:xterm")
        self.doc.add("Mouse", {"context": "root", "button": "-3"}, "root:1")
        text = self.doc.preview()
        self.assertIn('\r\n  <Key mask="C4" key="Return">exec:xterm</Key>\r\n', text)
        root = ET.fromstring(text)
        self.assertEqual(root.findall("Mouse")[-1].get("button"), "-3")
        self.assertIn("<WindowStyle><Font>Sans-12</Font></WindowStyle>", text)

    def test_self_closing_root_and_binding_can_be_expanded(self):
        for text in ("<JWM/>", '<JWM><Key key="a"/></JWM>'):
            self.path.write_text(text)
            doc = BindingDocument(self.path)
            if doc.entries():
                doc.update(doc.entries()[0].token, {"key": "a"}, "exec:true")
            else:
                doc.add("Key", {"key": "a"}, "exec:true")
            self.assertEqual(ET.fromstring(doc.preview()).findtext("Key"), "exec:true")

    def test_changing_key_identifier_removes_only_old_attribute(self):
        b = self.doc.entries()[0]
        attrs = dict(b.attrs, keycode="38")
        attrs.pop("key")
        self.doc.update(b.token, attrs, b.action)
        root = ET.fromstring(self.doc.preview())
        self.assertIsNone(root.find("Key").get("key"))
        self.assertEqual(root.find("Key").get("keycode"), "38")
        self.assertEqual(root.find("Key").get("extra"), "a & b")

    def test_restore_original_or_remove_new_binding_clears_dirty_state(self):
        b = self.doc.entries()[0]
        self.doc.update(b.token, dict(b.attrs, key="F1"), b.action)
        self.doc.update(b.token, b.attrs, b.action)
        self.assertFalse(self.doc.dirty)
        new = self.doc.add("Mouse", {"context": "root", "button": "1"}, "none")
        self.doc.remove(new.token)
        self.assertFalse(self.doc.dirty)

    def test_external_changes_abort_without_replacing_user_data(self):
        b = self.doc.entries()[0]
        self.doc.remove(b.token)
        self.path.write_text("<JWM><!--external--></JWM>")
        with self.assertRaises(ValueError):
            self.doc.save()
        self.assertEqual(self.path.read_text(), "<JWM><!--external--></JWM>")
        self.assertFalse(self.path.with_name("jwmrc.bak").exists())

    def test_save_failure_keeps_original_and_pending_changes(self):
        self.doc.add("Key", {"key": "F9"}, "exec:true")
        with patch(
            "jwm_tools.keys.model.save_atomic", side_effect=OSError("disk full")
        ):
            with self.assertRaises(OSError):
                self.doc.save()
        self.assertEqual(self.path.read_bytes(), self.text.encode())
        self.assertTrue(self.doc.dirty)

    def test_symlink_target_is_updated_without_replacing_link(self):
        link = self.base / "linked"
        link.symlink_to(self.path)
        doc = BindingDocument(link)
        doc.add("Key", {"key": "F9"}, "exec:true")
        doc.save()
        self.assertTrue(link.is_symlink())
        self.assertIn("F9", self.path.read_text())

    def test_static_includes_read_only_and_dynamic_includes_not_executed(self):
        include = self.base / "keys"
        include.write_text('<JWM><Key key="F9">exec:true</Key></JWM>')
        marker = self.base / "executed"
        self.path.write_text(
            f"<JWM><Include>{include}</Include><Include>exec:touch {marker}</Include></JWM>"
        )
        doc = BindingDocument(self.path)
        self.assertEqual(len(doc.entries()), 1)
        binding = doc.entries()[0]
        self.assertFalse(binding.editable)
        self.assertTrue(doc.config.warnings)
        with self.assertRaises(ValueError):
            doc.update(binding.token, binding.attrs, "none")
        with self.assertRaises(ValueError):
            doc.remove(binding.token)
        self.assertFalse(marker.exists())
        doc.add("Mouse", {"context": "root", "button": "4"}, "ldesktop")
        before = include.read_bytes()
        doc.save()
        self.assertEqual(include.read_bytes(), before)

    def test_external_include_change_aborts_local_save(self):
        include = self.base / "keys"
        include.write_text("<JWM/>")
        self.path.write_text(f"<JWM><Include>{include}</Include></JWM>")
        doc = BindingDocument(self.path)
        doc.add("Key", {"key": "F9"}, "exec:true")
        include.write_text("<JWM><!--changed--></JWM>")
        with self.assertRaises(ValueError):
            doc.save()

    def test_cdata_is_preserved_for_attribute_edits_but_not_rewritten(self):
        self.path.write_text(
            '<JWM><Key key="F9"><![CDATA[exec:echo a < b]]></Key></JWM>'
        )
        doc = BindingDocument(self.path)
        b = doc.entries()[0]
        doc.update(b.token, {"key": "F8"}, b.action)
        self.assertIn("<![CDATA[exec:echo a < b]]>", doc.preview())
        doc.update(b.token, {"key": "F8"}, "exec:changed")
        with self.assertRaises(ValueError):
            doc.preview()

    def test_modifier_aliases_and_template_conflicts(self):
        b = self.doc.entries()[0]
        candidate = Binding("", "Key", {"mask": "1", "key": "F4"}, "none", self.path)
        self.assertEqual(self.doc.conflicts(candidate)[0].token, b.token)
        self.doc.add("Key", {"mask": "C", "key": "#"}, "desktop#")
        digit = self.doc.add("Key", {"mask": "C", "key": "5"}, "none")
        self.assertIn(digit.token, self.doc.conflicts())

    def test_mouse_conflicts_respect_context_and_event(self):
        a = self.doc.add("Mouse", {"context": "root", "button": "1"}, "none")
        b = self.doc.add("Mouse", {"context": "title", "button": "1"}, "move")
        self.assertFalse(self.doc.conflicts())
        duplicate = Binding(
            "", "Mouse", {"context": "root", "button": "01"}, "none", self.path
        )
        self.assertEqual(
            [item.token for item in self.doc.conflicts(duplicate)], [a.token]
        )
        self.assertNotEqual(a.signatures(), b.signatures())

    def test_button_labels_follow_jwm_double_click_multiplier(self):
        self.assertEqual(mouse_label("11"), "Duplo esquerdo")
        self.assertEqual(mouse_label("22"), "Duplo central")
        self.assertEqual(mouse_label("33"), "Duplo direito")
        self.assertEqual(mouse_label("-1"), "Soltar esquerdo")

    def test_validation_rejects_invalid_shortcuts_and_actions(self):
        cases = [
            ("Key", {"key": "not_a_real_X11_keysym"}, "none"),
            ("Key", {"key": "F4", "mask": "M"}, "none"),
            ("Key", {"keycode": "0"}, "none"),
            ("Key", {"key": "F1", "keycode": "67"}, "none"),
            ("Key", {"key": "#"}, "exec:true"),
            ("Key", {"key": "F1"}, "exec:"),
            ("Key", {"key": "F1"}, "invented-action"),
            ("Mouse", {"context": "client", "button": "1"}, "none"),
            ("Mouse", {"context": "root", "button": "0"}, "none"),
            ("Mouse", {"context": "root", "button": "-256"}, "none"),
        ]
        for kind, attrs, action in cases:
            with self.subTest(attrs=attrs, action=action), self.assertRaises(
                ValueError
            ):
                validate(Binding("", kind, attrs, action, self.path))
        self.assertEqual(normalize_mask("1SCACA4"), "CSA4")
