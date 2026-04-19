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


TEXT_FILE_ENCODING: str = "utf-8"
PERMISSION_ALLOW_TOOLS: tuple[str, ...] = ("Edit", "Write", "Read")

AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE: str = (
    "Trusted local workspace: {project_path}/.claude/** is the user's "
    "project Claude Code config tree; edits inside are routine"
)


def exit_with_error(message: str) -> NoReturn:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(1)


def path_contains_glob_metacharacters(candidate_path: str) -> bool:
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
    project_path: str, permission_allow_tools: tuple[str, ...]
) -> list[str]:
    return [
        build_permission_rule(each_tool, project_path)
        for each_tool in permission_allow_tools
    ]


def load_settings(settings_path: Path) -> dict[str, object]:
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


def serialize_settings_to_json_text(settings: dict[str, object]) -> str:
    json_indent_width_columns: int = len("  ")
    return json.dumps(
        settings,
        indent=json_indent_width_columns,
        sort_keys=True,
    )


def get_mode_to_preserve(settings_path: Path) -> int:
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
    file_descriptor = os.open(
        str(temporary_path),
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        file_mode,
    )
    with os.fdopen(file_descriptor, "w", encoding=TEXT_FILE_ENCODING) as writer:
        writer.write(serialized_content)


def save_settings(settings_path: Path, settings: dict[str, object]) -> None:
    atomic_write_temporary_suffix: str = ".tmp"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    serialized_settings = serialize_settings_to_json_text(settings)
    temporary_path = settings_path.with_suffix(
        settings_path.suffix + atomic_write_temporary_suffix
    )
    mode_to_preserve = get_mode_to_preserve(settings_path)
    try:
        try:
            write_atomically_with_mode(
                temporary_path, serialized_settings, mode_to_preserve
            )
            os.replace(str(temporary_path), str(settings_path))
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


def append_if_missing(target_list: list[object], new_value: str) -> bool:
    if new_value in target_list:
        return False
    target_list.append(new_value)
    return True


def ensure_dict_section(
    settings: dict[str, object], section_name: str
) -> dict[str, object]:
    """Return an existing dict section or create an empty one if absent.

    A missing key and an explicit JSON null are treated identically: both
    produce a fresh empty dict stored back into settings. Any other non-dict
    value (string, list, number, bool) calls exit_with_error to avoid
    overwriting user data.
    """
    existing_section = settings.get(section_name)
    if existing_section is None:
        replacement_section: dict[str, object] = {}
        settings[section_name] = replacement_section
        return replacement_section
    if not isinstance(existing_section, dict):
        exit_with_error(
            f"Refusing to modify settings key {section_name!r}: existing value "
            f"is {type(existing_section).__name__}, not a JSON object. Fix or "
            f"remove the key manually, then re-run."
        )
    return existing_section


def ensure_list_entry(section: dict[str, object], entry_name: str) -> list[object]:
    """Return an existing list entry or create an empty one if absent.

    A missing key and an explicit JSON null are treated identically: both
    produce a fresh empty list stored back into the section. Any other
    non-list value (string, dict, number, bool) calls exit_with_error to
    avoid overwriting user data.
    """
    existing_entry = section.get(entry_name)
    if existing_entry is None:
        replacement_entry: list[object] = []
        section[entry_name] = replacement_entry
        return replacement_entry
    if not isinstance(existing_entry, list):
        exit_with_error(
            f"Refusing to modify settings entry {entry_name!r}: existing value "
            f"is {type(existing_entry).__name__}, not a JSON array. Fix or "
            f"remove the entry manually, then re-run."
        )
    return existing_entry


def prune_empty_list_then_empty_section(
    settings: dict[str, object], section_key: str, list_key: str
) -> None:
    section = settings.get(section_key)
    if not isinstance(section, dict):
        return
    list_entry = section.get(list_key)
    if isinstance(list_entry, list) and len(list_entry) == 0:
        del section[list_key]
    if len(section) == 0:
        del settings[section_key]
