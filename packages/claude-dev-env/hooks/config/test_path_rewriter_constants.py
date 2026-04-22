"""Pin tests for path_rewriter_constants — values consumed by es_exe_path_rewriter."""

import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from config.path_rewriter_constants import (
    BASH_TOOL_NAME,
    HOOK_EVENT_NAME,
    PERMISSION_ALLOW,
    PLACEHOLDER_TOKEN_PATTERN,
)


def test_bash_tool_name_is_bash() -> None:
    assert BASH_TOOL_NAME == "Bash"


def test_hook_event_name_is_pre_tool_use() -> None:
    assert HOOK_EVENT_NAME == "PreToolUse"


def test_permission_allow_is_allow() -> None:
    assert PERMISSION_ALLOW == "allow"


def test_placeholder_token_pattern_matches_curly_brace_form() -> None:
    match = PLACEHOLDER_TOKEN_PATTERN.match("{my-repo}")
    assert match is not None
    assert match.group(1) == "my-repo"


def test_placeholder_token_pattern_matches_double_quoted_form() -> None:
    match = PLACEHOLDER_TOKEN_PATTERN.match('"{my-repo}"')
    assert match is not None
    assert match.group(1) == "my-repo"


def test_placeholder_token_pattern_matches_single_quoted_form() -> None:
    match = PLACEHOLDER_TOKEN_PATTERN.match("'{my-repo}'")
    assert match is not None
    assert match.group(1) == "my-repo"


def test_placeholder_token_pattern_does_not_match_shell_parameter_expansion() -> None:
    assert PLACEHOLDER_TOKEN_PATTERN.search("${myrepo}") is None


def test_placeholder_token_pattern_does_not_match_embedded_in_flag() -> None:
    assert PLACEHOLDER_TOKEN_PATTERN.search("--flag={my-repo}") is None


def test_placeholder_token_pattern_does_not_match_embedded_in_token() -> None:
    assert PLACEHOLDER_TOKEN_PATTERN.search("foo{my-repo}bar") is None
