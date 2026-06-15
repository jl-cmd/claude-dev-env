"""Tests for destructive-command-blocker hook."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_PATH = Path(__file__).parent / "destructive_command_blocker.py"
GH_GATE_USER_FACING_PREFIX = "[gh-gate]"
GH_REDIRECT_ACTIVE_ENV_VAR = "CLAUDE_GH_REDIRECT_ACTIVE"
GH_REDIRECT_ACTIVE_VALUE = "1"


def _run_hook(
    payload: dict,
    gh_redirect_active: bool = True,
) -> subprocess.CompletedProcess[str]:
    child_environment = os.environ.copy()
    if gh_redirect_active:
        child_environment[GH_REDIRECT_ACTIVE_ENV_VAR] = GH_REDIRECT_ACTIVE_VALUE
    else:
        child_environment.pop(GH_REDIRECT_ACTIVE_ENV_VAR, None)
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=child_environment,
    )


def _make_bash_payload(command: str) -> dict:
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def test_denies_gh_issue_comment_as_redirect_duplicate_guard() -> None:
    payload = _make_bash_payload(
        'gh issue comment 83 --repo jl-cmd/claude-code-config --body "hello"'
    )
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert (
        "gh issue comment" in response["hookSpecificOutput"]["permissionDecisionReason"]
    )
    assert (
        "duplicate execution"
        in response["hookSpecificOutput"]["permissionDecisionReason"]
    )


def test_denies_gh_pr_comment_as_redirect_duplicate_guard() -> None:
    payload = _make_bash_payload('gh pr comment 42 --body "ok"')
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "gh pr comment" in response["hookSpecificOutput"]["permissionDecisionReason"]


def test_denies_gh_pr_review_as_redirect_duplicate_guard() -> None:
    payload = _make_bash_payload("gh pr review 42 --approve")
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "gh pr review" in response["hookSpecificOutput"]["permissionDecisionReason"]


def test_denies_gh_api_post_comment_as_redirect_duplicate_guard() -> None:
    payload = _make_bash_payload(
        "gh api /repos/owner/name/issues/1/comments -X POST -f body=hello"
    )
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_suppresses_output_on_gh_redirect_deny() -> None:
    payload = _make_bash_payload('gh issue comment 1 --body "x"')
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["suppressOutput"] is True
    assert response["systemMessage"].startswith(GH_GATE_USER_FACING_PREFIX)


def test_asks_on_rm_rf_still_works() -> None:
    payload = _make_bash_payload("rm -rf /var/log/myapp")
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "rm -rf" in response["hookSpecificOutput"]["permissionDecisionReason"]


def test_asks_on_git_push_force_still_works() -> None:
    payload = _make_bash_payload("git push --force origin main")
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert (
        "git push --force" in response["hookSpecificOutput"]["permissionDecisionReason"]
    )


def test_allows_plain_command_without_destructive_pattern() -> None:
    payload = _make_bash_payload("ls -la")
    result = _run_hook(payload)
    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_ignores_non_bash_tool() -> None:
    payload = {"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}}
    result = _run_hook(payload)
    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_gh_issue_comment_is_allowed_when_redirect_env_var_is_unset() -> None:
    payload = _make_bash_payload('gh issue comment 83 --body "hello"')

    result = _run_hook(payload, gh_redirect_active=False)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_gh_pr_comment_is_allowed_when_redirect_env_var_is_unset() -> None:
    payload = _make_bash_payload('gh pr comment 42 --body "ok"')

    result = _run_hook(payload, gh_redirect_active=False)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_gh_pr_review_is_allowed_when_redirect_env_var_is_unset() -> None:
    payload = _make_bash_payload("gh pr review 42 --approve")

    result = _run_hook(payload, gh_redirect_active=False)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_gh_api_post_comment_is_allowed_when_redirect_env_var_is_unset() -> None:
    payload = _make_bash_payload(
        "gh api /repos/owner/name/issues/1/comments -X POST -f body=hello"
    )

    result = _run_hook(payload, gh_redirect_active=False)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def _run_rm_hook(payload: dict) -> subprocess.CompletedProcess[str]:
    child_environment = os.environ.copy()
    child_environment.pop(GH_REDIRECT_ACTIVE_ENV_VAR, None)
    child_environment.pop("CLAUDE_DESTRUCTIVE_DISABLE_EPHEMERAL_AUTO_ALLOW", None)
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=child_environment,
    )


def test_rm_rf_asks_when_target_is_non_ephemeral_path() -> None:
    payload = _make_bash_payload("rm -rf /var/log/myapp")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_allowed_when_target_is_under_tmp_segment() -> None:
    payload = _make_bash_payload("rm -rf /tmp/some_scratch_dir")

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_allowed_when_target_is_under_os_temp_directory() -> None:
    system_temp_subdirectory = Path(tempfile.mkdtemp(prefix="rm_target_"))
    forward_slash_temp_path = str(system_temp_subdirectory).replace("\\", "/")
    payload = _make_bash_payload(f"rm -rf {forward_slash_temp_path}")

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_allowed_when_target_is_under_worktrees_segment() -> None:
    payload = _make_bash_payload("rm -rf /Users/me/repo/worktrees/feature_branch/build")

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_asks_when_target_is_bare_worktrees_directory() -> None:
    payload = _make_bash_payload("rm -rf /Users/me/repo/worktrees")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_rm_includes_option_with_equals_sign() -> None:
    payload = _make_bash_payload("rm -rf --files0-from=/tmp/list /tmp/scratch")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_allowed_when_both_targets_are_ephemeral() -> None:
    payload = _make_bash_payload("rm -rf /tmp/first_dir /tmp/second_dir")

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_asks_when_any_target_is_non_ephemeral() -> None:
    payload = _make_bash_payload("rm -rf /tmp/scratch /etc/passwd")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_target_has_nested_temp_segment_not_at_root() -> None:
    _assert_hook_asks("rm -rf /home/victim/temp/secret")


def test_rm_rf_asks_when_double_dash_includes_hyphen_prefixed_non_ephemeral_target() -> None:
    payload = _make_bash_payload("rm -rf -- /tmp/scratch -non_ephemeral")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_allowed_when_compound_with_ampersand_and_absolute_ephemeral_target() -> None:
    payload = _make_bash_payload("rm -rf /tmp/reply && gh pr checks 19")

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_allowed_when_leading_cd_into_ephemeral_subdirectory_double_quoted() -> None:
    payload = _make_bash_payload('cd "/tmp/bugteam_scratch" && rm -rf .bugteam-tmp')

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_allowed_when_leading_cd_into_ephemeral_subdirectory_single_quoted() -> None:
    payload = _make_bash_payload("cd '/tmp/bugteam_scratch' && rm -rf .bugteam-tmp")

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_allowed_when_leading_cd_into_ephemeral_subdirectory_unquoted() -> None:
    payload = _make_bash_payload("cd /tmp/bugteam_scratch && rm -rf .bugteam-tmp")

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_allowed_when_leading_cd_into_windows_temp_worktree_subdirectory() -> None:
    windows_style_temp_worktree = (
        r"C:\Users\jon\AppData\Local\Temp\bugteam-pr-58-20260424071040\pr-58\worktree"
    )
    payload = _make_bash_payload(
        f'cd "{windows_style_temp_worktree}" && rm -rf .bugteam-tmp'
    )

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_allowed_when_leading_cd_into_ephemeral_with_extra_compound_after_rm() -> None:
    payload = _make_bash_payload(
        'cd "/tmp/bugteam_scratch" && rm -rf .bugteam-tmp && gh pr checks 19'
    )

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_asks_when_leading_cd_into_ephemeral_with_wildcard_target() -> None:
    payload = _make_bash_payload('cd "/tmp/bugteam_scratch" && rm -rf *')

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_cwd_ephemeral_and_relative_target_escapes_via_dotdot() -> None:
    payload = _make_bash_payload('cd "/tmp/bugteam_scratch" && rm -rf ../../etc')

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_rm_uses_files0_from_long_option_with_equals() -> None:
    payload = _make_bash_payload(
        'cd "/tmp/bugteam_scratch" && rm -rf --files0-from=/etc/passwd'
    )

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_rm_uses_unknown_long_option() -> None:
    payload = _make_bash_payload(
        'cd "/tmp/bugteam_scratch" && rm -rf --nuke /tmp/bugteam_scratch/stuff'
    )

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_rm_target_uses_windows_backslash_absolute_path_unquoted() -> None:
    payload = _make_bash_payload(
        r'cd "/tmp/bugteam_scratch" && rm -rf C:\sensitive\path'
    )

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_relative_target_without_declared_cwd_fails_closed() -> None:
    payload_with_no_cwd = {
        "tool_name": "Bash",
        "tool_input": {"command": "rm -rf relative/path"},
    }

    result = _run_rm_hook(payload_with_no_cwd)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_allowed_when_cwd_ephemeral_and_relative_target_stays_within() -> None:
    payload = _make_bash_payload('cd "/tmp/bugteam_scratch" && rm -rf ./build')

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_asks_when_tool_input_cwd_is_ephemeral_but_rm_target_is_absolute_non_ephemeral() -> None:
    payload_with_tool_input_cwd = {
        "tool_name": "Bash",
        "tool_input": {
            "command": "rm -rf /var/log/myapp",
            "cwd": "/tmp/bugteam_scratch",
        },
    }

    result = _run_rm_hook(payload_with_tool_input_cwd)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_subshell_cd_changes_dir_before_relative_rm() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && (cd /; rm -rf etc)')


def test_rm_rf_asks_when_second_top_level_cd_changes_dir_before_relative_rm() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && cd / && rm -rf etc')


def test_rm_rf_asks_when_pushd_changes_dir_before_relative_rm() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && pushd / && rm -rf etc')


def test_rm_rf_allowed_when_subshell_cd_present_but_rm_target_is_absolute_ephemeral() -> None:
    _assert_hook_allows('cd "/tmp/scratch" && (cd /; rm -rf /tmp/scratch/keep)')


def test_rm_rf_asks_when_cd_ephemeral_but_target_has_nested_tmp_segment_not_at_root() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && rm -rf /home/victim/tmp/secret')


def test_git_push_force_asks_when_leading_cd_into_ephemeral_subdirectory() -> None:
    payload = _make_bash_payload('cd "/tmp/bugteam_scratch" && git push --force')

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "git push --force" in response["hookSpecificOutput"]["permissionDecisionReason"]


def test_git_clean_force_recursive_asks_when_leading_cd_into_ephemeral_subdirectory() -> None:
    payload = _make_bash_payload('cd "/tmp/bugteam_scratch" && git clean -fd')

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "git clean -fd" in response["hookSpecificOutput"]["permissionDecisionReason"]


def test_rm_rf_plus_git_push_force_piggyback_asks_when_leading_cd_into_ephemeral() -> None:
    payload = _make_bash_payload(
        'cd "/tmp/bugteam_scratch" && rm -rf cache && git push --force'
    )

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_plus_git_clean_piggyback_asks_when_leading_cd_into_ephemeral() -> None:
    payload = _make_bash_payload(
        'cd "/tmp/bugteam_scratch" && rm -rf cache && git clean -fd'
    )

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_plus_mkfs_piggyback_asks_when_leading_cd_into_ephemeral() -> None:
    payload = _make_bash_payload(
        'cd "/tmp/bugteam_scratch" && rm -rf cache && mkfs.ext4 /dev/sda1'
    )

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_plus_drop_table_piggyback_asks_when_leading_cd_into_ephemeral() -> None:
    payload = _make_bash_payload(
        'cd "/tmp/bugteam_scratch" && rm -rf cache && psql -c "DROP TABLE users"'
    )

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_leading_cd_into_ephemeral_but_rm_target_is_bare_tmp_root() -> None:
    payload = _make_bash_payload('cd "/tmp/bugteam_scratch" && rm -rf /tmp')

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_leading_cd_into_ephemeral_but_rm_target_is_bare_worktrees_root() -> None:
    payload = _make_bash_payload('cd "/tmp/bugteam_scratch" && rm -rf /worktrees')

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_command_fails_shlex_parse_with_unbalanced_quotes() -> None:
    payload_with_tool_input_cwd = {
        "tool_name": "Bash",
        "tool_input": {
            "command": 'rm -rf "unclosed_quote',
            "cwd": "/tmp/bugteam_scratch",
        },
    }

    result = _run_rm_hook(payload_with_tool_input_cwd)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_leading_cd_target_is_non_ephemeral_directory() -> None:
    payload = _make_bash_payload('cd "/etc" && rm -rf scratch')

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_leading_cd_target_is_bare_ephemeral_root() -> None:
    payload = _make_bash_payload('cd "/tmp" && rm -rf scratch')

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_allowed_when_leading_cd_target_is_git_worktrees_directory() -> None:
    payload = _make_bash_payload('cd "/Users/me/repo/worktrees" && rm -rf feature')

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_asks_when_leading_cd_target_is_relative_path() -> None:
    payload = _make_bash_payload('cd "./scratch" && rm -rf inner')

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_allowed_for_chat_observed_bugteam_backslash_worktree_scratch_cleanup() -> None:
    payload = _make_bash_payload(
        r'cd "C:\Users\jon\AppData\Local\Temp\bugteam-pr-58-20260424071040\pr-58\worktree" && rm -rf .bugteam-tmp'
    )

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_allowed_for_chat_observed_bugteam_forward_slash_worktree_scratch_cleanup() -> None:
    payload = _make_bash_payload(
        'cd "C:/Users/jon/AppData/Local/Temp/bugteam-pr-58-20260424071040/pr-58/worktree" && rm -rf .bugteam-tmp'
    )

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_allowed_for_chat_observed_bugfix_reply_scratch_file_cleanup() -> None:
    payload = _make_bash_payload(
        'cd "C:/Users/jon/AppData/Local/Temp/bugteam-pr-58-20260424071040/pr-58/worktree" && rm -rf tmp_reply_loop1-1.md'
    )

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_allowed_for_chat_observed_bugfind_multiple_scratch_files_cleanup() -> None:
    payload = _make_bash_payload(
        'cd "C:/Users/jon/AppData/Local/Temp/bugteam-pr-58-20260424071040/pr-256/worktree" && rm -rf tmp_review_body.md tmp_finding_1.md'
    )

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_allowed_via_tool_input_cwd_pointing_at_chat_observed_bugteam_worktree() -> None:
    payload_with_tool_input_cwd = {
        "tool_name": "Bash",
        "tool_input": {
            "command": "rm -rf .bugteam-tmp",
            "cwd": "C:/Users/jon/AppData/Local/Temp/bugteam-pr-58-20260424071040/pr-58/worktree",
        },
    }

    result = _run_rm_hook(payload_with_tool_input_cwd)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_allowed_for_chat_observed_absolute_path_in_bugteam_windows_worktree_scratch() -> None:
    payload = _make_bash_payload(
        'rm -rf "C:/Users/jon/AppData/Local/Temp/bugteam-pr-58-20260424071040/pr-58/worktree/.bugteam-tmp"'
    )

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_asks_when_leading_cd_target_contains_command_substitution_dollar_parenthesis() -> None:
    payload = _make_bash_payload(
        'cd "/tmp/$(rm -rf ~/.ssh)" && ls'
    )

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_leading_cd_target_contains_backtick_command_substitution() -> None:
    payload = _make_bash_payload(
        'cd "/tmp/`rm -rf ~/.ssh`" && rm -rf .bugteam-tmp'
    )

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_leading_cd_target_contains_variable_expansion() -> None:
    payload = _make_bash_payload(
        'cd "/tmp/$SNEAKY_VAR" && rm -rf .bugteam-tmp'
    )

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_leading_cd_adjacent_quoted_strings_resolve_outside_ephemeral() -> None:
    payload = _make_bash_payload(
        'cd "/tmp/a""/../../etc" && rm -rf .'
    )

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_leading_cd_adjacent_quoted_strings_use_mixed_quotes() -> None:
    payload = _make_bash_payload(
        """cd "/tmp/a"'/../../etc' && rm -rf ."""
    )

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_target_is_bare_tmp_root() -> None:
    payload = _make_bash_payload("rm -rf /tmp")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_target_is_double_slash_tmp_root() -> None:
    payload = _make_bash_payload("rm -rf //tmp")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_target_is_bare_os_temp_root() -> None:
    payload = _make_bash_payload(f"rm -rf {tempfile.gettempdir()}")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_ephemeral_auto_allow_disabled_via_env_var() -> None:
    payload = _make_bash_payload("rm -rf /tmp/scratch")

    child_environment = os.environ.copy()
    child_environment.pop(GH_REDIRECT_ACTIVE_ENV_VAR, None)
    child_environment["CLAUDE_DESTRUCTIVE_DISABLE_EPHEMERAL_AUTO_ALLOW"] = "1"
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=child_environment,
    )

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_recursive_force_long_flags_allowed_under_tmp() -> None:
    payload = _make_bash_payload("rm --recursive --force /tmp/long_flag_scratch")

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_asks_when_quoted_dotdot_traverses_out_of_ephemeral_root() -> None:
    payload = _make_bash_payload('rm -rf /tmp/".."/etc')

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_allowed_when_quoted_path_is_legitimate_ephemeral() -> None:
    payload = _make_bash_payload('rm -rf "/tmp/some scratch dir"')

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_asks_when_single_quoted_dotdot_traverses_out_of_ephemeral() -> None:
    payload = _make_bash_payload("rm -rf /tmp/'..'/etc")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_target_is_glob_wildcard_under_tmp() -> None:
    payload = _make_bash_payload("rm -rf /tmp/*")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_target_is_question_mark_glob_under_tmp() -> None:
    payload = _make_bash_payload("rm -rf /tmp/?")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_target_is_bracket_glob_under_tmp() -> None:
    payload = _make_bash_payload("rm -rf /tmp/[abc]")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_target_is_worktrees_glob() -> None:
    payload = _make_bash_payload("rm -rf /worktrees/*")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_target_is_os_temp_root_glob() -> None:
    system_temporary_root = tempfile.gettempdir()
    forward_slash_temp_root = system_temporary_root.replace("\\", "/")
    payload = _make_bash_payload(f"rm -rf {forward_slash_temp_root}/*")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_allowed_when_unquoted_windows_backslash_target_is_ephemeral() -> None:
    system_temporary_root = tempfile.gettempdir()
    windows_style_target = system_temporary_root.replace("/", "\\") + "\\scratch"
    payload = _make_bash_payload(f"rm -rf {windows_style_target}")

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_allowed_when_unquoted_windows_backslash_target_contains_worktrees_segment() -> None:
    payload = _make_bash_payload(
        r"rm -rf C:\Users\developer\project\worktrees\feature_branch\build"
    )

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_allowed_when_finding_example_windows_backslash_ephemeral_target() -> None:
    payload = _make_bash_payload(
        r"rm -rf C:\Users\jon\AppData\Local\Temp\scratch"
    )

    result = _run_rm_hook(payload)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_rm_rf_asks_when_target_is_literal_tmp_star_finding_example() -> None:
    payload = _make_bash_payload("rm -rf /tmp/*")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_target_basename_is_wildcard_with_prefix_under_tmp() -> None:
    payload = _make_bash_payload("rm -rf /tmp/foo*")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def _run_hook_with_fake_home(
    payload: dict,
    fake_home: Path,
    working_directory: Path,
    disable_ephemeral_auto_allow: bool = True,
) -> subprocess.CompletedProcess[str]:
    child_environment = os.environ.copy()
    child_environment.pop(GH_REDIRECT_ACTIVE_ENV_VAR, None)
    child_environment["HOME"] = str(fake_home)
    child_environment["USERPROFILE"] = str(fake_home)
    if disable_ephemeral_auto_allow:
        child_environment["CLAUDE_DESTRUCTIVE_DISABLE_EPHEMERAL_AUTO_ALLOW"] = "1"
    else:
        child_environment.pop("CLAUDE_DESTRUCTIVE_DISABLE_EPHEMERAL_AUTO_ALLOW", None)
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=child_environment,
        cwd=str(working_directory),
    )


def _write_settings_with_allow_list(fake_home: Path, allow_list: list[str]) -> None:
    claude_directory = fake_home / ".claude"
    claude_directory.mkdir(parents=True, exist_ok=True)
    settings_payload = {"hooks": {"allowGitResetHardProjects": allow_list}}
    (claude_directory / "settings.json").write_text(
        json.dumps(settings_payload), encoding="utf-8"
    )


def test_git_reset_hard_allowed_when_cwd_matches_settings_allow_list(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    project_directory = tmp_path / "approved_project"
    project_directory.mkdir()
    project_path_forward = str(project_directory).replace("\\", "/")
    _write_settings_with_allow_list(fake_home, [project_path_forward])
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, project_directory)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_git_reset_hard_asks_when_cwd_not_in_settings_allow_list(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    approved_directory = tmp_path / "approved_project"
    approved_directory.mkdir()
    unapproved_directory = tmp_path / "unapproved_project"
    unapproved_directory.mkdir()
    approved_path_forward = str(approved_directory).replace("\\", "/")
    _write_settings_with_allow_list(fake_home, [approved_path_forward])
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, unapproved_directory)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "git reset --hard" in response["hookSpecificOutput"]["permissionDecisionReason"]


def test_git_reset_hard_asks_when_settings_missing(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    project_directory = tmp_path / "unapproved_project"
    project_directory.mkdir()
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, project_directory)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_git_reset_hard_asks_when_allow_list_is_empty(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    project_directory = tmp_path / "some_project"
    project_directory.mkdir()
    _write_settings_with_allow_list(fake_home, [])
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, project_directory)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_git_reset_hard_allowed_in_linked_git_worktree(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    main_repository = tmp_path / "main_repository"
    main_repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=main_repository, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=main_repository, check=True)
    worktree_directory = tmp_path / "worktree_copy"
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "feature", str(worktree_directory)],
        cwd=main_repository,
        check=True,
    )
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, worktree_directory, disable_ephemeral_auto_allow=False)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_git_reset_hard_allowed_when_path_contains_worktrees_segment(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    worktree_directory = tmp_path / "worktrees" / "some_feature"
    worktree_directory.mkdir(parents=True)
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, worktree_directory, disable_ephemeral_auto_allow=False)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_git_reset_hard_allowed_under_os_temp_directory() -> None:
    fake_home = Path(tempfile.mkdtemp(prefix="home_"))
    working_directory = Path(tempfile.mkdtemp(prefix="ephemeral_work_"))
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, working_directory, disable_ephemeral_auto_allow=False)

    assert result.stdout.strip() == ""
    assert result.returncode == 0


def test_git_reset_hard_asks_in_plain_directory_with_no_settings(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    plain_directory = tmp_path / "regular_project"
    plain_directory.mkdir()
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, plain_directory)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_git_reset_hard_asks_when_settings_file_is_invalid_json(tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    (fake_home / ".claude").mkdir(parents=True)
    (fake_home / ".claude" / "settings.json").write_text(
        "{not valid json", encoding="utf-8"
    )
    project_directory = tmp_path / "unapproved_project"
    project_directory.mkdir()
    payload = _make_bash_payload("git reset --hard origin/main")

    result = _run_hook_with_fake_home(payload, fake_home, project_directory)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


# --- compound ephemeral rm and quoted-mention guard tests ---


def _assert_hook_allows(command: str) -> None:
    result = _run_rm_hook(_make_bash_payload(command))
    assert result.stdout.strip() == "", (
        f"Expected allow (no output) for {command!r}, got: {result.stdout!r}"
    )
    assert result.returncode == 0


def _assert_hook_asks(command: str, expected_reason_fragment: str | None = None) -> None:
    result = _run_rm_hook(_make_bash_payload(command))
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask", (
        f"Expected ask for {command!r}, got: {response!r}"
    )
    if expected_reason_fragment is not None:
        assert (
            expected_reason_fragment
            in response["hookSpecificOutput"]["permissionDecisionReason"]
        ), f"Reason must mention {expected_reason_fragment!r}, got: {response!r}"


def test_compound_rm_allowed_when_two_absolute_ephemeral_targets_then_echo() -> None:
    _assert_hook_allows("rm -rf /tmp/pr136 /tmp/difftest && echo 'cleaned'")


def test_compound_rm_allowed_when_subshell_paren_glued_rm_targets_absolute_ephemeral() -> None:
    _assert_hook_allows("rm -rf /tmp/a && (rm -rf /tmp/b)")


def test_compound_rm_asks_when_subshell_paren_glued_rm_targets_non_ephemeral() -> None:
    _assert_hook_asks("rm -rf /tmp/a && (rm -rf /etc)")


def test_compound_rm_allowed_when_followed_by_gh_pipeline_and_echo() -> None:
    _assert_hook_allows('rm -rf /tmp/reply && gh pr checks 19 2>&1 | head -5 && echo "x"')


def test_compound_rm_allowed_when_followed_by_gh_command() -> None:
    _assert_hook_allows("rm -rf /tmp/reply && gh pr checks 19")


def test_compound_rm_asks_when_shred_targets_non_ephemeral_path() -> None:
    _assert_hook_asks("rm -rf /tmp/x && shred -u /etc/passwd")


def test_compound_rm_asks_when_truncate_targets_non_ephemeral_path() -> None:
    _assert_hook_asks("rm -rf /tmp/x && truncate -s0 /etc/passwd")


def test_compound_rm_asks_when_find_delete_walks_root() -> None:
    _assert_hook_asks("rm -rf /tmp/x && find / -name secret -delete")


def test_compound_rm_asks_when_chmod_recursive_targets_non_ephemeral_path() -> None:
    _assert_hook_asks("rm -rf /tmp/x && chmod -R 000 /etc")


def test_compound_rm_asks_when_mv_moves_non_ephemeral_path() -> None:
    _assert_hook_asks("rm -rf /tmp/x && mv /home/user/important /tmp/x2")


def test_compound_rm_asks_when_gh_repo_delete_rides_alongside_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && gh repo delete jl-cmd/foo --yes")


def test_compound_rm_asks_when_git_checkout_discards_worktree_after_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git checkout -- .")


def test_compound_rm_asks_when_git_stash_drop_rides_alongside_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git stash drop")


def test_compound_rm_asks_when_git_branch_force_delete_rides_alongside_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git branch -D main")


def test_compound_rm_asks_when_git_clean_force_rides_alongside_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git clean -fd")


def test_compound_rm_asks_when_git_rm_rides_alongside_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git rm -rf src")


def test_compound_rm_asks_when_benign_segment_redirects_into_non_ephemeral_file() -> None:
    _assert_hook_asks("rm -rf /tmp/x && cat /dev/null > /etc/important.conf")


def test_compound_rm_asks_when_benign_segment_appends_redirect_to_non_ephemeral_file() -> None:
    _assert_hook_asks("rm -rf /tmp/x && echo hi >> /etc/important.conf")


def test_compound_rm_allowed_when_gh_read_only_subcommand_follows_ephemeral_rm() -> None:
    _assert_hook_allows("rm -rf /tmp/reply && gh pr view 19")


def test_compound_rm_allowed_when_git_read_only_subcommand_follows_ephemeral_rm() -> None:
    _assert_hook_allows("rm -rf /tmp/reply && git status")


def test_compound_rm_asks_when_benign_segment_glues_redirect_to_non_ephemeral_file() -> None:
    _assert_hook_asks("rm -rf /tmp/x && echo pwned>/etc/passwd")


def test_compound_rm_asks_when_benign_segment_glues_append_redirect_to_non_ephemeral_file() -> None:
    _assert_hook_asks("rm -rf /tmp/x && echo hi>>/etc/important.conf")


def test_compound_rm_asks_when_benign_segment_uses_fd_prefixed_redirect_to_non_ephemeral_file() -> None:
    _assert_hook_asks("rm -rf /tmp/x && echo hi 1>/etc/important.conf")


def test_compound_rm_asks_when_benign_segment_uses_glued_combined_redirect_to_non_ephemeral_file() -> None:
    _assert_hook_asks("rm -rf /tmp/x && echo hi &>/etc/important.conf")


def test_compound_rm_asks_when_benign_segment_glues_redirect_directly_to_program() -> None:
    _assert_hook_asks("rm -rf /tmp/x && cat secret>/etc/important.conf")


def test_compound_rm_asks_when_sort_writes_output_file_to_non_ephemeral_path() -> None:
    _assert_hook_asks("rm -rf /tmp/x && sort -o /etc/important.conf /etc/passwd")


def test_compound_rm_asks_when_rm_target_glues_redirect_to_non_ephemeral_file() -> None:
    _assert_hook_asks("rm -rf /tmp/x>/etc/passwd")


def test_compound_rm_asks_when_rm_target_glues_append_redirect_to_non_ephemeral_file() -> None:
    _assert_hook_asks("rm -rf /tmp/x>>/etc/passwd")


def test_compound_rm_asks_when_second_rm_target_glues_redirect_to_non_ephemeral_file() -> None:
    _assert_hook_asks("rm -rf /tmp/a /tmp/b>/etc/hosts")


def test_rm_rf_asks_when_cd_ephemeral_but_rm_segment_redirects_to_non_ephemeral_file() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && rm -rf /tmp/x>/etc/passwd')


def test_rm_rf_asks_when_cd_ephemeral_but_relative_rm_target_redirects_to_non_ephemeral_file() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && rm -rf build>/etc/passwd')


def test_compound_rm_asks_when_git_config_sets_value_after_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git config --global user.name evil")


def test_compound_rm_asks_when_git_config_sets_value_equal_to_long_read_only_flag() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git config core.editor --get")


def test_compound_rm_asks_when_git_config_sets_value_equal_to_list_read_only_flag() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git config alias.x --list")


def test_compound_rm_asks_when_git_config_sets_value_equal_to_short_read_only_flag() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git config core.pager -l")


def test_compound_rm_allowed_when_git_config_get_urlmatch_reads_after_ephemeral_rm() -> None:
    _assert_hook_allows("rm -rf /tmp/reply && git config --get-urlmatch a b")


def test_compound_rm_asks_when_git_remote_add_rides_alongside_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git remote add evil http://e")


def test_compound_rm_asks_when_git_remote_remove_rides_alongside_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git remote remove origin")


def test_compound_rm_asks_when_gh_api_http_delete_rides_alongside_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && gh api repos/foo -X DELETE")


def test_compound_rm_asks_when_gh_api_raw_field_implicit_post_rides_alongside_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && gh api repos/o/r/issues -f title=x")


def test_compound_rm_asks_when_gh_api_field_file_implicit_post_rides_alongside_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && gh api -F a=@b repos/o/r/comments")


def test_compound_rm_asks_when_gh_api_input_implicit_post_rides_alongside_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && gh api repos/o/r/x --input body.json")


def test_compound_rm_allowed_when_gh_api_field_with_explicit_get_follows_ephemeral_rm() -> None:
    _assert_hook_allows("rm -rf /tmp/reply && gh api repos/foo -X GET -f a=b")


def test_compound_rm_asks_when_gh_api_glued_short_delete_rides_alongside_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && gh api repos/foo -XDELETE")


def test_compound_rm_asks_when_gh_api_glued_long_delete_rides_alongside_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && gh api repos/foo --method=DELETE")


def test_compound_rm_asks_when_gh_api_glued_short_put_rides_alongside_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && gh api repos/foo -XPUT")


def test_compound_rm_asks_when_gh_api_glued_long_patch_lowercase_rides_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && gh api repos/foo --method=patch")


def test_compound_rm_allowed_when_gh_api_glued_short_get_follows_ephemeral_rm() -> None:
    _assert_hook_allows("rm -rf /tmp/reply && gh api repos/foo -XGET")


def test_compound_rm_allowed_when_gh_api_glued_long_get_follows_ephemeral_rm() -> None:
    _assert_hook_allows("rm -rf /tmp/reply && gh api repos/foo --method=GET")


def test_compound_rm_asks_when_gh_repo_delete_targets_read_only_verb_named_repo() -> None:
    _assert_hook_asks("rm -rf /tmp/x && gh repo delete status --yes")


def test_compound_rm_asks_when_git_stash_drop_targets_read_only_verb_named_ref() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git stash drop status")


def test_compound_rm_asks_when_git_branch_force_delete_targets_read_only_verb_named_branch() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git branch -D log")


def test_compound_rm_asks_when_git_checkout_discards_read_only_verb_named_path() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git checkout -- log")


def test_compound_rm_asks_when_git_push_targets_read_only_verb_named_ref() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git push origin log")


def test_compound_rm_allowed_when_gh_pr_view_takes_read_only_verb_named_argument() -> None:
    _assert_hook_allows("rm -rf /tmp/reply && gh pr view status")


def test_compound_rm_asks_when_git_remote_add_after_verbose_flag_rides_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git remote -v add evil http://attacker")


def test_compound_rm_asks_when_git_remote_set_url_after_verbose_flag_rides_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git remote -v set-url origin http://evil")


def test_compound_rm_asks_when_stdbuf_separate_output_value_wraps_bash_dash_c() -> None:
    _assert_hook_asks('stdbuf -o L bash -c "rm -rf /etc"')


def test_compound_rm_asks_when_stdbuf_long_output_value_wraps_bash_dash_c() -> None:
    _assert_hook_asks('stdbuf --output L bash -c "rm -rf /etc"')


def test_compound_rm_asks_when_stdbuf_separate_error_value_wraps_bash_dash_c() -> None:
    _assert_hook_asks('stdbuf -e 0 bash -c "rm -rf /etc"')


def test_compound_rm_asks_when_ionice_classdata_name_wraps_bash_dash_c() -> None:
    _assert_hook_asks('ionice --classdata foo bash -c "rm -rf /etc"')


def test_compound_rm_allowed_when_git_config_lists_after_ephemeral_rm() -> None:
    _assert_hook_allows("rm -rf /tmp/reply && git config --list")


def test_compound_rm_allowed_when_git_remote_lists_after_ephemeral_rm() -> None:
    _assert_hook_allows("rm -rf /tmp/reply && git remote -v")


def test_compound_rm_allowed_when_gh_api_get_follows_ephemeral_rm() -> None:
    _assert_hook_allows("rm -rf /tmp/reply && gh api repos/foo")


def test_quoted_mention_allowed_when_rm_appears_inside_grep_pattern() -> None:
    _assert_hook_allows("grep 'rm -rf foo' history.jsonl | tail -5")


def test_quoted_mention_allowed_when_rm_appears_inside_echo_argument() -> None:
    _assert_hook_allows('echo "rm -rf x"')


def test_quoted_mention_allowed_when_rm_appears_inside_git_commit_message() -> None:
    _assert_hook_allows('git commit -m "rm -rf cleanup"')


def test_compound_rm_asks_when_single_target_is_non_ephemeral() -> None:
    _assert_hook_asks("rm -rf /var/log/myapp")


def test_compound_rm_asks_when_second_rm_segment_targets_non_ephemeral() -> None:
    _assert_hook_asks("rm -rf /tmp/x && rm -rf /etc")


def test_compound_rm_asks_when_force_push_rides_alongside_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git push --force origin main")


def test_compound_rm_asks_when_git_reset_hard_rides_alongside_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && git reset --hard")


def test_compound_rm_asks_when_command_substitution_present() -> None:
    _assert_hook_asks("rm -rf /tmp/x && echo $(whoami)")


def test_compound_rm_asks_when_backtick_substitution_present() -> None:
    _assert_hook_asks("rm -rf /tmp/x && echo `whoami`")


def test_compound_rm_asks_when_relative_target_without_declared_cwd() -> None:
    _assert_hook_asks("rm -rf scratch && echo done")


def test_compound_rm_asks_when_rm_token_is_a_variable_expansion() -> None:
    _assert_hook_asks("$RM -rf /etc")


def test_quoted_mention_asks_when_absolute_path_rm_runs_on_non_ephemeral() -> None:
    _assert_hook_asks("/bin/rm -rf /etc")


def test_quoted_mention_asks_when_sudo_rm_runs_on_non_ephemeral() -> None:
    _assert_hook_asks("sudo rm -rf /etc")


def test_quoted_mention_asks_when_backslash_rm_runs_on_non_ephemeral() -> None:
    _assert_hook_asks(r"\rm -rf /etc")


def test_quoted_mention_asks_when_real_force_push_rides_alongside_quoted_rm() -> None:
    _assert_hook_asks(
        "grep 'rm -rf' f && git push --force origin main",
        expected_reason_fragment="git push --force",
    )


def test_interpreter_execution_asks_when_bash_dash_c_runs_quoted_rm() -> None:
    _assert_hook_asks("bash -c 'rm -rf /etc'")


def test_interpreter_execution_asks_when_sh_dash_c_runs_quoted_rm() -> None:
    _assert_hook_asks("sh -c 'rm -rf /home/user/x'")


def test_interpreter_execution_asks_when_eval_runs_quoted_rm() -> None:
    _assert_hook_asks("eval 'rm -rf /etc'")


def test_interpreter_execution_asks_when_ssh_runs_remote_quoted_rm() -> None:
    _assert_hook_asks("ssh host 'rm -rf /etc'")


def test_interpreter_execution_asks_when_python_dash_c_runs_quoted_rm() -> None:
    _assert_hook_asks("""python -c "import os; os.system('rm -rf /etc')\"""")


