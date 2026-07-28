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

Gate base: a branch push takes its `--base` from the merge base between the
pushed object and the remote default branch, so violations are scoped to the
commits the branch itself carries and a rebase onto the default branch leaves
the gate reading only the branch's own work. The stdin remote object name is
the base when no default-branch ref resolves and when the pushed branch is
the default branch. When every remote object name is zero (new branch) or
stdin is empty, the gate falls back to the remote's default branch symbolic
ref.

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
from typing import NamedTuple

from git_hooks_constants import (
    ALL_DEFAULT_BRANCH_FALLBACK_REFERENCES,
    ALL_GIT_MERGE_BASE_COMMAND_PREFIX,
    ALL_GIT_SYMBOLIC_REFERENCE_COMMAND_PREFIX,
    ALL_GIT_VERIFY_REFERENCE_COMMAND_PREFIX,
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
    GIT_REFERENCE_QUERY_TIMEOUT_SECONDS,
    INVOKE_GATE_FAILURE_MESSAGE,
    LOCAL_BRANCH_REFERENCE_PREFIX,
    LOCAL_REFERENCE_FIELD_INDEX,
    LOCAL_SHA_FIELD_INDEX,
    MALFORMED_STDIN_LINE_MESSAGE,
    NO_PARSEABLE_STDIN_LINES_MESSAGE,
    NO_PARSEABLE_STDIN_LINES_SENTINEL,
    ORIGIN_HEAD_SYMBOLIC_REFERENCE,
    ORIGIN_REMOTE_TRACKING_REFERENCE_PREFIX,
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


class PushLine(NamedTuple):
    """One parsed ``<local-ref> <local-sha> <remote-ref> <remote-sha>`` stdin line."""

    local_branch_name: str
    local_object_name: str
    remote_branch_name: str
    remote_object_name: str


def parse_push_line(stripped_line: str) -> PushLine | None:
    """Return the four fields of one push line, or None when the line is malformed.

    Args:
        stripped_line: One whitespace-stripped stdin line.

    Returns:
        The parsed line with both ref names reduced to branch names, or None
        when the line carries fewer than the four fields git writes.
    """
    fields = stripped_line.split()
    if len(fields) < STDIN_LINE_FIELD_COUNT:
        return None
    return PushLine(
        local_branch_name=fields[LOCAL_REFERENCE_FIELD_INDEX].removeprefix(
            LOCAL_BRANCH_REFERENCE_PREFIX
        ),
        local_object_name=fields[LOCAL_SHA_FIELD_INDEX],
        remote_branch_name=fields[REMOTE_REFERENCE_FIELD_INDEX].removeprefix(
            LOCAL_BRANCH_REFERENCE_PREFIX
        ),
        remote_object_name=fields[STDIN_REMOTE_OBJECT_FIELD_INDEX],
    )


def is_branch_update(push_line: PushLine) -> bool:
    """Report whether a push line moves a branch the remote already holds.

    Args:
        push_line: One parsed push line.

    Returns:
        True when the local and the remote object names are both non-zero.
    """
    if is_all_zeros_object_name(push_line.local_object_name):
        return False
    return not is_all_zeros_object_name(push_line.remote_object_name)


class ParsedPushStdin(NamedTuple):
    """Every well-formed push line from one stdin payload, and whether text arrived."""

    all_push_lines: tuple[PushLine, ...]
    has_stdin_content: bool


def _parse_push_stdin(stdin_text: str) -> ParsedPushStdin:
    """Parse the whole stdin payload once, warning on each malformed line.

    Args:
        stdin_text: The pre-push stdin payload.

    Returns:
        Every well-formed line in stdin order, paired with whether stdin
        carried any non-blank text at all.
    """
    all_push_lines: list[PushLine] = []
    has_stdin_content = False
    for each_line in stdin_text.splitlines():
        stripped_line = each_line.strip()
        if not stripped_line:
            continue
        has_stdin_content = True
        push_line = parse_push_line(stripped_line)
        if push_line is None:
            print(
                MALFORMED_STDIN_LINE_MESSAGE.format(line=stripped_line),
                file=sys.stderr,
            )
            continue
        all_push_lines.append(push_line)
    return ParsedPushStdin(tuple(all_push_lines), has_stdin_content)


def _resolve_base_reference_from_lines(parsed_stdin: ParsedPushStdin) -> str | None:
    """Return the stdin-derived base reference for already-parsed lines.

    Args:
        parsed_stdin: The parsed stdin payload.

    Returns:
        The first branch update's remote object name, the no-parseable-lines
        sentinel, None for a deletion-only push, or the remote default branch
        reference.
    """
    is_all_valid_lines_deletions = True
    for each_push_line in parsed_stdin.all_push_lines:
        if is_all_zeros_object_name(each_push_line.local_object_name):
            continue
        is_all_valid_lines_deletions = False
        if is_branch_update(each_push_line):
            return each_push_line.remote_object_name
    if parsed_stdin.has_stdin_content and not parsed_stdin.all_push_lines:
        return NO_PARSEABLE_STDIN_LINES_SENTINEL
    if parsed_stdin.all_push_lines and is_all_valid_lines_deletions:
        return None
    return DEFAULT_REMOTE_BASE_REFERENCE


def resolve_base_reference_from_stdin(stdin_text: str) -> str | None:
    return _resolve_base_reference_from_lines(_parse_push_stdin(stdin_text))


def run_git_reference_query(all_git_arguments: tuple[str, ...]) -> str | None:
    """Return the stripped stdout of a read-only git query.

    Args:
        all_git_arguments: The full git argv, including the ``git`` word.

    Returns:
        The stripped stdout, or None when git exits non-zero, prints nothing,
        or cannot run.
    """
    try:
        completion = subprocess.run(
            list(all_git_arguments),
            capture_output=True,
            text=True,
            check=False,
            timeout=GIT_REFERENCE_QUERY_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completion.returncode != 0:
        return None
    return completion.stdout.strip() or None


def resolve_default_branch_reference() -> str | None:
    """Return the remote-tracking ref name of the remote's default branch.

    The remote's HEAD symbolic ref answers first. When it is unset, each
    candidate default-branch remote-tracking ref answers in turn.

    Resolution reads ``origin`` alone and never the remote name git passes as
    argv[1], and its unset-``origin/HEAD`` fallback prefers ``origin/main``
    over ``origin/master``, so a repo whose default is another branch beside a
    legacy ``main`` resolves the wrong base — the assumption set tracked at
    ~/.claude/orchestrator-runs/falsify-first/parked-items.md row 3.

    Returns:
        A remote-tracking ref name, or None when no default-branch ref
        resolves.
    """
    symbolic_reference = run_git_reference_query(
        (*ALL_GIT_SYMBOLIC_REFERENCE_COMMAND_PREFIX, ORIGIN_HEAD_SYMBOLIC_REFERENCE)
    )
    if symbolic_reference is not None:
        return symbolic_reference
    for each_candidate_reference in ALL_DEFAULT_BRANCH_FALLBACK_REFERENCES:
        verified_reference = run_git_reference_query(
            (*ALL_GIT_VERIFY_REFERENCE_COMMAND_PREFIX, each_candidate_reference)
        )
        if verified_reference is not None:
            return each_candidate_reference
    return None


def _find_branch_update_in_lines(
    all_push_lines: tuple[PushLine, ...],
) -> PushLine | None:
    """Return the first already-parsed line that moves an existing remote branch.

    Args:
        all_push_lines: Well-formed push lines in stdin order.

    Returns:
        The first branch-update line, or None when no line updates a branch
        the remote already holds.
    """
    for each_push_line in all_push_lines:
        if is_branch_update(each_push_line):
            return each_push_line
    return None


def find_branch_update_push(stdin_text: str) -> PushLine | None:
    """Return the first stdin line that moves a branch the remote already holds.

    Args:
        stdin_text: The pre-push stdin payload.

    Returns:
        The parsed branch-update line, or None when no line updates a branch
        the remote already holds.
    """
    return _find_branch_update_in_lines(_parse_push_stdin(stdin_text).all_push_lines)


def resolve_default_branch_merge_base(
    remote_branch_name: str, pushed_object_name: str
) -> str | None:
    """Return the merge base of the pushed object and the default branch.

    The remote branch the push updates decides whether a merge base applies,
    so ``git push origin release-candidate:develop`` reads as an update of
    ``develop`` whatever the local branch is called.

    Args:
        remote_branch_name: The remote branch the push updates.
        pushed_object_name: The object name the push carries.

    Returns:
        The merge-base object name, or None when no default-branch ref
        resolves, when the push updates the default branch, or when git
        reports no merge base.
    """
    default_branch_reference = resolve_default_branch_reference()
    if default_branch_reference is None:
        return None
    default_branch_name = default_branch_reference.removeprefix(
        ORIGIN_REMOTE_TRACKING_REFERENCE_PREFIX
    )
    if remote_branch_name == default_branch_name:
        return None
    # Anchors to the pushed object; deferring to the gate's HEAD-based merge-base would change behavior on non-HEAD pushes.
    return run_git_reference_query(
        (
            *ALL_GIT_MERGE_BASE_COMMAND_PREFIX,
            pushed_object_name,
            default_branch_reference,
        )
    )


def resolve_gate_base_reference(stdin_text: str) -> str | None:
    """Return the reference the gate scopes its changed lines to.

    A branch update reads from the merge base with the remote default branch,
    and every other push reads from the stdin remote object name::

        branch update, default branch resolved -> merge-base(pushed, default)
        branch update, no default branch ref   -> stdin remote object name
        default-branch push                    -> stdin remote object name
        new branch or empty stdin              -> remote default branch ref
        deletion                               -> None

    Args:
        stdin_text: The pre-push stdin payload.

    Returns:
        The gate's base reference, the no-parseable-lines sentinel, or None
        when the push only deletes remote branches.
    """
    return _resolve_gate_base_from_parsed(_parse_push_stdin(stdin_text))


def _resolve_gate_base_from_parsed(parsed_stdin: ParsedPushStdin) -> str | None:
    """Return the gate's base reference for an already-parsed stdin payload.

    Args:
        parsed_stdin: The parsed stdin payload.

    Returns:
        The merge base with the remote default branch for a branch update, the
        branch update's remote object name when no merge base resolves, and
        otherwise whatever the stdin-derived base reference reports.
    """
    branch_update = _find_branch_update_in_lines(parsed_stdin.all_push_lines)
    if branch_update is None:
        return _resolve_base_reference_from_lines(parsed_stdin)
    merge_base_object_name = resolve_default_branch_merge_base(
        branch_update.remote_branch_name, branch_update.local_object_name
    )
    if merge_base_object_name is None:
        return branch_update.remote_object_name
    return merge_base_object_name


def _find_protected_violation_in_lines(
    all_push_lines: tuple[PushLine, ...],
) -> tuple[str, str] | None:
    """Return the first already-parsed line that pushes onto a protected branch.

    Args:
        all_push_lines: Well-formed push lines in stdin order.

    Returns:
        The local and protected remote branch names, or None when no line
        lands a differently named branch on a protected one.
    """
    for each_push_line in all_push_lines:
        if is_all_zeros_object_name(each_push_line.local_object_name):
            continue
        if (
            each_push_line.remote_branch_name in ALL_PROTECTED_BRANCH_PUSH_NAMES
            and each_push_line.local_branch_name != each_push_line.remote_branch_name
        ):
            return (
                each_push_line.local_branch_name,
                each_push_line.remote_branch_name,
            )
    return None


def find_protected_branch_push_violation(stdin_text: str) -> tuple[str, str] | None:
    return _find_protected_violation_in_lines(_parse_push_stdin(stdin_text).all_push_lines)


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
    parsed_stdin = _parse_push_stdin(stdin_text)
    protected_branch_push_violation = _find_protected_violation_in_lines(
        parsed_stdin.all_push_lines
    )
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
    base_reference = _resolve_gate_base_from_parsed(parsed_stdin)
    if base_reference is None:
        return 0
    if base_reference == no_parseable_stdin_lines_sentinel:
        print(no_parseable_stdin_lines_message, file=sys.stderr)
        return gate_infrastructure_failure_exit_code
    code_rules_exit_code = invoke_gate(gate_script_path, base_reference)
    if code_rules_exit_code != 0:
        return code_rules_exit_code
    return code_review_stamp_block_exit_code()


if __name__ == "__main__":
    sys.exit(main())
