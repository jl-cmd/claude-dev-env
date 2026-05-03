#!/usr/bin/env python3
"""PreToolUse hook: rewrite es.exe commands by substituting registry tokens with absolute paths.

Reads tool_input.command from stdin JSON. When the command invokes the Everything
command-line binary, substitutes {project-name} placeholder tokens and bare registry-key
tokens with their quoted absolute paths from ~/.claude/project-paths.json before
the Bash call runs. Never blocks or denies — on any error exits 0 with empty output.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath


def _insert_hooks_tree_for_imports() -> None:
    hooks_tree = Path(__file__).resolve().parent.parent
    hooks_tree_string = str(hooks_tree)
    if hooks_tree_string not in sys.path:
        sys.path.insert(0, hooks_tree_string)


_insert_hooks_tree_for_imports()

from config.dynamic_stderr_handler import DynamicStderrHandler
from config.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin
from config.path_rewriter_constants import (
    BASH_TOOL_NAME,
    HOOK_EVENT_NAME,
    PERMISSION_ALLOW,
    PLACEHOLDER_TOKEN_PATTERN,
)
from config.project_paths_reader import load_registry

_ES_EXE_TRIGGER_PATTERN = re.compile(
    r"(?i)(?<![\w.])(?:Everything[/\\])?es\.exe(?![\w.])",
)


_logger = logging.getLogger("es_exe_path_rewriter")
if not _logger.handlers:
    _stderr_handler = DynamicStderrHandler()
    _stderr_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    _logger.addHandler(_stderr_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def command_invokes_es_exe(command: str) -> bool:
    """Return True when the command string contains an es.exe invocation."""
    return bool(_ES_EXE_TRIGGER_PATTERN.search(command))


def _token_is_absolute_path(token: str) -> bool:
    stripped = token.strip("\"'")
    try:
        return (
            PureWindowsPath(stripped).is_absolute()
            or PurePosixPath(stripped).is_absolute()
        )
    except (ValueError, TypeError):
        return False


def _quote_path(absolute_path: str) -> str:
    return f'"{absolute_path}"'


def _rewrite_placeholder_tokens(command_suffix: str, registry: dict[str, str]) -> str:
    def replace_placeholder(match: re.Match) -> str:
        inner_name = match.group(1)
        if inner_name not in registry:
            return match.group(0)
        return _quote_path(registry[inner_name])

    return PLACEHOLDER_TOKEN_PATTERN.sub(replace_placeholder, command_suffix)


def _split_on_es_exe(command: str) -> tuple[str, str]:
    match = _ES_EXE_TRIGGER_PATTERN.search(command)
    if not match:
        return command, ""
    return command[: match.end()], command[match.end() :]


def _strip_matching_outer_quotes(token: str) -> tuple[str, bool]:
    """Return (inner_text, was_quoted) after removing matched outer quotes."""
    if len(token) > 1 and token[0] in ('"', "'") and token[-1] == token[0]:
        return token[1:-1], True
    return token, False


def _rewrite_bare_tokens(command_suffix: str, registry: dict[str, str]) -> str:
    all_raw_parts = re.split(r"(\s+)", command_suffix)
    all_rewritten_parts: list[str] = []
    for each_raw_part in all_raw_parts:
        if not each_raw_part or each_raw_part.isspace():
            all_rewritten_parts.append(each_raw_part)
            continue
        unquoted_text, _was_quoted = _strip_matching_outer_quotes(each_raw_part)
        if unquoted_text in registry and not _token_is_absolute_path(unquoted_text):
            all_rewritten_parts.append(_quote_path(registry[unquoted_text]))
        else:
            all_rewritten_parts.append(each_raw_part)
    return "".join(all_rewritten_parts)


def rewrite_command(command: str, registry: dict[str, str]) -> str:
    """Apply registry substitutions to any es.exe argument tokens.

    Applies placeholder form {name} first, then bare-token form.
    Absolute-path arguments and unknown tokens are left untouched.
    Returns the original command when no substitution applies.
    """
    if not registry:
        return command
    prefix, suffix = _split_on_es_exe(command)
    rewritten_suffix = _rewrite_placeholder_tokens(suffix, registry)
    rewritten_suffix = _rewrite_bare_tokens(rewritten_suffix, registry)
    return prefix + rewritten_suffix


def _build_allow_response(rewritten_command: str, original_tool_input: dict) -> dict:
    updated_input = {**original_tool_input, "command": rewritten_command}
    return {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": PERMISSION_ALLOW,
            "updatedInput": updated_input,
        }
    }


def main() -> None:
    try:
        hook_input = read_hook_input_dictionary_from_stdin()
        if hook_input is None:
            sys.exit(0)
        tool_name = hook_input.get("tool_name", "")
        if tool_name != BASH_TOOL_NAME:
            sys.exit(0)
        tool_input = hook_input.get("tool_input", {})
        command = tool_input.get("command", "")
        if not command_invokes_es_exe(command):
            sys.exit(0)
        known_registry = load_registry()
        if not known_registry:
            sys.exit(0)
        rewritten_command = rewrite_command(command, known_registry)
        if rewritten_command == command:
            sys.exit(0)
        print(json.dumps(_build_allow_response(rewritten_command, tool_input)))
    except Exception as e:
        _logger.error("%s", e)
    sys.exit(0)


if __name__ == "__main__":
    main()
