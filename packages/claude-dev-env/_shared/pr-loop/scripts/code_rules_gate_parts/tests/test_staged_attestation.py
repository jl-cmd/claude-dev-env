"""Focused tests for staged CODE_RULES attestation failure handling."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from code_rules_gate_parts import staged_attestation


def test_invalid_utf8_attestation_is_not_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attestation_file = tmp_path / "attestation.json"
    attestation_file.write_bytes(b"\xff\xfe")
    attestation = staged_attestation.StagedAttestation("root", "head", "index")
    monkeypatch.setattr(
        staged_attestation,
        "_snapshot_with_attestation_path",
        lambda _root: (attestation, attestation_file),
    )

    assert not staged_attestation.has_current_staged_attestation(tmp_path)


def test_malformed_attestation_schema_is_not_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attestation_file = tmp_path / "attestation.json"
    attestation_file.write_text("[]", encoding="utf-8")
    attestation = staged_attestation.StagedAttestation("root", "head", "index")
    monkeypatch.setattr(
        staged_attestation,
        "_snapshot_with_attestation_path",
        lambda _root: (attestation, attestation_file),
    )

    assert not staged_attestation.has_current_staged_attestation(tmp_path)


def test_git_timeout_returns_no_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def raise_timeout(*_arguments, **_keywords):
        raise subprocess.TimeoutExpired("git", 1)

    monkeypatch.setattr(staged_attestation.subprocess, "run", raise_timeout)

    assert staged_attestation.snapshot_staged_attestation(tmp_path) is None


def test_git_os_failure_returns_no_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def raise_os_error(*_arguments, **_keywords):
        raise OSError("git unavailable")

    monkeypatch.setattr(staged_attestation.subprocess, "run", raise_os_error)

    assert staged_attestation.snapshot_staged_attestation(tmp_path) is None


def test_current_attestation_reads_private_directory_and_head_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_git_directory = tmp_path / "private-git"
    private_git_directory.mkdir()
    expected_attestation = staged_attestation.StagedAttestation(
        str(tmp_path.resolve()).replace("\\", "/").lower(), "head", "index"
    )
    attestation_file = private_git_directory / "code-rules-staged-attestation.json"
    attestation_file.write_text(
        json.dumps(staged_attestation._attestation_payload(expected_attestation)), encoding="utf-8"
    )
    all_commands: list[tuple[str, ...]] = []

    def run_git(all_arguments, **_keywords):
        all_commands.append(tuple(all_arguments[3:]))
        if all_arguments[-3:] == [
            "rev-parse",
            "--show-toplevel",
            "--git-dir",
        ]:
            return subprocess.CompletedProcess(
                all_arguments,
                0,
                f"{tmp_path.resolve()}\n{private_git_directory}\n",
                "",
            )
        if all_arguments[-3:] == ["rev-parse", "--verify", "HEAD"]:
            return subprocess.CompletedProcess(all_arguments, 0, "head\n", "")
        return subprocess.CompletedProcess(all_arguments, 0, "index\n", "")

    monkeypatch.setattr(staged_attestation.subprocess, "run", run_git)

    assert staged_attestation.has_current_staged_attestation(tmp_path)
    assert all_commands == [
        ("rev-parse", "--show-toplevel", "--git-dir"),
        ("rev-parse", "--verify", "HEAD"),
        ("write-tree",),
    ]


def test_atomic_write_failure_removes_temporary_attestation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attestation_file = tmp_path / "attestation.json"
    attestation = staged_attestation.StagedAttestation("root", "head", "index")
    monkeypatch.setattr(staged_attestation, "attestation_path", lambda _root: attestation_file)
    monkeypatch.setattr(
        staged_attestation, "snapshot_staged_attestation", lambda _root: attestation
    )

    def raise_replace(_from_path: Path, _to_path: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(staged_attestation.os, "replace", raise_replace)

    assert not staged_attestation.mint_staged_attestation(tmp_path, attestation)
    assert not list(tmp_path.glob(".code-rules-staged-attestation-*"))


def test_attestation_path_uses_private_git_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_git_directory = tmp_path / "private-git"
    monkeypatch.setattr(
        staged_attestation,
        "_top_level_and_private_git_directory",
        lambda _root: (tmp_path, private_git_directory),
    )

    assert staged_attestation.attestation_path(tmp_path) == (
        private_git_directory / "code-rules-staged-attestation.json"
    )


def test_nested_repository_path_binds_attestation_to_top_level(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    nested_directory = repository_root / "nested" / "deeper"
    nested_directory.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
    )
    (repository_root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "tracked.txt"],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "seed"],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
    )

    snapshot = staged_attestation.snapshot_staged_attestation(nested_directory)

    assert snapshot is not None
    assert snapshot.worktree == str(repository_root.resolve()).replace("\\", "/").lower()
    assert staged_attestation.attestation_path(nested_directory) == (
        repository_root / ".git" / "code-rules-staged-attestation.json"
    )


def test_unborn_head_snapshot_mint_and_staged_gate_succeed(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
    )
    configuration_path = repository_root / "config" / "constants.py"
    configuration_path.parent.mkdir()
    configuration_path.write_text("IS_READY = True\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "config/constants.py"],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
    )

    snapshot = staged_attestation.snapshot_staged_attestation(repository_root)

    assert snapshot is not None
    assert snapshot.head_oid == "UNBORN_HEAD"
    assert staged_attestation.mint_staged_attestation(repository_root, snapshot)
    assert staged_attestation.has_current_staged_attestation(repository_root)
    gate_path = Path(__file__).resolve().parents[2] / "code_rules_gate.py"
    completed_gate = subprocess.run(
        [
            sys.executable,
            str(gate_path),
            "--repo-root",
            str(repository_root),
            "--staged",
        ],
        cwd=str(repository_root),
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed_gate.returncode == 0, completed_gate.stderr
    assert staged_attestation.has_current_staged_attestation(repository_root)


def test_clear_staged_attestation_removes_stored_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attestation_file = tmp_path / "attestation.json"
    attestation_file.write_text("proof", encoding="utf-8")
    monkeypatch.setattr(staged_attestation, "attestation_path", lambda _root: attestation_file)

    assert staged_attestation.clear_staged_attestation(tmp_path)
    assert not attestation_file.exists()
