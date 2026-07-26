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
pushed object and the remote default branch, so a rebase onto the default
branch leaves the gate reading only the branch's own work. The stdin remote
object name is the base when no default-branch ref resolves and when the
pushed branch is the default branch. When every remote object name is zero
(new branch) or stdin is empty, the gate falls back to the remote's default
branch symbolic ref. When a default-branch ref resolves and git still reports
no merge base, the base stays pending and the hook reports the infrastructure
status with a printed reason, preserving the scope boundary for rebased tips.

Gate scope: the gate process this hook launches diffs its `--base` against the
current checkout's HEAD, so the surface is the commits between that base and
HEAD. A push whose pushed object is HEAD reads as the branch's own work; a
push of any other object is still scoped to HEAD.

Exit codes:
  0 - the push destination is allowed and its commits pass the gate, or the
      gate is not installed.
  1 - the push would land a non-protected local branch onto a protected
      remote branch, or a commit introduces a blocking violation.
  2 - infrastructure attention is required because a subprocess could not
      launch, stdin carried no parseable line, a base could not be resolved,
      or a usable commit name could not be produced.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from gate_utils import is_safe_regular_file, resolve_gate_script_path
from git_hooks_constants import (
    ALL_FALLBACK_REMOTE_DEFAULT_BRANCH_NAMES,
    ALL_GIT_MERGE_BASE_COMMAND_PREFIX,
    ALL_GIT_SYMBOLIC_REFERENCE_COMMAND_PREFIX,
    ALL_GIT_VERIFY_REFERENCE_COMMAND_PREFIX,
    ALL_PROTECTED_BRANCH_PUSH_NAMES,
    ALL_ZEROS_OBJECT_NAME_CHARACTER,
    ABBREVIATE_REFERENCE_OPTION,
    ALL_REMOTE_TRACKING_REFERENCES_OPTION,
    BASE_REFERENCE_ARGUMENT,
    COMMIT_PEEL_TEMPLATE,
    DEFAULT_REMOTE_BASE_REFERENCE,
    DEFAULT_REMOTE_NAME,
    GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE,
    GIT_COMMAND_TIMEOUT_SECONDS,
    GIT_COMMAND_UNAVAILABLE_MESSAGE,
    GIT_EXECUTABLE_NAME,
    GIT_OUTPUT_DECODE_ERRORS_POLICY,
    GIT_OUTPUT_ENCODING_NAME,
    GIT_REFERENCE_QUERY_TIMEOUT_SECONDS,
    GIT_QUIET_FLAG,
    GIT_REV_PARSE_SUBCOMMAND,
    GIT_REV_PARSE_VERIFY_FLAG,
    EXCLUDE_REACHABLE_OPTION,
    CONFIGURED_UPSTREAM_BASE_SOURCE,
    FIRST_PUSH_BASE_FALLBACK_MESSAGE,
    FIRST_PUSH_BASE_RESOLVED_MESSAGE,
    INVOKE_GATE_FAILURE_MESSAGE,
    LOCAL_BRANCH_REFERENCE_PREFIX,
    LOCAL_REFERENCE_FIELD_INDEX,
    LOCAL_SHA_FIELD_INDEX,
    MALFORMED_STDIN_LINE_MESSAGE,
    NO_PARSEABLE_STDIN_LINES_MESSAGE,
    NO_PARSEABLE_STDIN_LINES_SENTINEL,
    PRE_PUSH_GATE_SCRIPT_NOT_FOUND_MESSAGE,
    PARENT_COMMIT_TEMPLATE,
    PROTECTED_BRANCH_PUSH_BLOCK_EXIT_CODE,
    PROTECTED_BRANCH_PUSH_BLOCK_MESSAGE,
    REMOTE_BRANCH_REFERENCE_TEMPLATE,
    REMOTE_REFERENCE_FIELD_INDEX,
    REV_LIST_SUBCOMMAND,
    STDIN_LINE_FIELD_COUNT,
    STDIN_READ_FAILURE_MESSAGE,
    STDIN_REMOTE_OBJECT_FIELD_INDEX,
    UNRESOLVABLE_MERGE_BASE_MESSAGE,
    UNRESOLVABLE_MERGE_BASE_SENTINEL,
    UNPUSHED_COMMITS_BASE_SOURCE,
)
from pre_push_base_reference import (
    resolve_remote_name_from_arguments,
    resolve_usable_base_reference,
)


