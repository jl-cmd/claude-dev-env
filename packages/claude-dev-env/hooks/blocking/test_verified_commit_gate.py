"""Tests for the gated-invocation parser in verified_commit_gate.

Each test asserts which directories a command string's git commit/push verbs
target, exercising the same token-walk the verified_commit_gate hook runs to
decide what to gate.
"""

import importlib.util
import os
import pathlib
import sys

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

gate_spec = importlib.util.spec_from_file_location(
    "verified_commit_gate",
    _HOOK_DIR / "verified_commit_gate.py",
)
assert gate_spec is not None
assert gate_spec.loader is not None
gate_module = importlib.util.module_from_spec(gate_spec)
gate_spec.loader.exec_module(gate_module)
gated_repo_directories = gate_module.gated_repo_directories


def test_plain_git_commit_is_gated() -> None:
    assert gated_repo_directories("git commit -m x", "FALLBACK") == ["FALLBACK"]


def test_git_exe_commit_is_gated() -> None:
    assert gated_repo_directories("git.exe commit -m x", "FALLBACK") == ["FALLBACK"]


def test_git_exe_push_is_gated() -> None:
    assert gated_repo_directories("git.exe push origin main", "FALLBACK") == [
        "FALLBACK"
    ]


def test_git_exe_commit_records_repo_directory_option() -> None:
    assert gated_repo_directories('git.exe -C "/repo" commit -m x', "FALLBACK") == [
        "/repo"
    ]


def test_git_log_grep_commit_is_not_gated() -> None:
    assert gated_repo_directories("git log --grep commit", "FALLBACK") == []


def test_git_stash_push_is_not_gated() -> None:
    assert gated_repo_directories("git stash push", "FALLBACK") == []


def test_git_dir_option_value_yields_single_entry() -> None:
    assert gated_repo_directories(
        "git --git-dir=/x/.git commit", "FALLBACK"
    ) == ["FALLBACK"]


def test_substring_git_in_branch_name_is_not_a_git_word() -> None:
    assert gated_repo_directories("git push origin legit-branch", "FALLBACK") == [
        "FALLBACK"
    ]


def test_two_real_git_commits_yield_two_entries() -> None:
    assert gated_repo_directories(
        "git commit -m x && git push origin main", "FALLBACK"
    ) == ["FALLBACK", "FALLBACK"]


def test_unix_path_prefixed_git_commit_is_gated() -> None:
    assert gated_repo_directories("/usr/bin/git commit -m x", "FALLBACK") == [
        "FALLBACK"
    ]


def test_windows_path_prefixed_git_exe_commit_is_gated() -> None:
    assert gated_repo_directories(
        "C:/Program Files/Git/bin/git.exe commit -m x", "FALLBACK"
    ) == ["FALLBACK"]


def test_backslash_path_prefixed_git_exe_commit_is_gated() -> None:
    assert gated_repo_directories(
        "C:\\Program Files\\Git\\cmd\\git.exe commit", "FALLBACK"
    ) == ["FALLBACK"]


def test_quoted_git_word_commit_is_gated() -> None:
    assert gated_repo_directories('"git" commit -m x', "FALLBACK") == ["FALLBACK"]


def test_call_operator_path_git_exe_commit_is_gated() -> None:
    assert gated_repo_directories("& 'C:/x/git.exe' commit", "FALLBACK") == [
        "FALLBACK"
    ]


def test_call_operator_program_files_git_exe_commit_is_gated() -> None:
    assert gated_repo_directories(
        '& "C:\\Program Files\\Git\\cmd\\git.exe" commit -m x', "C:/repo"
    ) == ["C:/repo"]


def test_quoted_program_files_git_exe_commit_is_gated() -> None:
    assert gated_repo_directories(
        '"C:/Program Files/Git/cmd/git.exe" commit', "C:/repo"
    ) == ["C:/repo"]


def test_quoted_program_files_path_without_git_segment_is_not_gated() -> None:
    assert gated_repo_directories(
        '"C:/Program Files/Other/tool.exe" commit', "C:/repo"
    ) == []


def test_path_prefixed_git_log_grep_commit_is_not_gated() -> None:
    assert gated_repo_directories("/usr/bin/git log --grep commit", "FALLBACK") == []


def test_mygit_commit_is_not_a_git_word() -> None:
    assert gated_repo_directories("mygit commit", "FALLBACK") == []


