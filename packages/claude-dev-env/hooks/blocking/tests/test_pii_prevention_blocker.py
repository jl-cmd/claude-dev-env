"""Repository-resolution behavior of the PII commit gate (issue #65).

The gate scans the repository the command names, not the session working
directory, so::

    git -C <healthy repo> commit  ->  scans <healthy repo> from any cwd
    cd <repo> && git commit        ->  scans <repo>
    git -C <repo> commit (cwd gone) ->  still scans <repo>, never refuses for cwd
    git -C <not-a-repo> commit      ->  refusal names <not-a-repo>
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pii_prevention_blocker import evaluate, evaluate_bash_command

_HOOK_PATH = Path(__file__).resolve().parents[1] / "pii_prevention_blocker.py"
_ALLOW_SLUG = "AllowOwner/allow-repo"
_OTHER_SLUG = "OtherOwner/other-repo"


def _run_hook(payload: dict[str, object]) -> tuple[int, str]:
    completed_process = subprocess.run(
        [sys.executable, str(_HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return completed_process.returncode, completed_process.stdout


def _assembled_fixture_email() -> str:
    return "owner.fixture" + "@" + "acme-corp" + ".example" + ".io"


def _assembled_unlisted_email() -> str:
    return "other.person" + "@" + "different-co" + ".example" + ".io"


def _write_allowlist_identity(identity_path: Path, slug: str, value: str) -> None:
    identity_path.write_text(
        json.dumps({"pii_allowlisted_values": {slug: [value]}}),
        encoding="utf-8",
    )


def _init_repo_with_origin_and_staged_value(
    repository_root: Path, origin_slug: str, staged_value: str
) -> None:
    repository_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=repository_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "dev@example.com"],
        cwd=repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Fixture Dev"], cwd=repository_root, check=True
    )
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/" + origin_slug + ".git"],
        cwd=repository_root,
        check=True,
    )
    (repository_root / "notes.md").write_text(
        "owner email " + staged_value + "\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "notes.md"], cwd=repository_root, check=True)


def _commit_payload(repository_root: Path) -> dict[str, object]:
    return {
        "tool_name": "Bash",
        "tool_input": {"command": f"git -C {repository_root} commit -m x"},
    }


def test_commit_subprocess_allows_allowlisted_value_in_the_allowlisted_repo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    allowed_value = _assembled_fixture_email()
    identity_path = tmp_path / "local-identity.json"
    _write_allowlist_identity(identity_path, _ALLOW_SLUG, allowed_value)
    monkeypatch.setenv("CLAUDE_LOCAL_IDENTITY_PATH", str(identity_path))
    repository_root = tmp_path / "repo"
    _init_repo_with_origin_and_staged_value(repository_root, _ALLOW_SLUG, allowed_value)
    return_code, hook_stdout = _run_hook(_commit_payload(repository_root))
    assert return_code == 0
    assert hook_stdout.strip() == ""


def test_commit_subprocess_blocks_allowlisted_value_in_a_different_repo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    allowed_value = _assembled_fixture_email()
    identity_path = tmp_path / "local-identity.json"
    _write_allowlist_identity(identity_path, _ALLOW_SLUG, allowed_value)
    monkeypatch.setenv("CLAUDE_LOCAL_IDENTITY_PATH", str(identity_path))
    repository_root = tmp_path / "repo"
    _init_repo_with_origin_and_staged_value(repository_root, _OTHER_SLUG, allowed_value)
    _return_code, hook_stdout = _run_hook(_commit_payload(repository_root))
    assert "email" in hook_stdout


def test_commit_blocks_an_unlisted_value_in_the_allowlisted_repo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    identity_path = tmp_path / "local-identity.json"
    _write_allowlist_identity(identity_path, _ALLOW_SLUG, _assembled_fixture_email())
    monkeypatch.setenv("CLAUDE_LOCAL_IDENTITY_PATH", str(identity_path))
    repository_root = tmp_path / "repo"
    _init_repo_with_origin_and_staged_value(
        repository_root, _ALLOW_SLUG, _assembled_unlisted_email()
    )
    deny_reason = evaluate_bash_command(
        f"git -C {repository_root} commit -m x",
        working_directory=str(repository_root),
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_commit_with_missing_local_identity_still_blocks_the_value(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLAUDE_LOCAL_IDENTITY_PATH", str(tmp_path / "absent.json"))
    repository_root = tmp_path / "repo"
    _init_repo_with_origin_and_staged_value(
        repository_root, _ALLOW_SLUG, _assembled_fixture_email()
    )
    deny_reason = evaluate_bash_command(
        f"git -C {repository_root} commit -m x",
        working_directory=str(repository_root),
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_commit_allows_the_public_anthropic_bot_address_by_safe_domain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLAUDE_LOCAL_IDENTITY_PATH", str(tmp_path / "absent.json"))
    repository_root = tmp_path / "repo"
    _init_repo_with_origin_and_staged_value(
        repository_root,
        _OTHER_SLUG,
        "Co-Authored-By: Claude <noreply@anthropic.com>",
    )
    deny_reason = evaluate_bash_command(
        f"git -C {repository_root} commit -m x",
        working_directory=str(repository_root),
    )
    assert deny_reason is None


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
