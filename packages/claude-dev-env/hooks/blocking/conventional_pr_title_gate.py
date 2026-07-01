#!/usr/bin/env python3
"""PreToolUse hook: block a non-conventional gh pr create/edit --title in a repo whose CI enforces it.

Autoconverge's standards-deferral path opens draft environment-hardening PRs
across many repos. A repo whose CI runs a semantic-pull-request check (the
amannn/action-semantic-pull-request GitHub Action or an equivalent) rejects a
PR whose title is not a Conventional Commit, and that failure only surfaces
after the PR already exists. This hook blocks the malformed `gh pr create` or
`gh pr edit` before the PR is opened, so the title gets fixed first.

Detection strategy: match `gh pr create`/`gh pr edit` on the command's logical
first line (after joining bash/PowerShell continuations), extract the
--title/-t value with a small shlex-based token scan, then resolve the git
repo root from the tool call's cwd and scan `.github/workflows/*.yml(.yaml)`
for a semantic-pull-request marker string. The gate only fires when a marker
is found; every other case -- an unparseable command, a missing title, a
--repo flag pointing at a repo this hook cannot inspect on disk, a directory
that resolves to no repo root, or a repo with no matching workflow -- fails
OPEN (allow), since the authoritative CI check still runs on GitHub.
"""

import json
import shlex
import sys
from pathlib import Path

_blocking_dir = str(Path(__file__).resolve().parent)
if _blocking_dir not in sys.path:
    sys.path.insert(0, _blocking_dir)

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from verification_verdict_store import resolve_repo_root  # noqa: E402

from blocking._gh_body_arg_utils import (  # noqa: E402
    count_extra_tokens_to_skip_for_split_quoted_value,
    get_logical_first_line,
    strip_surrounding_quotes,
)
from hooks_constants.conventional_pr_title_gate_constants import (  # noqa: E402
    ALL_SEMANTIC_TITLE_CI_MARKERS,
    ALL_WORKFLOW_FILE_GLOB_PATTERNS,
    BASH_TOOL_NAME,
    CONVENTIONAL_COMMIT_TITLE_PATTERN,
    CORRECTIVE_MESSAGE,
    GH_PR_TITLE_SUBCOMMAND_PATTERN,
    REPO_LONG_FLAG,
    REPO_SHORT_FLAG,
    TITLE_LONG_FLAG,
    TITLE_SHORT_FLAG,
    WORKFLOWS_DIRECTORY_RELATIVE_PATH,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402


def _matches_gh_pr_title_subcommand(command: str) -> bool:
    return bool(GH_PR_TITLE_SUBCOMMAND_PATTERN.search(get_logical_first_line(command)))


def _parsed_command_tokens(command: str) -> list[str] | None:
    logical_line = get_logical_first_line(command)
    if not logical_line:
        return None
    try:
        return shlex.split(logical_line, posix=False)
    except ValueError:
        return None


def _joined_equals_form_value(equals_prefix: str, each_token: str, all_remaining_tokens: list[str]) -> str | None:
    """Join an equals-form flag value that shlex(posix=False) split on an internal space.

    shlex.split(command, posix=False) treats the quote character inside
    `--title="fix: a b"` as starting mid-token, so it splits the quoted value
    at each unquoted-looking space instead of keeping it as one token. This
    rejoins those split tokens up to the matching closing quote.
    """
    value_token = each_token[len(equals_prefix) :]
    extra_tokens_to_join = count_extra_tokens_to_skip_for_split_quoted_value(
        all_remaining_tokens, value_token
    )
    if extra_tokens_to_join is None:
        return None
    return strip_surrounding_quotes(
        " ".join([value_token, *all_remaining_tokens[:extra_tokens_to_join]])
    )


def _extract_flag_value(all_tokens: list[str], long_flag: str, short_flag: str) -> str | None:
    long_flag_equals_prefix = f"{long_flag}="
    short_flag_equals_prefix = f"{short_flag}="
    for each_token_index, each_token in enumerate(all_tokens):
        all_remaining_tokens = all_tokens[each_token_index + 1 :]
        if each_token.startswith(long_flag_equals_prefix):
            return _joined_equals_form_value(long_flag_equals_prefix, each_token, all_remaining_tokens)
        if each_token.startswith(short_flag_equals_prefix):
            return _joined_equals_form_value(short_flag_equals_prefix, each_token, all_remaining_tokens)
        if each_token in {long_flag, short_flag}:
            if not all_remaining_tokens:
                return None
            return strip_surrounding_quotes(all_remaining_tokens[0])
    return None


def _is_conventional_commit_title(title: str) -> bool:
    return bool(CONVENTIONAL_COMMIT_TITLE_PATTERN.match(title))


def _repo_enforces_semantic_pr_titles(repo_root: str) -> bool:
    workflows_directory = Path(repo_root) / WORKFLOWS_DIRECTORY_RELATIVE_PATH
    if not workflows_directory.is_dir():
        return False
    for each_glob_pattern in ALL_WORKFLOW_FILE_GLOB_PATTERNS:
        for each_workflow_file in workflows_directory.glob(each_glob_pattern):
            workflow_text = _read_workflow_text(each_workflow_file)
            if any(each_marker in workflow_text for each_marker in ALL_SEMANTIC_TITLE_CI_MARKERS):
                return True
    return False


def _read_workflow_text(workflow_file: Path) -> str:
    try:
        return workflow_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _pull_request_title_to_validate(command: str) -> str | None:
    """Return the --title/-t value this call should be checked against, or None.

    Returns None for a command that is not `gh pr create`/`gh pr edit`, an
    unparseable command, a command carrying a --repo/-R flag (a repo this hook
    cannot inspect on the local filesystem), or a command with no --title/-t
    value.
    """
    if not _matches_gh_pr_title_subcommand(command):
        return None
    all_tokens = _parsed_command_tokens(command)
    if all_tokens is None:
        return None
    if _extract_flag_value(all_tokens, REPO_LONG_FLAG, REPO_SHORT_FLAG) is not None:
        return None
    return _extract_flag_value(all_tokens, TITLE_LONG_FLAG, TITLE_SHORT_FLAG) or None


def _resolved_repo_root(payload_by_field: dict[str, object]) -> str | None:
    working_directory = payload_by_field.get("cwd")
    start_directory = (
        working_directory
        if isinstance(working_directory, str) and working_directory
        else str(Path.cwd())
    )
    return resolve_repo_root(start_directory)


def _deny_reason(payload_by_field: dict[str, object]) -> str | None:
    tool_input = payload_by_field.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command", "")
    if not isinstance(command, str) or not command:
        return None
    pull_request_title = _pull_request_title_to_validate(command)
    if not pull_request_title or _is_conventional_commit_title(pull_request_title):
        return None
    repo_root = _resolved_repo_root(payload_by_field)
    if repo_root is None:
        return None
    if not _repo_enforces_semantic_pr_titles(repo_root):
        return None
    return CORRECTIVE_MESSAGE


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    if not isinstance(hook_input, dict):
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if tool_name != BASH_TOOL_NAME:
        sys.exit(0)

    deny_reason = _deny_reason(hook_input)
    if deny_reason is None:
        sys.exit(0)

    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
        }
    }
    tool_input = hook_input.get("tool_input", {})
    command_preview = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    log_hook_block(
        calling_hook_name="conventional_pr_title_gate.py",
        hook_event="PreToolUse",
        block_reason=deny_reason,
        tool_name=tool_name,
        offending_input_preview=command_preview,
    )
    print(json.dumps(deny_payload))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
