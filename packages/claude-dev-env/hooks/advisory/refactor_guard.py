#!/usr/bin/env python3
"""
Refactor guard - blocks edits that rename/restructure existing code not in the git diff.

Detects when an Edit tool call is modifying existing code (renaming variables,
functions, restructuring) rather than writing new code or replacing wholesale.

Only fires for Edit operations (not Write, which creates/replaces entire files).
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

REFACTOR_BYPASS_TOKEN_PATH = Path.home() / ".claude" / ".refactor-bypass-token"


def get_git_diff_added_lines(file_path: str) -> set[str]:
    """Get the set of added lines (stripped) from git diff for a file."""
    added_lines: set[str] = set()
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", file_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.split("\n"):
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.add(line[1:].strip())

        staged_result = subprocess.run(
            ["git", "diff", "--staged", "--", file_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in staged_result.stdout.split("\n"):
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.add(line[1:].strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return set()
    return added_lines


def is_new_file(file_path: str) -> bool:
    """Check if file is untracked (entirely new)."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "--", file_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def is_hook_infrastructure(file_path: str) -> bool:
    """Check if file is a Claude Code hook."""
    path_lower = file_path.lower().replace("\\", "/")
    return "/.claude/" in path_lower


def extract_identifiers(code: str) -> set[str]:
    """Extract meaningful identifiers (variable/function/class names) from code."""
    identifier_pattern = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]{2,})\b')
    identifiers = set(identifier_pattern.findall(code))
    python_keywords = {
        "def", "class", "return", "import", "from", "if", "elif", "else",
        "for", "while", "try", "except", "finally", "with", "as", "yield",
        "raise", "pass", "break", "continue", "and", "or", "not", "in",
        "is", "lambda", "None", "True", "False", "self", "cls", "async",
        "await", "global", "nonlocal", "assert", "del", "print", "len",
        "range", "list", "dict", "set", "str", "int", "float", "bool",
        "type", "isinstance", "hasattr", "getattr", "setattr", "super",
        "property", "staticmethod", "classmethod", "abstractmethod",
        "Optional", "Union", "List", "Dict", "Set", "Tuple", "Any",
    }
    return identifiers - python_keywords


def is_refactor_edit(old_string: str, new_string: str) -> Optional[str]:
    """Detect if an edit is a rename/refactor rather than a functional change.

    Returns a description of the refactor if detected, None otherwise.
    """
    old_lines = [line.strip() for line in old_string.strip().split("\n") if line.strip()]
    new_lines = [line.strip() for line in new_string.strip().split("\n") if line.strip()]

    if not old_lines or not new_lines:
        return None

    if abs(len(old_lines) - len(new_lines)) > max(len(old_lines) // 2, 3):
        return None

    old_identifiers = extract_identifiers(old_string)
    new_identifiers = extract_identifiers(new_string)

    removed_identifiers = old_identifiers - new_identifiers
    added_identifiers = new_identifiers - old_identifiers

    if not removed_identifiers or not added_identifiers:
        return None

    old_no_ids = old_string
    new_no_ids = new_string
    for identifier in old_identifiers | new_identifiers:
        old_no_ids = old_no_ids.replace(identifier, "ID")
        new_no_ids = new_no_ids.replace(identifier, "ID")

    old_structure = re.sub(r'\s+', ' ', old_no_ids.strip())
    new_structure = re.sub(r'\s+', ' ', new_no_ids.strip())

    if old_structure == new_structure:
        renamed = []
        for old_id in sorted(removed_identifiers):
            for new_id in sorted(added_identifiers):
                if old_id.lower().replace("_", "") == new_id.lower().replace("_", ""):
                    renamed.append(f"{old_id} -> {new_id}")
                    break
                old_words = set(re.findall(r'[a-z]+|[A-Z][a-z]*', old_id))
                new_words = set(re.findall(r'[a-z]+|[A-Z][a-z]*', new_id))
                if old_words and new_words and len(old_words & new_words) >= len(old_words) * 0.5:
                    renamed.append(f"{old_id} -> {new_id}")
                    break

        if renamed:
            return f"Renaming detected: {', '.join(renamed[:3])}"

        if len(removed_identifiers) >= 2 and len(added_identifiers) >= 2:
            return f"Multiple identifiers changed with same structure: removed {sorted(removed_identifiers)[:3]}, added {sorted(added_identifiers)[:3]}"

    return None


def is_bypass_approved() -> bool:
    """Check if user explicitly approved a refactor bypass via one-time token file.

    The token file is deleted after a single use, so each refactor
    requires fresh explicit approval from the user.
    """
    if REFACTOR_BYPASS_TOKEN_PATH.exists():
        REFACTOR_BYPASS_TOKEN_PATH.unlink()
        return True
    return False


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Edit":
        sys.exit(0)

    if is_bypass_approved():
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    old_string = tool_input.get("old_string", "")
    new_string = tool_input.get("new_string", "")

    if not file_path or not old_string or not new_string:
        sys.exit(0)

    if is_hook_infrastructure(file_path):
        sys.exit(0)

    if is_new_file(file_path):
        sys.exit(0)

    refactor_description = is_refactor_edit(old_string, new_string)
    if not refactor_description:
        sys.exit(0)

    diff_added_lines = get_git_diff_added_lines(file_path)

    old_lines_stripped = {line.strip() for line in old_string.split("\n") if line.strip()}
    old_lines_in_diff = old_lines_stripped & diff_added_lines

    if old_lines_in_diff and len(old_lines_in_diff) >= len(old_lines_stripped) * 0.5:
        sys.exit(0)

    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "additionalContext": f"[HOOK ADVISORY] Refactor guard — {refactor_description} in {file_path}. Only modify lines already changed in the current git diff. Ask the user for explicit approval first. If the user approves, create the bypass token then retry.",
        }
    }
    print(json.dumps(result))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
