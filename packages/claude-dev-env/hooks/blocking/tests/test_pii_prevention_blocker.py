"""Repository-resolution behavior of the PII commit gate (issue #65).

The gate scans the repository the command names, not the session working
directory, so::

    git -C <healthy repo> commit  ->  scans <healthy repo> from any cwd
    cd <repo> && git commit        ->  scans <repo>
    git -C <repo> commit (cwd gone) ->  still scans <repo>, never refuses for cwd
    git -C <not-a-repo> commit      ->  refusal names <not-a-repo>
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from pii_prevention_blocker import evaluate, evaluate_bash_command


def _assembled_fixture_email() -> str:
    return "owner.fixture" + "@" + "acme-corp" + ".example" + ".io"


def _init_repo_with_staged_pii(repository_root: Path) -> None:
    repository_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=repository_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "dev@example.com"],
        cwd=repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Fixture Dev"],
        cwd=repository_root,
        check=True,
    )
    (repository_root / "notes.md").write_text(
        "owner email " + _assembled_fixture_email() + "\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "notes.md"], cwd=repository_root, check=True)


def test_dash_c_scans_named_repo_from_unrelated_cwd(tmp_path: Path) -> None:
    repository_root = tmp_path / "healthy_repo"
    _init_repo_with_staged_pii(repository_root)
    deny_reason = evaluate_bash_command(
        f"git -C {repository_root} commit -m x",
        working_directory="/tmp",
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_cd_prefix_scans_named_repo_from_unrelated_cwd(tmp_path: Path) -> None:
    repository_root = tmp_path / "healthy_repo"
    _init_repo_with_staged_pii(repository_root)
    deny_reason = evaluate_bash_command(
        f"cd {repository_root} && git commit -m x",
        working_directory="/tmp",
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_cd_prefix_with_git_exe_scans_named_repo_from_unrelated_cwd(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "healthy_repo"
    _init_repo_with_staged_pii(repository_root)
    deny_reason = evaluate_bash_command(
        f"cd {repository_root} && git.exe commit -m x",
        working_directory="/tmp",
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_removed_working_directory_does_not_block_named_repo(tmp_path: Path) -> None:
    repository_root = tmp_path / "healthy_repo"
    _init_repo_with_staged_pii(repository_root)
    removed_directory = tmp_path / "gone"
    removed_directory.mkdir()
    removed_directory.rmdir()
    deny_reason = evaluate_bash_command(
        f"git -C {repository_root} commit -m x",
        working_directory=str(removed_directory),
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_multiple_dash_c_compose_to_the_named_repo(tmp_path: Path) -> None:
    repository_root = tmp_path / "parent" / "healthy_repo"
    _init_repo_with_staged_pii(repository_root)
    deny_reason = evaluate_bash_command(
        f"git -C {tmp_path / 'parent'} -C healthy_repo commit -m x",
        working_directory="/tmp",
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_full_dispatch_blocks_pii_commit_from_unrelated_cwd(tmp_path: Path) -> None:
    repository_root = tmp_path / "healthy_repo"
    _init_repo_with_staged_pii(repository_root)
    deny_reason = evaluate(
        {
            "tool_name": "Bash",
            "tool_input": {"command": f"git -C {repository_root} commit -m x"},
            "cwd": "/tmp",
        }
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_unresolvable_named_repo_refusal_names_the_path() -> None:
    deny_reason = evaluate_bash_command(
        "git -C /nonexistent/repo/xyz commit -m x",
        working_directory="/tmp",
    )
    assert deny_reason is not None
    assert "repository root" in deny_reason
    assert "/nonexistent/repo/xyz" in deny_reason


def test_clean_named_repo_passes(tmp_path: Path) -> None:
    repository_root = tmp_path / "clean_repo"
    repository_root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository_root, check=True)
    (repository_root / "readme.md").write_text("all clear\n", encoding="utf-8")
    subprocess.run(["git", "add", "readme.md"], cwd=repository_root, check=True)
    deny_reason = evaluate_bash_command(
        f"git -C {repository_root} commit -m x",
        working_directory="/tmp",
    )
    assert deny_reason is None
