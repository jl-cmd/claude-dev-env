"""Shared helpers for grant_project_claude_permissions and revoke_project_claude_permissions.

Writes to ~/.claude/settings.json are atomic and permission-preserving: the
target file's existing POSIX mode is captured, a sibling temp file is
created via os.open with O_CREAT | O_EXCL and the preserved mode, content
is written, then os.replace swaps it into place. Output is serialized with
sort_keys=True for a stable on-disk layout; the first run on a hand-ordered
settings file produces a one-time re-sort diff, subsequent writes are stable.
"""

import json
import os
import secrets
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn

sys.modules.pop("config", None)
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.claude_permissions_constants import (
    ALL_TRUST_ENTRY_PROJECT_PATH_BOUNDARY_QUOTE_CHARACTERS,
    CLAUDE_SETTINGS_DIRECTORY_NAME,
    GIT_DIRECTORY_NAME,
    TEXT_FILE_ENCODING as TEXT_FILE_ENCODING,
    UNIQUE_TEMPORARY_SUFFIX_BYTE_LENGTH,
)


def exit_with_error(message: str) -> NoReturn:
    """Print an error message to stderr and terminate the process.

    Args:
        message: The error message to print to stderr.

    Raises:
        SystemExit: Always raised with a non-zero exit code.
    """
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(1)


def path_contains_glob_metacharacters(candidate_path: str) -> bool:
    """Check whether a path contains characters reserved for glob patterns.

    Args:
        candidate_path: The file path string to inspect.

    Returns:
        True when any glob metacharacter is present in the path.
    """
    all_glob_metacharacters_in_path: tuple[str, ...] = (
        "*",
        "?",
        "[",
        "]",
        "{",
        "}",
    )
    return any(
        each_character in candidate_path
        for each_character in all_glob_metacharacters_in_path
    )


def get_current_project_path() -> str:
    """Return the normalized current working directory path.

    Returns:
        The cwd as a POSIX-style path string.

    Raises:
        ValueError: When the path contains glob metacharacters.
    """
    normalized_project_path = str(Path.cwd()).replace("\\", "/")
    if path_contains_glob_metacharacters(normalized_project_path):
        raise ValueError(
            f"Current directory path contains glob metacharacters and cannot "
            f"be used to build permission rules safely: {normalized_project_path}"
        )
    return normalized_project_path


def build_permission_rule(tool_name: str, project_path: str) -> str:
    return f"{tool_name}({project_path}/.claude/**)"


def build_permission_rules(
    project_path: str, all_permission_allow_tools: tuple[str, ...]
) -> list[str]:
    """Construct permission rule strings for each tool.

    Args:
        project_path: The POSIX-style project root path.
        all_permission_allow_tools: Tool names to build rules for.

    Returns:
        List of permission rule strings for the given project path.
    """
    return [
        build_permission_rule(each_tool, project_path)
        for each_tool in all_permission_allow_tools
    ]


def build_agent_config_deny_rule(
    tool_name: str, project_path: str, agent_config_path_pattern: str
) -> str:
    """Construct a deny rule for a single agent-config path pattern.

    Args:
        tool_name: The permission tool name (e.g., "Edit", "Write", "Read").
        project_path: The POSIX-style project root path.
        agent_config_path_pattern: The agent-config path pattern under .claude/.

    Returns:
        The deny rule string Claude Code matches against tool invocations.
    """
    return f"{tool_name}({project_path}/.claude/{agent_config_path_pattern})"


def build_agent_config_deny_rules(
    project_path: str,
    all_permission_allow_tools: tuple[str, ...],
    all_agent_config_path_patterns: tuple[str, ...],
) -> list[str]:
    """Construct deny rules covering every tool and pattern pair.

    Args:
        project_path: The POSIX-style project root path.
        all_permission_allow_tools: Tool names to build deny rules for.
        all_agent_config_path_patterns: Agent-config path patterns to deny under .claude/.

    Returns:
        List of deny rule strings, one per tool/pattern combination.
    """
    return [
        build_agent_config_deny_rule(each_tool, project_path, each_pattern)
        for each_tool in all_permission_allow_tools
        for each_pattern in all_agent_config_path_patterns
    ]


def _is_project_path_token_at_word_boundary(
    body_after_prefix: str, token_position: int
) -> bool:
    if token_position == 0:
        return True
    preceding_character = body_after_prefix[token_position - 1]
    if preceding_character.isspace():
        return True
    return preceding_character in ALL_TRUST_ENTRY_PROJECT_PATH_BOUNDARY_QUOTE_CHARACTERS


