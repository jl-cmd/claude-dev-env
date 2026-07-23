"""Behavioral tests for analyze_pr plan building (offline files-json path)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from analyze_pr import build_plan_from_pr_payload, slugify_feature  # noqa: E402
from split_pr_scripts_constants.config.analyze_constants import (  # noqa: E402
    EXIT_CODE_SUCCESS,
    GH_FIELD_BASE_REF,
    GH_FIELD_FILES,
    GH_FIELD_HEAD_OID,
    GH_FIELD_HEAD_REF,
    GH_FIELD_NUMBER,
    GH_FIELD_TITLE,
    GH_FILE_PATH,
)
from split_pr_scripts_constants.config.plan_constants import (  # noqa: E402
    PLAN_KEY_FILE_COUNT,
    PLAN_KEY_PROPOSED_SLICES,
    SLICE_KEY_BASE,
    SLICE_KEY_BRANCH,
)


def test_slugify_feature_strips_noise() -> None:
    assert slugify_feature("feat: Hello World!!", 9) == "feat-hello-world"


def test_build_plan_from_pr_payload_chains_bases() -> None:
    payload = {
        GH_FIELD_NUMBER: 42,
        GH_FIELD_TITLE: "Notification system",
        GH_FIELD_BASE_REF: "main",
        GH_FIELD_HEAD_REF: "feature/notifications",
        GH_FIELD_HEAD_OID: "abc123",
        GH_FIELD_FILES: [
            {GH_FILE_PATH: "prisma/schema.prisma", "additions": 10, "deletions": 0},
            {GH_FILE_PATH: "src/api/notify.ts", "additions": 20, "deletions": 1},
            {GH_FILE_PATH: "src/components/Bell.tsx", "additions": 30, "deletions": 0},
        ],
    }
    plan = build_plan_from_pr_payload(payload, repo="acme/app", title_prefix="feat")
    assert plan[PLAN_KEY_FILE_COUNT] == 3
    all_slices = plan[PLAN_KEY_PROPOSED_SLICES]
    assert len(all_slices) == 3
    assert all_slices[0][SLICE_KEY_BASE] == "main"
    assert all_slices[1][SLICE_KEY_BASE] == all_slices[0][SLICE_KEY_BRANCH]
    assert all_slices[2][SLICE_KEY_BASE] == all_slices[1][SLICE_KEY_BRANCH]
    assert all_slices[0][SLICE_KEY_BRANCH].startswith("split/42/")


def test_analyze_pr_cli_files_json(tmp_path: Path) -> None:
    files_path = tmp_path / "files.json"
    files_path.write_text(
        json.dumps(
            [
                {GH_FILE_PATH: "prisma/a.prisma"},
                {GH_FILE_PATH: "src/api/b.ts"},
            ]
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIRECTORY / "analyze_pr.py"),
            "--pr",
            "7",
            "--files-json",
            str(files_path),
            "--title",
            "Demo feature",
            "--pretty",
        ],
        cwd=str(SCRIPTS_DIRECTORY),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == EXIT_CODE_SUCCESS, completed.stderr
    plan = json.loads(completed.stdout)
    assert plan[PLAN_KEY_FILE_COUNT] == 2
    assert len(plan[PLAN_KEY_PROPOSED_SLICES]) == 2
