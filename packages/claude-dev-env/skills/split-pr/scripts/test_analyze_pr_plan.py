"""Behavioral tests for analyze_pr file sourcing, statuses, and split advice."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import analyze_pr  # noqa: E402
from categorize_files import assign_layer  # noqa: E402
from split_pr_scripts_constants.config.analyze_constants import (  # noqa: E402
    GH_API,
    GH_FIELD_BASE_REF,
    GH_FIELD_BODY,
    GH_FIELD_CHANGED_FILES,
    GH_FIELD_FILES,
    GH_FIELD_HEAD_OID,
    GH_FIELD_HEAD_REF,
    GH_FIELD_NUMBER,
    GH_FIELD_TITLE,
    GH_FIELD_URL,
    GH_PAGINATE_FLAG,
    MAXIMUM_SLICE_CHANGED_LINES,
    PLAN_THRESHOLD_NOTE_KEY,
)
from split_pr_scripts_constants.config.categorize_constants import (  # noqa: E402
    LAYER_BACKEND,
)
from split_pr_scripts_constants.config.plan_constants import (  # noqa: E402
    FILE_KEY_PATH,
    FILE_KEY_STATUS,
    FILE_STATUS_REMOVED,
    PLAN_KEY_ALL_FILES,
    PLAN_KEY_PROPOSED_SLICES,
    SLICE_KEY_BRANCH,
    SLICE_KEY_SLUG,
)

GH_PAGE_SIZE = 100
OVERSIZED_PR_FILE_COUNT = 150
TRUNCATED_PR_FILE_COUNT = 672
SMALL_PR_FILE_COUNT = 9
FEW_FILE_COUNT = 5
LARGE_CHANGED_LINES_PER_FILE = 400
PR_NUMBER = 123
TITLE_PREFIX = "feat"


def build_api_file(path: str, status: str, additions: int = 4) -> dict[str, object]:
    return {
        "filename": path,
        "status": status,
        "additions": additions,
        "deletions": 0,
    }


def build_overview(changed_files: int) -> dict[str, object]:
    return {
        GH_FIELD_NUMBER: PR_NUMBER,
        GH_FIELD_TITLE: "Add notification bell",
        GH_FIELD_BASE_REF: "main",
        GH_FIELD_HEAD_REF: "feature/bell",
        GH_FIELD_HEAD_OID: "deadbeef",
        GH_FIELD_CHANGED_FILES: changed_files,
        GH_FIELD_URL: None,
        GH_FIELD_BODY: "",
    }


def build_page_of_files(start_index: int, count: int) -> list[dict[str, object]]:
    return [
        build_api_file(f"src/services/file_{each_index}.py", "modified")
        for each_index in range(start_index, start_index + count)
    ]


def install_fake_gh(
    monkeypatch: pytest.MonkeyPatch,
    overview: dict[str, object],
    all_pages: list[list[dict[str, object]]],
) -> list[list[str]]:
    all_recorded_commands: list[list[str]] = []

    def fake_run(
        all_command: list[str],
        **_keyword_arguments: object,
    ) -> subprocess.CompletedProcess[str]:
        all_recorded_commands.append(all_command)
        payload = all_pages if GH_API in all_command else overview
        return subprocess.CompletedProcess(
            args=all_command,
            returncode=0,
            stdout=json.dumps(payload),
            stderr="",
        )

    monkeypatch.setattr(analyze_pr.subprocess, "run", fake_run)
    return all_recorded_commands


def test_pagination_reads_every_file_past_the_first_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_pages = [
        build_page_of_files(0, GH_PAGE_SIZE),
        build_page_of_files(GH_PAGE_SIZE, OVERSIZED_PR_FILE_COUNT - GH_PAGE_SIZE),
    ]
    all_recorded_commands = install_fake_gh(
        monkeypatch,
        build_overview(OVERSIZED_PR_FILE_COUNT),
        all_pages,
    )

    all_pr_fields = analyze_pr._fetch_pr_payload(PR_NUMBER, "owner/name")

    all_files = all_pr_fields[GH_FIELD_FILES]
    assert isinstance(all_files, list)
    assert len(all_files) == OVERSIZED_PR_FILE_COUNT
    assert any(GH_PAGINATE_FLAG in each for each in all_recorded_commands)


def test_a_truncated_file_list_fails_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_gh(
        monkeypatch,
        build_overview(TRUNCATED_PR_FILE_COUNT),
        [build_page_of_files(0, GH_PAGE_SIZE)],
    )

    with pytest.raises(RuntimeError) as raised:
        analyze_pr._fetch_pr_payload(PR_NUMBER, "owner/name")

    assert str(GH_PAGE_SIZE) in str(raised.value)
    assert str(TRUNCATED_PR_FILE_COUNT) in str(raised.value)


def test_a_complete_file_list_passes_the_count_check() -> None:
    all_pr_fields = build_overview(2)
    all_pr_fields[GH_FIELD_FILES] = build_page_of_files(0, 2)

    analyze_pr.assert_file_list_is_complete(all_pr_fields)


def test_deleted_and_added_statuses_survive_into_the_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_pages = [
        [
            build_api_file("src/services/gone.py", FILE_STATUS_REMOVED),
            build_api_file("src/services/fresh.py", "added"),
        ]
    ]
    install_fake_gh(monkeypatch, build_overview(2), all_pages)

    all_pr_fields = analyze_pr._fetch_pr_payload(PR_NUMBER, "owner/name")
    plan_payload = analyze_pr.build_plan_from_pr_payload(
        all_pr_fields,
        repo="owner/name",
        title_prefix=TITLE_PREFIX,
    )

    all_files = plan_payload[PLAN_KEY_ALL_FILES]
    assert isinstance(all_files, list)
    status_by_path = {
        str(each[FILE_KEY_PATH]): each[FILE_KEY_STATUS] for each in all_files
    }
    assert status_by_path["src/services/gone.py"] == FILE_STATUS_REMOVED
    assert status_by_path["src/services/fresh.py"] == "added"


def test_a_few_files_with_heavy_churn_still_advises_a_split() -> None:
    all_pr_fields = build_overview(FEW_FILE_COUNT)
    all_pr_fields[GH_FIELD_FILES] = [
        build_api_file(
            f"src/services/big_{each_index}.py",
            "modified",
            additions=LARGE_CHANGED_LINES_PER_FILE,
        )
        for each_index in range(FEW_FILE_COUNT)
    ]

    plan_payload = analyze_pr.build_plan_from_pr_payload(
        all_pr_fields,
        repo=None,
        title_prefix=TITLE_PREFIX,
    )

    assert plan_payload[PLAN_THRESHOLD_NOTE_KEY] is None
    all_slices = plan_payload[PLAN_KEY_PROPOSED_SLICES]
    assert isinstance(all_slices, list)
    assert len(all_slices) > 1


def test_a_pr_inside_the_review_budget_emits_one_slice_with_the_optional_note() -> None:
    all_pr_fields = build_overview(SMALL_PR_FILE_COUNT)
    all_pr_fields[GH_FIELD_FILES] = [
        build_api_file(f"src/services/small_{each_index}.py", "modified", additions=1)
        for each_index in range(SMALL_PR_FILE_COUNT)
    ]

    plan_payload = analyze_pr.build_plan_from_pr_payload(
        all_pr_fields,
        repo=None,
        title_prefix=TITLE_PREFIX,
    )

    all_slices = plan_payload[PLAN_KEY_PROPOSED_SLICES]
    assert isinstance(all_slices, list)
    assert len(all_slices) == 1
    assert plan_payload[PLAN_THRESHOLD_NOTE_KEY]
    assert len(all_slices[0]["files"]) == SMALL_PR_FILE_COUNT


def test_branch_names_carry_the_slice_slug() -> None:
    all_pr_fields = build_overview(2)
    all_pr_fields[GH_FIELD_FILES] = [
        build_api_file("src/services/api.py", "modified", additions=300),
        build_api_file("docs/guide.md", "modified", additions=300),
    ]

    plan_payload = analyze_pr.build_plan_from_pr_payload(
        all_pr_fields,
        repo=None,
        title_prefix=TITLE_PREFIX,
    )

    all_slices = plan_payload[PLAN_KEY_PROPOSED_SLICES]
    assert isinstance(all_slices, list)
    for each_slice in all_slices:
        assert str(each_slice[SLICE_KEY_SLUG]) in str(each_slice[SLICE_KEY_BRANCH])


@pytest.mark.parametrize(
    "hook_path",
    [
        "packages/claude-dev-env/hooks/observability/hook_block_logger.py",
        "packages/claude-dev-env/hooks/validation/check_x.py",
        "packages/claude-dev-env/hooks/git-hooks/pre_commit.py",
        "packages/claude-dev-env/hooks/blocking/gate.py",
    ],
)
def test_every_hook_subdirectory_lands_in_the_backend_layer(hook_path: str) -> None:
    assert assign_layer(hook_path) == LAYER_BACKEND


def test_a_heavy_single_file_pr_is_not_called_optional() -> None:
    all_pr_fields = build_overview(1)
    all_pr_fields[GH_FIELD_FILES] = [
        build_api_file(
            "src/services/huge.py",
            "modified",
            additions=MAXIMUM_SLICE_CHANGED_LINES + 1,
        )
    ]

    plan_payload = analyze_pr.build_plan_from_pr_payload(
        all_pr_fields,
        repo=None,
        title_prefix=TITLE_PREFIX,
    )

    assert plan_payload[PLAN_THRESHOLD_NOTE_KEY] is None
