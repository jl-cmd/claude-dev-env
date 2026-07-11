"""Parse gh pr create/edit/comment commands into auditable body content.

Tokenizes the captured shell command and extracts the PR body that should be
audited, resolving body-file paths and rejecting unauditable shell variables,
stdin sentinels, and path-traversal targets. Positional PR-number extraction
lives in pr_description_pr_number.py.
"""

import shlex
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from blocking._gh_body_arg_utils import (  # noqa: E402
    all_body_flags,
    body_file_flag,
    body_file_short_flag,
    count_extra_tokens_to_skip_for_split_quoted_value,
    get_logical_first_line,
    is_flag_shaped_token,
    is_unresolvable_shell_value,
    iter_significant_tokens,
    match_body_file_equals_prefix,
    match_body_flag_equals_prefix,
    match_non_body_value_flag_equals_prefix,
    non_body_value_flags,
    strip_surrounding_quotes,
)
from hooks_constants.pr_description_enforcer_constants import (  # noqa: E402
    BODY_FILE_STDIN_SENTINEL,
)
from hooks_constants.setup_project_paths_constants import UTF8_ENCODING  # noqa: E402


class PathTraversalError(Exception):
    pass


def _read_body_file_contents(file_path: str) -> str | None:
    given_path = Path(file_path)
    allowed_root = Path.cwd().resolve()
    if given_path.is_symlink():
        resolved_target = given_path.resolve()
        try:
            resolved_target.relative_to(allowed_root)
        except ValueError:
            raise PathTraversalError("symlink target resolves outside allowed root")
    resolved_path = given_path.resolve()
    if not given_path.is_absolute():
        try:
            resolved_path.relative_to(allowed_root)
        except ValueError:
            raise PathTraversalError("relative path resolves outside allowed root")
    try:
        with open(resolved_path, "r", encoding=UTF8_ENCODING, errors="replace") as body_file:
            return body_file.read()
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError):
        return None


def _resolve_body_file_value(raw_value_token: str) -> str | None:
    """Return file contents, or None when the body cannot be audited.

    None means body is present but unauditable -- skip enforcement.
    This covers: stdin sentinel, unresolvable shell variables, and path-traversal-rejected paths.
    """
    stripped_value = strip_surrounding_quotes(raw_value_token)
    if not stripped_value:
        return None
    if stripped_value == BODY_FILE_STDIN_SENTINEL:
        return None
    if is_unresolvable_shell_value(stripped_value):
        return None
    try:
        return _read_body_file_contents(stripped_value)
    except PathTraversalError:
        return None


def _resolve_body_string_value(raw_value_token: str) -> str | None:
    """Return the literal body string, or None when the value is an
    unresolvable shell variable.

    Distinguishing the two cases lets `pr_description_enforcer.main()` skip enforcement only for
    unauditable bodies; a literal `--body ""` still returns `""` and flows
    into `validate_pr_body` so the substantive-prose check blocks it.
    """
    stripped_value = strip_surrounding_quotes(raw_value_token)
    if is_unresolvable_shell_value(stripped_value):
        return None
    return stripped_value


def _reassemble_split_quoted_value(
    first_value_token: str, all_remaining_tokens: list[str]
) -> str | None:
    extra_tokens_consumed = count_extra_tokens_to_skip_for_split_quoted_value(
        all_remaining_tokens,
        first_value_token,
    )
    if extra_tokens_consumed is None:
        return None
    if extra_tokens_consumed == 0:
        return first_value_token
    continuation_tokens = all_remaining_tokens[:extra_tokens_consumed]
    return " ".join([first_value_token, *continuation_tokens])


