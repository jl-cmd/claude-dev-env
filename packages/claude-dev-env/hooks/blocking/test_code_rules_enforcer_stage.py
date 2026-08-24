"""Test stage ownership for the code-rules enforcer entrypoint."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)
from blocking import _path_setup  # noqa: F401

from code_rules_enforcer import (  # noqa: E402
    _fragment_or_deferred_check,
    main,
)
from code_rules_enforcer_test_support import (  # noqa: E402
    run_write_entrypoint,
)


PRODUCTION_FILE_PATH = "packages/app/services.py"


def _run_write_stage(
    file_path: str,
    source: str,
) -> str:
    captured_stdout, _exit_code = run_write_entrypoint(main, file_path, source)
    return captured_stdout


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


def test_write_stage_runs_the_real_entrypoint_and_reports_a_deny_payload() -> None:
    source = "def process_data() -> None:\n    print('payload')\n"

    captured_stdout = _run_write_stage(PRODUCTION_FILE_PATH, source)

    deny_payload = json.loads(captured_stdout)
    deny_reason = deny_payload["hookSpecificOutput"]["permissionDecisionReason"]
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "process_data" in deny_reason


def test_write_stage_allows_a_clean_candidate_through_the_real_entrypoint() -> None:
    source = "def calculate_total() -> int:\n    return 0\n"

    captured_stdout = _run_write_stage(PRODUCTION_FILE_PATH, source)

    assert captured_stdout == ""