def test_interpreter_execution_asks_when_awk_system_runs_quoted_rm() -> None:
    _assert_hook_asks("""awk 'BEGIN{system("rm -rf /etc")}'""")


def test_interpreter_execution_asks_when_gawk_system_runs_quoted_rm() -> None:
    _assert_hook_asks("""gawk 'BEGIN{system("rm -rf /etc")}'""")


def test_interpreter_execution_asks_when_make_runs_quoted_rm() -> None:
    _assert_hook_asks("""make -f - 'rm -rf /etc'""")


def test_compound_rm_asks_when_awk_segment_runs_quoted_rm_after_ephemeral_rm() -> None:
    _assert_hook_asks("""rm -rf /tmp/x && awk 'BEGIN{system("rm -rf /etc")}'""")


def test_interpreter_execution_asks_when_benign_command_precedes_bash_dash_c() -> None:
    _assert_hook_asks("echo hi && bash -c 'rm -rf /etc'")


def test_interpreter_execution_asks_when_benign_command_precedes_ssh() -> None:
    _assert_hook_asks("ls && ssh host 'rm -rf /etc'")


def test_interpreter_execution_asks_when_benign_command_precedes_eval() -> None:
    _assert_hook_asks("true; eval 'rm -rf /etc'")


def test_interpreter_execution_asks_when_benign_command_precedes_python_dash_c() -> None:
    _assert_hook_asks(
        """echo start && python -c "import os; os.system('rm -rf /etc')\""""
    )


