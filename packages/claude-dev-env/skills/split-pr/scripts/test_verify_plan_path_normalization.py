"""Behavioral tests for the path normalization verify_plan applies to a plan."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from split_pr_scripts_constants.config.plan_constants import (  # noqa: E402
    PLAN_KEY_ALL_FILES,
    PLAN_KEY_BASE_REF,
    PLAN_KEY_HEAD_SHA,
    PLAN_KEY_PR_NUMBER,
    PLAN_KEY_PROPOSED_SLICES,
    PLAN_KEY_SOURCE_BRANCH,
    SLICE_KEY_BASE,
    SLICE_KEY_BRANCH,
    SLICE_KEY_FILES,
    SLICE_KEY_SLUG,
    VERIFY_KEY_IS_VALID,
    VERIFY_KEY_MISSING_FILES,
    VERIFY_KEY_UNKNOWN_FILES,
)
from verify_plan import verify_plan  # noqa: E402


def build_plan_covering(all_slice_paths: list[str]) -> dict[str, object]:
    return {
        PLAN_KEY_ALL_FILES: [{"path": "src/a.ts", "additions": 3, "deletions": 1}],
        PLAN_KEY_PROPOSED_SLICES: [
            {
                SLICE_KEY_SLUG: "frontend",
                SLICE_KEY_FILES: all_slice_paths,
                SLICE_KEY_BRANCH: "split/1/01-frontend",
                SLICE_KEY_BASE: "main",
            }
        ],
        PLAN_KEY_SOURCE_BRANCH: "feature/one",
        PLAN_KEY_BASE_REF: "main",
        PLAN_KEY_PR_NUMBER: 7,
        PLAN_KEY_HEAD_SHA: "abc123",
    }


def test_dot_slash_slice_path_matches_the_bare_source_path() -> None:
    report = verify_plan(build_plan_covering(["./src/a.ts"]))

    assert report[VERIFY_KEY_MISSING_FILES] == []
    assert report[VERIFY_KEY_UNKNOWN_FILES] == []
    assert report[VERIFY_KEY_IS_VALID] is True


def test_backslash_slice_path_matches_the_posix_source_path() -> None:
    report = verify_plan(build_plan_covering(["src\\a.ts"]))

    assert report[VERIFY_KEY_MISSING_FILES] == []
    assert report[VERIFY_KEY_IS_VALID] is True


def test_dot_slash_source_path_matches_the_bare_slice_path() -> None:
    plan_payload = build_plan_covering(["src/a.ts"])
    plan_payload[PLAN_KEY_ALL_FILES] = [{"path": "./src/a.ts", "additions": 3}]

    report = verify_plan(plan_payload)

    assert report[VERIFY_KEY_UNKNOWN_FILES] == []
    assert report[VERIFY_KEY_IS_VALID] is True
