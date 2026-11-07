"""Edit a menu tree while retaining unrelated XML and unknown elements."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
import os
import xml.etree.ElementTree as ET
from ..style.config import TAG, masked, find_elements, save_atomic
from ..xmlutil import patch_node, append_nodes

CONTAINERS = {"JWM", "RootMenu", "Menu"}
KINDS = (
    "Program",
    "Menu",
    "Separator",
    "Include",
    "Dynamic",
    "Restart",
    "Exit",
    "Desktops",
    "SendTo",
    "Stick",
    "Maximize",
    "Minimize",
    "Shade",
    "Move",
    "Resize",
    "Kill",
    "Close",
)
TEXT_KINDS = {"Program", "Include", "Dynamic", "Exit"}


@dataclass(eq=False)
class Node:
    kind: str
    attrs: dict = field(default_factory=dict)
    value: str = ""
    children: list = field(default_factory=list)
    parent: object = None
    span: tuple | None = None
    original_attrs: dict = field(default_factory=dict)
    original_value: str = ""
    original_children: list = field(default_factory=list)

    @property
    def label(self):
        return self.attrs.get("label") or self.value or self.kind

    @property
    def editable(self):
        return self.kind in (*KINDS, "RootMenu") and (
            self.kind in CONTAINERS or not self.children
        )


class MenuDocument:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        self.original = self.path.read_bytes() if self.path.exists() else None
        self.text = (
            self.original.decode("utf-8")
            if self.original is not None
            else "<JWM>\n</JWM>\n"
        )
        element = ET.fromstring(self.text)
        if element.tag != "JWM":
            raise ValueError("Expected a JWM root element.")
        names = {
            match.group(2)
            for match in TAG.finditer(masked(self.text))
            if not match.group(1)
        }
        spans = {name: iter(find_elements(self.text, name)) for name in names}

        def build(elem, parent=None):
            node = Node(
                elem.tag,
                dict(elem.attrib),
                (elem.text or "").strip(),
                parent=parent,
                span=next(spans[elem.tag]),
            )
            node.original_attrs = dict(node.attrs)
            node.original_value = node.value
            node.children = [build(child, node) for child in elem]
            node.original_children = list(node.children)
            return node

        self.root = build(element)

    def roots(self):
        rootmenus = [node for node in self.root.children if node.kind == "RootMenu"]
        if rootmenus:
            return [
                node
                for node in self.root.children
                if node.kind in ("RootMenu", "Include")
            ]
        return [node for node in self.root.children if node.kind in KINDS]

    def require_container(self, parent, kind):
        if parent.kind not in CONTAINERS:
            raise ValueError("Select a menu to hold this entry.")
        if kind == "RootMenu" and parent is not self.root:
            raise ValueError("Root menus belong directly under JWM.")
        if (
            parent is self.root
            and any(n.kind == "RootMenu" for n in parent.children)
            and kind != "RootMenu"
        ):
            raise ValueError("Select a root menu or submenu first.")

    def validate(self, kind, attrs, value, previous=None):
        try:
            ET.fromstring(ET.tostring(ET.Element(kind, attrs), encoding="unicode"))
            value_element = ET.Element("Value")
            value_element.text = value
            ET.fromstring(ET.tostring(value_element, encoding="unicode"))
        except ET.ParseError as exc:
            raise ValueError("The entry contains invalid XML characters.") from exc
        if kind not in (*KINDS, "RootMenu"):
            raise ValueError("This element is preserved but cannot be edited.")
        if (
            kind in ("Program", "Menu")
            and not attrs.get("label", "").strip()
            and (previous is None or previous.attrs.get("label", "").strip())
        ):
            raise ValueError("Enter a label.")
        if kind in ("Program", "Include", "Dynamic") and not value.strip():
            raise ValueError("Enter a command or Include path.")
        if (
            "\x00" in value
            or ("\n" in value or "\r" in value)
            and (previous is None or previous.value != value)
        ):
            raise ValueError("Enter the command or path on a single line.")
        if kind in ("Program", "Dynamic") and value.startswith("exec:"):
            raise ValueError("Enter the command without the exec: prefix.")

    def add(self, parent, kind, attrs=None, value="", after=None):
        attrs = dict(attrs or {})
        self.require_container(parent, kind)
        self.validate(kind, attrs, value)
        node = Node(kind, attrs, value, parent=parent)
        index = parent.children.index(after) + 1 if after else len(parent.children)
        parent.children.insert(index, node)
        return node

    def update(self, node, attrs, value):
        if not node.editable:
            raise ValueError("This element is preserved but cannot be edited.")
        self.validate(node.kind, attrs, value, node)
        old_attrs, old_value = node.attrs, node.value
        node.attrs, node.value = dict(attrs), value
        try:
            ET.fromstring(self.render(node))
        except (ValueError, ET.ParseError):
            node.attrs, node.value = old_attrs, old_value
            raise

    def remove(self, node):
        if not node.editable:
            raise ValueError("This element is preserved but cannot be deleted.")
        node.parent.children.remove(node)

    def move(self, node, step):
        if step not in (-1, 1):
            raise ValueError("Direction must be -1 or 1.")
        siblings = node.parent.children
        index = siblings.index(node)
        target = index + step
        if not 0 <= target < len(siblings):
            return False
        # Do not exchange menu roots with unrelated configuration sections.
        if node.parent is self.root and siblings[target] not in self.roots():
            return False
        siblings[index], siblings[target] = siblings[target], siblings[index]
        return True

    def indent(self, node):
        siblings = node.parent.children
        index = siblings.index(node)
        if index == 0 or siblings[index - 1].kind != "Menu" or node.kind == "RootMenu":
            return False
        parent = siblings[index - 1]
        siblings.remove(node)
        parent.children.append(node)
        node.parent = parent
        return True

    def outdent(self, node):
        parent = node.parent
        if parent.kind != "Menu" or parent.parent is None:
            return False
        grandparent = parent.parent
        self.require_container(grandparent, node.kind)
        parent.children.remove(node)
        grandparent.children.insert(grandparent.children.index(parent) + 1, node)
        node.parent = grandparent
        return True

    def render(self, node):
        if node.span is None:
            elem = ET.Element(node.kind, node.attrs)
            elem.text = node.value or None
            raw = ET.tostring(elem, encoding="unicode", short_empty_elements=True)
            if node.children:
                raw = self.append(
                    raw, node.kind, [self.render(child) for child in node.children]
                )
            return raw
        a, b, cs, ce, _ = node.span
        raw = self.text[a:b]
        if node.kind in CONTAINERS:
            rendered = [self.render(child) for child in node.children]
            edits = []
            for child in node.original_children:
                edits.append(
                    (
                        child.span[0] - a,
                        child.span[1] - a,
                        rendered.pop(0) if rendered else "",
                    )
                )
            for start, end, value in reversed(edits):
                raw = raw[:start] + value + raw[end:]
            if rendered:
                raw = self.append(raw, node.kind, rendered)
        if node.attrs != node.original_attrs or node.value != node.original_value:
            span = find_elements(raw, node.kind)[0]
            original = SimpleNamespace(
                span=span, attrs=node.original_attrs, action=node.original_value
            )
            changed = SimpleNamespace(
                kind=node.kind, attrs=node.attrs, action=node.value
            )
            raw = patch_node(raw, changed, original)
        return raw

    @staticmethod
    def append(raw, kind, nodes):
        if kind == "JWM":
            return append_nodes(raw, nodes)
        # Reuse the whitespace-preserving append helper without changing nested tags.
        span = find_elements(raw, kind)[0]
        a, b, cs, ce, _ = span
        opening = raw[a:cs]
        if opening.endswith("/>"):
            return opening[:-2] + ">" + "".join(nodes) + "</" + kind + ">"
        newline = "\r\n" if "\r\n" in raw else "\n"
        import re

        whitespace = re.search(r"\r?\n([ \t]*)$", raw[cs:ce])
        if whitespace:
            indent = whitespace.group(1)
            pos = cs + whitespace.start()
            return (
                raw[:pos]
                + "".join(newline + indent + "    " + n for n in nodes)
                + raw[pos:]
            )
        return raw[:ce] + "".join(nodes) + raw[ce:]

    def preview(self):
        a, b = self.root.span[:2]
        text = self.text[:a] + self.render(self.root) + self.text[b:]
        ET.fromstring(text)
        return text

    @property
    def dirty(self):
        return self.preview() != self.text

    def include_path(self, node):
        if node.kind != "Include" or not node.value or node.value.startswith("exec:"):
            return None
        return Path(os.path.expandvars(os.path.expanduser(node.value))).resolve()

    def save(self):
        current = self.path.read_bytes() if self.path.exists() else None
        if current != self.original:
            raise ValueError("The file changed on disk. Reload before saving.")
        data = self.preview().encode("utf-8")
        if data != self.original:
            if self.original is not None:
                save_atomic(self.path.with_name(self.path.name + ".bak"), self.original)
            save_atomic(self.path, data)
        self.__init__(self.path)
