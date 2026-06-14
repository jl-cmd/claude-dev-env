#!/usr/bin/env python3
"""PreToolUse hook: block a hook module whose prose overstates its path-shape detector.

A path-shape blocker hook detects a per-iteration token only when the token sits
next to a path separator (its detection regex keys off a `[\\/]`-style character
class). When such a hook's user-facing prose -- its module docstring lead
narrative or its CORRECTIVE_MESSAGE -- also claims it blocks an "output-key
segment", the prose describes a trigger the detector never fires on: a quoted
structured-output key alone, with no looped path, is never blocked.

This drift misleads two audiences at once. An author whose only per-iteration
token is an output key never sees the block, yet the message implies they would.
An author who does see the block is told an output key caused it, when only the
path-adjacent shape did.

Detection strategy: act only on Write/Edit to a `.py` file under `hooks/`. The
prose claim -- the phrase "output-key segment" describing a blocked trigger --
is the violation. A `*_constants.py` companion holds only the corrective message
and never the detector, so that file is flagged on the claim alone. Any other
hook module is flagged when it also keys a detection regex off a path-separator
character class (a `[...\\...]`/`[.../...]` class), proving the co-located
detector is path-shape only and the docstring claim overstates it.

This detector's own three source files -- the hook module, its `*_constants.py`
companion, and its `test_*` module -- carry the forbidden phrase and the
separator-class shape as load-bearing description, so they are exempt by basename
and stay editable through the harness this rule runs in.

Fails OPEN (approves) on malformed input or a non-hook path; the invariant is
narrow enough that a false negative is preferable to blocking unrelated edits.
"""

import json
import re
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.hook_prose_detector_consistency_constants import (  # noqa: E402
    CONSTANTS_MODULE_SUFFIX,
    CORRECTIVE_MESSAGE,
    EDIT_TOOL_NAME,
    HOOK_MODULE_PATH_SEGMENT,
    OVERSTATED_OUTPUT_KEY_PHRASE_PATTERN,
    PATH_SEPARATOR_CLASS_PATTERN,
    PYTHON_FILE_SUFFIX,
    TEST_MODULE_PREFIX,
    WRITE_TOOL_NAME,
)


def written_content(tool_name: str, all_tool_input: dict[str, object]) -> str:
    if tool_name == WRITE_TOOL_NAME:
        content = all_tool_input.get("content", "")
        return content if isinstance(content, str) else ""
    if tool_name == EDIT_TOOL_NAME:
        new_string = all_tool_input.get("new_string", "")
        return new_string if isinstance(new_string, str) else ""
    return ""


def target_path(all_tool_input: dict[str, object]) -> str:
    file_path = all_tool_input.get("file_path", "")
    return file_path if isinstance(file_path, str) else ""


def is_hook_python_module(file_path: str) -> bool:
    normalized_path = file_path.replace("\\", "/")
    if not normalized_path.endswith(PYTHON_FILE_SUFFIX):
        return False
    return HOOK_MODULE_PATH_SEGMENT in normalized_path


def is_constants_module(file_path: str) -> bool:
    normalized_path = file_path.replace("\\", "/")
    return normalized_path.endswith(CONSTANTS_MODULE_SUFFIX)


def is_own_detector_family(file_path: str) -> bool:
    own_module_stem = Path(__file__).stem
    own_family_basenames = {
        f"{own_module_stem}{PYTHON_FILE_SUFFIX}",
        f"{own_module_stem}{CONSTANTS_MODULE_SUFFIX}",
        f"{TEST_MODULE_PREFIX}{own_module_stem}{PYTHON_FILE_SUFFIX}",
    }
    normalized_path = file_path.replace("\\", "/")
    edited_basename = normalized_path.rsplit("/", 1)[-1]
    return edited_basename in own_family_basenames


def detects_only_path_shape(content: str) -> bool:
    separator_class_pattern = re.compile(PATH_SEPARATOR_CLASS_PATTERN)
    return bool(separator_class_pattern.search(content))


def claims_output_key_trigger(content: str) -> bool:
    overstated_phrase_pattern = re.compile(OVERSTATED_OUTPUT_KEY_PHRASE_PATTERN, re.IGNORECASE)
    return bool(overstated_phrase_pattern.search(content))


def content_has_violation(content: str, file_path: str) -> bool:
    if is_own_detector_family(file_path):
        return False
    if not claims_output_key_trigger(content):
        return False
    if is_constants_module(file_path):
        return True
    return detects_only_path_shape(content)


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in (WRITE_TOOL_NAME, EDIT_TOOL_NAME):
        sys.exit(0)

    all_tool_input = hook_input.get("tool_input", {})
    if not isinstance(all_tool_input, dict):
        sys.exit(0)

    edited_path = target_path(all_tool_input)
    if not is_hook_python_module(edited_path):
        sys.exit(0)

    if not content_has_violation(
        written_content(tool_name, all_tool_input), edited_path
    ):
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
