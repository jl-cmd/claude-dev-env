#!/usr/bin/env python3
"""Git pre-push hook: guard the push destination, then run the CODE_RULES gate.

Installed to the user's shared git-hooks directory via the claude-dev-env
installer; git invokes this file as `pre-push` (the installer strips the
`_` and `.py` suffix when copying into the live hooks path).

Protocol: git pre-push provides remote name and URL as argv, then writes
`<local-ref> <local-sha> <remote-ref> <remote-sha>` lines on stdin.

Destination guard: any line that pushes a local branch onto a protected
remote branch (`main` or `master`) whose name differs from the local
branch is blocked before the gate runs. This catches a branch that tracks
`origin/main` under `push.default=upstream`, where a bare `git push`
resolves to `main`. The guard runs whether or not the CODE_RULES gate is
installed; deletions and same-name pushes pass.

Gate base: the first non-zero remote-sha is used as the gate `--base`, so
violations are scoped to commits that are not already on the remote. When
every remote object name is zero (new branch) or stdin is empty, the gate
falls back to the remote's default branch symbolic ref.

Exit codes:
  0 - the push destination is allowed and its commits pass the gate (or
      the gate is not installed).
  1 - the push would land a non-protected local branch onto a protected
      remote branch, or a commit introduces a blocking violation.
  2 - unexpected invocation failure (e.g., subprocess could not launch).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

from git_hooks_constants import (
    ALL_PROTECTED_BRANCH_PUSH_NAMES,
    ALL_ZEROS_OBJECT_NAME_CHARACTER,
    BASE_REFERENCE_ARGUMENT,
    BLOCKING_DIRECTORY_NAME,
    CODE_REVIEW_DENY_REASON_FUNCTION_NAME,
    CODE_REVIEW_PUSH_GATE_MODULE_NAME,
    CODE_REVIEW_PUSH_GATE_PATH_OVERRIDE_ENV_VAR,
    CODE_REVIEW_PUSH_GATE_SCRIPT_FILENAME,
    CODE_REVIEW_STAMP_BLOCK_EXIT_CODE,
    DEFAULT_REMOTE_BASE_REFERENCE,
    GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE,
    INVOKE_GATE_FAILURE_MESSAGE,
    LOCAL_BRANCH_REFERENCE_PREFIX,
    LOCAL_REFERENCE_FIELD_INDEX,
    LOCAL_SHA_FIELD_INDEX,
    MALFORMED_STDIN_LINE_MESSAGE,
    NO_PARSEABLE_STDIN_LINES_MESSAGE,
    NO_PARSEABLE_STDIN_LINES_SENTINEL,
    PRE_PUSH_GATE_SCRIPT_NOT_FOUND_MESSAGE,
    PROTECTED_BRANCH_PUSH_BLOCK_EXIT_CODE,
    PROTECTED_BRANCH_PUSH_BLOCK_MESSAGE,
    REMOTE_REFERENCE_FIELD_INDEX,
    STDIN_LINE_FIELD_COUNT,
    STDIN_READ_FAILURE_MESSAGE,
    STDIN_REMOTE_OBJECT_FIELD_INDEX,
)
from gate_utils import is_safe_regular_file, resolve_gate_script_path


def is_all_zeros_object_name(object_name: str) -> bool:
    all_zeros_object_name_character = ALL_ZEROS_OBJECT_NAME_CHARACTER
    stripped_object_name = object_name.strip()
    if not stripped_object_name:
        return True
    return all(
        each_character == all_zeros_object_name_character
        for each_character in stripped_object_name
    )


def resolve_base_reference_from_stdin(stdin_text: str) -> str | None:
    stdin_line_field_count = STDIN_LINE_FIELD_COUNT
    stdin_remote_object_field_index = STDIN_REMOTE_OBJECT_FIELD_INDEX
    local_sha_field_index = LOCAL_SHA_FIELD_INDEX
    default_remote_base_reference = DEFAULT_REMOTE_BASE_REFERENCE
    malformed_stdin_line_message = MALFORMED_STDIN_LINE_MESSAGE
    has_seen_any_valid_line = False
    is_all_valid_lines_deletions = True
    has_stdin_content = False
    for each_line in stdin_text.splitlines():
        stripped_line = each_line.strip()
        if not stripped_line:
            continue
        has_stdin_content = True
        fields = stripped_line.split()
        if len(fields) < stdin_line_field_count:
            print(
                malformed_stdin_line_message.format(line=stripped_line),
                file=sys.stderr,
            )
            continue
        has_seen_any_valid_line = True
        if is_all_zeros_object_name(fields[local_sha_field_index]):
            continue
        is_all_valid_lines_deletions = False
        remote_object_name = fields[stdin_remote_object_field_index]
        if not is_all_zeros_object_name(remote_object_name):
            return remote_object_name
    if has_stdin_content and not has_seen_any_valid_line:
        return NO_PARSEABLE_STDIN_LINES_SENTINEL
    if has_seen_any_valid_line and is_all_valid_lines_deletions:
        return None
    return default_remote_base_reference


def find_protected_branch_push_violation(stdin_text: str) -> tuple[str, str] | None:
    stdin_line_field_count = STDIN_LINE_FIELD_COUNT
    local_reference_field_index = LOCAL_REFERENCE_FIELD_INDEX
    local_sha_field_index = LOCAL_SHA_FIELD_INDEX
    remote_reference_field_index = REMOTE_REFERENCE_FIELD_INDEX
    local_branch_reference_prefix = LOCAL_BRANCH_REFERENCE_PREFIX
    protected_branch_push_names = ALL_PROTECTED_BRANCH_PUSH_NAMES
    for each_line in stdin_text.splitlines():
        stripped_line = each_line.strip()
        if not stripped_line:
            continue
        fields = stripped_line.split()
        if len(fields) < stdin_line_field_count:
            continue
        if is_all_zeros_object_name(fields[local_sha_field_index]):
            continue
        local_branch_name = fields[local_reference_field_index].removeprefix(
            local_branch_reference_prefix
        )
        remote_branch_name = fields[remote_reference_field_index].removeprefix(
            local_branch_reference_prefix
        )
        if (
            remote_branch_name in protected_branch_push_names
            and local_branch_name != remote_branch_name
        ):
            return (local_branch_name, remote_branch_name)
    return None


def invoke_gate(gate_script_path: Path, base_reference: str) -> int:
    base_reference_argument = BASE_REFERENCE_ARGUMENT
    invoke_gate_failure_message = INVOKE_GATE_FAILURE_MESSAGE
    gate_infrastructure_failure_exit_code = GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE
    try:
        resolved_gate_path = gate_script_path.resolve(strict=True)
        completion = subprocess.run(
            [
                sys.executable,
                str(resolved_gate_path),
                base_reference_argument,
                base_reference,
            ],
            check=False,
        )
    except OSError as launch_error:
        print(
            invoke_gate_failure_message.format(error=launch_error),
            file=sys.stderr,
        )
        return gate_infrastructure_failure_exit_code
    return completion.returncode


def resolve_code_review_gate_path() -> tuple[Path, Path | None]:
    """Return the code-review push gate script path and its exact-allow override.

    The override environment variable, when set, names the only path the trust
    check accepts; otherwise the gate script resolves to the ``blocking``
    directory beside this hook's ``git-hooks`` directory, which holds in both
    the repository layout and the installed ``~/.claude/hooks`` layout.

    Returns:
        A pair of the resolved gate script path and either the exact override
        path (override set) or None (trust-root case).
    """
    override_path_raw = os.environ.get(
        CODE_REVIEW_PUSH_GATE_PATH_OVERRIDE_ENV_VAR, ""
    ).strip()
    if override_path_raw:
        exact_override = Path(override_path_raw).resolve()
        return exact_override, exact_override
    blocking_directory = Path(__file__).resolve().parent.parent / BLOCKING_DIRECTORY_NAME
    return blocking_directory / CODE_REVIEW_PUSH_GATE_SCRIPT_FILENAME, None


def load_code_review_deny_reason(gate_script_path: Path, work_tree_directory: str) -> str | None:
    """Import the gate script and read its push deny reason for a work tree.

    Any import or evaluation failure reads as no deny reason.

    Args:
        gate_script_path: The resolved code-review push gate script path.
        work_tree_directory: The work tree the push targets.

    Returns:
        The gate's deny reason when the surface lacks a covering low stamp;
        None when the gate allows the push or could not be evaluated.
    """
    try:
        gate_specification = importlib.util.spec_from_file_location(
            CODE_REVIEW_PUSH_GATE_MODULE_NAME, str(gate_script_path)
        )
        if gate_specification is None or gate_specification.loader is None:
            return None
        gate_module = importlib.util.module_from_spec(gate_specification)
        gate_specification.loader.exec_module(gate_module)
        deny_reason_function = getattr(gate_module, CODE_REVIEW_DENY_REASON_FUNCTION_NAME, None)
        if deny_reason_function is None:
            return None
        deny_reason = deny_reason_function(work_tree_directory)
    except Exception:
        return None
    if isinstance(deny_reason, str) and deny_reason:
        return deny_reason
    return None


def code_review_stamp_block_exit_code() -> int:
    """Block the push when no clean low code-review stamp covers the surface.

    Runs the gate decision only when the gate script sits at a trusted
    installed location (or the exact override path). When the gate is absent
    from a trusted location, the check is skipped and the push is allowed,
    matching the CODE_RULES gate's fail-open posture.

    Returns:
        The block exit code when a covering low stamp is missing; 0 when the
        surface is covered or the gate is not installed at a trusted location.
    """
    gate_script_path, exact_allowed_path = resolve_code_review_gate_path()
    if not is_safe_regular_file(gate_script_path, exact_allowed_path):
        return 0
    deny_reason = load_code_review_deny_reason(gate_script_path, os.getcwd())
    if deny_reason is None:
        return 0
    sys.stderr.write(deny_reason + "\n")
    return CODE_REVIEW_STAMP_BLOCK_EXIT_CODE


def main() -> int:
    stdin_read_failure_message = STDIN_READ_FAILURE_MESSAGE
    gate_infrastructure_failure_exit_code = GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE
    pre_push_gate_script_not_found_message = PRE_PUSH_GATE_SCRIPT_NOT_FOUND_MESSAGE
    no_parseable_stdin_lines_message = NO_PARSEABLE_STDIN_LINES_MESSAGE
    no_parseable_stdin_lines_sentinel = NO_PARSEABLE_STDIN_LINES_SENTINEL
    protected_branch_push_block_message = PROTECTED_BRANCH_PUSH_BLOCK_MESSAGE
    protected_branch_push_block_exit_code = PROTECTED_BRANCH_PUSH_BLOCK_EXIT_CODE
    try:
        stdin_text = sys.stdin.read()
    except OSError as read_error:
        print(
            stdin_read_failure_message.format(error=read_error),
            file=sys.stderr,
        )
        return gate_infrastructure_failure_exit_code
    protected_branch_push_violation = find_protected_branch_push_violation(stdin_text)
    if protected_branch_push_violation is not None:
        local_branch_name, remote_branch_name = protected_branch_push_violation
        print(
            protected_branch_push_block_message.format(
                local_branch=local_branch_name,
                remote_branch=remote_branch_name,
            ),
            file=sys.stderr,
        )
        return protected_branch_push_block_exit_code
    gate_script_path, exact_allowed_path = resolve_gate_script_path()
    if not is_safe_regular_file(gate_script_path, exact_allowed_path):
        print(
            pre_push_gate_script_not_found_message.format(path=gate_script_path),
            file=sys.stderr,
        )
        return code_review_stamp_block_exit_code()
    base_reference = resolve_base_reference_from_stdin(stdin_text)
    if base_reference is None:
        return code_review_stamp_block_exit_code()
    if base_reference == no_parseable_stdin_lines_sentinel:
        print(no_parseable_stdin_lines_message, file=sys.stderr)
        return gate_infrastructure_failure_exit_code
    code_rules_exit_code = invoke_gate(gate_script_path, base_reference)
    if code_rules_exit_code != 0:
        return code_rules_exit_code
    return code_review_stamp_block_exit_code()


if __name__ == "__main__":
    sys.exit(main())
