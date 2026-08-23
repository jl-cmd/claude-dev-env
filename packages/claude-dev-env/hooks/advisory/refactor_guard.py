#!/usr/bin/env python3
"""Warn about refactors that reach beyond the current Edit change surface."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from hooks_constants.precommit_code_rules_gate_constants import GIT_COMMAND_TIMEOUT_SECONDS
from hooks_constants.python_style_checks_constants import MINIMUM_ARGUMENT_COUNT
from hooks_constants.session_edit_stage_gate_constants import GIT_EXECUTABLE_TOKEN

REFACTOR_BYPASS_TOKEN_PATH = Path.home() / ".claude" / ".refactor-bypass-token"
changed_surface_match_ratio = 0.5
identifier_join_separator = ", "


def _git_query_context(file_path: str) -> tuple[str, str]:
    target_path = Path(file_path).resolve()
    return str(target_path.parent), str(target_path)


def _read_added_lines_from_git(all_git_arguments: tuple[str, ...], file_path: str) -> set[str]:
    """Return added lines from one Git diff command."""
    working_directory, absolute_file_path = _git_query_context(file_path)
    try:
        completed_process = subprocess.run(
            [*all_git_arguments, "--", absolute_file_path],
            check=False,
            capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            cwd=working_directory,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return set()
    if completed_process.returncode != 0:
        return set()
    return {
        each_line[1:].strip()
        for each_line in completed_process.stdout.splitlines()
        if each_line.startswith("+") and not each_line.startswith("+++")
    }


def get_git_diff_added_lines(file_path: str) -> set[str]:
    """Return staged and unstaged added lines for a tracked file."""
    all_added_lines = _read_added_lines_from_git((GIT_EXECUTABLE_TOKEN, "diff"), file_path)
    all_added_lines.update(
        _read_added_lines_from_git((GIT_EXECUTABLE_TOKEN, "diff", "--cached"), file_path)
    )
    return all_added_lines


def is_new_file(file_path: str) -> bool:
    """Return whether Git reports the file as untracked."""
    working_directory, absolute_file_path = _git_query_context(file_path)
    try:
        completed_process = subprocess.run(
            [
                GIT_EXECUTABLE_TOKEN,
                "ls-files",
                "--others",
                "--exclude-standard",
                "--",
                absolute_file_path,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            cwd=working_directory,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
    return completed_process.returncode == 0 and bool(completed_process.stdout.strip())


def is_hook_infrastructure(file_path: str) -> bool:
    """Return whether a path belongs to the installed Claude hook tree."""
    normalized_path = file_path.lower().replace("\\", "/")
    return "/.claude/" in normalized_path


def extract_identifiers(code: str) -> set[str]:
    """Return meaningful Python identifiers from a code fragment."""
    all_identifiers = set(re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]{2,})\b", code))
    python_keywords = {
        "def",
        "class",
        "return",
        "import",
        "from",
        "if",
        "elif",
        "else",
        "for",
        "while",
        "try",
        "except",
        "finally",
        "with",
        "as",
        "yield",
        "raise",
        "pass",
        "break",
        "continue",
        "and",
        "or",
        "not",
        "in",
        "is",
        "lambda",
        "None",
        "True",
        "False",
        "self",
        "cls",
        "async",
        "await",
        "global",
        "nonlocal",
        "assert",
        "del",
        "print",
        "len",
        "range",
        "list",
        "dict",
        "set",
        "str",
        "int",
        "float",
        "bool",
        "type",
        "isinstance",
        "hasattr",
        "getattr",
        "setattr",
        "super",
        "property",
        "staticmethod",
        "classmethod",
        "abstractmethod",
        "Optional",
        "Union",
        "List",
        "Dict",
        "Set",
        "Tuple",
        "Any",
    }
    return all_identifiers - python_keywords


def _have_similar_words(old_identifier: str, new_identifier: str) -> bool:
    all_old_words = set(re.findall(r"[a-z]+|[A-Z][a-z]*", old_identifier))
    all_new_words = set(re.findall(r"[a-z]+|[A-Z][a-z]*", new_identifier))
    return (
        bool(all_old_words and all_new_words)
        and len(all_old_words & all_new_words) >= len(all_old_words) * changed_surface_match_ratio
    )


def _describe_identifier_changes(
    all_removed_identifiers: set[str], all_added_identifiers: set[str]
) -> str | None:
    all_renamed_identifiers: list[str] = []
    for each_old_identifier in sorted(all_removed_identifiers):
        for each_new_identifier in sorted(all_added_identifiers):
            is_same_spelling = each_old_identifier.lower().replace(
                "_", ""
            ) == each_new_identifier.lower().replace("_", "")
            if is_same_spelling or _have_similar_words(each_old_identifier, each_new_identifier):
                all_renamed_identifiers.append(f"{each_old_identifier} -> {each_new_identifier}")
                break
    if all_renamed_identifiers:
        return f"Renaming detected: {identifier_join_separator.join(all_renamed_identifiers[:3])}"
    if len(all_removed_identifiers) > 1 and len(all_added_identifiers) > 1:
        return (
            "Multiple identifiers changed with same structure: "
            f"removed {sorted(all_removed_identifiers)[:3]}, "
            f"added {sorted(all_added_identifiers)[:3]}"
        )
    return None


def is_refactor_edit(old_string: str, new_string: str) -> str | None:
    """Return a description when an edit preserves structure and changes names."""
    all_old_lines = [
        each_line.strip() for each_line in old_string.strip().splitlines() if each_line.strip()
    ]
    all_new_lines = [
        each_line.strip() for each_line in new_string.strip().splitlines() if each_line.strip()
    ]
    if not all_old_lines or not all_new_lines:
        return None
    if abs(len(all_old_lines) - len(all_new_lines)) > max(
        len(all_old_lines) // MINIMUM_ARGUMENT_COUNT, MINIMUM_ARGUMENT_COUNT + 1
    ):
        return None
    all_old_identifiers = extract_identifiers(old_string)
    all_new_identifiers = extract_identifiers(new_string)
    all_removed_identifiers = all_old_identifiers - all_new_identifiers
    all_added_identifiers = all_new_identifiers - all_old_identifiers
    if not all_removed_identifiers or not all_added_identifiers:
        return None
    all_identifiers = all_old_identifiers | all_new_identifiers
    old_structure = re.sub(r"\s+", " ", _replace_identifiers(old_string, all_identifiers).strip())
    new_structure = re.sub(r"\s+", " ", _replace_identifiers(new_string, all_identifiers).strip())
    if old_structure != new_structure:
        return None
    return _describe_identifier_changes(all_removed_identifiers, all_added_identifiers)


def _replace_identifiers(code: str, all_identifiers: set[str]) -> str:
    normalized_code = code
    for each_identifier in all_identifiers:
        normalized_code = normalized_code.replace(each_identifier, "ID")
    return normalized_code


def _nonempty_stripped_lines(text: str) -> set[str]:
    return {each_line.strip() for each_line in text.splitlines() if each_line.strip()}


def is_edit_within_changed_surface(file_path: str, old_string: str) -> bool:
    """Return whether at least half of the edited lines are current additions."""
    all_old_lines = _nonempty_stripped_lines(old_string)
    all_added_lines = get_git_diff_added_lines(file_path)
    if not all_old_lines or not all_added_lines:
        return False
    all_matching_lines = all_old_lines & all_added_lines
    return len(all_matching_lines) >= len(all_old_lines) * changed_surface_match_ratio


def _is_existing_edit_target(file_path: str) -> bool:
    if not file_path or is_hook_infrastructure(file_path):
        return False
    return not is_new_file(file_path)


def find_refactor_advisory_description(
    file_path: str, old_string: str, new_string: str
) -> str | None:
    """Return an advisory description for a refactor outside changed lines."""
    if not _is_existing_edit_target(file_path):
        return None
    refactor_description = is_refactor_edit(old_string, new_string)
    if refactor_description is None:
        return None
    if is_edit_within_changed_surface(file_path, old_string):
        return None
    return refactor_description


def is_refactor_eligible(file_path: str, old_string: str, new_string: str) -> bool:
    """Return whether an Edit is eligible for the refactor advisory."""
    return find_refactor_advisory_description(file_path, old_string, new_string) is not None


def is_bypass_approved() -> bool:
    """Consume the one-use bypass token when the user approved a refactor."""
    if not REFACTOR_BYPASS_TOKEN_PATH.exists():
        return False
    try:
        REFACTOR_BYPASS_TOKEN_PATH.unlink()
    except OSError:
        return False
    return True


def build_refactor_advisory_context(refactor_description: str, file_path: str) -> str:
    """Build guidance that names the Edit stage and changed-surface rule."""
    return (
        f"[HOOK ADVISORY] Refactor guard — {refactor_description} in {file_path}. "
        "Edit-stage guidance: Only modify lines already changed in the current git diff. "
        "Ask the user for explicit approval first. If the user approves, "
        "create the bypass token then retry."
    )


def build_refactor_advisory_payload(refactor_description: str, file_path: str) -> dict[str, object]:
    """Build the standalone allow payload used by the Edit advisory hook."""
    advisory_context = build_refactor_advisory_context(refactor_description, file_path)
    return {
        "systemMessage": advisory_context,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "additionalContext": advisory_context,
        },
    }


def _read_hook_input() -> dict[str, object] | None:
    try:
        parsed_input = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed_input, dict):
        return None
    return {str(each_key): each_field for each_key, each_field in parsed_input.items()}


def _read_edit_fields(payload_by_key: dict[str, object]) -> tuple[str, str, str, str]:
    raw_tool_name = payload_by_key.get("tool_name")
    tool_name = raw_tool_name if isinstance(raw_tool_name, str) else ""
    raw_tool_input = payload_by_key.get("tool_input")
    if not isinstance(raw_tool_input, dict):
        return tool_name, "", "", ""
    tool_input_by_key: dict[str, object] = {}
    for each_key, each_field in raw_tool_input.items():
        tool_input_by_key[str(each_key)] = each_field
    file_path_field = tool_input_by_key.get("file_path")
    old_string_field = tool_input_by_key.get("old_string")
    new_string_field = tool_input_by_key.get("new_string")
    if not isinstance(file_path_field, str):
        return tool_name, "", "", ""
    if not isinstance(old_string_field, str):
        return tool_name, "", "", ""
    if not isinstance(new_string_field, str):
        return tool_name, "", "", ""
    return tool_name, file_path_field, old_string_field, new_string_field


def main() -> None:
    """Emit an Edit-stage advisory for eligible out-of-surface refactors."""
    payload_by_key = _read_hook_input()
    if payload_by_key is None:
        return
    tool_name, file_path, old_string, new_string = _read_edit_fields(payload_by_key)
    if tool_name != "Edit" or is_bypass_approved():
        return
    refactor_description = find_refactor_advisory_description(file_path, old_string, new_string)
    if refactor_description is None:
        return
    advisory_payload = build_refactor_advisory_payload(refactor_description, file_path)
    sys.stdout.write(json.dumps(advisory_payload))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
