"""Unit tests for convergence-gate-blocker PreToolUse hook."""

import importlib.util
import io
import json
import pathlib
import subprocess
import sys

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

import re

_GH_PR_READY_PATTERN = re.compile(r"\bgh\s+pr\s+ready\b(?![^&|;\n]*--undo)")

hook_spec = importlib.util.spec_from_file_location(
    "convergence_gate_blocker",
    _HOOK_DIR / "convergence_gate_blocker.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
_resolve_pr_number = hook_module._resolve_pr_number


def test_matches_gh_pr_ready_with_number() -> None:
    assert _GH_PR_READY_PATTERN.search("gh pr ready 418")


def test_matches_gh_pr_ready_without_number() -> None:
    assert _GH_PR_READY_PATTERN.search("gh pr ready")


def test_matches_gh_pr_ready_with_flags() -> None:
    assert not _GH_PR_READY_PATTERN.search("gh pr ready --undo")


def test_does_not_match_gh_pr_create() -> None:
    assert not _GH_PR_READY_PATTERN.search("gh pr create --title T")


def test_does_not_match_gh_pr_view() -> None:
    assert not _GH_PR_READY_PATTERN.search("gh pr view 418")


def test_does_not_match_gh_issue_close() -> None:
    assert not _GH_PR_READY_PATTERN.search("gh issue close 42")


def test_extracts_pr_number_from_command() -> None:
    assert _resolve_pr_number("gh pr ready 418", None, None, None) == 418


def test_extracts_pr_number_when_repo_flag_precedes_number() -> None:
    assert (
        _resolve_pr_number(
            "gh pr ready --repo sample-owner/target-repo 161",
            None,
            "sample-owner",
            "target-repo",
        )
        == 161
    )


def test_extracts_pr_number_with_flags() -> None:
    assert _resolve_pr_number("gh pr ready 99 --undo", None, None, None) == 99


def test_returns_none_when_no_number_and_no_repo() -> None:
    assert _resolve_pr_number("gh pr ready", "/nonexistent/path", None, None) is None


def test_number_resolution_binds_gh_view_to_named_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_commands: list[list[str]] = []

    def fake_run(all_arguments: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        captured_commands.append(all_arguments)
        return subprocess.CompletedProcess(args=all_arguments, returncode=0, stdout="500\n", stderr="")

    monkeypatch.setattr(hook_module.subprocess, "run", fake_run)
    assert _resolve_pr_number("gh pr ready", None, "flag-owner", "flag-repo") == 500
    assert captured_commands
    for each_command in captured_commands:
        assert "--repo" in each_command
        assert "flag-owner/flag-repo" in each_command


def test_matches_gh_pr_ready_in_compound_command() -> None:
    assert not _GH_PR_READY_PATTERN.search("gh pr ready --undo && gh pr create")


def test_run_convergence_check_forwards_cwd_to_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_cwd: list[object] = []

    def fake_run(*_run_args: object, **run_keywords: object) -> subprocess.CompletedProcess[str]:
        captured_cwd.append(run_keywords.get("cwd"))
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(hook_module.subprocess, "run", fake_run)
    hook_module._run_convergence_check(
        "check_convergence.py", "owner", "repo", 783, "C:/worktrees/pr-783"
    )
    assert captured_cwd == ["C:/worktrees/pr-783"]


def test_run_convergence_check_forwards_none_cwd_as_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_cwd: list[object] = []

    def fake_run(*_run_args: object, **run_keywords: object) -> subprocess.CompletedProcess[str]:
        captured_cwd.append(run_keywords.get("cwd"))
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(hook_module.subprocess, "run", fake_run)
    hook_module._run_convergence_check("check_convergence.py", "owner", "repo", 783, None)
    assert captured_cwd == [None]


def test_main_reads_cwd_from_top_level_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    convergence_script = (
        tmp_path / ".claude" / "skills" / "pr-converge" / "scripts" / "check_convergence.py"
    )
    convergence_script.parent.mkdir(parents=True)
    convergence_script.write_text("")
    monkeypatch.setattr(hook_module.Path, "home", classmethod(lambda _cls: tmp_path))

    worktree_path = str(tmp_path / "worktrees" / "pr-783")
    monkeypatch.setattr(hook_module, "_resolve_owner_repo", lambda _cwd: ("jl-cmd", "repo"))

    captured_cwd: list[object] = []

    def fake_check(
        _script: str, _owner: str, _repo: str, _pr_number: int, cwd: str | None
    ) -> subprocess.CompletedProcess[str]:
        captured_cwd.append(cwd)
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(hook_module, "_run_convergence_check", fake_check)

    payload = {
        "tool_name": "Bash",
        "cwd": worktree_path,
        "tool_input": {"command": "gh pr ready 783", "cwd": "C:/wrong/session/dir"},
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    with pytest.raises(SystemExit):
        hook_module.main()

    assert captured_cwd == [worktree_path]


def _capture_convergence_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    command: str,
    cwd_owner_repo: tuple[str, str],
) -> tuple[str, str, int]:
    convergence_script = (
        tmp_path / ".claude" / "skills" / "pr-converge" / "scripts" / "check_convergence.py"
    )
    convergence_script.parent.mkdir(parents=True)
    convergence_script.write_text("")
    monkeypatch.setattr(hook_module.Path, "home", classmethod(lambda _cls: tmp_path))
    monkeypatch.setattr(hook_module, "_resolve_owner_repo", lambda _cwd: cwd_owner_repo)

    captured_identity: list[tuple[str, str, int]] = []

    def fake_check(
        _script: str, owner: str, repo: str, pr_number: int, _cwd: str | None
    ) -> subprocess.CompletedProcess[str]:
        captured_identity.append((owner, repo, pr_number))
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(hook_module, "_run_convergence_check", fake_check)

    payload = {
        "tool_name": "Bash",
        "cwd": str(tmp_path / "worktree"),
        "tool_input": {"command": command},
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    with pytest.raises(SystemExit):
        hook_module.main()
    return captured_identity[0]


def test_repo_flag_overrides_cwd_repo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    identity = _capture_convergence_identity(
        monkeypatch,
        tmp_path,
        "gh pr ready 161 --repo sample-owner/target-repo",
        ("cwd-owner", "cwd-repo"),
    )
    assert identity == ("sample-owner", "target-repo", 161)


def test_pr_url_yields_repo_and_number(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    identity = _capture_convergence_identity(
        monkeypatch,
        tmp_path,
        "gh pr ready https://github.com/sample-owner/target-repo/pull/161",
        ("cwd-owner", "cwd-repo"),
    )
    assert identity == ("sample-owner", "target-repo", 161)


def test_bare_pr_ready_resolves_repo_from_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    identity = _capture_convergence_identity(
        monkeypatch,
        tmp_path,
        "gh pr ready 418",
        ("cwd-owner", "cwd-repo"),
    )
    assert identity == ("cwd-owner", "cwd-repo", 418)


def test_parse_repo_flag_space_form() -> None:
    assert hook_module._parse_repo_flag("gh pr ready 161 --repo sample-owner/target-repo") == (
        "sample-owner",
        "target-repo",
    )


def test_parse_repo_flag_equals_form() -> None:
    assert hook_module._parse_repo_flag("gh pr ready 161 --repo=sample-owner/target-repo") == (
        "sample-owner",
        "target-repo",
    )


def test_parse_repo_flag_short_alias() -> None:
    assert hook_module._parse_repo_flag("gh pr ready 161 -R sample-owner/target-repo") == (
        "sample-owner",
        "target-repo",
    )


def test_parse_repo_flag_absent_returns_none() -> None:
    assert hook_module._parse_repo_flag("gh pr ready 418") is None


def test_parse_pr_url_yields_owner_repo_number() -> None:
    assert hook_module._parse_pr_url(
        "gh pr ready https://github.com/sample-owner/target-repo/pull/161"
    ) == ("sample-owner", "target-repo", 161)


def test_parse_pr_url_absent_returns_none() -> None:
    assert hook_module._parse_pr_url("gh pr ready 418") is None


def test_ready_segment_clips_at_command_separator() -> None:
    assert (
        hook_module._ready_command_segment(
            "gh pr ready 161 && gh pr comment 999 --repo other-owner/other-repo"
        )
        == "gh pr ready 161 "
    )


def test_ready_segment_keeps_repo_flag_on_a_continued_line() -> None:
    segment = hook_module._ready_command_segment(
        "gh pr ready 161 \\\n  --repo target-owner/target-repo"
    )
    assert "--repo" in segment
    assert "target-owner/target-repo" in segment


def test_continued_repo_flag_binds_the_gate_to_the_named_repo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    identity = _capture_convergence_identity(
        monkeypatch,
        tmp_path,
        "gh pr ready 161 \\\n  --repo target-owner/target-repo",
        ("cwd-owner", "cwd-repo"),
    )
    assert identity == ("target-owner", "target-repo", 161)


def test_chained_repo_flag_does_not_misbind_the_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    identity = _capture_convergence_identity(
        monkeypatch,
        tmp_path,
        "gh pr ready 161 && gh pr comment 999 --repo other-owner/other-repo --body-file note.md",
        ("cwd-owner", "cwd-repo"),
    )
    assert identity == ("cwd-owner", "cwd-repo", 161)


def test_chained_pr_url_does_not_misbind_the_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    identity = _capture_convergence_identity(
        monkeypatch,
        tmp_path,
        "gh pr ready 161 && echo https://github.com/other-owner/other-repo/pull/5",
        ("cwd-owner", "cwd-repo"),
    )
    assert identity == ("cwd-owner", "cwd-repo", 161)


def test_ready_segment_skips_a_leading_undo_invocation() -> None:
    assert (
        hook_module._ready_command_segment("gh pr ready --undo && gh pr ready 161")
        == "gh pr ready 161"
    )
