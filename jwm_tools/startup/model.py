"""Preserve JWM lifecycle commands and reversible disabled entries."""

from __future__ import annotations
import base64
import binascii
from dataclasses import dataclass, replace
from pathlib import Path
import re
import shlex
import xml.etree.ElementTree as ET
from ..xmlutil import (
    Configuration,
    find_elements,
    save_atomic,
    patch_node,
    serialize,
    append_nodes,
    top_level_comments,
)

PHASES = {
    "StartupCommand": "Session startup",
    "RestartCommand": "JWM restart",
    "ShutdownCommand": "Shutdown",
}
HINTS = {
    "StartupCommand": "Runs when a new JWM session starts. Restarting the window manager does not run these commands again.",
    "RestartCommand": "Runs after restarting JWM. Applications that are already open are not closed automatically.",
    "ShutdownCommand": "Runs when JWM exits without restarting.",
}
MARKER = "jwm_startup:disabled "


@dataclass
class Command:
    token: str
    kind: str
    command: str
    source: Path
    attrs: dict
    enabled: bool = True
    editable: bool = True
    span: tuple | None = None
    xml: str = ""

    @property
    def action(self):
        return self.command


def validate(command, previous=None):
    if command.kind not in PHASES:
        raise ValueError("Choose when to run the command.")
    if not command.command.strip():
        raise ValueError("Enter a command.")
    if "\x00" in command.command:
        raise ValueError("The command contains an invalid character.")
    if previous is not None and previous.command == command.command:
        return
    if "\n" in command.command or "\r" in command.command:
        raise ValueError("Enter the command on a single line.")
    if command.command.startswith("exec:"):
        raise ValueError("Enter the command without the exec: prefix.")


def disabled_xml(xml):
    # Standard base64 has no hyphens, so even commands with --flags and inner
    # comments are safe inside XML comments and can be restored byte-for-byte.
    return (
        "<!-- "
        + MARKER
        + base64.b64encode(xml.encode("utf-8")).decode("ascii")
        + " -->"
    )


def read_commands(path, data, editable):
    text = data.decode("utf-8")
    root = ET.fromstring(text)
    if root.tag != "JWM":
        return [], []
    result = []
    warnings = []
    for kind in PHASES:
        for span in find_elements(text, kind):
            if span[4] != 1:
                continue
            xml = text[span[0] : span[1]]
            node = ET.fromstring(xml)
            result.append(
                Command(
                    "",
                    kind,
                    "".join(node.itertext()).strip(),
                    path,
                    dict(node.attrib),
                    True,
                    editable,
                    span,
                    xml,
                )
            )
    for a, b, content in top_level_comments(text):
        content = content.strip()
        payload = content
        if content.startswith(MARKER):
            try:
                payload = base64.b64decode(
                    content[len(MARKER) :], validate=True
                ).decode("utf-8")
            except (ValueError, UnicodeError, binascii.Error):
                warnings.append(
                    f"Unreadable disabled command in {path}. The comment has been preserved."
                )
                continue
        try:
            node = ET.fromstring(payload)
        except ET.ParseError:
            if content.startswith(MARKER):
                warnings.append(
                    f"Invalid disabled command in {path}. The comment has been preserved."
                )
            continue
        if node.tag not in PHASES:
            continue
        result.append(
            Command(
                "",
                node.tag,
                "".join(node.itertext()).strip(),
                path,
                dict(node.attrib),
                False,
                editable,
                (a, b, a, b, 1),
                payload,
            )
        )
    return sorted(result, key=lambda c: c.span[0]), warnings


def changed_xml(command, original):
    xml = original.xml
    span = find_elements(xml, original.kind)[0]
    old = replace(original, span=span)
    # Patch values before changing the tag name, preserving attributes/comments.
    updated = patch_node(xml, replace(command, kind=original.kind), old)
    if command.kind != original.kind:
        updated = re.sub(
            r"^<" + original.kind + r"(?=[\s/>])", "<" + command.kind, updated, count=1
        )
        updated = re.sub(
            r"</" + original.kind + r"(\s*>)$", r"</" + command.kind + r"\1", updated
        )
    return updated if command.enabled else disabled_xml(updated)


def desktop_command(line, name="", icon="", filename=""):
    """Convert a desktop Exec line to a shell command, without launching it."""
    try:
        args = shlex.split(line)
    except ValueError as exc:
        raise ValueError("Invalid application command: " + str(exc)) from exc
    result = []
    for arg in args:
        if arg == "%i":
            if icon:
                result.extend(["--icon", icon])
            continue

        def field(match):
            code = match.group(1)
            if code == "%":
                return "%"
            if code in "fFuU":
                return ""
            if code == "c":
                return name
            if code == "k":
                return filename
            raise ValueError("Unsupported application command field: %" + code)

        value = re.sub(r"%(.)", field, arg)
        if value:
            result.append(value)
    if not result:
        raise ValueError("The application has no launch command.")
    return shlex.join(result)


