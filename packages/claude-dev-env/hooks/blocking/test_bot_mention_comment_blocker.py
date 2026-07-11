"""Unit tests for bot-mention-comment-blocker PreToolUse hook."""

import importlib.util
import io
import json
import pathlib
import sys

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_spec = importlib.util.spec_from_file_location(
    "bot_mention_comment_blocker",
    _HOOK_DIR / "bot_mention_comment_blocker.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)

_detect_bot_mention = hook_module._detect_bot_mention
_body_contains_token = hook_module._body_contains_token

from hooks_constants.bot_mention_comment_blocker_constants import (
    CORRECTIVE_MESSAGE_COPILOT,
    CORRECTIVE_MESSAGE_CURSOR,
    CURSOR_MENTION_TOKEN,
)


def test_passes_clean_body() -> None:
    assert _detect_bot_mention("bugbot run") is None


def test_passes_empty_body() -> None:
    assert _detect_bot_mention("") is None


def test_passes_unrelated_body() -> None:
    assert _detect_bot_mention("please review this PR") is None


def test_blocks_cursor_mention() -> None:
    reason = _detect_bot_mention("@cursor bugbot run")
    assert reason is not None
    assert "bugbot run" in reason


def test_blocks_cursor_bracket_mention() -> None:
    reason = _detect_bot_mention("@cursor[bot] bugbot run")
    assert reason is not None
    assert "bugbot run" in reason


def test_blocks_copilot_mention() -> None:
    reason = _detect_bot_mention("@copilot review this")
    assert reason is not None
    assert "copilot-pull-request-reviewer" in reason


def test_returns_cursor_message_for_cursor() -> None:
    assert _detect_bot_mention("@cursor run") == CORRECTIVE_MESSAGE_CURSOR


def test_returns_copilot_message_for_copilot() -> None:
    assert _detect_bot_mention("@copilot help") == CORRECTIVE_MESSAGE_COPILOT


def test_copilot_wins_when_both_present() -> None:
    assert _detect_bot_mention("@cursor and @copilot") == CORRECTIVE_MESSAGE_COPILOT


def test_body_contains_token_case_insensitive() -> None:
    assert _body_contains_token("Hello @CURSOR world", "@cursor")
    assert _body_contains_token("Hello @CoPilot world", "@copilot")


def test_body_contains_token_no_at_sign() -> None:
    assert not _body_contains_token("cursor without at-sign", CURSOR_MENTION_TOKEN)


from unittest import mock


def _run_main_with_io(input_text: str) -> str:
    with mock.patch("sys.stdin", io.StringIO(input_text)):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            try:
                hook_module.main()
            except SystemExit:
                pass
            return mock_stdout.getvalue()


def test_main_blocks_matching_cursor_comment() -> None:
    hook_input = {
        "tool_name": "mcp__plugin_github_github__add_issue_comment",
        "tool_input": {"body": "@cursor bugbot run"},
    }
    output_text = _run_main_with_io(json.dumps(hook_input))
    output = json.loads(output_text)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_main_passes_wrong_tool_name() -> None:
    hook_input = {
        "tool_name": "some_other_tool",
        "tool_input": {"body": "@cursor bugbot run"},
    }
    assert _run_main_with_io(json.dumps(hook_input)) == ""


def test_main_passes_empty_body() -> None:
    hook_input = {
        "tool_name": "mcp__plugin_github_github__add_issue_comment",
        "tool_input": {"body": ""},
    }
    assert _run_main_with_io(json.dumps(hook_input)) == ""


def test_main_passes_non_matching_body() -> None:
    hook_input = {
        "tool_name": "mcp__plugin_github_github__add_issue_comment",
        "tool_input": {"body": "please review this PR"},
    }
    assert _run_main_with_io(json.dumps(hook_input)) == ""


def test_main_passes_malformed_json() -> None:
    assert _run_main_with_io("not valid json {{{") == ""
