"""Behavior tests for environment-variable documentation checks."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TESTS_DIRECTORY = Path(__file__).resolve().parent
if str(_TESTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIRECTORY))

from repository_checks.config.constants import (
    CHECK_ID_ENV_VAR_DOCUMENTATION,
    FAILED_CHECK_EXIT_CODE,
    FINDINGS_EXIT_CODE,
    SUCCESS_EXIT_CODE,
)
from repository_policy_test_support import (
    commit_tracked_files,
    initialize_repository,
    patch_unreadable_named_file,
    run_policy,
    write_text,
)


def test_should_flag_environment_variable_documentation_drift(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    write_text(
        repository_root / "auth" / "google_auth.py", "def load() -> None:\n    return\n"
    )
    write_text(
        repository_root / "docs" / "configuration.md",
        "## Summary: Environment Variables\n\n"
        "| Variable | Used By | Purpose |\n"
        "|----------|---------|---------|\n"
        "| `GOOGLE_APPLICATION_CREDENTIALS` | `auth/google_auth.py` | Path to JSON |\n",
    )
    commit_tracked_files(repository_root)
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == FINDINGS_EXIT_CODE
    assert CHECK_ID_ENV_VAR_DOCUMENTATION in stdout_text
    assert "docs/configuration.md" in stdout_text
    assert "GOOGLE_APPLICATION_CREDENTIALS -> auth/google_auth.py" in stdout_text


def test_should_ignore_long_code_reference_inside_code_fence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    long_code_reference = ("x" * 300) + ".py"
    write_text(
        repository_root / "docs" / "review.md",
        f"# Review\n\n~~~diff\n+ `{long_code_reference}`\n~~~\n",
    )
    commit_tracked_files(repository_root)
    original_is_file = Path.is_file

    def reject_long_filename(candidate_path: Path) -> bool:
        if len(candidate_path.name) > 255:
            raise OSError(candidate_path)
        return original_is_file(candidate_path)

    monkeypatch.setattr(Path, "is_file", reject_long_filename)
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == SUCCESS_EXIT_CODE
    assert CHECK_ID_ENV_VAR_DOCUMENTATION not in stdout_text


def test_should_fail_closed_when_an_env_var_code_file_cannot_be_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    write_text(
        repository_root / "packages" / "service" / "auth" / "google_auth.py",
        "def load() -> None:\n    return\n",
    )
    write_text(
        repository_root / "docs" / "configuration.md",
        "## Summary: Environment Variables\n\n"
        "| Variable | Used By | Purpose |\n"
        "|----------|---------|---------|\n"
        "| `GOOGLE_APPLICATION_CREDENTIALS` | `auth/google_auth.py` | Path to JSON |\n",
    )
    commit_tracked_files(repository_root)
    patch_unreadable_named_file(monkeypatch, "google_auth.py", "code file unreadable")
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == FAILED_CHECK_EXIT_CODE
    assert CHECK_ID_ENV_VAR_DOCUMENTATION in stdout_text
    assert "error: rule failed:" in stdout_text


def test_should_fail_closed_before_reading_env_var_code_file_outside_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    outside_path = tmp_path / "outside.py"
    write_text(outside_path, "def load() -> None:\n    return\n")
    write_text(
        repository_root / "docs" / "configuration.md",
        "## Summary: Environment Variables\n\n"
        "| Variable | Used By | Purpose |\n"
        "|----------|---------|---------|\n"
        "| `EXTERNAL_TOKEN` | `../outside.py` | External consumer |\n",
    )
    commit_tracked_files(repository_root)
    all_read_paths = record_read_paths(monkeypatch)
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == FAILED_CHECK_EXIT_CODE
    assert CHECK_ID_ENV_VAR_DOCUMENTATION in stdout_text
    assert outside_path not in all_read_paths


def record_read_paths(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    original_read_text = Path.read_text
    all_read_paths: list[Path] = []

    def record_read_path(
        file_path: Path,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        all_read_paths.append(file_path.resolve())
        return original_read_text(file_path, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", record_read_path)
    return all_read_paths
