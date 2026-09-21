"""An owned match clears while every other scanner finding stays reported."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from repository_checks.config.policy_document import (
    EMAIL_EXEMPTION_FAMILY,
    PRIVATE_IP_EXEMPTION_FAMILY,
    MatchExemptionFamily,
)
from repository_checks.match_exemptions import (
    load_all_match_exemptions,
    load_match_exemptions,
)
from repository_checks.tracked_secrets import collect_tracked_secret_findings

CONTACT = "fixture-contact@company.io"
CHANGED_CONTACT = "changed-contact@company.io"
DIGEST = hashlib.sha256(CONTACT.encode()).hexdigest()
RUNNER_ADDRESS = "10.83.21.14"
CHANGED_RUNNER_ADDRESS = "10.83.21.15"
RUNNER_ADDRESS_DIGEST = hashlib.sha256(RUNNER_ADDRESS.encode()).hexdigest()


def _write_config(root: Path, entries: list[object]) -> None:
    _write_document(root, {"version": 1, "email_exemptions": entries})


def _write_private_ip_config(root: Path, entries: list[object]) -> None:
    _write_document(root, {"version": 1, "private_ip_exemptions": entries})


def _write_document(root: Path, document: dict[str, object]) -> None:
    directory = root / "config"
    directory.mkdir(exist_ok=True)
    (directory / "repository-policy.json").write_text(
        json.dumps(document), encoding="utf-8"
    )


def _entry(**changes: object) -> dict[str, object]:
    return {
        "path": "contacts.py",
        "sha256": DIGEST,
        "reason": "Published support contact",
        **changes,
    }


def _runner_entry(**changes: object) -> dict[str, object]:
    return {
        "path": "runner.py",
        "sha256": RUNNER_ADDRESS_DIGEST,
        "reason": "Documented address of the shared build runner",
        **changes,
    }


def _load_email_exemptions(root: Path) -> frozenset[tuple[str, str, str]]:
    return load_match_exemptions(root, EMAIL_EXEMPTION_FAMILY)


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


def test_matching_private_ip_has_no_findings(tmp_path: Path) -> None:
    _write_private_ip_config(tmp_path, [_runner_entry()])
    (tmp_path / "runner.py").write_text(
        f"host = '{RUNNER_ADDRESS}'\n", encoding="utf-8"
    )
    assert collect_tracked_secret_findings(tmp_path, ["runner.py"]) == []


def test_only_matching_private_ip_and_path_are_exempt(tmp_path: Path) -> None:
    _write_private_ip_config(tmp_path, [_runner_entry()])
    (tmp_path / "runner.py").write_text(
        f"host = '{RUNNER_ADDRESS}'\nspare = '{CHANGED_RUNNER_ADDRESS}'\n",
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(f"host = '{RUNNER_ADDRESS}'\n", encoding="utf-8")
    findings = collect_tracked_secret_findings(tmp_path, ["runner.py", "other.py"])
    assert [finding.relative_path for finding in findings] == ["runner.py", "other.py"]
    assert all(finding.message.startswith("[private-ip]") for finding in findings)


def test_private_ip_exemption_leaves_email_findings(tmp_path: Path) -> None:
    _write_document(
        tmp_path,
        {"version": 1, "private_ip_exemptions": [_runner_entry(path="hosts.py")]},
    )
    (tmp_path / "hosts.py").write_text(
        f"host = '{RUNNER_ADDRESS}'\ncontact = '{CONTACT}'\n", encoding="utf-8"
    )
    findings = collect_tracked_secret_findings(tmp_path, ["hosts.py"])
    assert [finding.message.split("]")[0] + "]" for finding in findings] == ["[email]"]


def test_both_families_apply_together(tmp_path: Path) -> None:
    _write_document(
        tmp_path,
        {
            "version": 1,
            "email_exemptions": [_entry(path="hosts.py")],
            "private_ip_exemptions": [_runner_entry(path="hosts.py")],
        },
    )
    (tmp_path / "hosts.py").write_text(
        f"host = '{RUNNER_ADDRESS}'\ncontact = '{CONTACT}'\n", encoding="utf-8"
    )
    assert collect_tracked_secret_findings(tmp_path, ["hosts.py"]) == []


def test_email_entry_does_not_exempt_a_private_ip(tmp_path: Path) -> None:
    _write_config(tmp_path, [_entry(path="runner.py", sha256=RUNNER_ADDRESS_DIGEST)])
    (tmp_path / "runner.py").write_text(
        f"host = '{RUNNER_ADDRESS}'\n", encoding="utf-8"
    )
    findings = collect_tracked_secret_findings(tmp_path, ["runner.py"])
    assert [finding.message.startswith("[private-ip]") for finding in findings] == [
        True
    ]


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
        _load_email_exemptions(tmp_path)


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
        _load_email_exemptions(tmp_path)


def test_rejects_duplicate_entries(tmp_path: Path) -> None:
    _write_config(tmp_path, [_entry(), _entry(reason="Another explanation")])
    with pytest.raises(ValueError):
        _load_email_exemptions(tmp_path)


def test_rejects_duplicate_private_ip_entries(tmp_path: Path) -> None:
    _write_private_ip_config(
        tmp_path, [_runner_entry(), _runner_entry(reason="Another explanation")]
    )
    with pytest.raises(ValueError):
        load_match_exemptions(tmp_path, PRIVATE_IP_EXEMPTION_FAMILY)


@pytest.mark.parametrize(
    "content",
    [
        "{",
        "[]",
        '{"version":true,"email_exemptions":[]}',
        '{"version":1,"email_exemptions":{}}',
        '{"version":1,"email_exemptions":[],"extra":0}',
        '{"version":1,"version":1,"email_exemptions":[]}',
        '{"version":1,"private_ip_exemptions":{}}',
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
    assert _load_email_exemptions(tmp_path) == frozenset()


@pytest.mark.parametrize(
    "family", [EMAIL_EXEMPTION_FAMILY, PRIVATE_IP_EXEMPTION_FAMILY]
)
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
def test_document_without_a_family_list_loads_no_exemptions(
    tmp_path: Path, document: dict[str, object], family: MatchExemptionFamily
) -> None:
    """A document may carry another family, or no exception list at all."""
    _write_document(tmp_path, document)
    assert load_match_exemptions(tmp_path, family) == frozenset()


def test_reason_rejection_names_the_ownership_requirement(tmp_path: Path) -> None:
    _write_config(tmp_path, [_entry(reason=" ")])
    with pytest.raises(ValueError) as rejection:
        _load_email_exemptions(tmp_path)
    assert (
        str(rejection.value)
        == "Email exemption reason must explain why the exception is owned"
    )


def test_private_ip_reason_rejection_names_its_own_family(tmp_path: Path) -> None:
    _write_private_ip_config(tmp_path, [_runner_entry(reason=" ")])
    with pytest.raises(ValueError) as rejection:
        load_match_exemptions(tmp_path, PRIVATE_IP_EXEMPTION_FAMILY)
    assert (
        str(rejection.value)
        == "Private IP exemption reason must explain why the exception is owned"
    )


def test_loading_every_family_returns_both_owned_matches(tmp_path: Path) -> None:
    _write_document(
        tmp_path,
        {
            "version": 1,
            "email_exemptions": [_entry()],
            "private_ip_exemptions": [_runner_entry()],
        },
    )

    assert load_all_match_exemptions(tmp_path) == frozenset(
        {
            ("contacts.py", "email", DIGEST),
            ("runner.py", "private-ip", RUNNER_ADDRESS_DIGEST),
        }
    )


def test_loading_every_family_returns_nothing_without_a_policy_document(
    tmp_path: Path,
) -> None:
    assert load_all_match_exemptions(tmp_path) == frozenset()
