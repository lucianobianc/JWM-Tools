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
    "StartupCommand": "Início de sessão",
    "RestartCommand": "Reinício do JWM",
    "ShutdownCommand": "Encerramento",
}
HINTS = {
    "StartupCommand": "Executado ao iniciar uma nova sessão do JWM. Reiniciar o gerenciador não executa estes comandos novamente.",
    "RestartCommand": "Executado após reiniciar o JWM. Os aplicativos que já estavam abertos não são encerrados automaticamente.",
    "ShutdownCommand": "Executado ao encerrar o JWM, sem reinício.",
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
        raise ValueError("Escolha quando o comando deve ser executado.")
    if not command.command.strip():
        raise ValueError("Informe um comando.")
    if "\x00" in command.command:
        raise ValueError("O comando contém um caractere inválido.")
    if previous is not None and previous.command == command.command:
        return
    if "\n" in command.command or "\r" in command.command:
        raise ValueError("Informe o comando em uma única linha.")
    if command.command.startswith("exec:"):
        raise ValueError("Use apenas o comando, sem o prefixo exec:.")


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
                    f"Comando desativado ilegível em {path}. O comentário foi preservado."
                )
                continue
        try:
            node = ET.fromstring(payload)
        except ET.ParseError:
            if content.startswith(MARKER):
                warnings.append(
                    f"Comando desativado inválido em {path}. O comentário foi preservado."
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
        raise ValueError("Comando do aplicativo inválido: " + str(exc)) from exc
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
            raise ValueError("Campo não suportado no comando do aplicativo: %" + code)

        value = re.sub(r"%(.)", field, arg)
        if value:
            result.append(value)
    if not result:
        raise ValueError("O aplicativo não tem um comando para iniciar.")
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

    @property
    def dirty(self):
        return bool(self.changes or self.additions)

    def entries(self):
        return (
            [
                self.changes.get(c.token, c)
                for c in self.local
                if self.changes.get(c.token, c) is not None
            ]
            + self.additions
            + self.included
        )

    def get(self, token):
        return next(c for c in self.entries() if c.token == token)

    def add(self, kind, command, enabled=True):
        item = Command("N" + str(self.next_id), kind, command, self.path, {}, enabled)
        validate(item)
        self.next_id += 1
        self.additions.append(item)
        return item

    def update(self, token, kind, command, enabled):
        current = self.get(token)
        if not current.editable:
            raise ValueError("Abra o arquivo de origem para editar este comando.")
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
            raise ValueError("Abra o arquivo de origem para excluir este comando.")
        if token.startswith("N"):
            self.additions = [c for c in self.additions if c.token != token]
        else:
            self.changes[token] = None

    def reset(self):
        self.changes.clear()
        self.additions.clear()

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
        for original in reversed(self.local):
            if original.token not in self.changes:
                continue
            changed = self.changes[original.token]
            node = "" if changed is None else changed_xml(changed, original)
            a, b = original.span[:2]
            text = text[:a] + node + text[b:]
        additions = []
        for command in self.additions:
            node = serialize(command)
            additions.append(node if command.enabled else disabled_xml(node))
        text = append_nodes(text, additions)
        ET.fromstring(text)
        return text

    def save(self):
        if not self.config.unchanged():
            raise ValueError(
                "A configuração ou um Include mudou no disco. Recarregue antes de salvar."
            )
        data = self.preview().encode("utf-8")
        if data != self.original:
            if not self.config.unchanged():
                raise ValueError(
                    "A configuração mudou enquanto as alterações eram preparadas."
                )
            save_atomic(self.path.with_name(self.path.name + ".bak"), self.original)
            save_atomic(self.path, data)
        self.__init__(self.path)
