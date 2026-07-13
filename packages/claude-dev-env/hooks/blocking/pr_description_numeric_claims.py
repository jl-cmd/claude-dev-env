"""Flag a PR-body count claim that disagrees with the repository it describes.

::

    body:  "the tdd_enforcer_parts/tests/ directory holds 3 unit tests"
    repo:  tdd_enforcer_parts/tests/ actually defines 4 test functions
    flag:  3 (claimed)  vs  4 (counted)   the body undercounts the suite
    ok:    "... holds 4 unit tests"       the claim matches the count

A count typed from memory drifts from the code the moment the suite or the
file grows. This check re-measures each test-count and line-count claim
against the path the same line names and reports every mismatch.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

try:
    from hooks_constants.pr_description_numeric_claims_constants import (
        ALL_GH_PR_BODY_SUBCOMMAND_MARKERS,
        BASE_GIT_REF,
        DENY_REASON_JOIN,
        DENY_REASON_PREFIX,
        DENY_REASON_SUFFIX,
        DIRECTORY_TOKEN_PATTERN,
        FILE_TOKEN_PATTERN,
        GIT_EXECUTABLE,
        GIT_METADATA_DIRECTORY_NAME,
        GIT_REF_PATH_SPEC_TEMPLATE,
        GIT_SHOW_SUBCOMMAND,
        GIT_SHOW_TIMEOUT_SECONDS,
        HOOK_SCRIPT_NAME,
        LINE_COUNT_CLAIM_PATTERN,
        LINE_COUNT_MISMATCH_MESSAGE_TEMPLATE,
        TEST_COUNT_CLAIM_PATTERN,
        TEST_COUNT_MISMATCH_MESSAGE_TEMPLATE,
        TEST_FILE_GLOB,
        TEST_FUNCTION_DEFINITION_PATTERN,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from hooks_constants.pr_description_numeric_claims_constants import (
        ALL_GH_PR_BODY_SUBCOMMAND_MARKERS,
        BASE_GIT_REF,
        DENY_REASON_JOIN,
        DENY_REASON_PREFIX,
        DENY_REASON_SUFFIX,
        DIRECTORY_TOKEN_PATTERN,
        FILE_TOKEN_PATTERN,
        GIT_EXECUTABLE,
        GIT_METADATA_DIRECTORY_NAME,
        GIT_REF_PATH_SPEC_TEMPLATE,
        GIT_SHOW_SUBCOMMAND,
        GIT_SHOW_TIMEOUT_SECONDS,
        HOOK_SCRIPT_NAME,
        LINE_COUNT_CLAIM_PATTERN,
        LINE_COUNT_MISMATCH_MESSAGE_TEMPLATE,
        TEST_COUNT_CLAIM_PATTERN,
        TEST_COUNT_MISMATCH_MESSAGE_TEMPLATE,
        TEST_FILE_GLOB,
        TEST_FUNCTION_DEFINITION_PATTERN,
    )

try:
    from blocking.pr_description_command_parser import extract_body_from_command
    from blocking.pr_description_pr_number import _command_carries_body_flag
    from hooks_constants.bash_pre_tool_use_dispatcher_constants import (
        BASH_TOOL_NAME,
        DENY_DECISION,
        HOOK_EVENT_NAME,
    )
    from hooks_constants.hook_block_logger import log_hook_block
    from hooks_constants.pre_tool_use_stdin import (
        read_hook_input_dictionary_from_stdin,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from blocking.pr_description_command_parser import extract_body_from_command
    from blocking.pr_description_pr_number import _command_carries_body_flag
    from hooks_constants.bash_pre_tool_use_dispatcher_constants import (
        BASH_TOOL_NAME,
        DENY_DECISION,
        HOOK_EVENT_NAME,
    )
    from hooks_constants.hook_block_logger import log_hook_block
    from hooks_constants.pre_tool_use_stdin import (
        read_hook_input_dictionary_from_stdin,
    )


def main() -> None:
    """Deny a gh pr body command whose numeric claims mismatch the repository."""
    all_input_fields = read_hook_input_dictionary_from_stdin()
    if all_input_fields is None:
        return
    if all_input_fields.get("tool_name") != BASH_TOOL_NAME:
        return
    command = _command_text(all_input_fields)
    body = _pr_body_from_command(command)
    if body is None:
        return
    repository_root = discover_repository_root(Path.cwd())
    if repository_root is None:
        return
    all_violations = find_inaccurate_numeric_claims(body, repository_root)
    if all_violations:
        _emit_denial(all_violations)


def _command_text(all_input_fields: dict[str, object]) -> str:
    """Return the Bash command string from the hook payload, or an empty string."""
    tool_input = all_input_fields.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    command = tool_input.get("command", "")
    if not isinstance(command, str):
        return ""
    return command


def _pr_body_from_command(command: str) -> str | None:
    """Return the body of a gh pr create/edit/comment command, or None otherwise."""
    if not command:
        return None
    if not any(each_marker in command for each_marker in ALL_GH_PR_BODY_SUBCOMMAND_MARKERS):
        return None
    if not _command_carries_body_flag(command):
        return None
    return extract_body_from_command(command)


def _emit_denial(all_violations: list[str]) -> None:
    """Log the block and print the PreToolUse deny payload for the violations."""
    reason = DENY_REASON_PREFIX + DENY_REASON_JOIN.join(all_violations) + DENY_REASON_SUFFIX
    log_hook_block(
        calling_hook_name=HOOK_SCRIPT_NAME,
        hook_event=HOOK_EVENT_NAME,
        block_reason=reason,
    )
    denial_payload = {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": DENY_DECISION,
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(denial_payload))
    sys.stdout.flush()


def find_inaccurate_numeric_claims(body: str, repository_root: Path) -> list[str]:
    """Return one message per PR-body count claim that mismatches the repository.

    Args:
        body: The PR body markdown text to audit.
        repository_root: The repository root the body's paths resolve against.

    Returns:
        A message list; empty when every measurable claim matches the repository.
    """
    violations: list[str] = []
    for each_line in body.splitlines():
        violations.extend(_test_count_violations(each_line, repository_root))
        violations.extend(_line_count_violations(each_line, repository_root))
    return violations


def discover_repository_root(start_directory: Path) -> Path | None:
    """Return the nearest ancestor of start_directory that holds a .git entry.

    Args:
        start_directory: The directory to begin the upward walk from.

    Returns:
        The repository root, or None when no ancestor holds a .git entry.
    """
    for each_directory in (start_directory, *start_directory.parents):
        if (each_directory / GIT_METADATA_DIRECTORY_NAME).exists():
            return each_directory
    return None


def _test_count_violations(line: str, repository_root: Path) -> list[str]:
    """Return a message when the line's test-count claim mismatches its directory."""
    claim = TEST_COUNT_CLAIM_PATTERN.search(line)
    if claim is None:
        return []
    directory = _resolve_unique_directory(line, repository_root)
    if directory is None:
        return []
    claimed_count = int(claim.group("count"))
    actual_count = _count_test_functions(directory)
    if claimed_count == actual_count:
        return []
    return [
        TEST_COUNT_MISMATCH_MESSAGE_TEMPLATE.format(
            claimed=claimed_count,
            actual=actual_count,
            path=_display_path(directory, repository_root),
        )
    ]


