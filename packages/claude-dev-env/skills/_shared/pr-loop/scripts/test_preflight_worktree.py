"""Tests for preflight_worktree against real git working trees."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _load_preflight() -> ModuleType:
    module_path = _SCRIPTS_DIR / "preflight_worktree.py"
    spec = importlib.util.spec_from_file_location("preflight_worktree", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["preflight_worktree"] = module
    spec.loader.exec_module(module)
    return module


preflight = _load_preflight()

GIT_TIMEOUT = 30
CLAUDE_REMOTE = "https://github.com/jl-cmd/claude-code-config.git"
GIT_CEILING_DIRECTORIES = "GIT_CEILING_DIRECTORIES"


@pytest.fixture(autouse=True)
def _isolate_git_from_ancestor_repos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(GIT_CEILING_DIRECTORIES, str(tmp_path))


def _git(repo_dir: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_dir), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT,
    )


def _init_repo(repo_dir: Path, origin_url: str | None) -> Path:
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q", str(repo_dir)],
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT,
    )
    if origin_url is not None:
        _git(repo_dir, "remote", "add", "origin", origin_url)
    return repo_dir


@pytest.mark.parametrize(
    ("remote_url", "expected_owner", "expected_repo"),
    [
        (
            "https://github.com/jl-cmd/claude-code-config.git",
            "jl-cmd",
            "claude-code-config",
        ),
        (
            "https://github.com/jl-cmd/claude-code-config",
            "jl-cmd",
            "claude-code-config",
        ),
        ("git@github.com:JonEcho/llm-settings.git", "jonecho", "llm-settings"),
        (
            "ssh://git@github.com/jl-cmd/Claude-Code-Config",
            "jl-cmd",
            "claude-code-config",
        ),
        ("https://github.com/jl-cmd/repo/", "jl-cmd", "repo"),
    ],
)
def test_parse_repo_identity_accepts_every_github_remote_form(
    remote_url: str, expected_owner: str, expected_repo: str
) -> None:
    identity = preflight.parse_repo_identity(remote_url)
    assert identity is not None
    assert identity.owner == expected_owner
    assert identity.repo == expected_repo


@pytest.mark.parametrize(
    "remote_url",
    ["https://gitlab.com/foo/bar.git", "", "not-a-url"],
)
def test_parse_repo_identity_rejects_non_github_remotes(remote_url: str) -> None:
    assert preflight.parse_repo_identity(remote_url) is None


def test_classify_same_repo_when_origin_matches_pr(tmp_path: Path) -> None:
    repo_dir = _init_repo(tmp_path / "session", CLAUDE_REMOTE)
    pr_identity = preflight.RepoIdentity("jl-cmd", "claude-code-config")
    verdict = preflight.classify_environment(repo_dir, pr_identity)
    assert verdict.outcome == preflight.OUTCOME_SAME_REPO
    assert verdict.cwd_identity == pr_identity
    assert verdict.has_healthy_worktree_machinery is True


def test_classify_different_repo_when_origin_is_another_github_repo(
    tmp_path: Path,
) -> None:
    repo_dir = _init_repo(
        tmp_path / "session", "https://github.com/jonecho/llm-settings.git"
    )
    pr_identity = preflight.RepoIdentity("jl-cmd", "claude-code-config")
    verdict = preflight.classify_environment(repo_dir, pr_identity)
    assert verdict.outcome == preflight.OUTCOME_DIFFERENT_REPO
    assert verdict.cwd_identity == preflight.RepoIdentity("jonecho", "llm-settings")


def test_classify_different_repo_when_origin_is_non_github(tmp_path: Path) -> None:
    repo_dir = _init_repo(tmp_path / "session", "https://gitlab.com/foo/bar.git")
    pr_identity = preflight.RepoIdentity("jl-cmd", "claude-code-config")
    verdict = preflight.classify_environment(repo_dir, pr_identity)
    assert verdict.outcome == preflight.OUTCOME_DIFFERENT_REPO
    assert verdict.cwd_identity is None


def test_classify_re_rooted_when_origin_is_absent(tmp_path: Path) -> None:
    repo_dir = _init_repo(tmp_path / "session", None)
    pr_identity = preflight.RepoIdentity("jl-cmd", "claude-code-config")
    verdict = preflight.classify_environment(repo_dir, pr_identity)
    assert verdict.outcome == preflight.OUTCOME_RE_ROOTED


def test_classify_re_rooted_when_directory_is_not_a_work_tree(
    tmp_path: Path,
) -> None:
    plain_dir = tmp_path / "home"
    plain_dir.mkdir()
    pr_identity = preflight.RepoIdentity("jl-cmd", "claude-code-config")
    verdict = preflight.classify_environment(plain_dir, pr_identity)
    assert verdict.outcome == preflight.OUTCOME_RE_ROOTED
    assert verdict.has_healthy_worktree_machinery is False


@pytest.mark.parametrize(
    ("outcome", "is_healthy", "mode", "expected_exit"),
    [
        ("same_repo", True, "strict", 0),
        ("same_repo", True, "classify", 0),
        ("same_repo", False, "strict", 1),
        ("same_repo", False, "classify", 1),
        ("different_repo", True, "strict", 1),
        ("different_repo", True, "classify", 0),
        ("re_rooted", False, "strict", 1),
        ("re_rooted", False, "classify", 1),
    ],
)
def test_decide_exit_code_matrix(
    outcome: str, is_healthy: bool, mode: str, expected_exit: int
) -> None:
    verdict = preflight.PreflightVerdict(
        outcome=outcome,
        cwd_identity=None,
        has_healthy_worktree_machinery=is_healthy,
    )
    assert preflight.decide_exit_code(verdict, mode) == expected_exit


def test_build_report_lines_marks_outcome_and_routes_cross_repo() -> None:
    verdict = preflight.PreflightVerdict(
        outcome=preflight.OUTCOME_DIFFERENT_REPO,
        cwd_identity=preflight.RepoIdentity("jonecho", "llm-settings"),
        has_healthy_worktree_machinery=True,
    )
    pr_identity = preflight.RepoIdentity("jl-cmd", "claude-code-config")
    classify_lines = preflight.build_report_lines(
        verdict, "classify", Path("/tmp/x"), pr_identity
    )
    assert classify_lines[0] == "PREFLIGHT_OUTCOME=different_repo"
    assert any("ROUTE" in line for line in classify_lines)
    strict_lines = preflight.build_report_lines(
        verdict, "strict", Path("/tmp/x"), pr_identity
    )
    assert any("ABORT" in line for line in strict_lines)


def test_build_report_lines_aborts_on_broken_worktree_machinery() -> None:
    verdict = preflight.PreflightVerdict(
        outcome=preflight.OUTCOME_SAME_REPO,
        cwd_identity=preflight.RepoIdentity("jl-cmd", "claude-code-config"),
        has_healthy_worktree_machinery=False,
    )
    pr_identity = preflight.RepoIdentity("jl-cmd", "claude-code-config")
    lines = preflight.build_report_lines(verdict, "strict", Path("/tmp/x"), pr_identity)
    assert lines[0] == "PREFLIGHT_OUTCOME=same_repo"
    assert any("git worktree prune" in line for line in lines)


def test_main_strict_passes_in_matching_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_dir = _init_repo(tmp_path / "session", CLAUDE_REMOTE)
    monkeypatch.chdir(repo_dir)
    exit_code = preflight.main(
        ["--owner", "jl-cmd", "--repo", "claude-code-config", "--mode", "strict"]
    )
    captured = capsys.readouterr()
    assert exit_code == preflight.EXIT_PREFLIGHT_OK
    assert "PREFLIGHT_OUTCOME=same_repo" in captured.out


def test_main_strict_aborts_when_session_rooted_in_other_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_dir = _init_repo(
        tmp_path / "session", "https://github.com/jonecho/llm-settings.git"
    )
    monkeypatch.chdir(repo_dir)
    exit_code = preflight.main(
        ["--owner", "jl-cmd", "--repo", "claude-code-config", "--mode", "strict"]
    )
    captured = capsys.readouterr()
    assert exit_code == preflight.EXIT_PREFLIGHT_ABORT
    assert "PREFLIGHT_OUTCOME=different_repo" in captured.out
    assert "ABORT" in captured.out


def test_main_classify_routes_cross_repo_without_abort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_dir = _init_repo(
        tmp_path / "session", "https://github.com/jonecho/llm-settings.git"
    )
    monkeypatch.chdir(repo_dir)
    exit_code = preflight.main(
        ["--owner", "jl-cmd", "--repo", "claude-code-config", "--mode", "classify"]
    )
    captured = capsys.readouterr()
    assert exit_code == preflight.EXIT_PREFLIGHT_OK
    assert "PREFLIGHT_OUTCOME=different_repo" in captured.out
    assert "ROUTE" in captured.out


def test_main_classify_aborts_when_re_rooted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    plain_dir = tmp_path / "home"
    plain_dir.mkdir()
    monkeypatch.chdir(plain_dir)
    exit_code = preflight.main(
        ["--owner", "jl-cmd", "--repo", "claude-code-config", "--mode", "classify"]
    )
    captured = capsys.readouterr()
    assert exit_code == preflight.EXIT_PREFLIGHT_ABORT
    assert "PREFLIGHT_OUTCOME=re_rooted" in captured.out