class StartupDocument:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        self.config = Configuration(self.path)
        self.original = self.config.snapshots[self.path]
        self.local, warnings = read_commands(self.path, self.original, True)
        self.warnings = list(self.config.warnings) + warnings
        for i, command in enumerate(self.local):
            command.token = "L" + str(i)
        self.included = []
        for path, data in self.config.snapshots.items():
            if path == self.path or data is None:
                continue
            try:
                entries, warnings = read_commands(path, data, False)
            except (ValueError, UnicodeError, ET.ParseError):
                continue
            self.warnings.extend(warnings)
            for command in entries:
                command.token = "I" + str(len(self.included))
                self.included.append(command)
        self.changes = {}
        self.additions = []
        self.next_id = 0
        self.order = [c.token for c in self.local]

    @property
    def reordered(self):
        baseline = [
            c.token for c in self.local if self.changes.get(c.token, c) is not None
        ]
        baseline += [c.token for c in self.additions]
        return self.order != baseline

    @property
    def dirty(self):
        return bool(self.changes or self.additions or self.reordered)

    def entries(self):
        current = {c.token: self.changes.get(c.token, c) for c in self.local}
        current.update({c.token: c for c in self.additions})
        return [current[token] for token in self.order] + self.included

    def move_target(self, token, direction):
        if direction not in (-1, 1):
            raise ValueError("Direction must be -1 or 1.")
        command = self.get(token)
        if not command.editable:
            return None
        index = self.order.index(token)
        target = index + direction
        while 0 <= target < len(self.order):
            other = self.get(self.order[target])
            if other.kind == command.kind:
                # Moving past an Include would also change the relationship to
                # commands owned by another file. Require opening that origin.
                slots = [
                    c.span[0]
                    for c in self.local
                    if self.changes.get(c.token, c) is not None
                ]
                slots += [len(self.original)] * len(self.additions)
                lo, hi = sorted((slots[index], slots[target]))
                text = self.original.decode("utf-8")
                if any(
                    lo < span[0] < hi
                    for span in find_elements(text, "Include")
                    if span[4] == 1
                ):
                    return None
                return target
            target += direction
        return None

    def move(self, token, direction):
        target = self.move_target(token, direction)
        if target is None:
            return False
        index = self.order.index(token)
        self.order[index], self.order[target] = self.order[target], self.order[index]
        return True

    def get(self, token):
        return next(c for c in self.entries() if c.token == token)

    def add(self, kind, command, enabled=True):
        item = Command("N" + str(self.next_id), kind, command, self.path, {}, enabled)
        validate(item)
        self.next_id += 1
        self.additions.append(item)
        self.order.append(item.token)
        return item

    def update(self, token, kind, command, enabled):
        current = self.get(token)
        if not current.editable:
            raise ValueError("Open the source file to edit this command.")
        candidate = replace(current, kind=kind, command=command, enabled=enabled)
        validate(candidate, current)
        if token.startswith("N"):
            self.additions = [
                candidate if c.token == token else c for c in self.additions
            ]
        else:
            original = next(c for c in self.local if c.token == token)
            if (candidate.kind, candidate.command, candidate.enabled) == (
                original.kind,
                original.command,
                original.enabled,
            ):
                self.changes.pop(token, None)
            else:
                self.changes[token] = candidate
        return candidate

    def remove(self, token):
        command = self.get(token)
        if not command.editable:
            raise ValueError("Open the source file to delete this command.")
        self.order.remove(token)
        if token.startswith("N"):
            self.additions = [c for c in self.additions if c.token != token]
        else:
            self.changes[token] = None

    def reset(self):
        self.changes.clear()
        self.additions.clear()
        self.order = [c.token for c in self.local]

    def duplicates(self, candidate=None, exclude=None):
        groups = {}
        for command in self.entries():
            if command.token == exclude or not command.enabled:
                continue
            groups.setdefault((command.kind, command.command.strip()), []).append(
                command
            )
        if candidate is not None:
            return (
                groups.get((candidate.kind, candidate.command.strip()), [])
                if candidate.enabled
                else []
            )
        return {c.token for group in groups.values() if len(group) > 1 for c in group}

    def preview(self):
        text = self.original.decode("utf-8")
        originals = {c.token: c for c in self.local}
        nodes = []
        for token in self.order:
            command = self.get(token)
            original = originals.get(token)
            if original is None:
                node = serialize(command)
                node = node if command.enabled else disabled_xml(node)
            elif token in self.changes:
                node = changed_xml(command, original)
            else:
                node = text[original.span[0] : original.span[1]]
            nodes.append(node)
        replacements = []
        for original in self.local:
            if self.changes.get(original.token, original) is None:
                node = ""
            else:
                node = nodes.pop(0)
            replacements.append((*original.span[:2], node))
        for start, end, node in reversed(replacements):
            text = text[:start] + node + text[end:]
        text = append_nodes(text, nodes)
        ET.fromstring(text)
        return text

    def save(self):
        if not self.config.unchanged():
            raise ValueError(
                "The configuration or an Include changed on disk. Reload before saving."
            )
        data = self.preview().encode("utf-8")
        if data != self.original:
            if not self.config.unchanged():
                raise ValueError(
                    "The configuration changed while preparing the changes."
                )
            save_atomic(self.path.with_name(self.path.name + ".bak"), self.original)
            save_atomic(self.path, data)
        self.__init__(self.path)
