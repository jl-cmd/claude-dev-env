"""Tests for direct and dispatched refactor guidance."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ADVISORY_DIRECTORY = Path(__file__).resolve().parent
HOOK_SCRIPT_PATH = ADVISORY_DIRECTORY / "refactor_guard.py"
DISPATCHER_SCRIPT_PATH = ADVISORY_DIRECTORY.parent / "blocking" / "pre_tool_use_dispatcher.py"
if str(ADVISORY_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(ADVISORY_DIRECTORY))

import refactor_guard  # noqa: E402
from refactor_guard_test_support import commit_file, stage_file  # noqa: E402

pytestmark = pytest.mark.usefixtures("ephemeral_exempt_off")


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
    commit_file(
        git_repository,
        source_path,
        "def calculate_total(amount: int) -> int:\n    return amount\n",
    )
    stage_file(
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
    commit_file(
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
    commit_file(
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
    """A red step (staged, uncommitted test) plus a staged refactor still allows."""
    source_path = git_repository / "module.py"
    matching_test_path = git_repository / "test_module.py"
    commit_file(
        git_repository,
        source_path,
        "def calculate_total(amount: int) -> int:\n    return amount\n",
    )
    stage_file(
        git_repository,
        matching_test_path,
        "def calculate_total(amount: int) -> int:\n    return amount\n\n"
        "def test_calculate_total() -> None:\n    assert calculate_total(1) == 1\n",
    )
    stage_file(
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


def _multi_edit_payload(file_path: Path, all_edits: list[dict[str, str]]) -> str:
    return json.dumps(
        {
            "tool_name": "MultiEdit",
            "tool_input": {"file_path": str(file_path), "edits": all_edits},
        }
    )


def _commit_and_stage_the_renamed_module(git_repository: Path, source_path: Path) -> None:
    """Commit the base module, then stage an unrelated numeric change to it."""
    commit_file(
        git_repository,
        source_path,
        "def calculate_total(amount: int) -> int:\n    return amount\n",
    )
    stage_file(
        git_repository,
        source_path,
        "def calculate_total(amount: int) -> int:\n    return amount + 1\n",
    )


def test_direct_hook_flags_refactor_in_second_multi_edit(git_repository: Path) -> None:
    """A rename buried in the second edit of a MultiEdit is caught, not only the first.

    The first edit is an ordinary numeric change; only the second edit renames
    calculate_total to compute_total outside the currently staged diff.
    """
    source_path = git_repository / "module.py"
    _commit_and_stage_the_renamed_module(git_repository, source_path)
    payload_text = _multi_edit_payload(
        source_path,
        [
            {"old_string": "return amount", "new_string": "return amount + 1"},
            {
                "old_string": "def calculate_total(amount: int) -> int:\n    return amount",
                "new_string": "def compute_total(amount: int) -> int:\n    return amount",
            },
        ],
    )

    completed_hook = _run_hook(HOOK_SCRIPT_PATH, git_repository, payload_text)
    advisory_payload = json.loads(completed_hook.stdout)
    hook_specific_output = advisory_payload["hookSpecificOutput"]

    assert hook_specific_output["permissionDecision"] == "allow"
    assert "Edit-stage" in advisory_payload["systemMessage"]


def test_direct_hook_stays_silent_for_ordinary_multi_edit(git_repository: Path) -> None:
    source_path = git_repository / "module.py"
    commit_file(
        git_repository,
        source_path,
        "def calculate_total(amount: int) -> int:\n    return amount\n",
    )
    payload_text = _multi_edit_payload(
        source_path,
        [{"old_string": "return amount", "new_string": "return amount + 1"}],
    )

    completed_hook = _run_hook(HOOK_SCRIPT_PATH, git_repository, payload_text)

    assert completed_hook.returncode == 0
    assert completed_hook.stdout == ""
