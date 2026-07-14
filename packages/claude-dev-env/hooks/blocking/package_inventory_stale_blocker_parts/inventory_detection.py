"""Survey a directory's package inventories and detect a stale omission.

Reads each ``README.md`` / ``CLAUDE.md`` / ``SKILL.md`` beside a file, collects
the bare filenames they name in backticks, and reports whether a maintained
inventory omits the file being written.
"""

import os
from pathlib import Path

from hooks_constants.package_inventory_stale_blocker_constants import (
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
)


def _basename_token(backtick_inner_text: str) -> str | None:
    """Return the bare filename a backticked token names, when it names one.

    A token names a bare filename when it is a single filename or path token
    carrying a known file extension; a path keeps only its final segment. A
    slash-command, a glob/pattern token, a multi-word command-example span, and
    an extension-less token yield None.

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


def _line_named_basenames(inventory_line: str) -> set[str]:
    """Return the bare filenames one inventory line names in backticks.

    Args:
        inventory_line: One line drawn from outside any code fence.

    Returns:
        The set of bare basenames the line's backticked tokens name.
    """
    line_basenames: set[str] = set()
    for each_match in BACKTICK_TOKEN_PATTERN.finditer(inventory_line):
        each_basename = _basename_token(each_match.group(1))
        if each_basename is not None:
            line_basenames.add(each_basename)
    return line_basenames


def inventory_named_basenames(inventory_content: str) -> set[str]:
    """Return every bare filename a package inventory document names in backticks.

    Lines inside a fenced code block are skipped as example text. Each backticked
    token that names a literal file contributes its basename; a token holding a
    path contributes its final segment.

    Args:
        inventory_content: The text of a README.md or CLAUDE.md inventory.

    Returns:
        The set of bare basenames the inventory names.
    """
    named_basenames: set[str] = set()
    for each_line in _lines_outside_code_fences(inventory_content):
        named_basenames |= _line_named_basenames(each_line)
    return named_basenames


def _read_inventory_content(inventory_path: Path) -> str | None:
    """Return the text of an inventory document, or None when it is unreadable.

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
        True when the name matches a test-file shape.
    """
    if basename.startswith("test_") and basename.endswith(PYTHON_FILE_EXTENSION):
        return True
    if basename.endswith("_test" + PYTHON_FILE_EXTENSION):
        return True
    return any(each_marker in basename for each_marker in ALL_TEST_FILE_MARKERS)


def _is_under_exempt_directory(package_directory: Path) -> bool:
    """Return whether the file's directory is itself an exempt directory.

    Args:
        package_directory: The directory that holds the file being written.

    Returns:
        True when the directory's own name is an exempt directory name.
    """
    return package_directory.name in ALL_EXEMPT_DIRECTORY_NAMES


def is_inventoried_production_file(file_path: str) -> bool:
    """Return whether *file_path* is a production file an inventory should name.

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


def _sibling_named_basenames(package_directory: Path, all_named_basenames: set[str]) -> set[str]:
    """Return the named basenames that exist as files in *package_directory*.

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

    A production file landing in a skill's ``scripts/`` directory is governed by
    the parent ``SKILL.md`` Layout table one level up. Any other directory and a
    missing or unreadable parent ``SKILL.md`` yield None.

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


def _merged_survey_names(
    package_directory: Path, survey: _InventorySurvey
) -> tuple[list[str], set[str]]:
    """Return the survey names merged with any parent skill ``SKILL.md`` survey.

    Args:
        package_directory: The directory that holds the file being written.
        survey: The file's own directory inventory survey.

    Returns:
        The present inventory names and named basenames, unioned across the
        directory's own inventories and the parent skill Layout table.
    """
    present_inventory_names = list(survey.present_inventory_names)
    named_basenames = set(survey.named_basenames)
    parent_skill_survey = _parent_skill_inventory(package_directory)
    if parent_skill_survey is not None:
        present_inventory_names += parent_skill_survey.present_inventory_names
        named_basenames |= parent_skill_survey.named_basenames
    return present_inventory_names, named_basenames


def find_stale_inventory(file_path: str) -> _InventorySurvey | None:
    """Return the maintained inventory survey a new file is absent from, or None.

    The survey reports a stale inventory only when at least one inventory document
    is present, those documents name at least the minimum count of on-disk sibling
    files, and no inventory already names this file's basename.

    Args:
        file_path: The destination path of the write.

    Returns:
        The inventory survey when the file is a stale omission, or None.
    """
    package_directory = Path(file_path).resolve().parent
    if not package_directory.is_dir():
        return None
    survey = survey_directory_inventories(package_directory)
    present_inventory_names, named_basenames = _merged_survey_names(package_directory, survey)
    if not present_inventory_names:
        return None
    sibling_basenames = _sibling_named_basenames(package_directory, named_basenames)
    if len(sibling_basenames) < MINIMUM_INVENTORY_ENTRY_COUNT:
        return None
    if os.path.basename(file_path) in named_basenames:
        return None
    return _InventorySurvey(present_inventory_names, sibling_basenames)
