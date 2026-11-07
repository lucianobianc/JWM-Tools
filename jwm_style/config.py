"""Read effective JWM configuration; patch only explicitly selected XML bytes.

Static includes are read for preview, never executed or written. When a property
exists only in an include, append an explicit override to the opened jwmrc.
Ambiguous duplicate blocks are rejected instead of guessing a write target.
"""

import os
import re
import stat
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from .themes import STYLES

# Ignore XML constructs that may contain tag-shaped text, preserving offsets.
SPECIAL = re.compile(r"<!--.*?-->|<!\[CDATA\[.*?\]\]>|<\?.*?\?>", re.S)
TAG = re.compile(
    r"<(/?)([A-Za-z_][\w:.-]*)(?:\s+(?:[^<>\'\"]|\"[^\"]*\"|\'[^\']*\')*?)?\s*(/?)>",
    re.S,
)
COMMENT = re.compile(r"<!--.*?-->", re.S)


def masked(text):
    return SPECIAL.sub(lambda m: re.sub(r"[^\r\n]", " ", m.group()), text)


def find_elements(text, name, start=0, end=None):
    stack, found = [], []
    for m in TAG.finditer(masked(text), start, len(text) if end is None else end):
        closing, tag, selfclosing = m.groups()
        if closing:
            if not stack or stack[-1][0] != tag:
                raise ValueError("Malformed XML around " + tag)
            _, begin, open_end, depth = stack.pop()
            if tag == name:
                found.append((begin, m.end(), open_end, m.start(), depth))
        elif selfclosing:
            if tag == name:
                found.append((m.start(), m.end(), m.end(), m.end(), len(stack)))
        else:
            stack.append((tag, m.start(), m.end(), len(stack)))
    if stack:
        raise ValueError("Unclosed XML element")
    return sorted(found)


def _direct(text, name):
    return [span for span in find_elements(text, name) if span[4] == 0]


def _append(text, span, tag, value):
    a, b, cs, ce, _ = span
    if text[a:cs].rstrip().endswith("/>"):
        opening = re.sub(r"/\s*>$", ">", text[a:cs])
        return (
            text[:a]
            + opening
            + f"<{tag}>{value}</{tag}></"
            + ET.fromstring(text[a:b]).tag
            + ">"
            + text[b:]
        )
    content = text[cs:ce]
    newline = "\r\n" if "\r\n" in text else "\n"
    existing = re.search(r"(?:\r?\n)([ \t]*)<", content)
    closing_indent = re.search(r"(?:^|\n)([ \t]*)$", text[:ce])
    parent_indent = re.search(r"(?:^|\n)([ \t]*)$", text[:a])
    indent = (
        existing.group(1)
        if existing
        else (parent_indent.group(1) if parent_indent else "") + "    "
    )
    if closing_indent and "\n" in content:
        pos = ce - len(closing_indent.group(1))
        return text[:pos] + f"{indent}<{tag}>{value}</{tag}>" + newline + text[pos:]
    return text[:ce] + f"<{tag}>{value}</{tag}>" + text[ce:]


def replace_leaf(text, parent, child, value):
    spans = _direct(text, parent)
    if len(spans) != 1:
        raise ValueError(f"Expected exactly one {parent}, found {len(spans)}")
    span = spans[0]
    a, b, cs, ce, _ = span
    children = _direct(text[cs:ce], child)
    if len(children) > 1:
        raise ValueError(f"Multiple {child} elements inside {parent}")
    safe = escape(value)
    if not children:
        return _append(text, span, child, safe)
    ca, cb, ci, cj, _ = children[0]
    ca, cb, ci, cj = (v + cs for v in (ca, cb, ci, cj))
    if text[ca:ci].rstrip().endswith("/>"):
        opening = re.sub(r"/\s*>$", ">", text[ca:ci])
        return text[:ca] + opening + safe + f"</{child}>" + text[cb:]
    old = text[ci:cj]
    if "<" in COMMENT.sub("", old):
        raise ValueError(f"Cannot safely edit mixed content in {child}")
    matches = list(re.finditer(r"<!--.*?-->|[^<]+", old, re.S))
    visible = [
        m for m in matches if not m.group().startswith("<!--") and m.group().strip()
    ]
    if len(visible) > 1:
        raise ValueError(f"Cannot safely edit mixed content in {child}")
    if visible:
        m = visible[0]
        segment = m.group()
        replacement = (
            segment[: len(segment) - len(segment.lstrip())]
            + safe
            + segment[len(segment.rstrip()) :]
        )
        return text[: ci + m.start()] + replacement + text[ci + m.end() :]
    return text[:cj] + safe + text[cj:]


