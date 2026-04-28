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

_WRITE_EDIT_TOOL_NAMES = {"Write", "Edit"}
_BASH_TOOL_NAME = "Bash"

_RMTREE_IGNORE_ERRORS_PATTERN = re.compile(
    r"shutil\s*\.\s*rmtree\s*\([^)]*\bignore_errors\s*=\s*True\b",
    re.DOTALL,
)

_CORRECTIVE_MESSAGE = (
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


def payload_contains_unsafe_rmtree(payload_text: str) -> bool:
    if not payload_text:
        return False
    return bool(_RMTREE_IGNORE_ERRORS_PATTERN.search(payload_text))


def extract_payload_text(tool_name: str, tool_input: dict) -> str:
    if tool_name in _WRITE_EDIT_TOOL_NAMES:
        return tool_input.get("content", "") or tool_input.get("new_string", "") or ""
    if tool_name == _BASH_TOOL_NAME:
        return tool_input.get("command", "") or ""
    return ""


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
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
            "permissionDecisionReason": _CORRECTIVE_MESSAGE,
        }
    }
    print(json.dumps(deny_response))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
