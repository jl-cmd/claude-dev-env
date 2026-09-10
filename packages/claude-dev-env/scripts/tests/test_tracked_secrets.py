"""Behavior tests for tracked-secret checks."""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from repository_checks.config.constants import (
    ALL_TRACKED_SECRET_EXACT_EXEMPTIONS,
    CHECK_ID_TRACKED_PERSONAL_DATA,
    FAILED_CHECK_EXIT_CODE,
    FINDINGS_EXIT_CODE,
    SUCCESS_EXIT_CODE,
)
from repository_checks.hook_modules import load_hooks_module
from repository_checks.tracked_secrets import collect_tracked_secret_findings

_TESTS_DIRECTORY = Path(__file__).resolve().parent
if str(_TESTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIRECTORY))

from repository_policy_test_support import (
    commit_tracked_files,
    initialize_repository,
    run_policy,
    write_text,
)

_SYNTHETIC_GITHUB_TOKEN = "ghp_" + ("A" * 36)
_UTF8_ENCODING = "utf-8"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_EXEMPT_FIXTURE_EMAIL = "fixture-owner@company.io"
_OTHER_FIXTURE_EMAIL = "other-owner@company.io"
_OTHER_FIXTURE_HOME_PATH = "C:/Users/realname/notes.txt"
_FIXTURE_NOTES_RELATIVE_PATH = "src/notes.py"
_OTHER_NOTES_RELATIVE_PATH = "src/other_notes.py"
_FROZEN_RELATIVE_PATH = "evidence/manifest.json"
_STALE_DIGEST = hashlib.sha256(b"different bytes").hexdigest()
_PII_PREVENTION_CONSTANTS = load_hooks_module(
    "hooks_constants.pii_prevention_constants"
)
_PII_CATEGORY_EMAIL = _PII_PREVENTION_CONSTANTS.CATEGORY_EMAIL
_PII_CATEGORY_HOME_PATH = _PII_PREVENTION_CONSTANTS.CATEGORY_HOME_PATH


