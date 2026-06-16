"""Tests for the gated-invocation parser in verified_commit_gate.

Each test asserts which directories a command string's git commit/push verbs
target, exercising the same token-walk the verified_commit_gate hook runs to
decide what to gate.
"""

import importlib.util
import io
import json
import os
import pathlib
import subprocess
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
deny_reason_for_directory = gate_module.deny_reason_for_directory
gate_main = gate_module.main

store_spec = importlib.util.spec_from_file_location(
    "verification_verdict_store",
    _HOOK_DIR / "verification_verdict_store.py",
)
assert store_spec is not None
assert store_spec.loader is not None
store_module = importlib.util.module_from_spec(store_spec)
store_spec.loader.exec_module(store_module)
resolve_merge_base = store_module.resolve_merge_base
branch_surface_manifest = store_module.branch_surface_manifest
manifest_sha256 = store_module.manifest_sha256

PRODUCTION_SOURCE = "def add(left: int, right: int) -> int:\n    return left + right\n"


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


def _run_git(repo_dir: pathlib.Path, *git_arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_dir), *git_arguments],
        check=True,
        capture_output=True,
        text=True,
    )


def _make_gated_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    origin_dir = tmp_path / "origin.git"
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(origin_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    _run_git(work_dir, "init", "--initial-branch=main")
    _run_git(work_dir, "config", "user.email", "tests@example.com")
    _run_git(work_dir, "config", "user.name", "Gate Tests")
    (work_dir / "app.py").write_text(PRODUCTION_SOURCE, encoding="utf-8")
    _run_git(work_dir, "add", "-A")
    _run_git(work_dir, "commit", "-m", "base")
    _run_git(work_dir, "remote", "add", "origin", str(origin_dir))
    _run_git(work_dir, "push", "-u", "origin", "main")
    (work_dir / "app.py").write_text(
        "def add(left: int, right: int) -> int:\n    return left - right\n",
        encoding="utf-8",
    )
    return work_dir


def _live_surface_hash(work_dir: pathlib.Path) -> str:
    merge_base_sha = resolve_merge_base(str(work_dir))
    assert merge_base_sha is not None
    surface_manifest_text = branch_surface_manifest(str(work_dir), merge_base_sha)
    assert surface_manifest_text is not None
    return manifest_sha256(surface_manifest_text)


def _write_workflow_verdict(
    transcript_path: pathlib.Path, bound_manifest_sha256: str
) -> None:
    subagents_dir = transcript_path.with_suffix("") / "subagents"
    workflow_dir = subagents_dir / "workflows" / "wf_x"
    workflow_dir.mkdir(parents=True)
    verdict_record = {
        "all_pass": True,
        "findings": [],
        "manifest_sha256": bound_manifest_sha256,
    }
    assistant_text = (
        "Verification complete.\n\n```verdict\n"
        + json.dumps(verdict_record)
        + "\n```\n"
    )
    assistant_entry = {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": assistant_text}]},
    }
    (workflow_dir / "agent-01.jsonl").write_text(
        json.dumps(assistant_entry) + "\n", encoding="utf-8"
    )
    (workflow_dir / "agent-01.meta.json").write_text(
        json.dumps({"agentType": "code-verifier"}), encoding="utf-8"
    )


def _isolate_home(monkeypatch: pytest.MonkeyPatch, fake_home: pathlib.Path) -> None:
    home_text = str(fake_home)
    monkeypatch.setenv("HOME", home_text)
    monkeypatch.setenv("USERPROFILE", home_text)
    monkeypatch.delenv("HOMEDRIVE", raising=False)
    monkeypatch.delenv("HOMEPATH", raising=False)


def test_workflow_verdict_allows_commit_without_a_minted_verdict_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    work_dir = _make_gated_repo(tmp_path)
    live_surface_hash = _live_surface_hash(work_dir)
    transcript_path = tmp_path / "projects" / "demo" / "sess1.jsonl"
    transcript_path.parent.mkdir(parents=True)
    transcript_path.write_text("", encoding="utf-8")
    _write_workflow_verdict(transcript_path, live_surface_hash)
    assert (
        deny_reason_for_directory(str(work_dir), str(transcript_path)) is None
    )


def test_no_verdict_of_either_kind_denies_the_commit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    work_dir = _make_gated_repo(tmp_path)
    transcript_path = tmp_path / "projects" / "demo" / "sess1.jsonl"
    transcript_path.parent.mkdir(parents=True)
    transcript_path.write_text("", encoding="utf-8")
    deny_reason = deny_reason_for_directory(str(work_dir), str(transcript_path))
    assert deny_reason is not None
    assert "VERIFIED_COMMIT_GATE" in deny_reason


def _run_gate_main(
    monkeypatch: pytest.MonkeyPatch, command_text: str, work_dir: pathlib.Path
) -> None:
    payload_text = json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {"command": command_text},
            "cwd": str(work_dir),
            "transcript_path": "",
        }
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload_text))
    gate_main()


def test_verification_bypass_marker_allows_an_otherwise_gated_commit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: pathlib.Path,
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    work_dir = _make_gated_repo(tmp_path)
    _run_gate_main(monkeypatch, "git commit -m x", work_dir)
    assert "VERIFIED_COMMIT_GATE" in capsys.readouterr().out
    _run_gate_main(monkeypatch, "git commit -m x # verify-skip", work_dir)
    assert capsys.readouterr().out == ""


def test_minted_verdict_from_other_worktree_allows_commit_by_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    work_dir = _make_gated_repo(tmp_path)
    live_surface_hash = _live_surface_hash(work_dir)
    store_module.write_verdict(
        str(tmp_path / "sibling" / "worktree"),
        live_surface_hash,
        True,
        [],
        "agent-x",
    )
    transcript_path = tmp_path / "projects" / "demo" / "sess1.jsonl"
    transcript_path.parent.mkdir(parents=True)
    transcript_path.write_text("", encoding="utf-8")
    assert deny_reason_for_directory(str(work_dir), str(transcript_path)) is None


def test_minted_verdict_from_other_worktree_with_wrong_hash_denies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    work_dir = _make_gated_repo(tmp_path)
    store_module.write_verdict(
        str(tmp_path / "sibling" / "worktree"),
        "d" * 64,
        True,
        [],
        "agent-x",
    )
    transcript_path = tmp_path / "projects" / "demo" / "sess1.jsonl"
    transcript_path.parent.mkdir(parents=True)
    transcript_path.write_text("", encoding="utf-8")
    deny_reason = deny_reason_for_directory(str(work_dir), str(transcript_path))
    assert deny_reason is not None
    assert "VERIFIED_COMMIT_GATE" in deny_reason
