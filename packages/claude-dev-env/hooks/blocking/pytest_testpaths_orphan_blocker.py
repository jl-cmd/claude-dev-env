#!/usr/bin/env python3
"""PreToolUse hook: blocks a test file written outside a package's explicit pytest testpaths allowlist.

A package whose ``pyproject.toml`` declares ``[tool.pytest.ini_options]`` with an
explicit ``testpaths`` list runs only the directories that list names. A new
``test_*.py`` written into a directory that no ``testpaths`` entry covers is
collected by no default ``pytest`` run, so the test silently never executes and a
regression in the code it guards passes the standard suite undetected. This hook
fires on Write, Edit, and MultiEdit that create a ``test_*.py`` file, walks up
from the file to the nearest ``pyproject.toml`` that declares an explicit
``testpaths`` allowlist, and blocks the write when the file's directory (relative
to that package root) is covered by no entry. A package whose pyproject declares
no pytest section, or a pytest section with no explicit ``testpaths`` list, is out
of scope, since pytest then discovers tests by recursive default and the file is
collected wherever it lands.
"""

import fnmatch
import json
import sys
import tomllib
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.pytest_testpaths_orphan_blocker_constants import (  # noqa: E402
    ALL_PRUNED_PARENT_DIRECTORY_NAMES,
    GLOB_METACHARACTERS,
    MAX_PARENT_DIRECTORIES_SEARCHED,
    PACKAGE_ROOT_ENTRY,
    PACKAGE_ROOT_ENTRY_PREFIX,
    PYPROJECT_FILENAME,
    TEST_FILE_BASENAME_PATTERN,
    TESTPATHS_KEY,
    UNREGISTERED_TEST_DIRECTORY_ADDITIONAL_CONTEXT,
    UNREGISTERED_TEST_DIRECTORY_MESSAGE_TEMPLATE,
    UNREGISTERED_TEST_DIRECTORY_SYSTEM_MESSAGE,
)


def is_test_file(file_path: str) -> bool:
    """Return whether *file_path* names a pytest-collectable ``test_*.py`` file.

    Args:
        file_path: The destination path of the write or edit.

    Returns:
        True when the path's basename matches the ``test_*.py`` pattern.
    """
    return TEST_FILE_BASENAME_PATTERN.match(Path(file_path).name) is not None


class _PytestPackage:
    """A pyproject.toml that declares an explicit pytest testpaths allowlist.

    Attributes:
        package_root: The directory holding the pyproject.toml, against which
            every testpaths entry and the test file's location are resolved.
        all_testpaths: Each directory the testpaths list names, as written.
    """

    def __init__(self, package_root: Path, all_testpaths: list[str]) -> None:
        self.package_root = package_root
        self.all_testpaths = all_testpaths


def _nested_dict_table(parent_table: dict, table_key: str) -> dict | None:
    """Return the child table at *table_key*, or None when it is absent or a scalar.

    Args:
        parent_table: The enclosing TOML table to look the key up in.
        table_key: The key whose value is expected to be a nested table.

    Returns:
        The nested table, or None when the key is missing or maps to a non-table.
    """
    child_table = parent_table.get(table_key, {})
    if not isinstance(child_table, dict):
        return None
    return child_table


def _explicit_testpaths(pyproject_path: Path) -> list[str] | None:
    """Return the explicit testpaths entries a pyproject declares, when it has them.

    The pyproject declares an explicit allowlist only when its
    ``[tool.pytest.ini_options]`` table holds a ``testpaths`` key whose value is a
    non-empty list of strings. A pyproject with no pytest table, no ``testpaths``
    key, or a malformed value yields None, so the caller treats that package as
    out of scope (pytest then discovers tests by recursive default). A scalar
    ``tool``, ``pytest``, or ``ini_options`` value also yields None, since the
    descent through those nested tables stops at the first non-table.

    Args:
        pyproject_path: The path of the pyproject.toml to read.

    Returns:
        The list of testpaths entries, or None when the pyproject declares no
        explicit list or cannot be parsed.
    """
    try:
        parsed_pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    tool_table = _nested_dict_table(parsed_pyproject, "tool")
    pytest_table = _nested_dict_table(tool_table, "pytest") if tool_table is not None else None
    pytest_section = (
        _nested_dict_table(pytest_table, "ini_options") if pytest_table is not None else None
    )
    if pytest_section is None:
        return None
    declared_testpaths = pytest_section.get(TESTPATHS_KEY)
    if not isinstance(declared_testpaths, list):
        return None
    string_entries = [each for each in declared_testpaths if isinstance(each, str) and each]
    if not string_entries:
        return None
    return string_entries