def test_should_flag_a_tracked_secret(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    write_text(
        repository_root / "src" / "app.py", f"token = '{_SYNTHETIC_GITHUB_TOKEN}'\n"
    )
    commit_tracked_files(repository_root)
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == FINDINGS_EXIT_CODE
    assert CHECK_ID_TRACKED_PERSONAL_DATA in stdout_text
    assert "src/app.py" in stdout_text
    assert _SYNTHETIC_GITHUB_TOKEN not in stdout_text


def test_should_fail_closed_for_malformed_repository_email_policy(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    write_text(repository_root / "config" / "repository-policy.json", "{")
    commit_tracked_files(repository_root)
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == FAILED_CHECK_EXIT_CODE
    assert f"error: rule failed: {CHECK_ID_TRACKED_PERSONAL_DATA}" in stdout_text


def test_should_fail_closed_before_reading_a_tracked_symlink_outside_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    outside_path = tmp_path / "outside.py"
    write_text(outside_path, f"token = '{_SYNTHETIC_GITHUB_TOKEN}'\n")
    tracked_symlink = repository_root / "linked.py"
    tracked_symlink.symlink_to(outside_path)
    original_read_text = Path.read_text
    all_read_paths: list[Path] = []

    def record_read_path(
        file_path: Path,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        all_read_paths.append(file_path)
        return original_read_text(file_path, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", record_read_path)
    with pytest.raises(OSError):
        collect_tracked_secret_findings(repository_root, ["linked.py"])
    assert tracked_symlink not in all_read_paths


def test_should_flag_a_different_email_in_the_same_exact_exempted_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    _write_exact_exemption_fixture(repository_root)
    commit_tracked_files(repository_root)
    _install_exact_email_exemption(monkeypatch)
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == FINDINGS_EXIT_CODE
    assert _pii_categories_for_path(stdout_text, _FIXTURE_NOTES_RELATIVE_PATH) == [
        _PII_CATEGORY_EMAIL,
        _PII_CATEGORY_HOME_PATH,
        _PII_PREVENTION_CONSTANTS.CATEGORY_SECRET,
    ]
    assert _EXEMPT_FIXTURE_EMAIL not in stdout_text
    assert _SYNTHETIC_GITHUB_TOKEN not in stdout_text


def test_should_flag_an_exact_exempt_value_at_a_different_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    _write_exact_exemption_fixture(repository_root)
    commit_tracked_files(repository_root)
    _install_exact_email_exemption(monkeypatch)
    _exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert _PII_CATEGORY_EMAIL in _pii_categories_for_path(
        stdout_text, _OTHER_NOTES_RELATIVE_PATH
    )


def test_should_store_tracked_secret_exemptions_as_digests() -> None:
    sha256_hex_digest_length = hashlib.sha256(b"").digest_size * 2
    assert ALL_TRACKED_SECRET_EXACT_EXEMPTIONS
    for _relative_path, _category, each_digest in ALL_TRACKED_SECRET_EXACT_EXEMPTIONS:
        assert len(each_digest) == sha256_hex_digest_length
        bytes.fromhex(each_digest)


def test_should_keep_owned_checker_modules_free_of_tracked_secret_findings() -> None:
    checker_directory = (
        _REPOSITORY_ROOT
        / "packages"
        / "claude-dev-env"
        / "scripts"
        / "repository_checks"
    )
    all_relative_paths = [
        each_path.relative_to(_REPOSITORY_ROOT).as_posix()
        for each_path in checker_directory.rglob("*.py")
        if each_path.is_file()
    ]
    assert collect_tracked_secret_findings(_REPOSITORY_ROOT, all_relative_paths) == []


def test_should_skip_every_category_in_a_frozen_file_whose_digest_matches(
    tmp_path: Path,
) -> None:
    """One recorded digest silences the whole file, not one matched value."""
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    _write_frozen_path_exemption_fixture(repository_root, _matching_digest)
    commit_tracked_files(repository_root)
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == SUCCESS_EXIT_CODE
    assert _pii_categories_for_path(stdout_text, _FROZEN_RELATIVE_PATH) == []


def test_should_keep_reporting_a_frozen_file_whose_digest_is_stale(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    initialize_repository(repository_root)
    _write_frozen_path_exemption_fixture(repository_root, _stale_digest)
    commit_tracked_files(repository_root)
    exit_code, stdout_text, _stderr_text = run_policy(repository_root)
    assert exit_code == FINDINGS_EXIT_CODE
    assert _pii_categories_for_path(stdout_text, _FROZEN_RELATIVE_PATH) == [
        _PII_CATEGORY_HOME_PATH,
        _PII_PREVENTION_CONSTANTS.CATEGORY_SECRET,
    ]


def test_should_exempt_a_frozen_file_named_by_a_windows_tracked_path(
    tmp_path: Path,
) -> None:
    """Git on Windows can hand back backslashes, and the entry records slashes."""
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _write_frozen_path_exemption_fixture(repository_root, _matching_digest)
    windows_tracked_path = _FROZEN_RELATIVE_PATH.replace("/", "\\")
    assert (
        collect_tracked_secret_findings(repository_root, [windows_tracked_path]) == []
    )


def _write_frozen_path_exemption_fixture(
    repository_root: Path, choose_digest: Callable[[Path], str]
) -> None:
    frozen_path = repository_root / _FROZEN_RELATIVE_PATH
    write_text(
        frozen_path,
        f"home = '{_OTHER_FIXTURE_HOME_PATH}'\ntoken = '{_SYNTHETIC_GITHUB_TOKEN}'\n",
    )
    write_text(
        repository_root / "config" / "repository-policy.json",
        json.dumps(
            {
                "version": 1,
                "path_exemptions": [
                    {
                        "path": _FROZEN_RELATIVE_PATH,
                        "sha256": choose_digest(frozen_path),
                        "reason": "Frozen evidence file pinned by its consumers",
                    }
                ],
            }
        ),
    )


def _matching_digest(frozen_path: Path) -> str:
    return hashlib.sha256(frozen_path.read_bytes()).hexdigest()


def _stale_digest(_frozen_path: Path) -> str:
    return _STALE_DIGEST


def _write_exact_exemption_fixture(repository_root: Path) -> None:
    write_text(
        repository_root / _FIXTURE_NOTES_RELATIVE_PATH,
        f"contact = '{_EXEMPT_FIXTURE_EMAIL}'\nalt = '{_OTHER_FIXTURE_EMAIL}'\nhome = '{_OTHER_FIXTURE_HOME_PATH}'\ntoken = '{_SYNTHETIC_GITHUB_TOKEN}'\n",
    )
    write_text(
        repository_root / _OTHER_NOTES_RELATIVE_PATH,
        f"contact = '{_EXEMPT_FIXTURE_EMAIL}'\n",
    )


def _pii_categories_for_path(stdout_text: str, relative_path: str) -> list[str]:
    finding_prefix = f"{CHECK_ID_TRACKED_PERSONAL_DATA}: {relative_path}:"
    return sorted(
        each_line.split("[", 1)[1].split("]", 1)[0]
        for each_line in stdout_text.splitlines()
        if each_line.startswith(finding_prefix)
    )


def _install_exact_email_exemption(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "repository_checks.tracked_secrets.repository_constants.ALL_TRACKED_SECRET_EXACT_EXEMPTIONS",
        frozenset(
            {
                (
                    _FIXTURE_NOTES_RELATIVE_PATH,
                    _PII_CATEGORY_EMAIL,
                    hashlib.sha256(
                        _EXEMPT_FIXTURE_EMAIL.encode(_UTF8_ENCODING)
                    ).hexdigest(),
                )
            }
        ),
    )
