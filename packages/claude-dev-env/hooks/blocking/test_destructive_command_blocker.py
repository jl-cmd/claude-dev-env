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


def test_rm_rf_asks_when_double_dash_includes_hyphen_prefixed_non_ephemeral_target() -> None:
    payload = _make_bash_payload("rm -rf -- /tmp/scratch -non_ephemeral")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_rm_rf_asks_when_command_is_compound_with_ampersand() -> None:
    payload = _make_bash_payload("rm -rf /tmp/reply && gh pr checks 19")

    result = _run_rm_hook(payload)

    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask"


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