def _line_count_violations(line: str, repository_root: Path) -> list[str]:
    """Return a message when the line's line-count claim mismatches its file."""
    claim = LINE_COUNT_CLAIM_PATTERN.search(line)
    if claim is None:
        return []
    file_path = _resolve_unique_file(line, repository_root)
    if file_path is None:
        return []
    claimed_count = int(claim.group("count"))
    all_acceptable_counts = _acceptable_line_counts(file_path, repository_root)
    if claimed_count in all_acceptable_counts:
        return []
    return [
        LINE_COUNT_MISMATCH_MESSAGE_TEMPLATE.format(
            claimed=claimed_count,
            actual=min(all_acceptable_counts),
            path=_display_path(file_path, repository_root),
        )
    ]


def _resolve_unique_directory(line: str, repository_root: Path) -> Path | None:
    """Return the one directory the line's path token resolves to, or None."""
    token_match = DIRECTORY_TOKEN_PATTERN.search(line)
    if token_match is None:
        return None
    all_directory_matches = [
        each_path
        for each_path in _resolve_repository_paths(token_match.group(1), repository_root)
        if each_path.is_dir()
    ]
    if len(all_directory_matches) != 1:
        return None
    return all_directory_matches[0]


def _resolve_unique_file(line: str, repository_root: Path) -> Path | None:
    """Return the one file the line's path token resolves to, or None."""
    token_match = FILE_TOKEN_PATTERN.search(line)
    if token_match is None:
        return None
    all_file_matches = [
        each_path
        for each_path in _resolve_repository_paths(token_match.group(1), repository_root)
        if each_path.is_file()
    ]
    if len(all_file_matches) != 1:
        return None
    return all_file_matches[0]


def _resolve_repository_paths(token: str, repository_root: Path) -> list[Path]:
    """Return every repository path whose trailing segments equal the token."""
    direct_candidate = repository_root / token
    if direct_candidate.exists():
        return [direct_candidate]
    token_parts = Path(token).parts
    all_matches: list[Path] = []
    for each_path in repository_root.rglob(token_parts[-1]):
        if each_path.parts[-len(token_parts) :] == token_parts:
            all_matches.append(each_path)
    return all_matches


def _count_test_functions(directory: Path) -> int:
    """Return how many test functions the directory's test files define."""
    total = 0
    for each_test_file in directory.rglob(TEST_FILE_GLOB):
        content = _safe_read_text(each_test_file)
        total += len(TEST_FUNCTION_DEFINITION_PATTERN.findall(content))
    return total


def _acceptable_line_counts(file_path: Path, repository_root: Path) -> set[int]:
    """Return the working-tree and base line counts the claim may match."""
    all_counts: set[int] = {_line_count(_safe_read_text(file_path))}
    base_content = _base_revision_content(file_path, repository_root)
    if base_content is not None:
        all_counts.add(_line_count(base_content))
    return all_counts


def _base_revision_content(file_path: Path, repository_root: Path) -> str | None:
    """Return the base-revision text of the file, or None when git cannot read it."""
    try:
        relative_path = file_path.relative_to(repository_root).as_posix()
    except ValueError:
        return None
    reference_spec = GIT_REF_PATH_SPEC_TEMPLATE.format(
        reference=BASE_GIT_REF,
        relative_path=relative_path,
    )
    return _run_git_show(reference_spec, repository_root)


def _run_git_show(reference_spec: str, repository_root: Path) -> str | None:
    """Return the stdout of git show for the spec, or None on any failure."""
    try:
        completed = subprocess.run(
            [GIT_EXECUTABLE, GIT_SHOW_SUBCOMMAND, reference_spec],
            cwd=str(repository_root),
            capture_output=True,
            text=True,
            timeout=GIT_SHOW_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def _line_count(content: str) -> int:
    """Return how many lines the content holds."""
    return len(content.splitlines())


def _safe_read_text(file_path: Path) -> str:
    """Return the file's text, or an empty string when it cannot be read."""
    try:
        return file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _display_path(path: Path, repository_root: Path) -> str:
    """Return the repository-relative path when possible, else the bare name."""
    try:
        return path.relative_to(repository_root).as_posix()
    except ValueError:
        return path.name


if __name__ == "__main__":
    main()
