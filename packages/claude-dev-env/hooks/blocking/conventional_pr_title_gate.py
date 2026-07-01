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
workflow leaves the action's `types:` input at its default Conventional
Commits list; every other case -- an unparseable command, a missing title, a
title that is an unresolvable shell variable (a `$`-prefixed value this hook
cannot resolve), a --repo flag pointing at a repo this hook cannot inspect on
disk, a directory that resolves to no repo root, a repo with no matching
workflow, or a marker workflow whose semantic-pull-request action step declares
a custom `types:` input (so this hook cannot know the repo's allowed types) --
fails OPEN (allow), since the authoritative CI check still runs on GitHub.
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
    all_value_flags,
    count_extra_tokens_to_skip_for_split_quoted_value,
    get_logical_first_line,
    is_flag_shaped_token,
    is_unresolvable_shell_value,
    iter_significant_tokens,
    match_non_body_value_flag_equals_prefix,
    strip_surrounding_quotes,
)
from hooks_constants.conventional_pr_title_gate_constants import (  # noqa: E402
    ALL_GH_EXECUTABLE_BASENAMES,
    ALL_PR_TITLE_SUBCOMMAND_VERBS,
    ALL_SEMANTIC_TITLE_CI_MARKERS,
    ALL_WORKFLOW_FILE_GLOB_PATTERNS,
    BASH_TOOL_NAME,
    CONVENTIONAL_COMMIT_TITLE_PATTERN,
    CORRECTIVE_MESSAGE,
    GH_PR_SUBCOMMAND_MINIMUM_TOKEN_COUNT,
    PR_SUBCOMMAND_TOKEN,
    REPO_LONG_FLAG,
    REPO_SHORT_FLAG,
    SEMANTIC_ACTION_FLOW_TYPES_INPUT_PATTERN,
    SEMANTIC_ACTION_TYPES_INPUT_PATTERN,
    TITLE_LONG_FLAG,
    TITLE_SHORT_FLAG,
    WORKFLOWS_DIRECTORY_RELATIVE_PATH,
    YAML_LIST_ITEM_PREFIX,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402


def _matches_gh_pr_title_subcommand(command: str) -> bool:
    all_tokens = _parsed_command_tokens(command)
    if all_tokens is None or len(all_tokens) < GH_PR_SUBCOMMAND_MINIMUM_TOKEN_COUNT:
        return False
    executable_basename = Path(strip_surrounding_quotes(all_tokens[0])).name
    if executable_basename not in ALL_GH_EXECUTABLE_BASENAMES:
        return False
    if strip_surrounding_quotes(all_tokens[1]) != PR_SUBCOMMAND_TOKEN:
        return False
    return strip_surrounding_quotes(all_tokens[2]) in ALL_PR_TITLE_SUBCOMMAND_VERBS


def _parsed_command_tokens(command: str) -> list[str] | None:
    logical_line = get_logical_first_line(command)
    if not logical_line:
        return None
    try:
        return shlex.split(logical_line, posix=False)
    except ValueError:
        return None


def _joined_equals_form_value(
    equals_prefix: str, each_token: str, all_remaining_tokens: list[str]
) -> str | None:
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


def _extract_flag_value(
    command: str,
    long_flag: str,
    short_flag: str,
    all_pre_tokenized: tuple[str, list[str]] | None = None,
) -> str | None:
    """Return the value of long_flag/short_flag, skipping preceding value-flag values.

    Uses iter_significant_tokens so a long_flag/short_flag word exposed inside an
    earlier value flag's split quoted value is never mistaken for the flag
    itself, then scans the raw tokens to read the flag's own value. Recognizes
    the space form, the equals form, and the attached short form
    (``-Rowner/repo``). Returns None when the flag is absent or the command is
    unparseable.

    Args:
        command: The full shell command string.
        long_flag: The flag's long spelling, such as ``--title``.
        short_flag: The flag's short spelling, such as ``-t``.
        all_pre_tokenized: An optional ``(logical_line, raw_tokens)`` pair reused
            in place of recomputing the logical line and shlex split.
    """
    if all_pre_tokenized is not None:
        logical_line, all_tokens = all_pre_tokenized
    else:
        logical_line = get_logical_first_line(command)
        if not logical_line:
            return None
        try:
            all_tokens = shlex.split(logical_line, posix=False)
        except ValueError:
            return None
    try:
        all_significant_tokens = list(
            iter_significant_tokens(command, pre_tokenized=(logical_line, all_tokens))
        )
    except ValueError:
        return None
    if not _flag_present_in_significant_tokens(all_significant_tokens, long_flag, short_flag):
        return None
    return _scan_tokens_for_flag_value(all_tokens, long_flag, short_flag)


def _flag_present_in_significant_tokens(
    all_significant_tokens: list[tuple[str, list[str]]], long_flag: str, short_flag: str
) -> bool:
    return any(
        _token_begins_target_flag(each_token, long_flag, short_flag)
        for each_token, _all_remaining_tokens in all_significant_tokens
    )


def _scan_tokens_for_flag_value(
    all_tokens: list[str], long_flag: str, short_flag: str
) -> str | None:
    token_index = 0
    while token_index < len(all_tokens):
        each_token = all_tokens[token_index]
        all_remaining_tokens = all_tokens[token_index + 1 :]
        if _token_begins_target_flag(each_token, long_flag, short_flag):
            return _target_flag_value(each_token, all_remaining_tokens, long_flag, short_flag)
        token_index = _index_after_value_flag(all_tokens, token_index)
    return None


def _token_begins_target_flag(each_token: str, long_flag: str, short_flag: str) -> bool:
    if each_token in {long_flag, short_flag}:
        return True
    if each_token.startswith(f"{long_flag}=") or each_token.startswith(f"{short_flag}="):
        return True
    return _is_attached_short_flag(each_token, short_flag)


def _is_attached_short_flag(each_token: str, short_flag: str) -> bool:
    if each_token == short_flag or not each_token.startswith(short_flag):
        return False
    return not each_token.startswith(f"{short_flag}=")


def _target_flag_value(
    each_token: str, all_remaining_tokens: list[str], long_flag: str, short_flag: str
) -> str | None:
    long_flag_equals_prefix = f"{long_flag}="
    short_flag_equals_prefix = f"{short_flag}="
    if each_token.startswith(long_flag_equals_prefix):
        return _joined_equals_form_value(long_flag_equals_prefix, each_token, all_remaining_tokens)
    if each_token.startswith(short_flag_equals_prefix):
        return _joined_equals_form_value(short_flag_equals_prefix, each_token, all_remaining_tokens)
    if each_token in {long_flag, short_flag}:
        if not all_remaining_tokens:
            return None
        return strip_surrounding_quotes(all_remaining_tokens[0])
    return strip_surrounding_quotes(each_token[len(short_flag) :])


def _index_after_value_flag(all_tokens: list[str], token_index: int) -> int:
    each_token = all_tokens[token_index]
    all_remaining_tokens = all_tokens[token_index + 1 :]
    equals_prefix = match_non_body_value_flag_equals_prefix(each_token)
    if equals_prefix is not None:
        value_token = each_token[len(equals_prefix) :]
        extra_tokens_to_skip = count_extra_tokens_to_skip_for_split_quoted_value(
            all_remaining_tokens, value_token
        )
        return token_index + 1 + (extra_tokens_to_skip or 0)
    if each_token not in all_value_flags:
        return token_index + 1
    if not all_remaining_tokens or is_flag_shaped_token(all_remaining_tokens[0]):
        return token_index + 1
    value_token = all_remaining_tokens[0]
    extra_tokens_to_skip = count_extra_tokens_to_skip_for_split_quoted_value(
        all_remaining_tokens[1:], value_token
    )
    return token_index + 1 + 1 + (extra_tokens_to_skip or 0)


def _is_conventional_commit_title(title: str) -> bool:
    return bool(CONVENTIONAL_COMMIT_TITLE_PATTERN.match(title))


def _repo_enforces_default_conventional_pr_titles(repo_root: str) -> bool:
    """Return whether a workflow enforces PR titles against the default type list.

    A repo whose semantic-pull-request action step declares a custom ``types:``
    input accepts types this gate's default Conventional Commits list omits, so
    the gate cannot know the repo's allowed types and returns False (fail open)
    even though the marker is present -- the authoritative CI check on GitHub
    still validates the title. The gate only blocks when a marker workflow
    leaves the action's type list at its default.
    """
    workflows_directory = Path(repo_root) / WORKFLOWS_DIRECTORY_RELATIVE_PATH
    if not workflows_directory.is_dir():
        return False
    all_marker_workflow_texts = _all_semantic_marker_workflow_texts(workflows_directory)
    if not all_marker_workflow_texts:
        return False
    return not any(
        _workflow_customizes_semantic_types(each_workflow_text)
        for each_workflow_text in all_marker_workflow_texts
    )


def _all_semantic_marker_workflow_texts(workflows_directory: Path) -> list[str]:
    all_marker_workflow_texts: list[str] = []
    for each_glob_pattern in ALL_WORKFLOW_FILE_GLOB_PATTERNS:
        for each_workflow_file in workflows_directory.glob(each_glob_pattern):
            workflow_text = _read_workflow_text(each_workflow_file)
            if _text_has_semantic_marker(workflow_text):
                all_marker_workflow_texts.append(workflow_text)
    return all_marker_workflow_texts


def _text_has_semantic_marker(workflow_text: str) -> bool:
    return any(each_marker in workflow_text for each_marker in ALL_SEMANTIC_TITLE_CI_MARKERS)


def _workflow_customizes_semantic_types(workflow_text: str) -> bool:
    """Return whether a semantic-pull-request step declares a custom ``types:`` input.

    The action reads a ``types:`` input as the complete allowed-type list,
    replacing this gate's default Conventional Commits set, so a title this gate
    would reject may be one the repo's own CI accepts. Scoping the search to the
    marker step's indented block keeps the top-level ``on: pull_request: types:``
    event-activity list -- an unrelated ``types:`` key -- out of the match.
    """
    all_lines = workflow_text.splitlines()
    for each_line_index, each_line in enumerate(all_lines):
        if not _text_has_semantic_marker(each_line):
            continue
        if _step_block_declares_types_input(all_lines, each_line_index):
            return True
    return False


def _step_block_declares_types_input(all_lines: list[str], marker_line_index: int) -> bool:
    step_item_index = _enclosing_step_item_index(all_lines, marker_line_index)
    step_indentation = _leading_space_count(all_lines[step_item_index])
    for each_line in all_lines[step_item_index + 1 :]:
        if not each_line.strip():
            continue
        if _leading_space_count(each_line) <= step_indentation:
            return False
        if _line_declares_types_input(each_line):
            return True
    return False


def _line_declares_types_input(line: str) -> bool:
    """Return whether a step-block line declares a semantic-pull-request ``types:`` input.

    Matches both the block-style key (``types: |`` on its own line) and the
    flow-style mapping (``with: { types: [feat, wip] }``), so a custom type list
    written in either YAML shape counts.
    """
    if SEMANTIC_ACTION_TYPES_INPUT_PATTERN.match(line):
        return True
    return bool(SEMANTIC_ACTION_FLOW_TYPES_INPUT_PATTERN.search(line))


def _enclosing_step_item_index(all_lines: list[str], marker_line_index: int) -> int:
    """Return the index of the ``- `` list item that encloses the marker line.

    The semantic-pull-request marker sits either on the step's ``- `` list-item
    line or on a sibling ``uses:`` key one level in. Scanning the step block from
    that list item -- rather than the marker line -- reaches a nested
    ``with: types:`` input whether it sits above or below the ``uses:`` key,
    since YAML mapping key order within a step is arbitrary.
    """
    marker_indentation = _leading_space_count(all_lines[marker_line_index])
    for each_candidate_index in range(marker_line_index, -1, -1):
        candidate_line = all_lines[each_candidate_index]
        if not _is_yaml_list_item(candidate_line):
            continue
        if _leading_space_count(candidate_line) <= marker_indentation:
            return each_candidate_index
    return marker_line_index


def _is_yaml_list_item(line: str) -> bool:
    return line.lstrip().startswith(YAML_LIST_ITEM_PREFIX)


def _leading_space_count(line: str) -> int:
    return len(line) - len(line.lstrip())


def _read_workflow_text(workflow_file: Path) -> str:
    try:
        return workflow_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _pull_request_title_to_validate(command: str) -> str | None:
    """Return the --title/-t value this call should be checked against, or None.

    Returns None for a command that is not `gh pr create`/`gh pr edit`, an
    unparseable command, a command carrying a --repo/-R flag (a repo this hook
    cannot inspect on the local filesystem), a command with no --title/-t
    value, or a title that is an unresolvable shell variable (a `$`-prefixed
    value whose resolved text this hook cannot know), which fails open so the
    authoritative CI check on GitHub decides.
    """
    if not _matches_gh_pr_title_subcommand(command):
        return None
    all_tokens = _parsed_command_tokens(command)
    if all_tokens is None:
        return None
    all_pre_tokenized = (get_logical_first_line(command), all_tokens)
    if _extract_flag_value(command, REPO_LONG_FLAG, REPO_SHORT_FLAG, all_pre_tokenized) is not None:
        return None
    extracted_title = _extract_flag_value(
        command, TITLE_LONG_FLAG, TITLE_SHORT_FLAG, all_pre_tokenized
    )
    if not extracted_title or is_unresolvable_shell_value(extracted_title):
        return None
    return extracted_title


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
    if not _repo_enforces_default_conventional_pr_titles(repo_root):
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