def _scan_raw_tokens_for_body(all_raw_tokens: list[str]) -> str | None | bool:
    """Return the body value from a raw token list, or False if no body flag found.

    Returns False when no body/body-file flag is present (caller should continue).
    Returns None when a body-file flag is present but malformed (no value
    follows), OR when the body value is an unresolvable shell variable (e.g.
    `--body "$VAR"`) — in either case the body is unauditable and the caller
    skips enforcement.
    Returns str for resolved body string values. An empty string `""` is a
    literal-empty body (e.g. `--body ""`) and must still flow into
    `validate_pr_body` so the substantive-prose check blocks it.
    """
    token_index = 0
    while token_index < len(all_raw_tokens):
        current_token = all_raw_tokens[token_index]
        remaining_raw = all_raw_tokens[token_index + 1 :]
        non_body_equals_prefix = match_non_body_value_flag_equals_prefix(current_token)
        if non_body_equals_prefix is not None:
            first_value_token = current_token[len(non_body_equals_prefix) :]
            extra_skip = count_extra_tokens_to_skip_for_split_quoted_value(
                remaining_raw, first_value_token
            )
            token_index += 1 + (extra_skip or 0)
            continue
        if current_token in non_body_value_flags:
            if remaining_raw and not is_flag_shaped_token(remaining_raw[0]):
                first_value_token = remaining_raw[0]
                extra_skip = count_extra_tokens_to_skip_for_split_quoted_value(
                    remaining_raw[1:], first_value_token
                )
                token_index += 1 + 1 + (extra_skip or 0)
                continue
            token_index += 1
            continue
        body_equals_prefix = match_body_flag_equals_prefix(current_token)
        if body_equals_prefix is not None:
            first_value_token = current_token[len(body_equals_prefix) :]
            full_value_token = _reassemble_split_quoted_value(first_value_token, remaining_raw)
            if full_value_token is None:
                return None
            return _resolve_body_string_value(full_value_token)
        body_file_equals_prefix = match_body_file_equals_prefix(current_token)
        if body_file_equals_prefix is not None:
            first_value_token = current_token[len(body_file_equals_prefix) :]
            full_value_token = _reassemble_split_quoted_value(first_value_token, remaining_raw)
            if full_value_token is None:
                return None
            return _resolve_body_file_value(full_value_token)
        if current_token in all_body_flags:
            if not remaining_raw or is_flag_shaped_token(remaining_raw[0]):
                return None
            first_value_token = remaining_raw[0]
            full_value_token = _reassemble_split_quoted_value(first_value_token, remaining_raw[1:])
            if full_value_token is None:
                return None
            return _resolve_body_string_value(full_value_token)
        if current_token in {body_file_flag, body_file_short_flag}:
            if not remaining_raw or is_flag_shaped_token(remaining_raw[0]):
                return None
            first_value_token = remaining_raw[0]
            full_value_token = _reassemble_split_quoted_value(first_value_token, remaining_raw[1:])
            if full_value_token is None:
                return None
            return _resolve_body_file_value(full_value_token)
        token_index += 1
    return False


def extract_body_from_command(
    command: str,
    all_pre_tokenized: tuple[str, list[str]] | None = None,
) -> str | None:
    """Return the PR body content for validation, or None if unextractable.

    Uses iter_significant_tokens to skip values of non-body value-taking flags
    so that --body/--body-file embedded in a quoted --title value never false-matches.
    For space-form body-file flags, scans the raw token list directly because
    iter_significant_tokens consumes the value token (yielding remaining-after-value).

    If all_pre_tokenized is provided as (logical_line, raw_tokens), reuses those instead
    of recomputing the logical line and shlex split a second time.
    """
    if all_pre_tokenized is not None:
        logical_line, all_raw_tokens = all_pre_tokenized
    else:
        logical_line = get_logical_first_line(command)
        if not logical_line:
            return None
        try:
            all_raw_tokens = shlex.split(logical_line, posix=False)
        except ValueError:
            return None
    try:
        all_significant_tokens = list(
            iter_significant_tokens(command, pre_tokenized=(logical_line, all_raw_tokens))
        )
    except ValueError:
        return None

    significant_token_set = {each_token for each_token, _ in all_significant_tokens}
    body_flag_found_in_significant = (
        any(each_token in all_body_flags for each_token in significant_token_set)
        or any(
            match_body_flag_equals_prefix(each_token) is not None
            for each_token in significant_token_set
        )
        or any(
            match_body_file_equals_prefix(each_token) is not None
            for each_token in significant_token_set
        )
        or any(
            each_token in {body_file_flag, body_file_short_flag}
            for each_token in significant_token_set
        )
    )
    if not body_flag_found_in_significant:
        return None

    scan_outcome = _scan_raw_tokens_for_body(all_raw_tokens)
    if isinstance(scan_outcome, bool):
        return None
    return scan_outcome