def test_launcher_execution_asks_when_timeout_wraps_bash_dash_c() -> None:
    _assert_hook_asks("timeout 5 bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_nohup_wraps_bash_dash_c() -> None:
    _assert_hook_asks("nohup bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_nice_wraps_bash_dash_c() -> None:
    _assert_hook_asks("nice -n 10 bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_stdbuf_wraps_bash_dash_c() -> None:
    _assert_hook_asks("stdbuf -oL bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_time_wraps_bash_dash_c() -> None:
    _assert_hook_asks("time bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_setsid_wraps_bash_dash_c() -> None:
    _assert_hook_asks("setsid bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_ionice_wraps_bash_dash_c() -> None:
    _assert_hook_asks("ionice bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_chrt_wraps_bash_dash_c() -> None:
    _assert_hook_asks("chrt 1 bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_taskset_wraps_bash_dash_c() -> None:
    _assert_hook_asks("taskset -c 0 bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_stacked_wrappers_precede_bash_dash_c() -> None:
    _assert_hook_asks("nice -n 5 timeout 5 bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_timeout_wraps_python_dash_c() -> None:
    _assert_hook_asks(
        """timeout 5 python -c "import os; os.system('rm -rf /etc')\""""
    )


def test_launcher_execution_asks_when_timeout_wraps_bash_after_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && timeout 5 bash -c 'rm -rf /etc'")


def test_launcher_execution_allows_when_timeout_wraps_ephemeral_rm() -> None:
    _assert_hook_allows("timeout 5 rm -rf /tmp/scratch")


def test_launcher_execution_asks_when_taskset_hex_mask_wraps_bash_dash_c() -> None:
    _assert_hook_asks("taskset 0x1 bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_taskset_hex_mask_absolute_path_wraps_bash_dash_c() -> None:
    _assert_hook_asks("/usr/bin/taskset 0xff bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_taskset_cpu_range_wraps_bash_dash_c() -> None:
    _assert_hook_asks("taskset -c 0-3 bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_timeout_duration_suffix_wraps_bash_dash_c() -> None:
    _assert_hook_asks("timeout 5s bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_taskset_hex_mask_wraps_bash_after_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && timeout 5s bash -c 'rm -rf /etc'")


def test_newline_separated_interpreter_asks_when_bash_dash_c_runs_quoted_rm() -> None:
    _assert_hook_asks("echo safe\nbash -c 'rm -rf /etc'")


def test_carriage_return_separated_interpreter_asks_when_bash_dash_c_runs_quoted_rm() -> None:
    _assert_hook_asks("echo hi\rbash -c 'rm -rf /etc'")


def test_brace_group_newline_interpreter_asks_when_bash_dash_c_runs_quoted_rm() -> None:
    _assert_hook_asks("{ echo hi\nbash -c 'rm -rf /etc'; }")


def test_launcher_execution_asks_when_timeout_separate_signal_value_wraps_bash_dash_c() -> None:
    _assert_hook_asks("timeout -s KILL 5 bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_timeout_separate_sigkill_signal_wraps_bash_dash_c() -> None:
    _assert_hook_asks("timeout -s SIGKILL 5 bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_timeout_long_signal_value_wraps_bash_dash_c() -> None:
    _assert_hook_asks("timeout --signal KILL 5 bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_timeout_kill_after_value_wraps_bash_dash_c() -> None:
    _assert_hook_asks("timeout -k 1 5 bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_timeout_separate_signal_wraps_bash_after_ephemeral_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && timeout -s KILL 5 bash -c 'rm -rf /etc'")


def test_subshell_grouped_rm_asks_when_parenthesis_glued_to_rm() -> None:
    _assert_hook_asks("(rm -rf /etc)")


def test_brace_grouped_rm_asks_when_brace_glued_to_rm() -> None:
    _assert_hook_asks("{ rm -rf /etc; }")


def test_glued_semicolon_rm_asks_when_semicolon_prefixes_rm() -> None:
    _assert_hook_asks(";rm -rf /etc")


def test_glued_pipe_rm_asks_when_pipe_joins_echo_to_rm() -> None:
    _assert_hook_asks("echo|rm -rf /etc")


def test_subshell_grouped_rm_asks_when_benign_command_precedes_grouped_rm() -> None:
    _assert_hook_asks("echo hi; (rm -rf /etc)")


def test_string_execution_asks_when_subshell_paren_glued_to_bash_dash_c() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && (bash -c \'rm -rf /etc\')')


def test_string_execution_asks_when_subshell_paren_glued_to_timeout_wrapping_bash() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && (timeout 5 bash -c \'rm -rf /etc\')')


def test_rm_rf_asks_when_cd_ephemeral_but_subshell_paren_glued_to_rm_targets_etc() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && (rm -rf /etc)')


def test_rm_rf_asks_when_cd_ephemeral_but_brace_glued_to_rm_targets_etc() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && {rm -rf /etc;}')


def test_rm_rf_allowed_when_cd_ephemeral_and_subshell_paren_wraps_relative_ephemeral_target() -> None:
    _assert_hook_allows('cd "/tmp/scratch" && (rm -rf build)')


# --- convergence branch exemption unit tests ---

import importlib.util

_HOOK_DIR = Path(__file__).parent
_hook_spec = importlib.util.spec_from_file_location(
    "destructive_command_blocker",
    _HOOK_DIR / "destructive_command_blocker.py",
)
assert _hook_spec is not None
assert _hook_spec.loader is not None
_hook_module = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(_hook_module)
_force_push_targets_convergence_branch = _hook_module._force_push_targets_convergence_branch
_is_convergence_branch = _hook_module._is_convergence_branch
_all_refspecs_are_convergence_branches = _hook_module._all_refspecs_are_convergence_branches
_find_non_force_push_destructive_hazard = _hook_module._find_non_force_push_destructive_hazard


def test_convergence_branch_claude_prefix_allowed() -> None:
    assert _force_push_targets_convergence_branch(
        "git push --force origin claude/fix-123"
    )


def test_convergence_branch_worktree_prefix_allowed() -> None:
    assert _force_push_targets_convergence_branch(
        "git push --force origin worktree-pr-converge-418"
    )


def test_convergence_branch_pr_converge_allowed() -> None:
    assert _force_push_targets_convergence_branch(
        "git push --force origin pr-423-converge"
    )


def test_convergence_branch_f_variant_allowed() -> None:
    assert _force_push_targets_convergence_branch(
        "git push -f origin claude/fix-123"
    )


def test_convergence_branch_main_blocked() -> None:
    assert not _force_push_targets_convergence_branch(
        "git push --force origin main"
    )


def test_convergence_branch_refspec_destination_checked() -> None:
    assert not _force_push_targets_convergence_branch(
        "git push --force origin claude/fix:main"
    )


def test_convergence_branch_multi_refspec_main_blocked() -> None:
    assert not _force_push_targets_convergence_branch(
        "git push --force origin claude/fix-123 main"
    )


def test_convergence_branch_multi_refspec_all_convergence() -> None:
    assert _force_push_targets_convergence_branch(
        "git push --force origin claude/fix-123 worktree-other"
    )


def test_convergence_branch_multi_refspec_mixed_blocked() -> None:
    assert not _force_push_targets_convergence_branch(
        "git push --force origin claude/fix-123 main worktree-other"
    )


def test_convergence_branch_compound_main_piggyback_blocked() -> None:
    assert not _force_push_targets_convergence_branch(
        "git push --force origin claude/foo && git push --force origin main"
    )


def test_is_convergence_branch_claude_prefix() -> None:
    assert _is_convergence_branch("claude/fix-123")


def test_is_convergence_branch_worktree_prefix() -> None:
    assert _is_convergence_branch("worktree-pr-418")


def test_is_convergence_branch_pr_converge() -> None:
    assert _is_convergence_branch("pr-423-converge")


def test_is_convergence_branch_main_rejected() -> None:
    assert not _is_convergence_branch("main")


def test_is_convergence_branch_pr_converge_no_end_anchor() -> None:
    assert not _is_convergence_branch("pr-423-converge-extra")


def test_all_refspecs_empty_string_returns_false() -> None:
    assert not _all_refspecs_are_convergence_branches("")


def test_all_refspecs_whitespace_only_returns_false() -> None:
    assert not _all_refspecs_are_convergence_branches("   ")


def test_all_refspecs_flag_only_returns_false() -> None:
    assert not _all_refspecs_are_convergence_branches("--no-verify")


def test_all_refspecs_multiple_flags_only_returns_false() -> None:
    assert not _all_refspecs_are_convergence_branches("--no-verify --force")


def test_all_refspecs_flag_then_branch_checks_branch() -> None:
    assert not _all_refspecs_are_convergence_branches("--force main")


def test_all_refspecs_convergence_branch_with_flags() -> None:
    assert _all_refspecs_are_convergence_branches("--force claude/fix-123")


def test_force_push_convergence_with_no_verify_blocked() -> None:
    payload = _make_bash_payload(
        "git push --force origin --no-verify claude/fix-123"
    )

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "--no-verify" in response["hookSpecificOutput"]["permissionDecisionReason"]


def test_force_push_convergence_with_no_gpg_sign_blocked() -> None:
    payload = _make_bash_payload(
        "git push --force origin --no-gpg-sign claude/fix-123"
    )

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "--no-gpg-sign" in response["hookSpecificOutput"]["permissionDecisionReason"]


def test_force_push_convergence_allowed_when_quoted_rm_mention_precedes_push() -> None:
    _assert_hook_allows('echo "rm -rf foo" && git push --force origin claude/fix-123')


def test_force_push_main_asks_when_quoted_rm_mention_precedes_push() -> None:
    _assert_hook_asks(
        'echo "rm -rf foo" && git push --force origin main',
        expected_reason_fragment="git push --force",
    )


def test_compound_rm_asks_when_pipe_both_joins_tee_to_non_ephemeral_file() -> None:
    _assert_hook_asks("rm -rf /tmp/x && cat foo |& tee /etc/passwd")


def test_compound_rm_asks_when_glued_pipe_both_joins_tee_to_non_ephemeral_file() -> None:
    _assert_hook_asks("rm -rf /tmp/x && cat foo|&tee /etc/passwd")


def test_compound_rm_asks_when_pipe_both_joins_tee_append_to_non_ephemeral_file() -> None:
    _assert_hook_asks("rm -rf /tmp/x && cat foo |& tee -a /etc/passwd")


def test_find_non_force_push_hazard_detects_tee_after_pipe_both_operator() -> None:
    hazard_description = _find_non_force_push_destructive_hazard(
        "git push --force origin claude/x && cat foo |& tee /etc/passwd"
    )
    assert hazard_description is None or "rm" not in hazard_description
    assert not _hook_module.rm_compound_targets_only_absolute_ephemeral_paths(
        "rm -rf /tmp/x && cat foo |& tee /etc/passwd"
    )


def test_compound_rm_asks_when_glued_semicolon_hides_shred_segment() -> None:
    _assert_hook_asks("rm -rf /tmp/x && echo hi;shred -u /etc/passwd")


def test_compound_rm_asks_when_glued_and_operator_hides_rm_on_non_ephemeral() -> None:
    _assert_hook_asks("rm -rf /tmp/x && echo a&&rm -rf /etc")


def test_compound_rm_asks_when_glued_semicolon_hides_interpreter_running_rm() -> None:
    _assert_hook_asks("rm -rf /tmp/x && echo a;bash -c 'rm -rf /etc'")


def test_compound_rm_asks_when_glued_semicolon_hides_gh_repo_delete() -> None:
    _assert_hook_asks("rm -rf /tmp/x && echo a;gh repo delete jl-cmd/foo --yes")


def test_compound_rm_asks_when_glued_semicolon_hides_rm_after_gh_view() -> None:
    _assert_hook_asks("rm -rf /tmp/reply && gh pr view 1;rm -rf /etc")


def test_compound_rm_asks_when_glued_background_operator_hides_shred_segment() -> None:
    _assert_hook_asks("rm -rf /tmp/x && echo a&shred -u /etc/passwd")


def test_compound_rm_asks_when_glued_or_operator_hides_rm_on_non_ephemeral() -> None:
    _assert_hook_asks("rm -rf /tmp/x && echo a||rm -rf /etc")


def test_compound_rm_asks_when_newline_terminator_hides_shred_segment() -> None:
    _assert_hook_asks("rm -rf /tmp/x && echo a\nshred -u /etc/passwd")


def test_compound_rm_asks_when_git_fetch_force_refspec_rewrites_local_branch() -> None:
    _assert_hook_asks(
        "rm -rf /tmp/x && git fetch origin +refs/heads/main:refs/heads/main"
    )


def test_compound_rm_asks_when_git_fetch_long_force_flag_rewrites_local_branch() -> None:
    _assert_hook_asks(
        "rm -rf /tmp/x && git fetch --force origin refs/heads/main:refs/heads/main"
    )


def test_compound_rm_asks_when_git_fetch_short_force_flag_rewrites_local_branch() -> None:
    _assert_hook_asks(
        "rm -rf /tmp/x && git fetch -f origin refs/heads/main:refs/heads/main"
    )


def test_compound_rm_allowed_when_plain_git_fetch_follows_ephemeral_rm() -> None:
    _assert_hook_allows("rm -rf /tmp/reply && git fetch")


def test_compound_rm_allowed_when_git_fetch_origin_branch_follows_ephemeral_rm() -> None:
    _assert_hook_allows("rm -rf /tmp/reply && git fetch origin main")


def test_launcher_execution_asks_when_timeout_infinity_wraps_bash_dash_c() -> None:
    _assert_hook_asks("timeout inf bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_timeout_millisecond_duration_wraps_bash_dash_c() -> None:
    _assert_hook_asks("timeout 100ms bash -c 'rm -rf /etc'")


def test_launcher_execution_asks_when_nice_then_timeout_infinity_wraps_bash_dash_c() -> None:
    _assert_hook_asks("nice -n 5 timeout inf bash -c 'rm -rf /etc'")


def test_launcher_execution_allows_when_timeout_infinity_wraps_ephemeral_rm() -> None:
    _assert_hook_allows("timeout inf rm -rf /tmp/scratch")


def test_launcher_execution_allows_when_timeout_seconds_wraps_ephemeral_rm() -> None:
    _assert_hook_allows("timeout 5 rm -rf /tmp/scratch")


def test_rm_rf_allowed_when_cd_worktree_then_temp_env_var_rm_then_mkdir_tar_compound() -> None:
    _assert_hook_allows(
        'cd "/Users/dev/proj/.git/worktrees/spindle" '
        '&& rm -rf "$TEMP/pr621_check" '
        '&& mkdir -p "$TEMP/pr621_check" '
        "&& git archive HEAD packages | tar -x -C \"$TEMP/pr621_check\" "
        '&& ls "$TEMP/pr621_check/packages" | head -40'
    )


def test_rm_rf_allowed_when_cd_worktree_then_find_exec_rm_then_pytest_compound() -> None:
    _assert_hook_allows(
        'cd "/Users/dev/proj/worktrees/os-update-system" '
        '&& find shared_utils/samsung_utils -name "__pycache__" -type d '
        "-exec rm -rf {} + 2>/dev/null"
        '; PYTHONPATH="/Users/dev/proj/worktrees/os-update-system" '
        'C:/Python313/python.exe -m pytest "tests/" -p no:cacheprovider -q 2>&1 | tail -15'
    )


def test_rm_rf_allowed_when_cd_ephemeral_and_sibling_mkdir_has_dash_p_flag() -> None:
    _assert_hook_allows('cd "/tmp/scratch" && rm -rf build && mkdir -p out')


def test_rm_rf_allowed_when_cd_ephemeral_and_rm_target_uses_temp_env_var() -> None:
    _assert_hook_allows('cd "/tmp/scratch" && rm -rf "$TEMP/build"')


def test_rm_rf_asks_when_cd_ephemeral_but_bash_dash_c_executes_rm_on_non_ephemeral() -> None:
    _assert_hook_asks("cd \"/tmp/scratch\" && rm -rf build && bash -c 'rm -rf /etc'")


def test_rm_rf_asks_when_cd_ephemeral_but_rm_target_uses_non_temp_env_var() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && rm -rf "$HOME/important"')


def test_rm_rf_asks_when_cd_ephemeral_and_second_rm_segment_targets_non_ephemeral() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && rm -rf build && rm -rf /etc/passwd')


def test_rm_rf_asks_when_cd_ephemeral_but_bin_rm_targets_non_ephemeral() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && /bin/rm -rf /etc')


def test_rm_rf_asks_when_cd_ephemeral_but_target_is_command_substitution() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && rm -rf $(somecmd)')


def test_rm_rf_asks_when_cd_ephemeral_but_target_is_brace_expansion_escaping_namespace() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && rm -rf {build,/etc}')


def test_rm_rf_asks_when_cd_ephemeral_but_temp_var_splices_after_absolute_literal_prefix() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && rm -rf /data$TMP/x')


def test_rm_rf_asks_when_cd_ephemeral_but_find_exec_rm_search_root_escapes_namespace() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && find /etc -name x -exec rm -rf {} +')


def test_rm_rf_asks_when_cd_ephemeral_but_subshell_find_exec_rm_search_root_escapes() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && (find /etc -exec rm -rf {} +)')


def test_rm_rf_asks_when_find_exec_rm_safe_but_sibling_standalone_rm_targets_non_ephemeral() -> None:
    _assert_hook_asks(
        'cd "/tmp/scratch" && find . -name x -exec rm -rf {} + ; rm -rf /etc/passwd'
    )


def test_rm_rf_asks_when_cd_ephemeral_but_find_exec_rm_redirects_to_non_ephemeral_file() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && find /tmp/scratch -exec rm -rf {} + >/etc/passwd')


def test_rm_rf_allowed_when_cd_ephemeral_and_relative_build_target() -> None:
    _assert_hook_allows('cd "/tmp/scratch" && rm -rf build')


def test_rm_rf_allowed_when_cd_ephemeral_and_find_exec_rm_search_root_is_dot() -> None:
    _assert_hook_allows('cd "/tmp/scratch" && find . -name x -exec rm -rf {} +')


def test_rm_rf_asks_when_cd_ephemeral_but_find_exec_bash_dash_c_deletes_non_ephemeral() -> None:
    _assert_hook_asks("cd \"/tmp/scratch\" && find . -exec bash -c 'rm -rf /etc' \\;")


def test_rm_rf_asks_when_cd_ephemeral_but_find_exec_sh_dash_c_deletes_non_ephemeral() -> None:
    _assert_hook_asks("cd \"/tmp/scratch\" && find . -exec sh -c 'rm -rf /etc' \\;")


def test_rm_rf_asks_when_cd_ephemeral_but_find_execdir_bash_dash_c_deletes_non_ephemeral() -> None:
    _assert_hook_asks("cd \"/tmp/scratch\" && find . -execdir bash -c 'rm -rf /etc' \\;")


def test_rm_rf_asks_when_cd_ephemeral_but_find_exec_python_dash_c_deletes_non_ephemeral() -> None:
    _assert_hook_asks(
        "cd \"/tmp/scratch\" && find . -exec python -c 'import os; os.system(\"rm -rf /etc\")' \\;"
    )


# H1: find global option before the search root must not defeat the escape check


def test_rm_rf_asks_when_find_dash_l_global_option_precedes_non_ephemeral_search_root() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && find -L /etc -name x -exec rm -rf {} +')


def test_rm_rf_asks_when_find_dash_p_global_option_precedes_non_ephemeral_execdir_root() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && find -P /etc -execdir rm -rf {} +')


def test_rm_rf_asks_when_find_optimization_level_option_precedes_non_ephemeral_search_root() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && find -O3 /etc -exec rm -rf {} +')


def test_rm_rf_asks_when_standalone_find_optimization_option_precedes_non_ephemeral_search_root() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && find -O /etc -exec rm -rf {} +')


def test_rm_rf_asks_when_find_debug_option_value_precedes_non_ephemeral_search_root() -> None:
    _assert_hook_asks('cd "/tmp/scratch" && find -D tree /etc -exec rm -rf {} +')


def test_rm_rf_allowed_when_find_global_option_precedes_ephemeral_dot_search_root() -> None:
    _assert_hook_allows('cd "/tmp/scratch" && find -L . -name x -exec rm -rf {} +')


# H2: multi -exec with a \\; terminator must not sever the destructive action from detection


def test_rm_rf_asks_when_multi_exec_second_action_runs_bash_dash_c_deleting_non_ephemeral() -> None:
    _assert_hook_asks(
        "cd \"/tmp/scratch\" && find . -exec touch {} \\; -exec bash -c 'rm -rf /etc' \\;"
    )


def test_rm_rf_asks_when_multi_exec_second_action_runs_sh_dash_c_deleting_non_ephemeral() -> None:
    _assert_hook_asks(
        "cd \"/tmp/scratch\" && find . -exec echo {} \\; -exec sh -c 'rm -rf /etc' \\;"
    )


def test_rm_rf_allowed_when_multi_exec_both_actions_target_only_ephemeral_paths() -> None:
    _assert_hook_allows("cd \"/tmp/scratch\" && find . -exec echo {} \\; -exec rm -rf {} \\;")


# H3: parallel forwarding an interpreter that deletes a non-ephemeral path must ask


def test_rm_rf_asks_when_parallel_forwards_bash_dash_c_deleting_non_ephemeral() -> None:
    _assert_hook_asks("cd \"/tmp/scratch\" && parallel bash -c 'rm -rf /etc' ::: x")
