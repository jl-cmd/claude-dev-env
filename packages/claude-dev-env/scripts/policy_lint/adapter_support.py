from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from types import ModuleType

from .model import Diagnostic, Document, Location, Severity

HookModuleLoader = Callable[[str], ModuleType]


def _document_path(repository_root: Path, document: Document) -> Path:
    return repository_root / document.path.as_posix()


def _line_number(message: str) -> int | None:
    line_prefix = "Line "
    if not message.startswith(line_prefix):
        return _path_line_number(message) or None
    remainder = message[len(line_prefix) :]
    line_text, separator, _tail = remainder.partition(":")
    if not separator or not line_text.isdigit():
        return _path_line_number(message) or None
    parsed_line = int(line_text)
    if parsed_line < 1:
        return _path_line_number(message) or None
    return parsed_line


def _path_line_number(message: str) -> int:
    all_prefix_fields = message.partition(": ")[0].split(":")
    for each_field_index, each_field in enumerate(all_prefix_fields):
        if each_field.isdigit():
            return _line_number_when_prefix_is_a_location(
                all_prefix_fields, each_field_index
            )
    return 0


def _line_number_when_prefix_is_a_location(
    all_prefix_fields: list[str], digit_field_index: int
) -> int:
    all_non_path_characters = ("|", '"')
    if digit_field_index == 0:
        return 0
    all_path_fields = all_prefix_fields[:digit_field_index]
    looks_like_a_path = not any(
        each_character in each_path_field
        for each_path_field in all_path_fields
        for each_character in all_non_path_characters
    )
    all_trailing_fields = all_prefix_fields[digit_field_index + 1 :]
    if not looks_like_a_path:
        return 0
    if not all(each_field.isdigit() for each_field in all_trailing_fields):
        return 0
    return int(all_prefix_fields[digit_field_index])


def _diagnostics_for_messages(
    document: Document,
    rule_id: str,
    all_messages: Iterable[str],
) -> tuple[Diagnostic, ...]:
    all_diagnostics: list[Diagnostic] = []
    for each_message in all_messages:
        maybe_line = _line_number(each_message)
        location = (
            None if maybe_line is None else Location(document.path, maybe_line, 1)
        )
        all_diagnostics.append(
            Diagnostic(rule_id, Severity.ERROR, each_message, location)
        )
    return tuple(all_diagnostics)


def _source_line_for_phrase(source_text: str, phrase: str) -> int | None:
    normalized_phrase = phrase.casefold()
    for each_line_number, each_line in enumerate(source_text.splitlines(), 1):
        if normalized_phrase in each_line.casefold():
            return each_line_number
    return None


def _diagnostics_for_state_messages(
    document: Document, all_messages: Iterable[str]
) -> tuple[Diagnostic, ...]:
    all_diagnostics: list[Diagnostic] = []
    for each_message in all_messages:
        maybe_line = _source_line_for_phrase(document.text, each_message)
        location = (
            None if maybe_line is None else Location(document.path, maybe_line, 1)
        )
        all_diagnostics.append(
            Diagnostic("state-description", Severity.ERROR, each_message, location)
        )
    return tuple(all_diagnostics)
