"""Behavioral tests for the moved repository-exemption helpers.

Covers the origin-URL slug parser and the per-repository exemption decision::

    https://github.com/Owner/Repo.git   ->  owner/repo
    https://evil.test/Owner/Repo.git    ->  None
    ok:   origin slug in CLAUDE_PII_EXEMPT_REPOS  ->  exempt (True)
    flag: origin slug absent from the exempt set  ->  scanned (False)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pii_prevention_blocker_parts.repository_exemption import (
    _is_repository_exempt_from_pii_scan,
    _owner_repo_slug_from_origin_url,
)


def test_github_https_origin_yields_lowercased_owner_repo_slug() -> None:
    assert _owner_repo_slug_from_origin_url("https://github.com/Owner/Repo.git") == "owner/repo"


def test_github_ssh_origin_yields_lowercased_owner_repo_slug() -> None:
    assert _owner_repo_slug_from_origin_url("git@github.com:Owner/Repo.git") == "owner/repo"


def test_spoofed_host_origin_yields_no_slug() -> None:
    assert _owner_repo_slug_from_origin_url("https://evil.test/Owner/Repo.git") is None


def _init_repo_with_github_origin(repository_root: Path, origin_slug: str) -> None:
    repository_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=repository_root, check=True)
    origin_url = "https://github.com/" + origin_slug + ".git"
    subprocess.run(
        ["git", "remote", "add", "origin", origin_url],
        cwd=repository_root,
        check=True,
    )


def test_repository_with_exempt_origin_is_exempt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLAUDE_PII_EXEMPT_REPOS", "ExemptOwner/exempt-repo")
    repository_root = tmp_path / "repo"
    _init_repo_with_github_origin(repository_root, "ExemptOwner/exempt-repo")
    assert _is_repository_exempt_from_pii_scan(repository_root) is True


def test_repository_with_unlisted_origin_is_scanned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLAUDE_PII_EXEMPT_REPOS", "ExemptOwner/exempt-repo")
    repository_root = tmp_path / "repo"
    _init_repo_with_github_origin(repository_root, "OtherOwner/other-repo")
    assert _is_repository_exempt_from_pii_scan(repository_root) is False


def test_repository_without_origin_is_never_exempt(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository_root, check=True)
    assert _is_repository_exempt_from_pii_scan(repository_root) is False
