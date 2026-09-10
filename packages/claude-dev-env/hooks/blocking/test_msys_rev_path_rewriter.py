"""Tests for msys_rev_path_rewriter, the MSYS <rev>:<path> exclusion rewriter."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

import msys_rev_path_rewriter as rewriter

SETTINGS_SHOW_COMMAND = "git show origin/main:.claude/settings.json"
SETTINGS_SHOW_REWRITTEN = (
    "export MSYS2_ARG_CONV_EXCL='origin/main:'; git show origin/main:.claude/settings.json"
)


def _stdout_from_main(payload: dict[str, object]) -> str:
    """Return what main() wrote to stdout for one hook payload."""
    captured_stdout = StringIO()
    with patch("sys.stdin", StringIO(json.dumps(payload))), patch("sys.stdout", captured_stdout):
        try:
            rewriter.main()
        except SystemExit:
            pass
    return captured_stdout.getvalue()


def test_settings_path_after_slashed_revision_yields_one_prefix() -> None:
    assert rewriter.all_exclusion_prefixes(SETTINGS_SHOW_COMMAND) == ("origin/main:",)


def test_settings_path_command_gains_the_surgical_export_prefix() -> None:
    assert rewriter.command_with_exclusion_export(SETTINGS_SHOW_COMMAND) == SETTINGS_SHOW_REWRITTEN


def test_unslashed_revision_beside_a_slashed_one_stays_out_of_the_prefixes() -> None:
    assert rewriter.all_exclusion_prefixes(
        "git diff origin/main:.gitignore HEAD:.gitignore"
    ) == ("origin/main:",)


def test_two_slashed_revisions_join_with_a_semicolon_in_first_appearance_order() -> None:
    assert rewriter.command_with_exclusion_export(
        "git diff origin/main:.gitignore origin/develop:.gitignore"
    ) == (
        "export MSYS2_ARG_CONV_EXCL='origin/main:;origin/develop:'; "
        "git diff origin/main:.gitignore origin/develop:.gitignore"
    )


def test_one_slashed_revision_used_twice_yields_one_prefix() -> None:
    assert rewriter.all_exclusion_prefixes(
        "git diff origin/main:.gitignore origin/main:.gitattributes"
    ) == ("origin/main:",)


def test_dot_file_after_the_colon_is_collected() -> None:
    assert rewriter.all_exclusion_prefixes("git show origin/main:.gitignore") == ("origin/main:",)


def test_plain_directory_path_after_the_colon_is_left_alone() -> None:
    command = "git show origin/main:packages/app.py"
    assert rewriter.all_exclusion_prefixes(command) == ()
    assert rewriter.command_with_exclusion_export(command) == command


def test_revision_without_a_slash_is_left_alone() -> None:
    command = "git show HEAD:.claude/settings.json"
    assert rewriter.all_exclusion_prefixes(command) == ()
    assert rewriter.command_with_exclusion_export(command) == command


def test_dot_slash_path_after_the_colon_is_left_alone() -> None:
    assert rewriter.all_exclusion_prefixes("git show origin/main:./settings.json") == ()


def test_parent_directory_path_after_the_colon_is_left_alone() -> None:
    assert rewriter.all_exclusion_prefixes("git show origin/main:../settings.json") == ()


def test_command_already_naming_the_exclusion_variable_is_left_alone() -> None:
    command = "MSYS2_ARG_CONV_EXCL='*' git show origin/main:.gitignore"
    assert rewriter.command_with_exclusion_export(command) == command


def test_command_already_naming_the_path_conversion_variable_is_left_alone() -> None:
    command = "export MSYS_NO_PATHCONV=1; git show origin/main:.gitignore"
    assert rewriter.command_with_exclusion_export(command) == command


def test_colon_token_in_a_non_git_segment_is_left_alone() -> None:
    assert rewriter.all_exclusion_prefixes("echo origin/main:.gitignore") == ()


def test_quoted_message_token_carrying_a_slash_and_a_dot_is_left_alone() -> None:
    command = "git commit -m \"don't touch a/b:.x\""
    assert rewriter.all_exclusion_prefixes(command) == ()
    assert rewriter.command_with_exclusion_export(command) == command


def test_url_token_in_a_curl_command_is_left_alone() -> None:
    assert rewriter.all_exclusion_prefixes("curl https://example.com/x") == ()


def test_git_segment_after_a_non_git_segment_still_contributes() -> None:
    assert rewriter.all_exclusion_prefixes(
        "echo start && git show origin/main:.gitignore"
    ) == ("origin/main:",)


def test_main_emits_an_allow_carrying_the_rewritten_command() -> None:
    emitted_text = _stdout_from_main(
        {
            "tool_name": "Bash",
            "tool_input": {"command": SETTINGS_SHOW_COMMAND, "description": "read settings"},
        }
    )
    assert json.loads(emitted_text) == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {
                "command": SETTINGS_SHOW_REWRITTEN,
                "description": "read settings",
            },
        }
    }


def test_main_emits_nothing_for_a_non_bash_tool() -> None:
    emitted_text = _stdout_from_main(
        {"tool_name": "PowerShell", "tool_input": {"command": SETTINGS_SHOW_COMMAND}}
    )
    assert emitted_text == ""


def test_main_emits_nothing_for_a_command_with_no_collected_prefix() -> None:
    emitted_text = _stdout_from_main(
        {"tool_name": "Bash", "tool_input": {"command": "git show HEAD:.gitignore"}}
    )
    assert emitted_text == ""
