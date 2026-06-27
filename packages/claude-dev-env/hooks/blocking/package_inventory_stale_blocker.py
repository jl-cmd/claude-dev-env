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

import json
import os
import sys
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.package_inventory_stale_blocker_constants import (  # noqa: E402
    ALL_EXEMPT_BASENAMES,
    ALL_EXEMPT_DIRECTORY_NAMES,
    ALL_INVENTORY_DOCUMENT_NAMES,
    ALL_PRODUCTION_CODE_EXTENSIONS,
    ALL_TEST_FILE_MARKERS,
    BACKTICK_TOKEN_PATTERN,
    CODE_FENCE_PATTERN,
    GLOB_METACHARACTER_PATTERN,
    MAX_INVENTORY_FILE_BYTES,
    MINIMUM_INVENTORY_ENTRY_COUNT,
    NON_FILENAME_TOKEN_PATTERN,
    PYTHON_FILE_EXTENSION,
    SCRIPTS_SUBDIRECTORY_NAME,
    SKILL_INVENTORY_DOCUMENT_NAME,
    STALE_INVENTORY_ADDITIONAL_CONTEXT,
    STALE_INVENTORY_MESSAGE_TEMPLATE,
    STALE_INVENTORY_SYSTEM_MESSAGE,
)
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)


def _basename_token(backtick_inner_text: str) -> str | None:
    """Return the bare filename a backticked token names, when it names one.

    A token names a bare filename when it is a single filename or path token
    carrying a known file extension. A token that holds a path keeps only its
    final segment, so an inventory cell naming ``pipeline/seam_continuity.py``
    yields ``seam_continuity.py`` — the basename the directory file would match.
    A slash-command token (leading ``/``), a glob/pattern token carrying a
    metacharacter (``*``, ``?``, brace or bracket range, so ``*.py`` and
    ``test_*.py`` name no literal file), a multi-word command-example span
    carrying whitespace or shell punctuation (``:``, ``$``, ``<``, ``>``, so
    ``parent:node_modules package.json`` and ``python <file>.py`` name no
    literal file), and a token with no file extension yield None.

    Args:
        backtick_inner_text: The text between a backtick pair, stripped.

    Returns:
        The bare basename the token references, or None when it names no file.
    """
    inner_text = backtick_inner_text.strip()
    if not inner_text or inner_text.startswith("/"):
        return None
    if GLOB_METACHARACTER_PATTERN.search(inner_text) is not None:
        return None
    if NON_FILENAME_TOKEN_PATTERN.search(inner_text) is not None:
        return None
    basename = os.path.basename(inner_text.replace("\\", "/").rstrip("/"))
    if not basename:
        return None
    _, extension = os.path.splitext(basename)
    if not extension:
        return None
    return basename


def _lines_outside_code_fences(inventory_content: str) -> list[str]:
    """Return the inventory lines that sit outside any fenced code block.

    A line inside a ``` or ~~~ fence pair is example or sample text, not a live
    listing, so it is dropped — mirroring the fence handling in
    ``claude_md_orphan_file_blocker``.

    Args:
        inventory_content: The text of a README.md or CLAUDE.md inventory.

    Returns:
        The lines that lie outside every code fence, in document order.
    """
    live_lines: list[str] = []
    is_inside_code_fence = False
    for each_line in inventory_content.splitlines():
        if CODE_FENCE_PATTERN.match(each_line) is not None:
            is_inside_code_fence = not is_inside_code_fence
            continue
        if is_inside_code_fence:
            continue
        live_lines.append(each_line)
    return live_lines


def inventory_named_basenames(inventory_content: str) -> set[str]:
    """Return every bare filename a package inventory document names in backticks.

    Lines inside a fenced code block are skipped as example text. Each backticked
    token on a remaining line is examined; one that names a literal file (a single
    filename or path token that carries an extension, no glob metacharacter, and
    no whitespace or shell punctuation) contributes its basename, and a token
    holding a path contributes its final segment. A multi-word command-example
    span contributes nothing. This covers both a README.md table cell and a
    CLAUDE.md bullet, since both name files in backticks.

    Args:
        inventory_content: The text of a README.md or CLAUDE.md inventory.

    Returns:
        The set of bare basenames the inventory names.
    """
    named_basenames: set[str] = set()
    for each_line in _lines_outside_code_fences(inventory_content):
        for each_match in BACKTICK_TOKEN_PATTERN.finditer(each_line):
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
            directory (``README.md``, ``CLAUDE.md``, and/or ``SKILL.md``).
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

    A file directly inside a directory that carries no per-file inventory (such
    as ``config/`` or ``tests/``) has no individual entry, so its directory
    exempts it.

    Args:
        package_directory: The directory that holds the file being written.

    Returns:
        True when the directory's own name is an exempt directory name.
    """
    return package_directory.name in ALL_EXEMPT_DIRECTORY_NAMES


def is_inventoried_production_file(file_path: str) -> bool:
    """Return whether *file_path* is a production file an inventory should name.

    A production file is a non-test, non-exempt code file (``.py``, ``.mjs``,
    ``.js``, ``.ts``, ``.ps1``, ``.sh``) outside a directory that carries no
    per-file inventory (such as ``config/`` or ``tests/``). Exempt basenames
    (``__init__.py``, ``conftest.py``, ``setup.py``, ``_path_setup.py``) and
    test files are out of scope.

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
    return not _is_under_exempt_directory(Path(file_path).resolve().parent)


