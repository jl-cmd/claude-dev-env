"""Test stage ownership for the code-rules enforcer entrypoint."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_enforcer import (  # noqa: E402
    _fragment_or_deferred_check,
    main,
)


PRODUCTION_FILE_PATH = "packages/app/services.py"


def _write_payload(file_path: str, source: str) -> str:
    return json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": file_path, "content": source},
        }
    )


def _run_write_stage(
    file_path: str,
    source: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> str:
    payload = _write_payload(file_path, source)
    getattr(monkeypatch, "setattr")(
        sys,
        "stdin",
        io.StringIO(payload),
    )
    try:
        main([])
    except SystemExit:
        pass
    return getattr(capsys, "readouterr")().out


def test_edit_stage_baselines_the_new_fragment_against_the_old_fragment() -> None:
    all_seen_contents: list[str] = []

    def record_check(content: str, file_path: str) -> list[str]:
        all_seen_contents.append(content)
        if "introduced" in content:
            return [f"finding in {file_path}"]
        return []

    all_issues = _fragment_or_deferred_check(
        record_check,
        "existing fragment",
        "introduced fragment",
        PRODUCTION_FILE_PATH,
        defer_scope_to_caller=False,
    )

    assert all_seen_contents == ["introduced fragment", "existing fragment"]
    assert all_issues == [f"finding in {PRODUCTION_FILE_PATH}"]


def test_commit_stage_owns_scope_and_scans_the_complete_candidate_once() -> None:
    all_seen_contents: list[str] = []

    def record_check(content: str, file_path: str) -> list[str]:
        all_seen_contents.append(content)
        return [f"finding in {file_path}"]

    all_issues = _fragment_or_deferred_check(
        record_check,
        "HEAD content",
        "staged candidate",
        PRODUCTION_FILE_PATH,
        defer_scope_to_caller=True,
    )

    assert all_seen_contents == ["staged candidate"]
    assert all_issues == [f"finding in {PRODUCTION_FILE_PATH}"]


def test_write_stage_runs_the_real_entrypoint_and_reports_a_deny_payload(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    staging_directory = getattr(tmp_path_factory, "mktemp")("stage")
    target_path = str(staging_directory / "service.py")
    source = "def process_data() -> None:\n    print('payload')\n"

    captured_stdout = _run_write_stage(target_path, source, monkeypatch, capsys)

    deny_payload = json.loads(captured_stdout)
    deny_reason = deny_payload["hookSpecificOutput"]["permissionDecisionReason"]
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "process_data" in deny_reason


def test_write_stage_allows_a_clean_candidate_through_the_real_entrypoint(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    staging_directory = getattr(tmp_path_factory, "mktemp")("stage")
    target_path = str(staging_directory / "service.py")
    source = "def calculate_total() -> int:\n    return 0\n"

    captured_stdout = _run_write_stage(target_path, source, monkeypatch, capsys)

    assert captured_stdout == ""
