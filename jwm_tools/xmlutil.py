"""Shared helpers for preserving edits to individual JWM XML nodes."""

import re
from xml.sax.saxutils import escape
from xml.parsers import expat
from .style.config import Configuration, find_elements, save_atomic

__all__ = [
    "Configuration",
    "find_elements",
    "save_atomic",
    "patch_node",
    "serialize",
    "append_nodes",
    "top_level_comments",
]
ATTR = re.compile(r"""\s+([A-Za-z_:][\w:.-]*)\s*=\s*(["'])(.*?)\2""", re.S)
CONTENT = re.compile(r"<!--.*?-->|[^<]+", re.S)


def patch_node(text, binding, original):
    a, b, cs, ce, _ = original.span
    opening = text[a:cs]
    edits = []
    seen = set()
    for match in ATTR.finditer(opening):
        name = match.group(1)
        seen.add(name)
        if name not in binding.attrs:
            edits.append((match.start(), match.end(), ""))
        elif binding.attrs[name] != original.attrs.get(name):
            edits.append(
                (
                    *match.span(3),
                    escape(binding.attrs[name], {'"': "&quot;", "'": "&apos;"}),
                )
            )
    for lo, hi, value in reversed(edits):
        opening = opening[:lo] + value + opening[hi:]
    extra = "".join(
        " " + name + '="' + escape(value, {'"': "&quot;"}) + '"'
        for name, value in binding.attrs.items()
        if name not in seen
    )
    pos = len(opening) - (2 if opening.endswith("/>") else 1)
    opening = opening[:pos] + extra + opening[pos:]
    if original.action == binding.action:
        return opening + text[cs:b]
    safe = escape(binding.action)
    if opening.endswith("/>"):
        return opening[:-2] + ">" + safe + "</" + binding.kind + ">"
    inner = text[cs:ce]
    if "<" in re.sub(r"<!--.*?-->", "", inner, flags=re.S):
        raise ValueError("Action contains mixed content. Edit it in the source file.")
    visible = [
        m
        for m in CONTENT.finditer(inner)
        if not m.group().startswith("<!--") and m.group().strip()
    ]
    if len(visible) > 1:
        raise ValueError("Action is split by comments; edit it in the source file.")
    if visible:
        m = visible[0]
        part = m.group()
        new = part[: len(part) - len(part.lstrip())] + safe + part[len(part.rstrip()) :]
        inner = inner[: m.start()] + new + inner[m.end() :]
    else:
        inner += safe
    return opening + inner + text[ce:b]


def serialize(binding):
    attrs = "".join(
        " " + key + '="' + escape(value, {'"': "&quot;"}) + '"'
        for key, value in binding.attrs.items()
    )
    return (
        "<"
        + binding.kind
        + attrs
        + ">"
        + escape(binding.action)
        + "</"
        + binding.kind
        + ">"
    )


def append_nodes(text, nodes):
    if not nodes:
        return text
    root = [s for s in find_elements(text, "JWM") if s[4] == 0][0]
    a, b, cs, ce, _ = root
    if text[a:cs].endswith("/>"):
        return text[: cs - 2] + ">" + "".join(nodes) + "</JWM>" + text[b:]
    content = text[cs:ce]
    newline = "\r\n" if "\r\n" in text else "\n"
    indent = re.search(r"\n([ \t]+)<", content)
    indent = indent.group(1) if indent else "    "
    trailing = re.search(r"\r?\n[ \t]*$", content)
    if trailing:
        pos = cs + trailing.start()
        return (
            text[:pos] + "".join(newline + indent + node for node in nodes) + text[pos:]
        )
    return text[:ce] + "".join(nodes) + text[ce:]


def top_level_comments(text):
    """Return direct JWM comment spans; ignore nested comments and CDATA."""
    parser = expat.ParserCreate()
    raw = text.encode("utf-8")
    depth = 0
    result = []

    def start(_name, _attrs):
        nonlocal depth
        depth += 1

    def end(_name):
        nonlocal depth
        depth -= 1

    def comment(value):
        if depth != 1:
            return
        begin = len(raw[: parser.CurrentByteIndex].decode("utf-8"))
        finish = text.find("-->", begin) + 3
        result.append((begin, finish, value))

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CommentHandler = comment
    parser.Parse(raw, True)
    return result