def test_legit_commit_is_not_a_git_word() -> None:
    assert gated_repo_directories("legit commit", "FALLBACK") == []


def test_cd_then_git_commit_gates_the_cd_directory() -> None:
    assert gated_repo_directories(
        "cd /other/repo && git commit -m x", "FALLBACK"
    ) == ["/other/repo"]


def test_pushd_then_git_commit_gates_the_pushd_directory() -> None:
    assert gated_repo_directories(
        "pushd /other/repo; git commit -m x", "FALLBACK"
    ) == ["/other/repo"]


def test_cd_with_quoted_directory_gates_the_quoted_directory() -> None:
    assert gated_repo_directories(
        'cd "/path with spaces" && git commit -m x', "FALLBACK"
    ) == ["/path with spaces"]


def test_explicit_repo_option_overrides_cd_directory() -> None:
    assert gated_repo_directories(
        'cd /other/repo && git -C "/repo" commit -m x', "FALLBACK"
    ) == ["/repo"]


def test_later_cd_applies_to_later_git_commit() -> None:
    assert gated_repo_directories(
        "git commit -m a && cd /second && git commit -m b", "FALLBACK"
    ) == ["FALLBACK", "/second"]


def test_cd_without_argument_keeps_the_fallback_directory() -> None:
    assert gated_repo_directories("cd && git commit -m x", "FALLBACK") == [
        "FALLBACK"
    ]


def test_set_location_then_git_commit_gates_the_set_location_directory() -> None:
    assert gated_repo_directories(
        "Set-Location /other/repo; git commit -m x", "FALLBACK"
    ) == ["/other/repo"]


def test_sl_alias_then_git_commit_gates_the_sl_directory() -> None:
    assert gated_repo_directories(
        "sl /other/repo; git commit -m x", "FALLBACK"
    ) == ["/other/repo"]


def test_set_location_is_matched_case_insensitively() -> None:
    assert gated_repo_directories(
        "set-location /other/repo; git commit -m x", "FALLBACK"
    ) == ["/other/repo"]


def test_relative_cd_target_resolves_against_the_fallback_directory() -> None:
    expected_directory = os.path.join("/session/dir", "subdir")
    assert gated_repo_directories(
        "cd subdir && git commit -m x", "/session/dir"
    ) == [expected_directory]


def test_relative_set_location_target_resolves_against_the_fallback_directory() -> None:
    expected_directory = os.path.join("/session/dir", "subdir")
    assert gated_repo_directories(
        "Set-Location subdir; git commit -m x", "/session/dir"
    ) == [expected_directory]


def test_absolute_cd_target_is_not_joined_to_the_fallback_directory() -> None:
    assert gated_repo_directories(
        "cd /other/repo && git commit -m x", "/session/dir"
    ) == ["/other/repo"]


def test_work_tree_option_gates_the_work_tree_directory() -> None:
    assert gated_repo_directories(
        "git --git-dir=/other/.git --work-tree=/other commit", "/session"
    ) == ["/other"]


def test_work_tree_space_separated_option_gates_the_work_tree_directory() -> None:
    assert gated_repo_directories(
        "git --work-tree /other commit -m x", "/session"
    ) == ["/other"]


def test_repo_option_overrides_work_tree_option() -> None:
    assert gated_repo_directories(
        'git -C "/repo" --work-tree=/other commit', "/session"
    ) == ["/repo"]


def test_relative_repo_option_resolves_against_the_active_directory() -> None:
    expected_directory = os.path.join("/repo", "subdir")
    assert gated_repo_directories(
        "cd /repo && git -C subdir commit -m x", "FALLBACK"
    ) == [expected_directory]


def test_relative_work_tree_option_resolves_against_the_active_directory() -> None:
    expected_directory = os.path.join("/repo", "subtree")
    assert gated_repo_directories(
        "cd /repo && git --work-tree subtree commit -m x", "FALLBACK"
    ) == [expected_directory]


def test_relative_repo_option_resolves_against_the_fallback_directory() -> None:
    expected_directory = os.path.join("/session/dir", "subdir")
    assert gated_repo_directories(
        "git -C subdir commit -m x", "/session/dir"
    ) == [expected_directory]


