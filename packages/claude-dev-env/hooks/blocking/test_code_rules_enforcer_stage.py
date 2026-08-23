"""Test stage ownership for the code-rules enforcer entrypoint."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
_PR_LOOP_SCRIPTS_DIRECTORY = str(Path(__file__).resolve().parents[2] / "_shared" / "pr-loop" / "scripts")
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)
if _PR_LOOP_SCRIPTS_DIRECTORY not in sys.path:
    sys.path.insert(0, _PR_LOOP_SCRIPTS_DIRECTORY)

from code_rules_enforcer import (  # noqa: E402
    _fragment_or_deferred_check,
    main,
    validate_content,
)
from code_rules_gate_parts import gate_running  # noqa: E402
from code_rules_gate_parts.tests._repo_test_helpers import (  # noqa: E402
    init_repository,
    write_commit_and_stage_change,
)


PRODUCTION_FILE_PATH = "packages/app/services.py"
ENFORCER_SCRIPT_PATH = Path(__file__).with_name("code_rules_enforcer.py")


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
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    try:
        main([])
    except SystemExit:
        pass
    return capsys.readouterr().out


def _run_precheck_stage(candidate_path: Path, target_path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ENFORCER_SCRIPT_PATH),
            "--check",
            str(candidate_path),
            "--as",
            target_path,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


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


def test_precheck_stage_runs_the_cli_and_uses_the_declared_target_path(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    staging_directory = tmp_path_factory.mktemp("stage")
    candidate_path = staging_directory / "candidate.py"
    candidate_path.write_text(
        "def process_data() -> None:\n    print('payload')\n",
        encoding="utf-8",
    )
    target_path = str(staging_directory / "service.py")

    completed_process = _run_precheck_stage(candidate_path, target_path)

    assert completed_process.returncode == 1
    assert "process_data" in completed_process.stdout


def test_gate_caller_scans_staged_content_with_commit_stage_scope(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    init_repository(repository_root)
    committed_source = "def calculate_total() -> int:\n    return 0\n"
    staged_source = (
        "def calculate_total() -> int:\n"
        "    total = 9999\n"
        "    return total\n"
    )
    file_path = write_commit_and_stage_change(
        repository_root,
        "service.py",
        committed_source,
        staged_source,
    )

    all_partitioned_violations = gate_running._scoped_violations_for_file(
        validate_content=validate_content,
        resolved_path=file_path,
        repository_root=repository_root,
        all_added_lines_for_file={2, 3},
        should_read_staged_content=True,
    )

    assert all_partitioned_violations is not None
    all_blocking_violations, _all_advisory_violations = all_partitioned_violations
    assert any("9999" in each_issue for each_issue in all_blocking_violations)