def is_trust_entry_for_project(
    candidate_entry: object, project_path: str, prefix: str
) -> bool:
    """Detect whether an autoMode.environment entry is a trust entry for the project.

    The predicate matches any string entry whose prefix matches the trust-entry
    marker and that contains the project's .claude/** path token anchored on a
    non-path boundary (the start of the body after the prefix, a whitespace
    character, or a quote character). The boundary anchor prevents
    cross-project false positives where the current project's path is a path
    suffix of an unrelated entry's path. The exact wording after the prefix is
    allowed to vary between template revisions.

    Args:
        candidate_entry: The autoMode.environment list value to inspect.
        project_path: The POSIX-style project root path.
        prefix: The literal prefix that marks a trust entry.

    Returns:
        True when the entry is a prior trust entry for this project.
    """
    if not isinstance(candidate_entry, str):
        return False
    if not candidate_entry.startswith(prefix):
        return False
    project_path_token = f"{project_path}/.claude/**"
    body_after_prefix = candidate_entry[len(prefix):]
    token_position = body_after_prefix.find(project_path_token)
    while token_position != -1:
        if _is_project_path_token_at_word_boundary(body_after_prefix, token_position):
            return True
        next_search_start = token_position + 1
        token_position = body_after_prefix.find(project_path_token, next_search_start)
    return False


def remove_matching_entries_from_list(
    all_target_list: list[object],
    match_predicate: Callable[[object], bool],
) -> int:
    """Remove every entry from a list that satisfies the predicate.

    Args:
        all_target_list: The list to filter in place.
        match_predicate: Function returning True for entries to remove.

    Returns:
        Number of entries removed.
    """
    original_length = len(all_target_list)
    all_target_list[:] = [
        each_value
        for each_value in all_target_list
        if not match_predicate(each_value)
    ]
    return original_length - len(all_target_list)


def load_settings(settings_path: Path) -> dict[str, object]:
    """Read and parse a JSON settings file from disk.

    Args:
        settings_path: Path to the JSON settings file.

    Returns:
        Parsed settings dictionary. Returns an empty dict when the file
        does not exist.

    Raises:
        SystemExit: When the file exists but is not valid JSON, or when
            its root value is not a JSON object.
    """
    if not settings_path.exists():
        return {}
    parsed_settings: dict[str, object] = {}
    try:
        raw_text = settings_path.read_text(encoding=TEXT_FILE_ENCODING)
    except OSError as read_error:
        exit_with_error(f"Failed to read {settings_path}: {read_error}")
    try:
        parsed_settings = json.loads(raw_text)
    except json.JSONDecodeError as decode_error:
        exit_with_error(
            f"Refusing to modify {settings_path}: existing file is not valid JSON "
            f"({decode_error}). Fix or back up the file manually, then re-run."
        )
    if not isinstance(parsed_settings, dict):
        exit_with_error(
            f"Refusing to modify {settings_path}: existing file's root is "
            f"{type(parsed_settings).__name__}, not a JSON object. Fix or back up "
            f"the file manually, then re-run."
        )
    return parsed_settings


def serialize_settings_to_json_text(all_settings: dict[str, object]) -> str:
    """Serialize a settings dictionary to JSON text with stable formatting.

    Args:
        all_settings: The settings dictionary to serialize.

    Returns:
        Pretty-printed JSON string with sorted keys.
    """
    json_indent_width_columns: int = len("  ")
    return json.dumps(
        all_settings,
        indent=json_indent_width_columns,
        sort_keys=True,
    )


def get_mode_to_preserve(settings_path: Path) -> int:
    """Return the file permission bits from an existing settings file.

    Args:
        settings_path: Path to the target settings file to stat.

    Returns:
        The permission bits from the file mode. Returns the default
        secure mode when the file does not exist.
    """
    default_settings_file_mode: int = 0o600
    try:
        stat_result = os.stat(settings_path)
    except FileNotFoundError:
        return default_settings_file_mode
    except OSError as stat_error:
        exit_with_error(f"Failed to stat {settings_path}: {stat_error}")
    return stat.S_IMODE(stat_result.st_mode)


def write_atomically_with_mode(
    temporary_path: Path, serialized_content: str, file_mode: int
) -> None:
    """Create and write to a temporary file with the given mode.

    Uses os.open with O_CREAT | O_EXCL to create the file securely, then
    writes the serialized content. The caller is responsible for replacing
    the target file with os.replace afterward.

    Args:
        temporary_path: Path for the temporary file (sibling of target).
        serialized_content: The content to write to the temporary file.
        file_mode: Unix permission bits for the new file.

    Raises:
        OSError: When os.open or os.fdopen fails. The raw file descriptor
            is closed before re-raising so the descriptor does not leak.
        MemoryError: When os.fdopen runs out of buffer memory; the file
            descriptor is closed before re-raising.
    """
    file_descriptor = os.open(
        str(temporary_path),
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        file_mode,
    )
    try:
        writer = os.fdopen(file_descriptor, "w", encoding=TEXT_FILE_ENCODING)
    except (OSError, MemoryError):
        os.close(file_descriptor)
        raise
    with writer:
        writer.write(serialized_content)


