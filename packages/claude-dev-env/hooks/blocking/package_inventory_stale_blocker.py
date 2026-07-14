#!/usr/bin/env python3
"""PreToolUse hook: blocks a new production file absent from its package inventory.

A package directory documents its own files in a sibling inventory document — a
``README.md`` Layout table, a ``CLAUDE.md`` "Key files" list, or a skill
``SKILL.md`` Layout table that maps the ``scripts/`` subdirectory — whose entries
name each file in backticks. When a Write creates a new production code file in a
directory whose inventory already names two or more sibling files but carries no
entry naming the new file, the inventory and the directory disagree on the
package's file set: a reader who trusts the inventory to map the directory misses
the new file. This hook fires on a Write that creates such a file and blocks it,
directing the author to add the inventory entry in the same change. Edits to an
existing file, exempt files (``__init__.py``, ``conftest.py``, ``setup.py``,
``_path_setup.py``), test files, and files inside a directory that carries no
per-file inventory (such as ``config/`` or ``tests/``) are out of scope.
"""

import os
import sys
from pathlib import Path

try:
    _hooks_root_directory = str(Path(__file__).resolve().parent.parent)
    _blocking_directory = str(Path(__file__).resolve().parent)
    for each_bootstrap_directory in (_hooks_root_directory, _blocking_directory):
        if each_bootstrap_directory not in sys.path:
            sys.path.insert(0, each_bootstrap_directory)
    from inventory_intent_records import records
    from package_inventory_stale_blocker_parts import decision, inventory_detection

    from hooks_constants.pre_tool_use_stdin import (
        read_hook_input_dictionary_from_stdin,
    )
except ImportError as import_error:
    raise ImportError(
        "package_inventory_stale_blocker: cannot import its parts submodules; "
        "ensure the hooks directory is importable."
    ) from import_error


inventory_named_basenames = inventory_detection.inventory_named_basenames
is_inventoried_production_file = inventory_detection.is_inventoried_production_file
find_stale_inventory = inventory_detection.find_stale_inventory
survey_directory_inventories = inventory_detection.survey_directory_inventories
deny_stale_inventory = decision.deny_stale_inventory


def _resolve_payload(input_data: dict) -> tuple[str, dict, str]:
    """Return the tool name, tool input, and file path from a PreToolUse payload.

    Args:
        input_data: The parsed PreToolUse payload.

    Returns:
        The tool name, the tool input dict, and the file path — each emptied when
        its value is absent or the wrong type.
    """
    raw_tool_name = input_data.get("tool_name", "")
    tool_name = raw_tool_name if isinstance(raw_tool_name, str) else ""
    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return tool_name, {}, ""
    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str):
        return tool_name, tool_input, ""
    return tool_name, tool_input, file_path


def _emit_stale_decision(
    input_data: dict, file_path: str, survey: inventory_detection._InventorySurvey
) -> None:
    """Allow the write when a pending row intent matches, else record and deny.

    Args:
        input_data: The parsed PreToolUse payload.
        file_path: The destination path of the new file.
        survey: The maintained-inventory survey the file is absent from.
    """
    session_id = str(input_data.get("session_id") or "")
    directory = str(Path(file_path).resolve().parent)
    filename = os.path.basename(file_path)
    if records.has_fresh_row_intent(session_id, directory, filename):
        records.consume_row_intent(session_id, directory, filename)
        return
    records.record_file_intent(session_id, directory, filename)
    deny_stale_inventory(file_path, survey)


def main() -> None:
    """Read the PreToolUse payload from stdin and block a stale-inventory Write."""
    input_data = read_hook_input_dictionary_from_stdin()
    if input_data is None:
        sys.exit(0)
    tool_name, _tool_input, file_path = _resolve_payload(input_data)
    if tool_name != "Write" or not file_path:
        sys.exit(0)
    if os.path.exists(file_path) or not is_inventoried_production_file(file_path):
        sys.exit(0)
    survey = find_stale_inventory(file_path)
    if survey is None:
        sys.exit(0)
    _emit_stale_decision(input_data, file_path, survey)
    sys.exit(0)


if __name__ == "__main__":
    main()