def _sibling_named_basenames(
    package_directory: Path, all_named_basenames: set[str]
) -> set[str]:
    """Return the named basenames that exist as files in *package_directory*.

    A maintained inventory lists the directory's own files, so a named basename
    counts toward the inventory only when a file with that basename sits directly
    in the directory. A name the inventory mentions in passing — a file living in
    another directory (``install.mjs``), a sibling doc — is dropped, so prose that
    references non-sibling files never reads as a maintained inventory.

    Args:
        package_directory: The directory that holds the file being written.
        all_named_basenames: Every bare basename the inventory documents name.

    Returns:
        The subset of *all_named_basenames* present as a file in the directory.
    """
    sibling_basenames: set[str] = set()
    for each_basename in all_named_basenames:
        if (package_directory / each_basename).is_file():
            sibling_basenames.add(each_basename)
    return sibling_basenames


def _parent_skill_inventory(package_directory: Path) -> _InventorySurvey | None:
    """Return the parent skill ``SKILL.md`` survey for a ``scripts/`` directory.

    A skill package keeps its ``SKILL.md`` at the skill root and maps the
    ``scripts/`` subdirectory in a Layout table whose rows name files by their
    ``scripts/<name>`` path. A production file landing in that ``scripts/``
    directory is governed by the parent ``SKILL.md``, which sits one level up
    rather than beside the file. This reads that parent ``SKILL.md`` and reports
    the basenames it names. Any directory not named ``scripts/`` and any missing
    or unreadable parent ``SKILL.md`` yield None.

    Args:
        package_directory: The directory that holds the file being written.

    Returns:
        The parent ``SKILL.md`` survey, or None when there is none to read.
    """
    if package_directory.name != SCRIPTS_SUBDIRECTORY_NAME:
        return None
    skill_inventory_path = package_directory.parent / SKILL_INVENTORY_DOCUMENT_NAME
    inventory_content = _read_inventory_content(skill_inventory_path)
    if inventory_content is None:
        return None
    return _InventorySurvey(
        [SKILL_INVENTORY_DOCUMENT_NAME], inventory_named_basenames(inventory_content)
    )


def find_stale_inventory(file_path: str) -> _InventorySurvey | None:
    """Return the maintained inventory survey a new file is absent from, or None.

    The file's own directory inventories are surveyed and, when the file sits in
    a ``scripts/`` subdirectory, the parent skill ``SKILL.md`` Layout table is
    surveyed too; the named basenames union across both. They are then filtered
    to those that exist as files in the file's directory — the inventory's own
    sibling files. The survey reports a stale inventory only when every condition
    holds: at least one inventory document is present, those documents together
    name at least the minimum entry count of on-disk sibling files (marking them
    a maintained inventory rather than incidental prose that mentions files living
    elsewhere), and no inventory already names this file's basename. When any
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
    present_inventory_names = list(survey.present_inventory_names)
    named_basenames = set(survey.named_basenames)
    parent_skill_survey = _parent_skill_inventory(package_directory)
    if parent_skill_survey is not None:
        present_inventory_names += parent_skill_survey.present_inventory_names
        named_basenames |= parent_skill_survey.named_basenames
    if not present_inventory_names:
        return None
    sibling_basenames = _sibling_named_basenames(package_directory, named_basenames)
    if len(sibling_basenames) < MINIMUM_INVENTORY_ENTRY_COUNT:
        return None
    if os.path.basename(file_path) in named_basenames:
        return None
    return _InventorySurvey(present_inventory_names, sibling_basenames)


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
    input_data = read_hook_input_dictionary_from_stdin()
    if input_data is None:
        sys.exit(0)

    raw_tool_name = input_data.get("tool_name", "")
    tool_name = raw_tool_name if isinstance(raw_tool_name, str) else ""
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
    log_hook_block(
        calling_hook_name="package_inventory_stale_blocker.py",
        hook_event="PreToolUse",
        block_reason=block_payload["hookSpecificOutput"]["permissionDecisionReason"],
        tool_name=tool_name,
        offending_input_preview=file_path,
    )
    _emit_hook_result(block_payload, sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()