def _set_fake_home(monkeypatch: pytest.MonkeyPatch, fake_home: pathlib.Path) -> str:
    home_text = str(fake_home)
    monkeypatch.setenv("HOME", home_text)
    monkeypatch.setenv("USERPROFILE", home_text)
    monkeypatch.delenv("HOMEDRIVE", raising=False)
    monkeypatch.delenv("HOMEPATH", raising=False)
    return home_text


def test_cd_into_tilde_repo_gates_the_expanded_home_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    home_text = _set_fake_home(monkeypatch, tmp_path)
    expected_directory = os.path.expanduser("~/myrepo")
    assert home_text in expected_directory
    assert gated_repo_directories(
        "cd ~/myrepo && git commit -m x", "FALLBACK"
    ) == [expected_directory]


def test_git_dash_c_tilde_repo_gates_the_expanded_home_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    home_text = _set_fake_home(monkeypatch, tmp_path)
    expected_directory = os.path.expanduser("~/myrepo")
    assert home_text in expected_directory
    assert gated_repo_directories(
        "git -C ~/myrepo commit -m x", "FALLBACK"
    ) == [expected_directory]


def test_git_work_tree_tilde_repo_gates_the_expanded_home_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    home_text = _set_fake_home(monkeypatch, tmp_path)
    expected_directory = os.path.expanduser("~/myrepo")
    assert home_text in expected_directory
    assert gated_repo_directories(
        "git --work-tree ~/myrepo commit -m x", "FALLBACK"
    ) == [expected_directory]


def test_set_location_path_option_gates_the_path_value() -> None:
    assert gated_repo_directories(
        "Set-Location -Path /repo; git commit -m x", "FALLBACK"
    ) == ["/repo"]


def test_pushd_literal_path_option_gates_the_path_value() -> None:
    assert gated_repo_directories(
        "pushd -LiteralPath /repo; git commit", "FALLBACK"
    ) == ["/repo"]


def test_cd_double_dash_terminator_gates_the_path_value() -> None:
    assert gated_repo_directories(
        "cd -- /repo && git commit", "FALLBACK"
    ) == ["/repo"]


def test_cd_inside_double_quoted_commit_message_does_not_divert_later_push() -> None:
    assert gated_repo_directories(
        'git commit -m "context: cd /var/empty/nonrepo first" && git push',
        "/real/repo/worktree",
    ) == ["/real/repo/worktree", "/real/repo/worktree"]


def test_cd_inside_single_quoted_commit_message_does_not_divert_later_push() -> None:
    assert gated_repo_directories(
        "git commit -m 'context: cd /var/empty/nonrepo first' && git push",
        "/real/repo/worktree",
    ) == ["/real/repo/worktree", "/real/repo/worktree"]


def test_pushd_inside_quoted_commit_message_does_not_divert_later_push() -> None:
    assert gated_repo_directories(
        'git commit -m "context: pushd /var/empty/nonrepo first" && git push',
        "/real/repo/worktree",
    ) == ["/real/repo/worktree", "/real/repo/worktree"]


def test_real_cd_outside_quotes_still_diverts_after_a_quoted_message() -> None:
    assert gated_repo_directories(
        'git commit -m "msg" && cd /other/repo && git push',
        "/real/repo/worktree",
    ) == ["/real/repo/worktree", "/other/repo"]


def test_git_word_inside_quoted_commit_message_yields_one_entry() -> None:
    assert gated_repo_directories(
        'git commit -m "remember to git commit later"', "FB"
    ) == ["FB"]


def test_git_word_inside_single_quoted_message_value_yields_one_entry() -> None:
    assert gated_repo_directories(
        "git commit -m 'remember to git commit later'", "FB"
    ) == ["FB"]


def test_backslash_newline_after_git_word_is_gated() -> None:
    assert gated_repo_directories("git \\\n commit -m x", "FB") == ["FB"]


def test_backslash_newline_abutting_subcommand_is_gated() -> None:
    assert gated_repo_directories("git commit\\\n -m x", "FB") == ["FB"]


def test_backslash_newline_splitting_git_word_is_gated() -> None:
    assert gated_repo_directories("g\\\nit commit -m x", "FB") == ["FB"]


def test_git_verb_inside_echo_prose_is_not_gated() -> None:
    assert gated_repo_directories(
        'echo "Next: git commit and git push"', "/d"
    ) == []


def test_git_verb_inside_gh_comment_body_is_not_gated() -> None:
    assert gated_repo_directories(
        'gh pr comment -b "please git commit your work"', "/d"
    ) == []
