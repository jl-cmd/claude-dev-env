#!/usr/bin/env python3
"""PreToolUse hook: blocks a new production file absent from its package inventory.

A package directory documents its own files in a sibling inventory document — a
``README.md`` Layout table or a ``CLAUDE.md`` "Key files" list — whose entries
name each file in backticks. When a Write creates a new production code file in a
directory whose inventory already names two or more sibling files but carries no
entry naming the new file, the inventory and the directory disagree on the
package's file set: a reader who trusts the inventory to map the directory misses
the new file. This hook fires on a Write that creates such a file and blocks it,
directing the author to add the inventory entry in the same change. Edits to an
existing file, exempt files (``__init__.py``, ``conftest.py``, ``setup.py``,
``_path_setup.py``), test files, and files under ``config/`` or ``tests/`` are
out of scope.
"""

import json
import os
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.package_inventory_stale_blocker_constants import (  # noqa: E402
    ALL_EXEMPT_BASENAMES,
    ALL_EXEMPT_DIRECTORY_NAMES,
    ALL_INVENTORY_DOCUMENT_NAMES,
    ALL_PRODUCTION_CODE_EXTENSIONS,
    ALL_TEST_FILE_MARKERS,
    BACKTICK_TOKEN_PATTERN,
    MAX_INVENTORY_FILE_BYTES,
    MINIMUM_INVENTORY_ENTRY_COUNT,
    PYTHON_FILE_EXTENSION,
    STALE_INVENTORY_ADDITIONAL_CONTEXT,
    STALE_INVENTORY_MESSAGE_TEMPLATE,
    STALE_INVENTORY_SYSTEM_MESSAGE,
)


def _basename_token(backtick_inner_text: str) -> str | None:
    """Return the bare filename a backticked token names, when it names one.

    A token names a bare filename when it carries a known file extension. A
    token that holds a path keeps only its final segment, so an inventory cell
    naming ``pipeline/seam_continuity.py`` yields ``seam_continuity.py`` — the
    basename the directory file would match. A slash-command token (leading
    ``/``) and a token with no file extension yield None.

    Args:
        backtick_inner_text: The text between a backtick pair, stripped.

    Returns:
        The bare basename the token references, or None when it names no file.
    """
    inner_text = backtick_inner_text.strip()
    if not inner_text or inner_text.startswith("/"):
        return None
    basename = os.path.basename(inner_text.replace("\\", "/").rstrip("/"))
    if not basename:
        return None
    _, extension = os.path.splitext(basename)
    if not extension:
        return None
    return basename


def inventory_named_basenames(inventory_content: str) -> set[str]:
    """Return every bare filename a package inventory document names in backticks.

    Each backticked token in the inventory is examined; one that names a file
    (carries an extension) contributes its basename. A token holding a path
    contributes its final segment. This covers both a README.md table cell and a
    CLAUDE.md bullet, since both name files in backticks.

    Args:
        inventory_content: The text of a README.md or CLAUDE.md inventory.

    Returns:
        The set of bare basenames the inventory names.
    """
    named_basenames: set[str] = set()
    for each_match in BACKTICK_TOKEN_PATTERN.finditer(inventory_content):
        each_basename = _basename_token(each_match.group(1))
        if each_basename is not None:
            named_basenames.add(each_basename)
    return named_basenames


def _read_inventory_content(inventory_path: Path) -> str | None:
    """Return the text of an inventory document, or None when it is unreadable.

    A document larger than the byte budget is skipped (None), so an oversized
    file never stalls the hook.

    Args:
        inventory_path: The path of the README.md or CLAUDE.md to read.

    Returns:
        The document text, or None when it is missing, oversized, or undecodable.
    """
    try:
        if inventory_path.stat().st_size > MAX_INVENTORY_FILE_BYTES:
            return None
        return inventory_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


class _InventorySurvey:
    """The inventory documents found beside a file and the files they name.

    Attributes:
        present_inventory_names: The inventory document basenames present in the
            directory (``README.md`` and/or ``CLAUDE.md``).
        named_basenames: Every bare filename the present inventories name.
    """

    def __init__(
        self, all_present_inventory_names: list[str], all_named_basenames: set[str]
    ) -> None:
        self.present_inventory_names = all_present_inventory_names
        self.named_basenames = all_named_basenames


def survey_directory_inventories(package_directory: Path) -> _InventorySurvey:
    """Return the inventory documents beside a file and the basenames they name.

    Reads each present ``README.md`` and ``CLAUDE.md`` in *package_directory* and
    unions the basenames they name in backticks.

    Args:
        package_directory: The directory that holds the file being written.

    Returns:
        The survey pairing the present inventory document names with the union of
        the basenames they name.
    """
    present_inventory_names: list[str] = []
    named_basenames: set[str] = set()
    for each_inventory_name in sorted(ALL_INVENTORY_DOCUMENT_NAMES):
        inventory_path = package_directory / each_inventory_name
        inventory_content = _read_inventory_content(inventory_path)
        if inventory_content is None:
            continue
        present_inventory_names.append(each_inventory_name)
        named_basenames |= inventory_named_basenames(inventory_content)
    return _InventorySurvey(present_inventory_names, named_basenames)


