"""Tests for direct and dispatched refactor guidance."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path

import pytest

ADVISORY_DIRECTORY = Path(__file__).resolve().parent
HOOK_SCRIPT_PATH = ADVISORY_DIRECTORY / "refactor_guard.py"
DISPATCHER_SCRIPT_PATH = ADVISORY_DIRECTORY.parent / "blocking" / "pre_tool_use_dispatcher.py"
if str(ADVISORY_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(ADVISORY_DIRECTORY))

import refactor_guard  # noqa: E402


@pytest.fixture
def git_repository(tmp_path: Path) -> Generator[Path]:
    """Create a committed temporary repository for advisory checks."""
    repository_path = tmp_path / "repository"
    repository_path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository_path, check=True)
    yield repository_path


def _commit_file(repository_path: Path, file_path: Path, file_content: str) -> None:
    file_path.write_text(file_content, encoding="utf-8")
    subprocess.run(["git", "add", str(file_path)], cwd=repository_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Refactor Guard Test",
            "-c",
            "user.email=refactor-guard@example.invalid",
            "commit",
            "-q",
            "-m",
            "baseline",
            "--no-verify",
        ],
        cwd=repository_path,
        check=True,
    )


def _stage_file(repository_path: Path, file_path: Path, file_content: str) -> None:
    file_path.write_text(file_content, encoding="utf-8")
    subprocess.run(["git", "add", str(file_path)], cwd=repository_path, check=True)


def _refactor_payload(file_path: Path) -> str:
    return json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(file_path),
                "old_string": "def calculate_total(amount: int) -> int:\n    return amount",
                "new_string": "def compute_total(amount: int) -> int:\n    return amount",
            },
        }
    )


def _ordinary_edit_payload(file_path: Path) -> str:
    return json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(file_path),
                "old_string": "return amount",
                "new_string": "return amount + 1",
            },
        }
    )


def _run_hook(
    script_path: Path, repository_path: Path, payload_text: str
) -> subprocess.CompletedProcess[str]:
    environment_by_key = os.environ.copy()
    environment_by_key["HOME"] = str(repository_path)
    environment_by_key["USERPROFILE"] = str(repository_path)
    return subprocess.run(
        [sys.executable, str(script_path)],
        cwd=repository_path,
        input=payload_text,
        capture_output=True,
        text=True,
        env=environment_by_key,
        check=False,
    )


def test_direct_hook_emits_edit_stage_guidance_for_eligible_refactor(
    git_repository: Path,
) -> None:
    source_path = git_repository / "module.py"
    _commit_file(
        git_repository,
        source_path,
        "def calculate_total(amount: int) -> int:\n    return amount\n",
    )
    _stage_file(
        git_repository,
        source_path,
        "def calculate_total(amount: int) -> int:\n    return amount + 1\n",
    )

    completed_hook = _run_hook(HOOK_SCRIPT_PATH, git_repository, _refactor_payload(source_path))
    advisory_payload = json.loads(completed_hook.stdout)
    hook_specific_output = advisory_payload["hookSpecificOutput"]

    assert hook_specific_output["permissionDecision"] == "allow"
    assert "Edit-stage" in advisory_payload["systemMessage"]
    assert "current git diff" in hook_specific_output["additionalContext"]
    assert str(source_path) in advisory_payload["systemMessage"]


def test_direct_hook_stays_silent_for_ordinary_edit(git_repository: Path) -> None:
    source_path = git_repository / "module.py"
    _commit_file(
        git_repository,
        source_path,
        "def calculate_total(amount: int) -> int:\n    return amount\n",
    )

    completed_hook = _run_hook(
        HOOK_SCRIPT_PATH,
        git_repository,
        _ordinary_edit_payload(source_path),
    )

    assert completed_hook.returncode == 0
    assert completed_hook.stdout == ""


def test_direct_hook_stays_silent_for_write_payload(git_repository: Path) -> None:
    source_path = git_repository / "module.py"
    _commit_file(
        git_repository,
        source_path,
        "def calculate_total(amount: int) -> int:\n    return amount\n",
    )
    write_payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": str(source_path), "content": "new content"},
        }
    )

    completed_hook = _run_hook(HOOK_SCRIPT_PATH, git_repository, write_payload)

    assert completed_hook.returncode == 0
    assert completed_hook.stdout == ""


def test_dispatcher_preserves_edit_stage_guidance(git_repository: Path) -> None:
    source_path = git_repository / "module.py"
    matching_test_path = git_repository / "test_module.py"
    _commit_file(
        git_repository,
        source_path,
        "def calculate_total(amount: int) -> int:\n    return amount\n",
    )
    matching_test_path.write_text(
        "def calculate_total(amount: int) -> int:\n    return amount\n\n"
        "def test_calculate_total() -> None:\n    assert calculate_total(1) == 1\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "add", str(matching_test_path)],
        cwd=git_repository,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Refactor Guard Test",
            "-c",
            "user.email=refactor-guard@example.invalid",
            "commit",
            "-q",
            "-m",
            "test baseline",
            "--no-verify",
        ],
        cwd=git_repository,
        check=True,
    )
    _stage_file(
        git_repository,
        source_path,
        "def calculate_total(amount: int) -> int:\n    return amount + 1\n",
    )

    completed_dispatch = _run_hook(
        DISPATCHER_SCRIPT_PATH,
        git_repository,
        _refactor_payload(source_path),
    )
    dispatcher_payload = json.loads(completed_dispatch.stdout)
    hook_specific_output = dispatcher_payload["hookSpecificOutput"]

    assert hook_specific_output["permissionDecision"] == "allow", (
        f"Dispatcher output: {completed_dispatch.stdout!r}; stderr: {completed_dispatch.stderr!r}"
    )
    assert "Edit-stage" in dispatcher_payload["systemMessage"]
    assert "Refactor guard" in dispatcher_payload["systemMessage"]


def test_bypass_token_is_consumed_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bypass_token_path = tmp_path / "refactor-bypass-token"
    monkeypatch.setattr(refactor_guard, "REFACTOR_BYPASS_TOKEN_PATH", bypass_token_path)
    bypass_token_path.write_text("approved", encoding="utf-8")

    assert refactor_guard.is_bypass_approved()
    assert not bypass_token_path.exists()
    assert not refactor_guard.is_bypass_approved()
