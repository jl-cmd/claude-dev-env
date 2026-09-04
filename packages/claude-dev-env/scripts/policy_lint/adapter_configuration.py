from __future__ import annotations

import json
from pathlib import Path

from . import adapter_support
from .config import constants
from .model import Diagnostic, Document


def hook_configuration_diagnostics(
    document: Document, repository_root: Path
) -> tuple[Diagnostic, ...]:
    """Check hook configuration for policy decision fields.

    Args:
        document: Current hook configuration text.
        repository_root: Request repository root for document-path resolution.

    Returns:
        Hook configuration diagnostics.
    """
    adapter_support._document_path(repository_root, document)
    if document.path.name != "hooks.json":
        return ()
    all_messages = _hook_configuration_messages(document.text)
    return adapter_support._diagnostics_for_messages(
        document, "hook-configuration", all_messages
    )


def _hook_configuration_messages(configuration_text: str) -> tuple[str, ...]:
    try:
        parsed_configuration = json.loads(configuration_text)
    except json.JSONDecodeError:
        return ("Hook configuration is not valid JSON",)
    if not isinstance(parsed_configuration, dict):
        return ("Hook configuration must be an object",)
    all_registered_strings = _registered_hook_strings(parsed_configuration)
    if any(
        _contains_action_boundary_marker(each_string)
        for each_string in all_registered_strings
    ):
        return ("Hook configuration registers a deny, block, or ask policy path",)
    return ()


def _registered_hook_strings(
    all_configuration_entries: dict[object, object]
) -> tuple[str, ...]:
    all_registered_strings: list[str] = []
    for each_key, each_entry in all_configuration_entries.items():
        all_registered_strings.extend(
            _registered_strings_for_entry(each_key, each_entry)
        )
    return tuple(all_registered_strings)


def _registered_strings_for_entry(
    each_key: object, each_entry: object
) -> tuple[str, ...]:
    all_registered_strings: list[str] = []
    if each_key in constants.ALL_HOOK_REGISTRATION_KEYS and isinstance(each_entry, str):
        all_registered_strings.append(each_entry)
    if each_key in constants.ALL_DECISION_REGISTRATION_KEYS and isinstance(each_entry, str):
        all_registered_strings.append(each_entry)
    all_registered_strings.extend(_registered_nested_strings(each_entry))
    return tuple(all_registered_strings)


def _registered_nested_strings(each_entry: object) -> tuple[str, ...]:
    if isinstance(each_entry, dict):
        return _registered_hook_strings(each_entry)
    if not isinstance(each_entry, list):
        return ()
    all_registered_strings: list[str] = []
    for each_nested_entry in each_entry:
        if isinstance(each_nested_entry, dict):
            all_registered_strings.extend(_registered_hook_strings(each_nested_entry))
    return tuple(all_registered_strings)


def _contains_action_boundary_marker(registered_string: str) -> bool:
    normalized_string = registered_string.lower().replace("\\", "/")
    normalized_string = normalized_string.replace(".", "/").replace("-", "/")
    return any(
        each_segment in constants.ALL_ACTION_BOUNDARY_SEGMENTS
        or each_segment.startswith(constants.ALL_ACTION_BOUNDARY_PREFIXES)
        for each_segment in normalized_string.split("/")
        if each_segment
    )