def _report_unavailable_git(launch_error: Exception) -> int:
    """Report a git that would not run, and hand back the exit code to use."""
    git_command_unavailable_message = GIT_COMMAND_UNAVAILABLE_MESSAGE
    sys.stderr.write(
        git_command_unavailable_message.format(error=launch_error) + "\n"
    )
    return GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE


class GitCommandUnavailable(RuntimeError):
    """Git itself could not run: it failed to launch, or it timed out.

    A git that runs and reports nothing is ordinary absence, which stays a
    plain return. Separating the two keeps a broken toolchain from reading
    as a repository that simply has no default branch.
    """


def run_git_text_command(all_command_arguments: list[str]) -> tuple[int, str]:
    """Ask git a question and read back its answer.

    Output decodes with a replacing policy, so a reference whose bytes are
    invalid in this encoding becomes a marked string and matches nothing.

    Args:
        all_command_arguments: The git arguments following the executable name.

    Returns:
        The exit code paired with the trimmed standard output.

    Raises:
        GitCommandUnavailable: Git failed to launch or exceeded its timeout.
    """
    git_executable_name = GIT_EXECUTABLE_NAME
    git_command_timeout_seconds = GIT_COMMAND_TIMEOUT_SECONDS
    try:
        completion = subprocess.run(
            [git_executable_name, *all_command_arguments],
            check=False,
            capture_output=True,
            timeout=git_command_timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as launch_error:
        raise GitCommandUnavailable(str(launch_error)) from launch_error
    decoded_output = completion.stdout.decode(
        GIT_OUTPUT_ENCODING_NAME, errors=GIT_OUTPUT_DECODE_ERRORS_POLICY
    )
    return completion.returncode, decoded_output.strip()


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
        return resolve_first_push_base_reference(
            f"{LOCAL_BRANCH_REFERENCE_PREFIX}{each_push_line.local_branch_name}",
            each_push_line.local_object_name,
        )
    if parsed_stdin.has_stdin_content and not parsed_stdin.all_push_lines:
        return NO_PARSEABLE_STDIN_LINES_SENTINEL
    if parsed_stdin.all_push_lines and is_all_valid_lines_deletions:
        return None
    return DEFAULT_REMOTE_BASE_REFERENCE


def resolve_base_reference_from_stdin(stdin_text: str) -> str | None:
    return _resolve_base_reference_from_lines(_parse_push_stdin(stdin_text))


def run_git_reference_query(all_git_arguments: tuple[str, ...]) -> str | None:
    """Return the stripped stdout of a read-only git query.

    Output decodes with the same replacing policy as ``run_git_text_command``,
    so locale-invalid bytes become a marked string instead of crashing the hook.

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
            check=False,
            timeout=GIT_REFERENCE_QUERY_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completion.returncode != 0:
        return None
    decoded_output = completion.stdout.decode(
        GIT_OUTPUT_ENCODING_NAME, errors=GIT_OUTPUT_DECODE_ERRORS_POLICY
    )
    return decoded_output.strip() or None


def resolve_existing_reference(reference_expression: str) -> str | None:
    """Return the commit object resolved by a git reference expression."""
    return run_git_reference_query(
        (
            GIT_EXECUTABLE_NAME,
            GIT_REV_PARSE_SUBCOMMAND,
            GIT_REV_PARSE_VERIFY_FLAG,
            GIT_QUIET_FLAG,
            reference_expression,
        )
    )


def resolve_configured_upstream_reference(local_reference: str) -> str | None:
    """Return a live configured upstream for a first-push branch."""
    local_branch_name = local_reference.removeprefix(LOCAL_BRANCH_REFERENCE_PREFIX)
    upstream_reference = run_git_reference_query(
        (
            GIT_EXECUTABLE_NAME,
            GIT_REV_PARSE_SUBCOMMAND,
            ABBREVIATE_REFERENCE_OPTION,
            f"{local_branch_name}@{{upstream}}",
        )
    )
    if not upstream_reference:
        return None
    if not resolve_existing_reference(
        COMMIT_PEEL_TEMPLATE.format(reference=upstream_reference)
    ):
        return None
    return upstream_reference


def resolve_unpushed_commit_base(local_sha: str) -> str | None:
    """Return the parent of the oldest commit absent from remote refs."""
    unpushed_commit_text = run_git_reference_query(
        (
            GIT_EXECUTABLE_NAME,
            REV_LIST_SUBCOMMAND,
            local_sha,
            EXCLUDE_REACHABLE_OPTION,
            ALL_REMOTE_TRACKING_REFERENCES_OPTION,
        )
    )
    if not unpushed_commit_text:
        return None
    oldest_unpushed_commit = unpushed_commit_text.split()[-1]
    return resolve_existing_reference(
        PARENT_COMMIT_TEMPLATE.format(commit=oldest_unpushed_commit)
    )


def report_first_push_base(
    local_reference: str, base_reference: str, base_source: str
) -> None:
    """Report the base selected for a branch with no remote ref."""
    print(
        FIRST_PUSH_BASE_RESOLVED_MESSAGE.format(
            reference=local_reference, base=base_reference, source=base_source
        ),
        file=sys.stderr,
    )


def resolve_first_push_base_reference(local_reference: str, local_sha: str) -> str:
    """Resolve a first-push base from new commits, upstream, or the default ref."""
    unpushed_commit_base = resolve_unpushed_commit_base(local_sha)
    if unpushed_commit_base:
        report_first_push_base(
            local_reference, unpushed_commit_base, UNPUSHED_COMMITS_BASE_SOURCE
        )
        return unpushed_commit_base
    upstream_reference = resolve_configured_upstream_reference(local_reference)
    if upstream_reference:
        report_first_push_base(
            local_reference, upstream_reference, CONFIGURED_UPSTREAM_BASE_SOURCE
        )
        return upstream_reference
    print(
        FIRST_PUSH_BASE_FALLBACK_MESSAGE.format(
            reference=local_reference, base=DEFAULT_REMOTE_BASE_REFERENCE
        ),
        file=sys.stderr,
    )
    return DEFAULT_REMOTE_BASE_REFERENCE


def resolve_default_branch_reference(remote_name: str = DEFAULT_REMOTE_NAME) -> str | None:
    """Return the remote-tracking ref name of the remote's default branch.

    The remote's HEAD symbolic ref answers first. When it is unset, the
    supported default-branch tracking refs answer in turn.

    Args:
        remote_name: Remote whose default branch provides the gate base.

    Returns:
        A remote-tracking ref name, or None when no default-branch ref
        resolves.
    """
    remote_head_reference = REMOTE_BRANCH_REFERENCE_TEMPLATE.format(
        remote=remote_name, branch="HEAD"
    )
    symbolic_reference = run_git_reference_query(
        (*ALL_GIT_SYMBOLIC_REFERENCE_COMMAND_PREFIX, remote_head_reference)
    )
    if symbolic_reference is not None:
        verified_symbolic_target = run_git_reference_query(
            (*ALL_GIT_VERIFY_REFERENCE_COMMAND_PREFIX, symbolic_reference)
        )
        if verified_symbolic_target is not None:
            return symbolic_reference
    for each_branch_name in ALL_FALLBACK_REMOTE_DEFAULT_BRANCH_NAMES:
        each_candidate_reference = REMOTE_BRANCH_REFERENCE_TEMPLATE.format(
            remote=remote_name, branch=each_branch_name
        )
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
    remote_branch_name: str,
    pushed_object_name: str,
    remote_name: str = DEFAULT_REMOTE_NAME,
) -> str | None:
    """Return the merge base of the pushed object and the default branch.

    The remote branch the push updates decides whether a merge base applies,
    so ``git push origin release-candidate:develop`` reads as an update of
    ``develop`` whatever the local branch is called.

    Args:
        remote_branch_name: The remote branch the push updates.
        pushed_object_name: The object name the push carries.
        remote_name: The remote whose default branch provides the gate base.

    Returns:
        The merge-base object name; None when no default-branch ref resolves or
        when the push updates the default branch, which are the two cases where
        no merge base applies; or the unresolvable-merge-base sentinel when a
        default-branch ref resolves and git still reports no merge base.
    """
    default_branch_reference = resolve_default_branch_reference(remote_name)
    if default_branch_reference is None:
        return None
    default_branch_prefix = REMOTE_BRANCH_REFERENCE_TEMPLATE.format(
        remote=remote_name, branch=""
    )
    default_branch_name = default_branch_reference.removeprefix(default_branch_prefix)
    if remote_branch_name == default_branch_name:
        return None
    # Anchors to the pushed object; deferring to the gate's HEAD-based merge-base would change behavior on non-HEAD pushes.
    merge_base_object_name = run_git_reference_query(
        (
            *ALL_GIT_MERGE_BASE_COMMAND_PREFIX,
            pushed_object_name,
            default_branch_reference,
        )
    )
    if merge_base_object_name is None:
        return UNRESOLVABLE_MERGE_BASE_SENTINEL
    return merge_base_object_name


def resolve_gate_base_reference(
    stdin_text: str, remote_name: str = DEFAULT_REMOTE_NAME
) -> str | None:
    """Return the reference the gate scopes its changed lines to.

    A branch update reads from the merge base with the remote default branch,
    and every other push reads from the stdin remote object name::

        branch update, default branch resolved -> merge-base(pushed, default)
        branch update, no merge base found     -> unresolvable-merge-base sentinel
        branch update, no default branch ref   -> stdin remote object name
        default-branch push                    -> stdin remote object name
        new branch or empty stdin              -> remote default branch ref
        deletion                               -> None

    Args:
        stdin_text: The pre-push stdin payload.
        remote_name: The remote whose default branch provides the gate base.

    Returns:
        The gate's base reference, the no-parseable-lines sentinel, the
        unresolvable-merge-base sentinel, or None when the push only deletes
        remote branches.
    """
    return _resolve_gate_base_from_parsed(_parse_push_stdin(stdin_text), remote_name)


def _resolve_gate_base_from_parsed(
    parsed_stdin: ParsedPushStdin, remote_name: str = DEFAULT_REMOTE_NAME
) -> str | None:
    """Return the gate's base reference for an already-parsed stdin payload.

    Args:
        parsed_stdin: The parsed stdin payload.
        remote_name: The remote whose default branch provides the gate base.

    Returns:
        The merge base with the remote default branch for a branch update, the
        branch update's remote object name when no merge base applies, the
        unresolvable-merge-base sentinel when a default-branch ref resolves and
        git reports no merge base anyway, and otherwise whatever the
        stdin-derived base reference reports.
    """
    branch_update = _find_branch_update_in_lines(parsed_stdin.all_push_lines)
    if branch_update is None:
        return _resolve_base_reference_from_lines(parsed_stdin)
    merge_base_object_name = resolve_default_branch_merge_base(
        branch_update.remote_branch_name,
        branch_update.local_object_name,
        remote_name,
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




def main() -> int:
    stdin_read_failure_message = STDIN_READ_FAILURE_MESSAGE
    gate_infrastructure_failure_exit_code = GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE
    pre_push_gate_script_not_found_message = PRE_PUSH_GATE_SCRIPT_NOT_FOUND_MESSAGE
    no_parseable_stdin_lines_message = NO_PARSEABLE_STDIN_LINES_MESSAGE
    no_parseable_stdin_lines_sentinel = NO_PARSEABLE_STDIN_LINES_SENTINEL
    unresolvable_merge_base_message = UNRESOLVABLE_MERGE_BASE_MESSAGE
    unresolvable_merge_base_sentinel = UNRESOLVABLE_MERGE_BASE_SENTINEL
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
        return 0
    remote_name = resolve_remote_name_from_arguments(sys.argv)
    base_reference = _resolve_gate_base_from_parsed(parsed_stdin, remote_name)
    if base_reference is None:
        return 0
    if base_reference == no_parseable_stdin_lines_sentinel:
        print(no_parseable_stdin_lines_message, file=sys.stderr)
        return gate_infrastructure_failure_exit_code
    if base_reference == unresolvable_merge_base_sentinel:
        print(unresolvable_merge_base_message, file=sys.stderr)
        return gate_infrastructure_failure_exit_code
    try:
        usable_base_reference = resolve_usable_base_reference(
            base_reference, remote_name, run_git_text_command
        )
    except GitCommandUnavailable as unavailable_error:
        return _report_unavailable_git(unavailable_error)
    if usable_base_reference is None:
        return gate_infrastructure_failure_exit_code
    code_rules_exit_code = invoke_gate(gate_script_path, usable_base_reference)
    if code_rules_exit_code != 0:
        return code_rules_exit_code
    return 0


if __name__ == "__main__":
    sys.exit(main())
