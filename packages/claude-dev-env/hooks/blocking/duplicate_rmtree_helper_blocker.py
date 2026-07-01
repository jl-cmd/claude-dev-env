#!/usr/bin/env python3
"""PreToolUse hook: block a local re-definition of the Windows-safe rmtree helper trio.

The Windows-safe deletion helper trio — `_strip_read_only_and_retry`,
`_force_remove_tree`/`force_rmtree`, and the `inspect.signature` onexc/onerror guard —
is the sanctioned pattern for removing a directory tree that may hold ReadOnly files.
Because the windows_rmtree_blocker corrective message ships the trio as a paste-ready
snippet, agents paste a fresh local copy into each module that needs cleanup. Three
near-matching copies already span one codebase (a parser service, a categorizer, and a
test isolation helper), so a fix to one copy never reaches the others — the exact
"duplicated logic drifts" failure CODE_RULES.md section 3 (Reuse before create) names.

This hook scans Write/Edit content to a Python file for a `def` of any sanctioned
helper name and blocks it with a corrective message pointing to a single shared
force_rmtree utility. The canonical shared-helper home, the rmtree-blocker hook
sources (whose corrective strings embed the snippet), and test files are exempt.

This complements the same-directory `check_duplicate_function_body_across_files`
gate, which compares a written function only against `.py` siblings in its own
directory. That scope leaves a copy of this trio between two distant packages
unguarded, which is how the copies above spread. Keying on the sanctioned helper
names blocks the cross-directory copy the structural same-directory check cannot
reach.
"""

import json
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.duplicate_rmtree_helper_blocker_constants import (  # noqa: E402
    ALL_EXEMPT_PATH_FRAGMENTS,
    ALL_EXEMPT_TEST_FILE_PREFIXES,
    ALL_EXEMPT_TEST_FILE_SUFFIXES,
    HELPER_DEFINITION_PATTERN,
    PYTHON_FILE_EXTENSION,
    TRIPLE_QUOTED_STRING_PATTERN,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin  # noqa: E402


def payload_defines_sanctioned_helper(payload_text: str) -> bool:
    """Return True when the text defines a sanctioned Windows-safe rmtree helper.

    Args:
        payload_text: The file content or new_string fragment under inspection.

    Returns:
        True when a line defines `_strip_read_only_and_retry`, `_force_remove_tree`,
        or `force_rmtree`. Triple-quoted string bodies are masked before the
        line-anchored pattern runs, so a `def` that begins its own line inside a
        documentation snippet or multi-line string literal is left untouched. A
        helper name inside a single-line quoted string carries a quote before `def`,
        so the line-anchored pattern leaves it untouched as well.
    """
    if not payload_text:
        return False
    masked_text = TRIPLE_QUOTED_STRING_PATTERN.sub("", payload_text)
    return bool(HELPER_DEFINITION_PATTERN.search(masked_text))


def path_is_exempt(file_path: str) -> bool:
    """Return True when a Python path may carry the helper definition.

    Args:
        file_path: The target path the Write/Edit writes to.

    Returns:
        True when the path's basename is the canonical shared-helper home, an
        rmtree-blocker hook source, one of the existing in-repo definition sites
        (session_env_cleanup.py, _md_to_html_blocker_test_support.py,
        teardown_worktrees.py), or a test file. A definition there is intentional.
        Basename equality (not substring containment) prevents a sibling whose name
        merely contains an exempt fragment from bypassing the block.
    """
    normalized_path = file_path.replace("\\", "/")
    file_name = normalized_path.rsplit("/", 1)[-1]
    if any(file_name.startswith(each_prefix) for each_prefix in ALL_EXEMPT_TEST_FILE_PREFIXES):
        return True
    if any(file_name.endswith(each_suffix) for each_suffix in ALL_EXEMPT_TEST_FILE_SUFFIXES):
        return True
    return file_name in ALL_EXEMPT_PATH_FRAGMENTS


def extract_payload_text(tool_name: str, tool_input: dict) -> tuple[str, str]:
    """Return the (file_path, scanned_text) pair for a Write/Edit to a Python file.

    Args:
        tool_name: The PreToolUse tool name.
        tool_input: The tool input dictionary.

    Returns:
        A pair of the target path and the text to scan. The text is empty for an
        unrelated tool or a non-Python target, so the caller exits without blocking.
    """
    if tool_name not in {"Write", "Edit"}:
        return "", ""
    file_path = tool_input.get("file_path", "") or ""
    if file_path and not file_path.endswith(PYTHON_FILE_EXTENSION):
        return file_path, ""
    scanned_text = tool_input.get("content", "") or tool_input.get("new_string", "") or ""
    return file_path, scanned_text


def main() -> None:
    corrective_message = (
        "BLOCKED [duplicate-rmtree-helper]: this Write/Edit defines a local copy of "
        "the Windows-safe rmtree helper trio (_strip_read_only_and_retry, "
        "_force_remove_tree / force_rmtree). The trio is already implemented once; a "
        "second copy drifts from the original — a fix lands in one copy and the other "
        "keeps the bug (CODE_RULES.md section 3, Reuse before create).\n\n"
        "Import the shared force_rmtree helper rather than pasting the trio:\n\n"
        "    from <shared_package>.windows_filesystem import force_rmtree\n"
        "    force_rmtree(staging_directory)\n\n"
        "When no shared helper module exists yet, create ONE — a windows-filesystem "
        "utility module the consuming packages can import — define the trio there once, "
        "and import it from every call site. Do not paste the trio from the "
        "windows_rmtree_blocker corrective message into each module.\n\n"
        "See ~/.claude/rules/windows-filesystem-safe.md for the sanctioned pattern."
    )
    hook_input = read_hook_input_dictionary_from_stdin()
    if hook_input is None:
        sys.exit(0)

    raw_tool_name = hook_input.get("tool_name", "")
    raw_tool_input = hook_input.get("tool_input", {})
    tool_name = raw_tool_name if isinstance(raw_tool_name, str) else ""
    tool_input = raw_tool_input if isinstance(raw_tool_input, dict) else {}

    file_path, scanned_text = extract_payload_text(tool_name, tool_input)

    if not scanned_text:
        sys.exit(0)
    if path_is_exempt(file_path):
        sys.exit(0)
    if not payload_defines_sanctioned_helper(scanned_text):
        sys.exit(0)

    deny_response = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": corrective_message,
        }
    }
    log_hook_block(
        calling_hook_name="duplicate_rmtree_helper_blocker.py",
        hook_event="PreToolUse",
        block_reason=corrective_message,
        tool_name=tool_name,
    )
    print(json.dumps(deny_response))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