def update_style(text, section, property_path, value):
    if section not in STYLES or len(property_path) not in (1, 2):
        raise ValueError("Unknown style property")
    if not all(re.fullmatch(r"[A-Za-z_][\w.-]*", p) for p in property_path):
        raise ValueError("Invalid property name")
    root_span = _direct(text, "JWM")
    if len(root_span) != 1:
        raise ValueError("Expected a JWM root")
    ra, rb, rs, re_, _ = root_span[0]
    sections = _direct(text[rs:re_], section)
    if not sections:
        leaf = value
        for tag in reversed(property_path):
            leaf = (
                f"<{tag}>{escape(leaf) if tag == property_path[-1] else leaf}</{tag}>"
            )
        return _append(text, root_span[0], section, leaf)
    if len(sections) != 1:
        raise ValueError(
            f"Multiple {section} blocks; open a configuration with one unambiguous block to edit."
        )
    a, b, cs, ce, _ = (v + rs if i < 4 else v for i, v in enumerate(sections[0]))
    part = text[a:b]
    if len(property_path) == 1:
        new = replace_leaf(part, section, property_path[0], value)
    else:
        group, leaf = property_path
        local = _direct(part, section)[0]
        groups = _direct(part[local[2] : local[3]], group)
        if not groups:
            new = _append(part, local, group, f"<{leaf}>{escape(value)}</{leaf}>")
        elif len(groups) != 1:
            raise ValueError(f"Multiple {group} elements inside {section}")
        else:
            ga, gb, _, _, _ = groups[0]
            ga += local[2]
            gb += local[2]
            new = part[:ga] + replace_leaf(part[ga:gb], group, leaf, value) + part[gb:]
    return text[:a] + new + text[b:]


def property_values(text):
    result = {}
    for node in ET.fromstring(text):
        if node.tag not in STYLES:
            continue
        values = result.setdefault(node.tag, {})
        for child in node:
            if child.tag in ("Active", "Minimized"):
                values.setdefault(child.tag, {}).update(
                    {sub.tag: (sub.text or "").strip() for sub in child if not len(sub)}
                )
            elif not len(child):
                values[child.tag] = (child.text or "").strip()
    return result


def flatten(values):
    result = {}
    for section, fields in values.items():
        if section not in STYLES or not isinstance(fields, dict):
            continue
        for key, value in fields.items():
            if isinstance(value, dict):
                for subkey, subval in value.items():
                    if isinstance(subval, str):
                        result[(section, (key, subkey))] = subval
            elif isinstance(value, str):
                result[(section, (key,))] = value
    return result


def set_nested(values, section, path, value):
    target = values.setdefault(section, {})
    if len(path) == 1:
        target[path[0]] = value
    else:
        target.setdefault(path[0], {})[path[1]] = value


def get_value(text, section, path):
    return flatten(property_values(text)).get((section, path))


def save_atomic(path, data):
    path = Path(path)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    fd, tempname = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(tempname, mode)
        os.replace(tempname, path)
    finally:
        if os.path.exists(tempname):
            os.unlink(tempname)


def start_button(text):
    candidates = [
        s[:4]
        for s in find_elements(text, "TrayButton")
        if re.fullmatch(r"\s*root:\d+\s*", masked(text)[s[2] : s[3]])
    ]
    if len(candidates) > 1:
        raise ValueError("Multiple root-menu TrayButtons: cannot choose one safely.")
    return candidates[0] if candidates else None


def start_attributes(text):
    span = start_button(text)
    if span is None:
        return None
    return dict(ET.fromstring(text[span[0] : span[1]]).attrib)


def update_start_attribute(text, key, value):
    if key not in ("label", "icon", "tooltip"):
        raise ValueError("Unknown TrayButton attribute")
    span = start_button(text)
    if not span:
        raise ValueError("No root-menu TrayButton found.")
    a, b, cs, ce = span
    opening = text[a:cs]
    match = re.search(r"(?<![\w-])" + key + r"\s*=\s*([\"\'])(.*?)\1", opening, re.S)
    safe = escape(value, {'"': "&quot;", "'": "&apos;"})
    if match:
        opening = opening[: match.start(2)] + safe + opening[match.end(2) :]
    else:
        opening = opening[:-1] + f' {key}="{safe}">'
    return text[:a] + opening + text[cs:]


