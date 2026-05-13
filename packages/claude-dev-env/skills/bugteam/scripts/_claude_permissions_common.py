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
import stat
import sys
from pathlib import Path
from typing import NoReturn

_previously_cached_config = {}
for each_cached_module_name in [
    each_module_key
    for each_module_key in list(sys.modules)
    if each_module_key == "config" or each_module_key.startswith("config.")
]:
    _previously_cached_config[each_cached_module_name] = sys.modules.pop(
        each_cached_module_name
    )

from config.claude_permissions_common_constants import (
    ATOMIC_WRITE_TEMPORARY_SUFFIX,
    DEFAULT_SETTINGS_FILE_MODE,
    TEXT_FILE_ENCODING,
)

sys.modules.update(_previously_cached_config)


def exit_with_error(message: str) -> NoReturn:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(1)


def path_contains_glob_metacharacters(candidate_path: str) -> bool:
    """Check whether a path contains characters reserved for glob patterns.

    Args:
        candidate_path: The file path string to inspect.

    Returns:
        True when any glob metacharacter is present in the path.
    """
    glob_metacharacters_in_path: tuple[str, ...] = (
        "*",
        "?",
        "[",
        "]",
        "(",
        ")",
        "{",
        "}",
        ",",
    )
    return any(
        each_character in candidate_path
        for each_character in glob_metacharacters_in_path
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
        The permission bits from the file mode (lower portion).
        Returns DEFAULT_SETTINGS_FILE_MODE when the file does not exist.
    """
    try:
        stat_result = os.stat(settings_path)
    except FileNotFoundError:
        return DEFAULT_SETTINGS_FILE_MODE
    except OSError as stat_error:
        exit_with_error(f"Failed to stat {settings_path}: {stat_error}")
    return stat.S_IMODE(stat_result.st_mode)


def write_atomically_with_mode(
    temporary_path: Path, serialized_content: str, file_mode: int
) -> None:
    """Create and write to a temporary file with the given mode.

    Uses os.open with O_CREAT | O_EXCL to create the file securely,
    then writes the serialized content. The caller is responsible for
    replacing the target file with os.replace afterward.

    Args:
        temporary_path: Path for the temporary file (sibling of target).
        serialized_content: The content to write to the temporary file.
        file_mode: Unix permission bits for the new file (e.g., 0o600).

    Raises:
        OSError: When os.open or os.fdopen fails. The raw file descriptor
            is closed before re-raising so the FD does not leak.
        MemoryError: When os.fdopen runs out of buffer memory; the FD is
            closed before re-raising.
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
        try:
            os.unlink(str(temporary_path))
        except OSError:
            pass
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
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    serialized_settings = serialize_settings_to_json_text(all_settings)
    process_keyed_temporary_suffix = (
        f"{ATOMIC_WRITE_TEMPORARY_SUFFIX}.{os.getpid()}"
    )
    temporary_path = settings_path.with_suffix(
        settings_path.suffix + process_keyed_temporary_suffix
    )
    mode_to_preserve = get_mode_to_preserve(settings_path)
    is_temp_owned_by_this_invocation = False
    try:
        try:
            write_atomically_with_mode(
                temporary_path, serialized_settings, mode_to_preserve
            )
            is_temp_owned_by_this_invocation = True
            os.replace(str(temporary_path), str(settings_path))
            is_temp_owned_by_this_invocation = False
        except OSError as os_error:
            exit_with_error(
                f"Failed to write settings atomically to {settings_path}: {os_error}"
            )
    finally:
        if is_temp_owned_by_this_invocation and temporary_path.exists():
            try:
                temporary_path.unlink()
            except OSError as unlink_error:
                print(
                    f"Warning: could not remove temp file {temporary_path}: "
                    f"{type(unlink_error).__name__}: {unlink_error}",
                    file=sys.stderr,
                )


def append_if_missing(all_target_list: list[object], new_value: str) -> bool:
    """Add a value to a list if it is not already present.

    Args:
        all_target_list: The list to potentially append to.
        new_value: The string value to add if missing.

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
    """Return an existing dict section or create an empty one if absent.

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


def ensure_list_entry(
    all_section: dict[str, object], entry_name: str
) -> list[object]:
    """Return an existing list entry or create an empty one if absent.

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


def prune_empty_list_then_empty_section(
    all_settings: dict[str, object], section_key: str, list_key: str
) -> None:
    """Remove an empty list key and its parent section if both are empty.

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
