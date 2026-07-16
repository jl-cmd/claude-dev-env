"""Behavior tests for the ephemeral-path skip on the Write/Edit PII surface.

Sub-defect (ii): the Write/Edit surface scanned files under an ephemeral scratch
root that sit outside every git repository. Such a draft only becomes durable
through ``gh --body-file`` or a staged commit, and each of those surfaces keeps
its own PII scan, so scanning the draft at write time is a pure false positive.

The write surface consults the shared ``is_ephemeral_path`` predicate directly.
These tests drive that real predicate on genuine ephemeral shapes: a harness
session scratchpad under the user temp directory, and a ``CLAUDE_JOB_DIR``
scratch tree. A write inside a git repository keeps full scanning, and the
durable-post and staged-commit surfaces stay gated even from ephemeral sources.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

_HOOK_DIR = Path(__file__).parent
_HOOKS_DIR = _HOOK_DIR.parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

import tempfile  # noqa: E402

from pii_payload_scan import evaluate_write_edit_payload  # noqa: E402
from pii_prevention_blocker import evaluate_bash_command  # noqa: E402

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    CLAUDE_JOB_DIR_ENVIRONMENT_VARIABLE_NAME,
    CLAUDE_JOB_DIR_SCRATCH_SUBDIRECTORY,
    EPHEMERAL_EXEMPT_DISABLE_ENVIRONMENT_VARIABLE_NAME,
)
from hooks_constants.harness_scratchpad_constants import (  # noqa: E402
    HARNESS_SCRATCHPAD_LEAF_DIRECTORY_NAME,
    HARNESS_SCRATCHPAD_USER_DIRECTORY_NAME,
    HOOK_PAYLOAD_SESSION_ID_KEY,
)


def _real_pii_email() -> str:
    return "owner.fixture" + "@" + "acme-corp" + ".example" + ".io"


def _bot_trailer_address() -> str:
    return "noreply" + "@" + "anthropic" + ".com"


def _write_deny_reason(
    target_path: Path,
    sensitive_text: str,
    hook_payload: dict[str, object] | None = None,
) -> str | None:
    content = "owner contact " + sensitive_text + "\n"
    return evaluate_write_edit_payload(
        "Write",
        {"file_path": str(target_path), "content": content},
        hook_payload=hook_payload,
    )


def _enable_job_dir_ephemeral_root(
    monkeypatch: pytest.MonkeyPatch, job_directory: Path
) -> Path:
    monkeypatch.delenv(EPHEMERAL_EXEMPT_DISABLE_ENVIRONMENT_VARIABLE_NAME, raising=False)
    monkeypatch.setenv(CLAUDE_JOB_DIR_ENVIRONMENT_VARIABLE_NAME, str(job_directory))
    ephemeral_root = job_directory / CLAUDE_JOB_DIR_SCRATCH_SUBDIRECTORY
    ephemeral_root.mkdir(parents=True, exist_ok=True)
    return ephemeral_root


@pytest.fixture
def harness_scratchpad() -> Iterator[tuple[Path, str]]:
    session_id = "session-" + uuid.uuid4().hex
    mangled_working_directory = "cwd-" + uuid.uuid4().hex
    temp_root = Path(tempfile.gettempdir())
    user_root = temp_root / HARNESS_SCRATCHPAD_USER_DIRECTORY_NAME
    scratchpad_root = (
        user_root
        / mangled_working_directory
        / session_id
        / HARNESS_SCRATCHPAD_LEAF_DIRECTORY_NAME
    )
    scratchpad_root.mkdir(parents=True, exist_ok=True)
    try:
        yield scratchpad_root, session_id
    finally:
        try:
            shutil.rmtree(user_root / mangled_working_directory)
        except OSError:
            pass


def _init_repo_with_github_origin(repository_root: Path, origin_slug: str) -> None:
    repository_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=repository_root, check=True)
    origin_url = "https://github.com/" + origin_slug + ".git"
    subprocess.run(
        ["git", "remote", "add", "origin", origin_url],
        cwd=repository_root,
        check=True,
    )


def _init_repo_with_staged_email(repository_root: Path, staged_email: str) -> None:
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
    tracked_file = repository_root / "notes.md"
    tracked_file.write_text("owner email " + staged_email + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "notes.md"], cwd=repository_root, check=True)


def test_windows_shaped_scratchpad_write_is_skipped(
    harness_scratchpad: tuple[Path, str],
) -> None:
    scratchpad_root, session_id = harness_scratchpad
    scratch_target = scratchpad_root / "blocker-matrix.txt"
    payload = {HOOK_PAYLOAD_SESSION_ID_KEY: session_id}
    assert _write_deny_reason(scratch_target, _bot_trailer_address(), payload) is None


def test_job_dir_ephemeral_write_outside_repo_is_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ephemeral_root = _enable_job_dir_ephemeral_root(monkeypatch, tmp_path)
    scratch_target = ephemeral_root / "drafts" / "draft.md"
    scratch_target.parent.mkdir(parents=True)
    assert _write_deny_reason(scratch_target, _real_pii_email()) is None


def test_write_inside_ordinary_repository_is_still_denied(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repo"
    _init_repo_with_github_origin(repository_root, "SomeOwner/some-repo")
    deny_reason = _write_deny_reason(repository_root / "notes.md", _real_pii_email())
    assert deny_reason is not None
    assert "email" in deny_reason


def test_ephemeral_path_inside_a_repository_is_still_denied(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ephemeral_root = _enable_job_dir_ephemeral_root(monkeypatch, tmp_path)
    repository_root = ephemeral_root / "repo"
    _init_repo_with_github_origin(repository_root, "SomeOwner/some-repo")
    deny_reason = _write_deny_reason(repository_root / "notes.md", _real_pii_email())
    assert deny_reason is not None
    assert "email" in deny_reason


def test_gh_body_file_from_ephemeral_path_is_still_scanned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ephemeral_root = _enable_job_dir_ephemeral_root(monkeypatch, tmp_path)
    body_path = ephemeral_root / "pr_body.md"
    body_path.write_text("contact " + _real_pii_email() + "\n", encoding="utf-8")
    command = 'gh pr comment 12 --body-file "' + str(body_path) + '"'
    deny_reason = evaluate_bash_command(command, working_directory=None)
    assert deny_reason is not None
    assert "email" in deny_reason


def test_staged_commit_from_ephemeral_tree_is_still_scanned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ephemeral_root = _enable_job_dir_ephemeral_root(monkeypatch, tmp_path)
    repository_root = ephemeral_root / "repo"
    _init_repo_with_staged_email(repository_root, _real_pii_email())
    deny_reason = evaluate_bash_command(
        "git commit -m test", working_directory=str(repository_root)
    )
    assert deny_reason is not None
    assert "email" in deny_reason
    assert "staged commit" in deny_reason