class Configuration:
    """Ordered static include reader. Dynamic includes are never executed.

    Relative filenames use the process working directory, just like JWM's
    TokenizeFile/ExpandPath. Callers can supply a working directory explicitly.
    """

    def __init__(self, path, text=None, cwd=None):
        self.path = Path(path).expanduser().resolve()
        self.cwd = Path(cwd or Path.cwd())
        self.snapshots = {}
        self.nodes = []
        self.warnings = []
        self._read(self.path, text, [])

    def _read(self, path, override, stack):
        if path in stack or len(stack) >= 16:
            self.warnings.append(f"Include cycle/depth limit: {path}")
            return
        self.snapshots.setdefault(path, None)
        try:
            data = path.read_bytes()
            self.snapshots[path] = data
            root = ET.fromstring(
                override if override is not None else data.decode("utf-8")
            )
            if root.tag != "JWM":
                raise ValueError("Expected JWM root")
        except (OSError, ValueError, ET.ParseError) as exc:
            if not stack:
                raise
            self.warnings.append(f"Cannot read include {path}: {exc}")
            return
        for node in root:
            if node.tag == "Include":
                name = (node.text or "").strip()
                if name.startswith("exec:"):
                    self.warnings.append(
                        "Dynamic Include not executed; preview may be incomplete."
                    )
                elif name:
                    include = Path(os.path.expandvars(os.path.expanduser(name)))
                    self._read((self.cwd / include).resolve(), None, stack + [path])
            else:
                self.nodes.append((node, path))

    def values(self):
        values = {}
        for node, _ in self.nodes:
            if node.tag in STYLES:
                root = ET.Element("JWM")
                root.append(node)
                for (section, key), value in flatten(
                    property_values(ET.tostring(root, encoding="unicode"))
                ).items():
                    set_nested(values, section, key, value)
        return values

    def unchanged(self):
        for path, data in self.snapshots.items():
            try:
                current = path.read_bytes()
            except FileNotFoundError:
                current = None
            if current != data:
                return False
        return True

    def commit(self, pending, start_pending):
        if not self.unchanged():
            raise ValueError(
                "The configuration or an Include changed on disk. Reopen the editor to avoid overwriting it."
            )
        text = self.snapshots[self.path].decode("utf-8")
        # If an included file later overrides a local section, reject rather than
        # save a value that JWM would silently ignore.
        for section, key in pending:
            sources = [
                source
                for node, source in self.nodes
                if node.tag == section
                and flatten(
                    property_values(
                        "<JWM>" + ET.tostring(node, encoding="unicode") + "</JWM>"
                    )
                ).get((section, key))
                is not None
            ]
            if (
                sources
                and sources[-1] != self.path
                and ET.fromstring(text).find(section) is not None
            ):
                raise ValueError(
                    f"{section} is overridden by Include {sources[-1]}; open that file explicitly to edit it."
                )
        for (section, key), value in sorted(pending.items()):
            if key[-1] in ("Width", "Height", "Corner"):
                limits = {"Width": (1, 128), "Height": (0, 256), "Corner": (0, 128)}
                low, high = limits[key[-1]]
                if not value.isdecimal() or not low <= int(value) <= high:
                    raise ValueError(
                        f"{key[-1]} must be an integer from {low} to {high}."
                    )
            elif key[-1] == "Opacity":
                try:
                    valid = 0 <= float(value) <= 1
                except ValueError:
                    valid = False
                if not valid:
                    raise ValueError("Opacity must be a number from 0 to 1.")
            text = update_style(text, section, key, value)
        for key, value in start_pending.items():
            text = update_start_attribute(text, key, value)
        ET.fromstring(text)
        if text.encode("utf-8") != self.snapshots[self.path]:
            if not self.unchanged():
                raise ValueError("Configuration changed while preparing save.")
            save_atomic(
                self.path.with_name(self.path.name + ".bak"), self.snapshots[self.path]
            )
            save_atomic(self.path, text.encode("utf-8"))
        return text
