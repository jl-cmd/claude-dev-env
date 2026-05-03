#!/usr/bin/env python3
"""PreToolUse hook: block shutil.rmtree(..., ignore_errors=True).

shutil.rmtree on Windows raises PermissionError when it encounters a file carrying
the ReadOnly attribute (FILE_ATTRIBUTE_READONLY). With ignore_errors=True the failure
is silently swallowed and the tree stays on disk — cleanup looks successful but
pruned nothing. Linux never hits this because unlink on Linux only needs write on
the parent directory, not on the file itself. Tests run inside pytest's tmp_path
do not exercise the regression path because tmp dirs do not carry the attribute.

This hook scans Write/Edit content and Bash commands for the dangerous pattern and
blocks it with a corrective message pointing to the force_rmtree replacement.
"""

import json
import re
import sys
from pathlib import Path


def _insert_hooks_tree_for_imports() -> None:
    hooks_tree = Path(__file__).resolve().parent.parent
    hooks_tree_string = str(hooks_tree)
    if hooks_tree_string not in sys.path:
        sys.path.insert(0, hooks_tree_string)


_insert_hooks_tree_for_imports()

from config.windows_rmtree_blocker_constants import PYTHON_FILE_EXTENSION


def payload_contains_unsafe_rmtree(payload_text: str) -> bool:
    if not payload_text:
        return False
    rmtree_ignore_errors_pattern = re.compile(
        r"shutil\s*\.\s*rmtree\s*\(.*?\bignore_errors\s*=\s*True\b",
        re.DOTALL,
    )
    return bool(rmtree_ignore_errors_pattern.search(payload_text))


def extract_payload_text(tool_name: str, tool_input: dict) -> str:
    if tool_name in {"Write", "Edit"}:
        file_path = tool_input.get("file_path", "")
        if file_path and not file_path.endswith(PYTHON_FILE_EXTENSION):
            return ""
        return tool_input.get("content", "") or tool_input.get("new_string", "") or ""
    if tool_name == "Bash":
        return tool_input.get("command", "") or ""
    return ""


def main() -> None:
    corrective_message = (
        "BLOCKED [windows-rmtree]: shutil.rmtree(..., ignore_errors=True) silently "
        "fails on Windows when a file carries the ReadOnly attribute "
        "(FILE_ATTRIBUTE_READONLY). The PermissionError is swallowed and the tree "
        "stays on disk -- cleanup looks successful but removes nothing. Linux is "
        "unaffected because unlink only needs write on the parent directory.\n\n"
        "Use a Windows-safe handler that strips the attribute and retries the "
        "syscall:\n\n"
        "    import os\n"
        "    import shutil\n"
        "    import stat\n"
        "    import sys\n\n"
        "    def _strip_read_only_and_retry(removal_function, target_path, *_exc_info):\n"
        "        try:\n"
        "            os.chmod(target_path, stat.S_IWRITE)\n"
        "            removal_function(target_path)\n"
        "        except OSError:\n"
        "            pass\n\n"
        "    def force_rmtree(target_path: str) -> None:\n"
        "        handler_kw = (\n"
        '            {"onexc": _strip_read_only_and_retry}\n'
        "            if sys.version_info >= (3, 12)\n"
        '            else {"onerror": _strip_read_only_and_retry}\n'
        "        )\n"
        "        try:\n"
        "            shutil.rmtree(target_path, **handler_kw)\n"
        "        except OSError:\n"
        "            pass\n\n"
        "Two things to know about the handler:\n"
        "  - *_exc_info collapses the signature difference. onerror passes "
        "(type, value, traceback); onexc (Python 3.12+) passes a single exception.\n"
        "  - removal_function is whichever syscall rmtree was attempting "
        "(os.unlink for files, os.rmdir for dirs). Re-call it after chmod to finish "
        "the work that originally failed.\n\n"
        "See ~/.claude/rules/windows-filesystem-safe.md for full guidance."
    )
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.stderr.write("windows_rmtree_blocker: malformed JSON on stdin\n")
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    payload_text = extract_payload_text(tool_name, tool_input)

    if not payload_contains_unsafe_rmtree(payload_text):
        sys.exit(0)

    deny_response = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": corrective_message,
        }
    }
    print(json.dumps(deny_response))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
