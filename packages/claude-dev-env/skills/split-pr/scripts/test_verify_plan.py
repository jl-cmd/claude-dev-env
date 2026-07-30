"""Vertical-slice plan verification tests."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from config.split_pr_constants import (
    PLAN_KEY_IS_VALID,
    PLAN_KEY_PATHS,
    PLAN_KEY_SLICES,
    PLAN_KEY_STORY,
    PLAN_KEY_VIOLATIONS,
    VIOLATION_DUPLICATE_PATH,
    VIOLATION_TEST_WITHOUT_BEHAVIOR,
)
from verify_plan import is_test_path, related_behavior_stem, verify_vertical_plan


def test_is_test_path_detects_common_layouts() -> None:
    assert is_test_path("packages/app/test_foo.py")
    assert is_test_path("packages/app/foo_test.py")
    assert is_test_path("packages/app/foo.test.ts")
    assert not is_test_path("packages/app/foo.py")


def test_related_behavior_stem_strips_test_prefix_and_suffix() -> None:
    assert related_behavior_stem("scripts/test_claude_chain_runner.py") == (
        "claude_chain_runner"
    )
    assert related_behavior_stem("scripts/claude_chain_runner_test.py") == (
        "claude_chain_runner"
    )
    assert related_behavior_stem("scripts/helpers.py") is None


def test_valid_vertical_slice_keeps_tests_with_behavior() -> None:
    plan = {
        PLAN_KEY_SLICES: [
            {
                PLAN_KEY_STORY: "affinity store",
                PLAN_KEY_PATHS: [
                    "scripts/claude_chain_runner.py",
                    "scripts/test_claude_chain_runner.py",
                ],
            }
        ]
    }
    all_paths = [
        "scripts/claude_chain_runner.py",
        "scripts/test_claude_chain_runner.py",
    ]
    verdict = verify_vertical_plan(plan, all_changed_paths=all_paths)
    assert verdict[PLAN_KEY_IS_VALID] is True
    assert verdict[PLAN_KEY_VIOLATIONS] == []


def test_rejects_test_only_slice_without_behavior() -> None:
    plan = {
        PLAN_KEY_SLICES: [
            {
                PLAN_KEY_STORY: "tests only",
                PLAN_KEY_PATHS: ["scripts/test_claude_chain_runner.py"],
            }
        ]
    }
    verdict = verify_vertical_plan(
        plan,
        all_changed_paths=["scripts/test_claude_chain_runner.py"],
    )
    assert verdict[PLAN_KEY_IS_VALID] is False
    assert any(
        VIOLATION_TEST_WITHOUT_BEHAVIOR in each for each in verdict[PLAN_KEY_VIOLATIONS]
    )


def test_rejects_duplicate_path_across_slices() -> None:
    plan = {
        PLAN_KEY_SLICES: [
            {
                PLAN_KEY_STORY: "a",
                PLAN_KEY_PATHS: ["src/a.py", "src/test_a.py"],
            },
            {
                PLAN_KEY_STORY: "b",
                PLAN_KEY_PATHS: ["src/a.py"],
            },
        ]
    }
    verdict = verify_vertical_plan(
        plan, all_changed_paths=["src/a.py", "src/test_a.py"]
    )
    assert verdict[PLAN_KEY_IS_VALID] is False
    assert any(VIOLATION_DUPLICATE_PATH in each for each in verdict[PLAN_KEY_VIOLATIONS])


def test_rejects_missing_changed_path() -> None:
    plan = {
        PLAN_KEY_SLICES: [
            {
                PLAN_KEY_STORY: "partial",
                PLAN_KEY_PATHS: ["src/a.py", "src/test_a.py"],
            }
        ]
    }
    verdict = verify_vertical_plan(
        plan, all_changed_paths=["src/a.py", "src/test_a.py", "src/b.py"]
    )
    assert verdict[PLAN_KEY_IS_VALID] is False
    assert any("path_missing" in each for each in verdict[PLAN_KEY_VIOLATIONS])