def _is_test_file(basename: str) -> bool:
    """Return whether *basename* names a test file the inventory need not list.

    Args:
        basename: The bare filename of the file being written.

    Returns:
        True when the name matches a test-file shape (``test_*.py``,
        ``*_test.py``, ``*.spec.*``, or ``*.test.*``).
    """
    if basename.startswith("test_") and basename.endswith(PYTHON_FILE_EXTENSION):
        return True
    if basename.endswith("_test" + PYTHON_FILE_EXTENSION):
        return True
    return any(each_marker in basename for each_marker in ALL_TEST_FILE_MARKERS)


def _is_under_exempt_directory(package_directory: Path) -> bool:
    """Return whether the file's directory is itself an exempt directory.

    A file directly inside a ``config/`` or ``tests/`` directory carries no
    individual inventory entry, so its directory exempts it.

    Args:
        package_directory: The directory that holds the file being written.

    Returns:
        True when the directory's own name is an exempt directory name.
    """
    return package_directory.name in ALL_EXEMPT_DIRECTORY_NAMES


def is_inventoried_production_file(file_path: str) -> bool:
    """Return whether *file_path* is a production file an inventory should name.

    A production file is a non-test, non-exempt code file (``.py``, ``.mjs``,
    ``.js``, ``.ts``, ``.ps1``, ``.sh``) outside a ``config/`` or ``tests/``
    directory. Exempt basenames (``__init__.py``, ``conftest.py``, ``setup.py``,
    ``_path_setup.py``) and test files are out of scope.

    Args:
        file_path: The destination path of the write.

    Returns:
        True when the file is one an inventory entry should name.
    """
    basename = os.path.basename(file_path)
    _, extension = os.path.splitext(basename)
    if extension.lower() not in ALL_PRODUCTION_CODE_EXTENSIONS:
        return False
    if basename in ALL_EXEMPT_BASENAMES:
        return False
    if _is_test_file(basename):
        return False
    if _is_under_exempt_directory(Path(file_path).resolve().parent):
        return False
    return True


def find_stale_inventory(file_path: str) -> _InventorySurvey | None:
    """Return the maintained inventory survey a new file is absent from, or None.

    The file's directory inventories are surveyed. The survey reports a stale
    inventory only when every condition holds: the directory carries at least one
    inventory document, those documents together name at least the minimum entry
    count of sibling files (marking them a maintained inventory rather than
    incidental prose), and none of them names this file's basename. When any
    condition fails the file is in step with its inventory (or there is no
    inventory to be out of step with), so None results.

    Args:
        file_path: The destination path of the write.

    Returns:
        The inventory survey when the file is a stale omission, or None.
    """
    package_directory = Path(file_path).resolve().parent
    if not package_directory.is_dir():
        return None
    survey = survey_directory_inventories(package_directory)
    if not survey.present_inventory_names:
        return None
    if len(survey.named_basenames) < MINIMUM_INVENTORY_ENTRY_COUNT:
        return None
    if os.path.basename(file_path) in survey.named_basenames:
        return None
    return survey


def _build_block_payload(file_path: str, survey: _InventorySurvey) -> dict:
    """Build the PreToolUse deny payload for a stale-inventory omission.

    Args:
        file_path: The destination path of the write.
        survey: The maintained-inventory survey the file is absent from.

    Returns:
        The hook-result dictionary the harness reads to deny the write.
    """
    package_directory = str(Path(file_path).resolve().parent)
    formatted_inventories = ", ".join(survey.present_inventory_names)
    reason = STALE_INVENTORY_MESSAGE_TEMPLATE.format(
        filename=os.path.basename(file_path),
        directory=package_directory,
        inventories=formatted_inventories,
        entry_count=len(survey.named_basenames),
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": STALE_INVENTORY_ADDITIONAL_CONTEXT,
        },
        "systemMessage": STALE_INVENTORY_SYSTEM_MESSAGE,
        "suppressOutput": True,
    }


def _emit_hook_result(all_hook_data: dict, output_stream: TextIO) -> None:
    """Write the hook result JSON to the given output stream.

    Args:
        all_hook_data: The hook-result dictionary to serialize.
        output_stream: The stream the harness reads the decision from.
    """
    output_stream.write(json.dumps(all_hook_data) + "\n")
    output_stream.flush()


def main() -> None:
    """Read the PreToolUse payload from stdin and block a stale-inventory Write."""
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if not isinstance(input_data, dict):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Write":
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path:
        sys.exit(0)

    if os.path.exists(file_path):
        sys.exit(0)

    if not is_inventoried_production_file(file_path):
        sys.exit(0)

    survey = find_stale_inventory(file_path)
    if survey is None:
        sys.exit(0)

    block_payload = _build_block_payload(file_path, survey)
    _emit_hook_result(block_payload, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
