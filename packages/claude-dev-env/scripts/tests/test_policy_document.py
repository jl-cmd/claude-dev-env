"""The shared policy-document reader and entry validator."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from repository_checks.policy_document import (
    entry_path_and_digest,
    read_policy_entries,
)

RELATIVE_PATH = "evidence/manifest.json"
DIGEST = hashlib.sha256(b"frozen bytes").hexdigest()
CONFIG_RELATIVE_PATH = "config/repository-policy.json"


def _write_config(root: Path, document: object) -> None:
    config_path = root / CONFIG_RELATIVE_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(document), encoding="utf-8")


def _entry(**changes: object) -> dict[str, object]:
    return {
        "path": RELATIVE_PATH,
        "sha256": DIGEST,
        "reason": "Frozen evidence file pinned by its consumers",
        **changes,
    }


def test_reader_returns_the_recorded_entries_without_validating_them(
    tmp_path: Path,
) -> None:
    """The reader validates the document, and the caller validates each entry."""
    _write_config(tmp_path, {"version": 1, "path_exemptions": [{"anything": 1}]})
    assert read_policy_entries(tmp_path, "path_exemptions") == [{"anything": 1}]


def test_reader_returns_no_entries_for_a_field_the_document_omits(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path, {"version": 1, "path_exemptions": [_entry()]})
    assert read_policy_entries(tmp_path, "email_exemptions") == []


def test_reader_rejects_a_configuration_symlinked_outside_the_repository(
    tmp_path: Path,
) -> None:
    outside_path = tmp_path / "outside-policy.json"
    outside_path.write_text(json.dumps({"version": 1}), encoding="utf-8")
    repository_root = tmp_path / "repo"
    (repository_root / "config").mkdir(parents=True)
    (repository_root / CONFIG_RELATIVE_PATH).symlink_to(outside_path)
    with pytest.raises(ValueError) as rejection:
        read_policy_entries(repository_root, "path_exemptions")
    assert (
        str(rejection.value)
        == "Repository policy configuration must remain inside the repository"
    )


def test_entry_validator_returns_the_path_and_digest_without_the_reason() -> None:
    assert entry_path_and_digest(_entry(), "Path exemption") == (
        RELATIVE_PATH,
        DIGEST,
    )


@pytest.mark.parametrize(
    ("entry", "expected_message"),
    [
        ({}, "Path exemptions require path, sha256, and reason"),
        (_entry(path=1), "Path exemption path must name one repository file"),
        (
            _entry(path="../manifest.json"),
            "Path exemption path must be a literal relative file path",
        ),
        (
            _entry(sha256="F" * 64),
            "Path exemption sha256 must contain 64 lowercase hex digits",
        ),
        (
            _entry(reason=" "),
            "Path exemption reason must explain why the exception is owned",
        ),
    ],
)
def test_entry_validator_names_the_subject_in_every_rejection(
    entry: object, expected_message: str
) -> None:
    """One validator serves both families, so each message names its subject."""
    with pytest.raises(ValueError) as rejection:
        entry_path_and_digest(entry, "Path exemption")
    assert str(rejection.value) == expected_message


def test_entry_validator_uses_the_subject_it_is_given() -> None:
    with pytest.raises(ValueError) as rejection:
        entry_path_and_digest({}, "Email exemption")
    assert str(rejection.value) == "Email exemptions require path, sha256, and reason"
