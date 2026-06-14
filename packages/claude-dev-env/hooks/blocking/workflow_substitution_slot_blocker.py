#!/usr/bin/env python3
"""PreToolUse hook: block bare per-iteration index tokens in .workflow.js templates.

Root cause: a `.workflow.js` agent-prompt block that loops over an index (for
example "For EACH candidate i, build a dir cand_i ...") sometimes writes the
per-iteration directory or output key as a bare token like `cand_i`. A bare
`_i`-suffixed token reads as a fixed literal rather than a substitution slot, so
an agent can plausibly create one literal directory named `cand_i` and overwrite
it across every iteration -- collapsing an N-iteration gate into a single run.

The established convention in these templates marks every per-call substitution
slot with angle brackets (`<plate.svg>`, `<object.svg>`, `<glow_hex>`). The fix
is to mark the index the same way: `cand_<i>`.

Detection strategy: act only on Write/Edit to a path ending in `.workflow.js`.
Within the written content, fire only when ALL of the following hold, so the
hook catches exactly the bare-literal shape and never a template that does not
use the substitution convention at all:

  1. the content uses the angle-bracket substitution convention somewhere
     (a `<...>` slot), proving the author marks per-call values that way;
  2. the content establishes a per-iteration loop (an "each"/"EACH"/"for i"
     style phrase, or an explicit `cand_0` enumeration);
  3. a bare `<word>_<i|j|k>` token appears as a per-iteration path segment
     (adjacent to a path separator). A quoted structured-output key whose name
     ends in `_i|_j|_k` (a permanent identifier with no per-iteration path) does
     not fire on its own; only the per-iteration path shape triggers a block.

Fails OPEN (approves) on malformed input or a non-workflow path; the violation
shape is narrow enough that a false negative is preferable to blocking
unrelated edits.
"""

import json
import re
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.workflow_substitution_slot_blocker_constants import (  # noqa: E402
    CORRECTIVE_MESSAGE,
    EDIT_TOOL_NAME,
    MULTI_EDIT_TOOL_NAME,
    WORKFLOW_FILE_SUFFIX,
    WRITE_TOOL_NAME,
)

def multi_edit_new_strings(all_tool_input: dict[str, object]) -> str:
    all_edits = all_tool_input.get("edits", [])
    if not isinstance(all_edits, list):
        return ""
    all_new_strings = [
        each_edit["new_string"]
        for each_edit in all_edits
        if isinstance(each_edit, dict) and isinstance(each_edit.get("new_string"), str)
    ]
    return "\n".join(all_new_strings)


def written_content(tool_name: str, all_tool_input: dict[str, object]) -> str:
    if tool_name == WRITE_TOOL_NAME:
        content = all_tool_input.get("content", "")
        return content if isinstance(content, str) else ""
    if tool_name == EDIT_TOOL_NAME:
        new_string = all_tool_input.get("new_string", "")
        return new_string if isinstance(new_string, str) else ""
    if tool_name == MULTI_EDIT_TOOL_NAME:
        return multi_edit_new_strings(all_tool_input)
    return ""


def target_path(all_tool_input: dict[str, object]) -> str:
    file_path = all_tool_input.get("file_path", "")
    return file_path if isinstance(file_path, str) else ""


def uses_angle_slot_convention(content: str) -> bool:
    angle_slot_pattern = re.compile(r"<[^<>\n]+>")
    return bool(angle_slot_pattern.search(content))


def has_iteration_loop(content: str) -> bool:
    loop_phrase_pattern = re.compile(
        r"\b(?:for\s+each|each\s+candidate|for\s+[ijk]\b|candidate\s+[ijk]\b|cand_0)\b",
        re.IGNORECASE,
    )
    uppercase_each_keyword_pattern = re.compile(r"\bEACH\b")
    return bool(
        loop_phrase_pattern.search(content)
        or uppercase_each_keyword_pattern.search(content)
    )


def find_bare_path_segments(content: str) -> set[str]:
    loop_letters = "ijk"
    path_context = re.compile(
        r"(?:[\\/]\s*([A-Za-z][\w]*?_[" + loop_letters + r"])(?![\w>])"
        r"|([A-Za-z][\w]*?_[" + loop_letters + r"])(?![\w>])\s*[\\/])"
    )
    all_path_segments: set[str] = set()
    for each_match in path_context.finditer(content):
        each_token = next(
            (each_group for each_group in each_match.groups() if each_group),
            "",
        )
        if each_token:
            all_path_segments.add(each_token)
    return all_path_segments


def find_bare_index_segments(content: str) -> set[str]:
    return find_bare_path_segments(content)


def content_has_violation(content: str) -> bool:
    if not uses_angle_slot_convention(content):
        return False
    if not has_iteration_loop(content):
        return False
    return bool(find_bare_index_segments(content))


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in (WRITE_TOOL_NAME, EDIT_TOOL_NAME, MULTI_EDIT_TOOL_NAME):
        sys.exit(0)

    all_tool_input = hook_input.get("tool_input", {})
    if not isinstance(all_tool_input, dict):
        sys.exit(0)

    if not target_path(all_tool_input).endswith(WORKFLOW_FILE_SUFFIX):
        sys.exit(0)

    if not content_has_violation(written_content(tool_name, all_tool_input)):
        sys.exit(0)

    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": CORRECTIVE_MESSAGE,
        }
    }
    print(json.dumps(deny_payload))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
