"""Exact public-contact exceptions preserve all other scanner findings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from repository_checks.email_exemptions import load_email_exemptions
from repository_checks.tracked_secrets import collect_tracked_secret_findings

CONTACT = "fixture-contact@company.io"
CHANGED_CONTACT = "changed-contact@company.io"
DIGEST = hashlib.sha256(CONTACT.encode()).hexdigest()


def _write_config(root: Path, entries: list[object]) -> None:
    directory = root / "config"
    directory.mkdir(exist_ok=True)
    (directory / "repository-policy.json").write_text(
        json.dumps({"version": 1, "email_exemptions": entries}), encoding="utf-8"
    )


def _entry(**changes: object) -> dict[str, object]:
    return {
        "path": "contacts.py",
        "sha256": DIGEST,
        "reason": "Published support contact",
        **changes,
    }


def test_only_matching_email_and_path_are_exempt(tmp_path: Path) -> None:
    _write_config(tmp_path, [_entry()])
    (tmp_path / "contacts.py").write_text(
        f"contact = '{CONTACT}'\nchanged = '{CHANGED_CONTACT}'\n", encoding="utf-8"
    )
    (tmp_path / "other.py").write_text(f"contact = '{CONTACT}'\n", encoding="utf-8")
    findings = collect_tracked_secret_findings(tmp_path, ["contacts.py", "other.py"])
    assert [finding.relative_path for finding in findings] == [
        "contacts.py",
        "other.py",
    ]
    assert all(finding.message.startswith("[email]") for finding in findings)


def test_matching_contact_has_no_findings(tmp_path: Path) -> None:
    _write_config(tmp_path, [_entry()])
    (tmp_path / "contacts.py").write_text(f"contact = '{CONTACT}'\n", encoding="utf-8")
    assert collect_tracked_secret_findings(tmp_path, ["contacts.py"]) == []


@pytest.mark.parametrize(
    "path",
    [
        "/contacts.py",
        "C:/contacts.py",
        "../contacts.py",
        "src/../contacts.py",
        "*.py",
        "src/?.py",
        "src/[a].py",
        "src\\contacts.py",
        "src//contacts.py",
        "./contacts.py",
        "",
    ],
)
def test_rejects_nonliteral_or_nonrelative_paths(tmp_path: Path, path: str) -> None:
    _write_config(tmp_path, [_entry(path=path)])
    with pytest.raises(ValueError):
        load_email_exemptions(tmp_path)


@pytest.mark.parametrize(
    "entry",
    [
        None,
        {},
        _entry(reason=" "),
        _entry(sha256="f" * 63),
        _entry(sha256="z" * 64),
        _entry(category="secret"),
    ],
)
def test_rejects_invalid_entries(tmp_path: Path, entry: object) -> None:
    _write_config(tmp_path, [entry])
    with pytest.raises(ValueError):
        load_email_exemptions(tmp_path)


def test_rejects_duplicate_entries(tmp_path: Path) -> None:
    _write_config(tmp_path, [_entry(), _entry(reason="Another explanation")])
    with pytest.raises(ValueError):
        load_email_exemptions(tmp_path)


@pytest.mark.parametrize(
    "content",
    [
        "{",
        "[]",
        '{"version":true,"email_exemptions":[]}',
        '{"version":1,"email_exemptions":{}}',
        '{"version":1,"email_exemptions":[],"extra":0}',
        '{"version":1,"version":1,"email_exemptions":[]}',
    ],
)
def test_malformed_config_stops_scanning(tmp_path: Path, content: str) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "repository-policy.json").write_text(
        content, encoding="utf-8"
    )
    with pytest.raises(ValueError):
        collect_tracked_secret_findings(tmp_path, [])


def test_missing_config_has_no_exemptions(tmp_path: Path) -> None:
    assert load_email_exemptions(tmp_path) == frozenset()


@pytest.mark.parametrize(
    "document",
    [
        {"version": 1},
        {
            "version": 1,
            "path_exemptions": [
                {
                    "path": "evidence/manifest.json",
                    "sha256": DIGEST,
                    "reason": "Frozen evidence file pinned by its consumers",
                }
            ],
        },
    ],
)
def test_document_without_the_email_list_loads_no_email_exemptions(
    tmp_path: Path, document: dict[str, object]
) -> None:
    """A document may carry the other family, or no exception list at all."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "repository-policy.json").write_text(
        json.dumps(document), encoding="utf-8"
    )
    assert load_email_exemptions(tmp_path) == frozenset()


def test_reason_rejection_names_the_ownership_requirement(tmp_path: Path) -> None:
    _write_config(tmp_path, [_entry(reason=" ")])
    with pytest.raises(ValueError) as rejection:
        load_email_exemptions(tmp_path)
    assert (
        str(rejection.value)
        == "Email exemption reason must explain why the exception is owned"
    )
