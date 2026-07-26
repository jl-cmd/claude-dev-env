"""Behavioral tests for the plan contract verify_plan enforces for execute_split."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from split_pr_scripts_constants.config.common_constants import (  # noqa: E402
    PAYLOAD_KEY_ERROR,
)
from split_pr_scripts_constants.config.plan_constants import (  # noqa: E402
    PLAN_KEY_ALL_FILES,
    PLAN_KEY_BASE_REF,
    PLAN_KEY_HEAD_SHA,
    PLAN_KEY_PR_NUMBER,
    PLAN_KEY_PROPOSED_SLICES,
    PLAN_KEY_SOURCE_BRANCH,
    SLICE_KEY_BASE,
    SLICE_KEY_BRANCH,
    SLICE_KEY_CHANGED_LINES,
    SLICE_KEY_FILES,
    SLICE_KEY_SLUG,
    VERIFY_KEY_DUPLICATE_FILES,
    VERIFY_KEY_ERRORS,
    VERIFY_KEY_IS_VALID,
    VERIFY_KEY_OVERSIZED_SLICES,
)
from verify_plan import main, verify_plan  # noqa: E402

VERIFY_SCRIPT_PATH = SCRIPTS_DIRECTORY / "verify_plan.py"
PLAN_FILE_NAME = "plan.json"
LARGE_SLICE_FILE_COUNT = 40
LARGE_SLICE_CHANGED_LINES = 6000


def build_complete_plan() -> dict[str, object]:
    return {
        PLAN_KEY_ALL_FILES: [{"path": "src/one.py", "additions": 5, "deletions": 1}],
        PLAN_KEY_PROPOSED_SLICES: [
            {
                SLICE_KEY_SLUG: "backend",
                SLICE_KEY_FILES: ["src/one.py"],
                SLICE_KEY_BRANCH: "split/1/01-backend",
                SLICE_KEY_BASE: "main",
            }
        ],
        PLAN_KEY_SOURCE_BRANCH: "feature/one",
        PLAN_KEY_BASE_REF: "main",
        PLAN_KEY_PR_NUMBER: 7,
        PLAN_KEY_HEAD_SHA: "abc123",
    }


def run_verify_script(plan_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT_PATH), "--plan", str(plan_path)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_complete_plan_verifies_clean() -> None:
    report = verify_plan(build_complete_plan())

    assert report[VERIFY_KEY_IS_VALID] is True


def test_plan_without_executor_keys_is_rejected() -> None:
    bare_plan = {
        PLAN_KEY_ALL_FILES: [{"path": "src/one.py"}],
        PLAN_KEY_PROPOSED_SLICES: [{SLICE_KEY_FILES: ["src/one.py"]}],
    }

    report = verify_plan(bare_plan)

    all_errors = report[VERIFY_KEY_ERRORS]
    assert report[VERIFY_KEY_IS_VALID] is False
    assert any(PLAN_KEY_SOURCE_BRANCH in each for each in all_errors)
    assert any(PLAN_KEY_BASE_REF in each for each in all_errors)
    assert any(PLAN_KEY_PR_NUMBER in each for each in all_errors)


def test_slice_without_branch_and_base_is_rejected() -> None:
    plan_payload = build_complete_plan()
    plan_payload[PLAN_KEY_PROPOSED_SLICES] = [
        {SLICE_KEY_SLUG: "backend", SLICE_KEY_FILES: ["src/one.py"]}
    ]

    report = verify_plan(plan_payload)

    all_errors = report[VERIFY_KEY_ERRORS]
    assert report[VERIFY_KEY_IS_VALID] is False
    assert any(SLICE_KEY_BRANCH in each for each in all_errors)
    assert any(SLICE_KEY_BASE in each for each in all_errors)


def test_non_numeric_changed_lines_reports_a_plan_error() -> None:
    plan_payload = build_complete_plan()
    all_slices = plan_payload[PLAN_KEY_PROPOSED_SLICES]
    assert isinstance(all_slices, list)
    all_slices[0][SLICE_KEY_CHANGED_LINES] = ["not", "a", "number"]

    report = verify_plan(plan_payload)

    assert report[VERIFY_KEY_IS_VALID] is False
    assert any("changed_lines" in each for each in report[VERIFY_KEY_OVERSIZED_SLICES])


def test_oversized_slice_is_rejected_despite_a_plan_supplied_atomic_flag() -> None:
    all_paths = [f"src/file_{each_index}.py" for each_index in range(LARGE_SLICE_FILE_COUNT)]
    plan_payload = build_complete_plan()
    plan_payload[PLAN_KEY_ALL_FILES] = [{"path": each_path} for each_path in all_paths]
    plan_payload[PLAN_KEY_PROPOSED_SLICES] = [
        {
            SLICE_KEY_SLUG: "backend",
            SLICE_KEY_FILES: all_paths,
            SLICE_KEY_BRANCH: "split/1/01-backend",
            SLICE_KEY_BASE: "main",
            SLICE_KEY_CHANGED_LINES: LARGE_SLICE_CHANGED_LINES,
            "oversized_atomic": True,
        }
    ]

    report = verify_plan(plan_payload)

    assert report[VERIFY_KEY_IS_VALID] is False
    assert report[VERIFY_KEY_OVERSIZED_SLICES]


def test_duplicate_paths_across_slices_are_reported_once_each() -> None:
    plan_payload = build_complete_plan()
    plan_payload[PLAN_KEY_ALL_FILES] = [{"path": "src/one.py"}, {"path": "src/two.py"}]
    plan_payload[PLAN_KEY_PROPOSED_SLICES] = [
        {
            SLICE_KEY_SLUG: "one",
            SLICE_KEY_FILES: ["src/one.py", "src/two.py"],
            SLICE_KEY_BRANCH: "split/1/01-one",
            SLICE_KEY_BASE: "main",
        },
        {
            SLICE_KEY_SLUG: "two",
            SLICE_KEY_FILES: ["src/one.py"],
            SLICE_KEY_BRANCH: "split/1/02-two",
            SLICE_KEY_BASE: "split/1/01-one",
        },
    ]

    report = verify_plan(plan_payload)

    assert report[VERIFY_KEY_DUPLICATE_FILES] == ["src/one.py"]


def build_plan_failing_every_coverage_rule() -> dict[str, object]:
    plan_payload = build_complete_plan()
    plan_payload[PLAN_KEY_ALL_FILES] = [{"path": "src/one.py"}, {"path": "src/two.py"}]
    plan_payload[PLAN_KEY_PROPOSED_SLICES] = [
        {
            SLICE_KEY_SLUG: "one",
            SLICE_KEY_FILES: ["src/one.py", "src/ghost.py"],
            SLICE_KEY_BRANCH: "split/1/01-one",
            SLICE_KEY_BASE: "main",
        },
        {
            SLICE_KEY_SLUG: "two",
            SLICE_KEY_FILES: ["src/one.py"],
            SLICE_KEY_BRANCH: "split/1/02-two",
            SLICE_KEY_BASE: "split/1/01-one",
        },
        {
            SLICE_KEY_SLUG: "empty",
            SLICE_KEY_FILES: [],
            SLICE_KEY_BRANCH: "split/1/03-empty",
            SLICE_KEY_BASE: "split/1/02-two",
        },
    ]
    return plan_payload


def test_coverage_count_errors_keep_their_exact_wire_text() -> None:
    report = verify_plan(build_plan_failing_every_coverage_rule())

    all_errors = report[VERIFY_KEY_ERRORS]
    assert isinstance(all_errors, list)
    assert "missing_files:1" in all_errors
    assert "unknown_files:1" in all_errors
    assert "duplicate_files:1" in all_errors
    assert "empty_slices:1" in all_errors


def test_a_non_object_slice_entry_keeps_its_exact_wire_text() -> None:
    plan_payload = build_complete_plan()
    all_slices = plan_payload[PLAN_KEY_PROPOSED_SLICES]
    assert isinstance(all_slices, list)
    all_slices.append("not a slice object")

    report = verify_plan(plan_payload)

    all_errors = report[VERIFY_KEY_ERRORS]
    assert isinstance(all_errors, list)
    assert "slice entry is not an object" in all_errors


def test_main_reports_a_json_error_for_a_non_numeric_addition_count(
    tmp_path: Path,
) -> None:
    plan_payload = build_complete_plan()
    plan_payload[PLAN_KEY_ALL_FILES] = [{"path": "src/one.py", "additions": ["x"]}]
    plan_path = tmp_path / PLAN_FILE_NAME
    plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")

    completed = run_verify_script(plan_path)

    assert completed.returncode == 1
    assert PAYLOAD_KEY_ERROR in json.loads(completed.stdout)
    assert "Traceback" not in completed.stderr


def test_main_returns_zero_for_a_complete_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / PLAN_FILE_NAME
    plan_path.write_text(json.dumps(build_complete_plan()), encoding="utf-8")
    original_arguments = list(sys.argv)
    sys.argv = ["verify_plan.py", "--plan", str(plan_path)]
    try:
        exit_code = main()
    finally:
        sys.argv = original_arguments

    assert exit_code == 0
