"""Behavior tests for the Write/Edit payload PII evaluation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_HOOK_DIR = Path(__file__).parent
_HOOKS_DIR = _HOOK_DIR.parent

try:
    from pii_payload_scan import evaluate_post_body_texts, evaluate_write_edit_payload
except ImportError:
    for each_bootstrap_directory in (str(_HOOK_DIR), str(_HOOKS_DIR)):
        if each_bootstrap_directory not in sys.path:
            sys.path.insert(0, each_bootstrap_directory)
    from pii_payload_scan import evaluate_post_body_texts, evaluate_write_edit_payload

_ALLOW_SLUG = "AllowOwner/allow-repo"
_OTHER_SLUG = "OtherOwner/other-repo"


def test_post_body_with_pii_is_blocked_by_default() -> None:
    deny_reason = evaluate_post_body_texts([_assembled_fixture_email()])
    assert deny_reason is not None
    assert "post body" in deny_reason


def test_post_body_allowlisted_values_plumb_through_to_the_scan() -> None:
    allowed_value = _assembled_fixture_email()
    deny_reason = evaluate_post_body_texts(
        [allowed_value], all_allowlisted_values=frozenset({allowed_value})
    )
    assert deny_reason is None


def test_post_body_unlisted_value_still_blocked_beside_allowlist() -> None:
    deny_reason = evaluate_post_body_texts(
        [_assembled_unlisted_email()],
        all_allowlisted_values=frozenset({_assembled_fixture_email()}),
    )
    assert deny_reason is not None
    assert "post body" in deny_reason


def _assembled_fixture_email() -> str:
    return "owner.fixture" + "@" + "acme-corp" + ".example" + ".io"


def _assembled_unlisted_email() -> str:
    return "other.person" + "@" + "different-co" + ".example" + ".io"


def _write_allowlist_identity(identity_path: Path, slug: str, value: str) -> None:
    identity_path.write_text(
        json.dumps({"pii_allowlisted_values": {slug: [value]}}),
        encoding="utf-8",
    )


def _init_repo_with_github_origin(repository_root: Path, origin_slug: str) -> None:
    repository_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=repository_root, check=True)
    origin_url = "https://github.com/" + origin_slug + ".git"
    subprocess.run(
        ["git", "remote", "add", "origin", origin_url],
        cwd=repository_root,
        check=True,
    )


def _write_deny_reason(target_path: Path, value: str) -> str | None:
    content = "owner email " + value + "\n"
    return evaluate_write_edit_payload(
        "Write", {"file_path": str(target_path), "content": content}
    )


def test_write_payload_with_a_fixture_email_is_flagged(tmp_path: Path) -> None:
    deny_reason = _write_deny_reason(tmp_path / "notes.md", _assembled_fixture_email())
    assert deny_reason is not None
    assert "email" in deny_reason


def test_allowlisted_value_under_the_allowlisted_repo_is_allowed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    allowed_value = _assembled_fixture_email()
    identity_path = tmp_path / "local-identity.json"
    _write_allowlist_identity(identity_path, _ALLOW_SLUG, allowed_value)
    monkeypatch.setenv("CLAUDE_LOCAL_IDENTITY_PATH", str(identity_path))
    repository_root = tmp_path / "repo"
    _init_repo_with_github_origin(repository_root, _ALLOW_SLUG)
    assert _write_deny_reason(repository_root / "notes.md", allowed_value) is None


def test_allowlisted_value_in_a_different_repo_is_blocked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    allowed_value = _assembled_fixture_email()
    identity_path = tmp_path / "local-identity.json"
    _write_allowlist_identity(identity_path, _ALLOW_SLUG, allowed_value)
    monkeypatch.setenv("CLAUDE_LOCAL_IDENTITY_PATH", str(identity_path))
    repository_root = tmp_path / "repo"
    _init_repo_with_github_origin(repository_root, _OTHER_SLUG)
    deny_reason = _write_deny_reason(repository_root / "notes.md", allowed_value)
    assert deny_reason is not None
    assert "email" in deny_reason


def test_unlisted_value_in_the_allowlisted_repo_is_blocked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    identity_path = tmp_path / "local-identity.json"
    _write_allowlist_identity(identity_path, _ALLOW_SLUG, _assembled_fixture_email())
    monkeypatch.setenv("CLAUDE_LOCAL_IDENTITY_PATH", str(identity_path))
    repository_root = tmp_path / "repo"
    _init_repo_with_github_origin(repository_root, _ALLOW_SLUG)
    deny_reason = _write_deny_reason(
        repository_root / "notes.md", _assembled_unlisted_email()
    )
    assert deny_reason is not None
    assert "email" in deny_reason


def test_clean_write_payload_skips_repository_resolution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    identity_path = tmp_path / "local-identity.json"
    _write_allowlist_identity(identity_path, _ALLOW_SLUG, _assembled_fixture_email())
    monkeypatch.setenv("CLAUDE_LOCAL_IDENTITY_PATH", str(identity_path))
    repository_root = tmp_path / "repo"
    _init_repo_with_github_origin(repository_root, _ALLOW_SLUG)

    def _fail_if_called(_working_directory: str | None) -> None:
        raise AssertionError(
            "resolve_repository_root should not run for a payload with no PII"
        )

    monkeypatch.setattr(
        sys.modules["pii_payload_scan"], "resolve_repository_root", _fail_if_called
    )
    deny_reason = evaluate_write_edit_payload(
        "Write",
        {
            "file_path": str(repository_root / "notes.md"),
            "content": "nothing sensitive here\n",
        },
    )
    assert deny_reason is None


def test_allowlisted_value_under_missing_nested_parent_is_allowed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    allowed_value = _assembled_fixture_email()
    identity_path = tmp_path / "local-identity.json"
    _write_allowlist_identity(identity_path, _ALLOW_SLUG, allowed_value)
    monkeypatch.setenv("CLAUDE_LOCAL_IDENTITY_PATH", str(identity_path))
    repository_root = tmp_path / "repo"
    _init_repo_with_github_origin(repository_root, _ALLOW_SLUG)
    nested_target = repository_root / "new_dir" / "deeper" / "notes.md"
    assert not nested_target.parent.exists()
    assert _write_deny_reason(nested_target, allowed_value) is None