def save_settings(settings_path: Path, all_settings: dict[str, object]) -> None:
    """Write settings to a JSON file atomically with permission preservation.

    Creates a temporary sibling file, writes content, then atomically
    replaces the target. Cleans up the temporary file in a finally block.

    Args:
        settings_path: Path to the target settings JSON file.
        all_settings: The settings dictionary to serialize and save.
    """
    unique_temporary_suffix_byte_length = UNIQUE_TEMPORARY_SUFFIX_BYTE_LENGTH
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    serialized_settings = serialize_settings_to_json_text(all_settings)
    unique_temporary_suffix = (
        f".tmp.{os.getpid()}.{secrets.token_hex(unique_temporary_suffix_byte_length)}"
    )
    temporary_path = settings_path.with_suffix(
        settings_path.suffix + unique_temporary_suffix
    )
    mode_to_preserve = get_mode_to_preserve(settings_path)
    try:
        try:
            write_atomically_with_mode(
                temporary_path, serialized_settings, mode_to_preserve
            )
            os.replace(str(temporary_path), str(settings_path))
            os.chmod(str(settings_path), mode_to_preserve)
        except OSError as os_error:
            exit_with_error(
                f"Failed to write settings atomically to {settings_path}: {os_error}"
            )
    finally:
        if temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError:
                pass


def append_if_missing(all_target_list: list[object], new_value: str) -> bool:
    """Add a value to a list when it is not already present.

    Args:
        all_target_list: The list to potentially append to.
        new_value: The string value to add when missing.

    Returns:
        True when the value was appended, False when it already existed.
    """
    if new_value in all_target_list:
        return False
    all_target_list.append(new_value)
    return True


def ensure_dict_section(
    all_settings: dict[str, object], section_name: str
) -> dict[str, object]:
    """Return an existing dict section or create an empty one when absent.

    A missing key and an explicit JSON null are treated identically: both
    produce a fresh empty dict stored back into settings. Any other non-dict
    value (string, list, number, bool) calls exit_with_error to avoid
    overwriting user data.

    Args:
        all_settings: The parsed settings dictionary.
        section_name: Key name of the section to retrieve or create.

    Returns:
        The existing or newly created section dictionary.
    """
    existing_section = all_settings.get(section_name)
    if existing_section is None:
        replacement_section: dict[str, object] = {}
        all_settings[section_name] = replacement_section
        return replacement_section
    if not isinstance(existing_section, dict):
        exit_with_error(
            f"Refusing to modify settings key {section_name!r}: existing value "
            f"is {type(existing_section).__name__}, not a JSON object. Fix or "
            f"remove the key manually, then re-run."
        )
    return existing_section


def ensure_list_entry(all_section: dict[str, object], entry_name: str) -> list[object]:
    """Return an existing list entry or create an empty one when absent.

    A missing key and an explicit JSON null are treated identically: both
    produce a fresh empty list stored back into the section. Any other
    non-list value (string, dict, number, bool) calls exit_with_error to
    avoid overwriting user data.

    Args:
        all_section: The parent dictionary section.
        entry_name: Key name of the list entry to retrieve or create.

    Returns:
        The existing or newly created list entry.
    """
    existing_entry = all_section.get(entry_name)
    if existing_entry is None:
        replacement_entry: list[object] = []
        all_section[entry_name] = replacement_entry
        return replacement_entry
    if not isinstance(existing_entry, list):
        exit_with_error(
            f"Refusing to modify settings entry {entry_name!r}: existing value "
            f"is {type(existing_entry).__name__}, not a JSON array. Fix or "
            f"remove the entry manually, then re-run."
        )
    return existing_entry


def is_valid_project_root(candidate_path: Path) -> bool:
    git_marker_path = candidate_path / GIT_DIRECTORY_NAME
    claude_marker_path = candidate_path / CLAUDE_SETTINGS_DIRECTORY_NAME
    return git_marker_path.exists() or claude_marker_path.exists()


def prune_empty_list_then_empty_section(
    all_settings: dict[str, object], section_key: str, list_key: str
) -> None:
    """Remove an empty list key and its parent section when both are empty.

    Args:
        all_settings: The parsed settings dictionary to prune in place.
        section_key: Key of the parent section to check.
        list_key: Key of the list entry within the section.
    """
    section = all_settings.get(section_key)
    if not isinstance(section, dict):
        return
    list_entry = section.get(list_key)
    if isinstance(list_entry, list) and len(list_entry) == 0:
        del section[list_key]
    if len(section) == 0:
        del all_settings[section_key]