def _find_governing_package(test_file: Path) -> _PytestPackage | None:
    """Return the nearest ancestor package that governs *test_file* with an allowlist.

    Walks upward from the test file's directory, pruning noise directories, until
    it reaches a ``pyproject.toml`` that declares an explicit ``testpaths`` list.
    The first such pyproject governs the file. The walk stops at the budget, so a
    deeply nested file never searches indefinitely.

    Args:
        test_file: The resolved path of the test file being written.

    Returns:
        The governing package paired with its testpaths entries, or None when no
        ancestor declares an explicit allowlist within the budget.
    """
    searched_count = 0
    for each_directory in test_file.parents:
        if each_directory.name in ALL_PRUNED_PARENT_DIRECTORY_NAMES:
            continue
        searched_count += 1
        if searched_count > MAX_PARENT_DIRECTORIES_SEARCHED:
            return None
        candidate_pyproject = each_directory / PYPROJECT_FILENAME
        if not candidate_pyproject.is_file():
            continue
        all_testpaths = _explicit_testpaths(candidate_pyproject)
        if all_testpaths is None:
            continue
        return _PytestPackage(each_directory, all_testpaths)
    return None


def _is_collected_by_entry(relative_test_path: Path, testpaths_entry: str) -> bool:
    """Return whether one testpaths entry collects the test at *relative_test_path*.

    The entry and the relative path are normalized to forward-slash posix form
    (a leading ``./`` is stripped) so a Windows backslash path matches a
    posix-written testpaths entry. An entry that reduces to ``.`` or empty names
    the package root, which collects every test recursively, so it collects the
    file. An entry holding a glob metacharacter is matched as an fnmatch pattern
    against the file's relative path. Otherwise the entry collects the file when
    it names the file itself or names a directory the file sits inside (the entry
    is a path prefix of the file's relative path).

    Args:
        relative_test_path: The test file's path relative to the package root.
        testpaths_entry: One entry from the package's testpaths list.

    Returns:
        True when the entry collects the test file.
    """
    normalized_test_path = relative_test_path.as_posix()
    normalized_entry = testpaths_entry.strip().replace("\\", "/")
    if normalized_entry.startswith(PACKAGE_ROOT_ENTRY_PREFIX):
        normalized_entry = normalized_entry[len(PACKAGE_ROOT_ENTRY_PREFIX) :]
    normalized_entry = normalized_entry.strip("/")
    if normalized_entry in (PACKAGE_ROOT_ENTRY, ""):
        return True
    if any(metacharacter in normalized_entry for metacharacter in GLOB_METACHARACTERS):
        return _matches_glob_entry(normalized_test_path, normalized_entry)
    if normalized_test_path == normalized_entry:
        return True
    return normalized_test_path.startswith(normalized_entry + "/")


def _matches_glob_entry(normalized_test_path: str, normalized_entry: str) -> bool:
    """Return whether a glob testpaths entry collects the file at *normalized_test_path*.

    A glob entry collects the file when the entry matches the file's relative
    path, or when the entry matches an ancestor directory the file sits inside —
    so ``tests/*`` (which fnmatch-matches the directory ``tests/data``) collects
    ``tests/data/test_x.py``.

    Args:
        normalized_test_path: The test file's posix relative path.
        normalized_entry: The glob entry, normalized to posix form.

    Returns:
        True when the entry matches the file or a directory containing it.
    """
    if fnmatch.fnmatch(normalized_test_path, normalized_entry):
        return True
    ancestor_path = Path(normalized_test_path).parent
    while ancestor_path != ancestor_path.parent:
        if fnmatch.fnmatch(ancestor_path.as_posix(), normalized_entry):
            return True
        ancestor_path = ancestor_path.parent
    return False


