"""Frozen-file path exceptions preserve every other scanner finding."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from repository_checks.path_exemptions import load_path_exemptions
from repository_checks.tracked_secrets import collect_tracked_secret_findings

FROZEN_RELATIVE_PATH = "evidence/manifest.json"
OTHER_RELATIVE_PATH = "evidence/other.json"
HOME_PATH = "C:/Users/fixture-owner/source-document.md"
FROZEN_CONTENT = f'{{"source": "{HOME_PATH}"}}\n'
STALE_DIGEST = hashlib.sha256(b"different bytes").hexdigest()


def _write_config(root: Path, document: dict[str, object]) -> None:
    directory = root / "config"
    directory.mkdir(exist_ok=True)
    (directory / "repository-policy.json").write_text(
        json.dumps(document), encoding="utf-8"
    )


def _write_frozen_file(root: Path, relative_path: str) -> str:
    file_path = root / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(FROZEN_CONTENT, encoding="utf-8")
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def _entry(**changes: object) -> dict[str, object]:
    return {
        "path": FROZEN_RELATIVE_PATH,
        "sha256": STALE_DIGEST,
        "reason": "Frozen evidence file pinned by its consumers",
        **changes,
    }


def test_matching_digest_removes_every_finding(tmp_path: Path) -> None:
    digest = _write_frozen_file(tmp_path, FROZEN_RELATIVE_PATH)
    _write_config(tmp_path, {"version": 1, "path_exemptions": [_entry(sha256=digest)]})
    assert collect_tracked_secret_findings(tmp_path, [FROZEN_RELATIVE_PATH]) == []


def test_stale_digest_keeps_reporting_the_path(tmp_path: Path) -> None:
    _write_frozen_file(tmp_path, FROZEN_RELATIVE_PATH)
    _write_config(tmp_path, {"version": 1, "path_exemptions": [_entry()]})
    findings = collect_tracked_secret_findings(tmp_path, [FROZEN_RELATIVE_PATH])
    assert [finding.relative_path for finding in findings] == [FROZEN_RELATIVE_PATH]
    assert all(finding.message.startswith("[home-path]") for finding in findings)


def test_unlisted_path_keeps_reporting(tmp_path: Path) -> None:
    digest = _write_frozen_file(tmp_path, FROZEN_RELATIVE_PATH)
    _write_frozen_file(tmp_path, OTHER_RELATIVE_PATH)
    _write_config(tmp_path, {"version": 1, "path_exemptions": [_entry(sha256=digest)]})
    findings = collect_tracked_secret_findings(
        tmp_path, [FROZEN_RELATIVE_PATH, OTHER_RELATIVE_PATH]
    )
    assert [finding.relative_path for finding in findings] == [OTHER_RELATIVE_PATH]


def test_exempt_path_stays_out_of_the_email_exemption_identities(
    tmp_path: Path,
) -> None:
    digest = _write_frozen_file(tmp_path, FROZEN_RELATIVE_PATH)
    _write_config(tmp_path, {"version": 1, "path_exemptions": [_entry(sha256=digest)]})
    assert load_path_exemptions(tmp_path) == frozenset({(FROZEN_RELATIVE_PATH, digest)})


@pytest.mark.parametrize(
    "path",
    [
        "/manifest.json",
        "C:/manifest.json",
        "../manifest.json",
        "evidence/../manifest.json",
        "*.json",
        "evidence/?.json",
        "evidence/[a].json",
        "evidence\\manifest.json",
        "evidence//manifest.json",
        "./manifest.json",
        "",
    ],
)
def test_rejects_nonliteral_or_nonrelative_paths(tmp_path: Path, path: str) -> None:
    _write_config(tmp_path, {"version": 1, "path_exemptions": [_entry(path=path)]})
    with pytest.raises(ValueError):
        load_path_exemptions(tmp_path)


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
    _write_config(tmp_path, {"version": 1, "path_exemptions": [entry]})
    with pytest.raises(ValueError):
        load_path_exemptions(tmp_path)


def test_rejects_duplicate_entries(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        {
            "version": 1,
            "path_exemptions": [_entry(), _entry(reason="Another explanation")],
        },
    )
    with pytest.raises(ValueError):
        load_path_exemptions(tmp_path)


@pytest.mark.parametrize(
    "content",
    [
        "{",
        "[]",
        '{"version":true,"path_exemptions":[]}',
        '{"version":1,"path_exemptions":{}}',
        '{"version":1,"path_exemptions":[],"extra":0}',
        '{"version":1,"path_exemptions":[],"path_exemptions":[]}',
    ],
)
def test_malformed_config_stops_scanning(tmp_path: Path, content: str) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "repository-policy.json").write_text(
        content, encoding="utf-8"
    )
    with pytest.raises(ValueError):
        collect_tracked_secret_findings(tmp_path, [])


@pytest.mark.parametrize(
    "document",
    [
        {"version": 1},
        {"version": 1, "email_exemptions": []},
        {"version": 1, "path_exemptions": []},
        {"version": 1, "email_exemptions": [], "path_exemptions": []},
    ],
)
def test_documents_missing_one_list_still_load(
    tmp_path: Path, document: dict[str, object]
) -> None:
    _write_config(tmp_path, document)
    assert load_path_exemptions(tmp_path) == frozenset()


def test_missing_config_has_no_exemptions(tmp_path: Path) -> None:
    assert load_path_exemptions(tmp_path) == frozenset()