def _suggested_testpaths_entry(relative_test_path: Path) -> str:
    """Return the testpaths entry that would collect the test file's directory.

    Args:
        relative_test_path: The test file's path relative to the package root.

    Returns:
        The posix-form parent directory of the test file, the entry a maintainer
        would add to the testpaths list to collect it.
    """
    return relative_test_path.parent.as_posix()


def find_unregistered_test_directory(file_path: str) -> dict[str, str] | None:
    """Return the block details when a test file lands outside its package's allowlist.

    Resolves the test file, finds the nearest ancestor pyproject that declares an
    explicit ``testpaths`` allowlist, and checks whether any entry collects the
    file. When a governing allowlist exists and no entry covers the file's
    directory, the details name the file, the pyproject, the uncollected
    directory, and the entry a maintainer would add. A file under no explicit
    allowlist, or one already covered by an entry, yields None. A filesystem error
    yields None (fail open), so an unreadable tree never blocks a write.

    Args:
        file_path: The destination path of the test file being written.

    Returns:
        A mapping of message fields when the file is unregistered, or None.
    """
    test_file = Path(file_path).resolve()
    governing_package = _find_governing_package(test_file)
    if governing_package is None:
        return None
    try:
        relative_test_path = test_file.relative_to(governing_package.package_root)
    except ValueError:
        return None
    for each_entry in governing_package.all_testpaths:
        if _is_collected_by_entry(relative_test_path, each_entry):
            return None
    return {
        "test_file": relative_test_path.as_posix(),
        "pyproject": (governing_package.package_root / PYPROJECT_FILENAME).as_posix(),
        "test_directory": relative_test_path.parent.as_posix(),
        "suggested_entry": _suggested_testpaths_entry(relative_test_path),
    }


def _creates_file(tool_name: str, tool_input: dict, file_path: str) -> bool:
    """Return whether the tool call creates the test file rather than editing it.

    The check targets a newly created test file: a Write whose target does not yet
    exist, or any Edit/MultiEdit whose target file is absent (the harness models a
    create-via-edit as an edit against a missing path). An edit to an existing test
    file is out of scope, since the file's collection status was settled when it
    was first created.

    Args:
        tool_name: The intercepted tool — ``Write``, ``Edit``, or ``MultiEdit``.
        tool_input: The tool's input payload.
        file_path: The destination path of the write or edit.

    Returns:
        True when the call creates a test file that does not yet exist on disk.
    """
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        return False
    if not isinstance(tool_input, dict):
        return False
    return not Path(file_path).exists()


def _build_block_payload(block_details: dict[str, str]) -> dict:
    """Build the PreToolUse deny payload naming the uncollected test directory.

    Args:
        block_details: The message fields the find step produced.

    Returns:
        The hook-result dictionary the harness reads to deny the write.
    """
    reason = UNREGISTERED_TEST_DIRECTORY_MESSAGE_TEMPLATE.format(**block_details)
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": UNREGISTERED_TEST_DIRECTORY_ADDITIONAL_CONTEXT,
        },
        "systemMessage": UNREGISTERED_TEST_DIRECTORY_SYSTEM_MESSAGE,
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
    """Read the PreToolUse payload from stdin and block an unregistered test file."""
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if not isinstance(input_data, dict):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if not isinstance(tool_name, str):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not is_test_file(file_path):
        sys.exit(0)

    if not _creates_file(tool_name, tool_input, file_path):
        sys.exit(0)

    try:
        block_details = find_unregistered_test_directory(file_path)
    except OSError:
        sys.exit(0)
    if block_details is None:
        sys.exit(0)

    block_payload = _build_block_payload(block_details)
    log_hook_block(
        calling_hook_name="pytest_testpaths_orphan_blocker.py",
        hook_event="PreToolUse",
        block_reason=block_payload["hookSpecificOutput"]["permissionDecisionReason"],
        tool_name=tool_name,
        offending_input_preview=file_path,
    )
    _emit_hook_result(block_payload, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
