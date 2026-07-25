"""Behavioral tests for supersede_source_pr (comment + close source after split)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from split_pr_scripts_constants.config.execute_constants import (  # noqa: E402
    GH_BODY_FILE,
    GH_CLOSE,
    GH_COMMAND,
    GH_COMMENT,
    GH_PR,
    PAYLOAD_KEY_CHILD_PR_NUMBERS,
    PAYLOAD_KEY_CLOSED,
    PAYLOAD_KEY_COMMENTED,
    PAYLOAD_KEY_SKIPPED,
    PAYLOAD_KEY_SKIP_REASON,
    SUPERSEDE_HEADING,
    SUPERSEDE_SKIP_ALREADY_DONE,
    SUPERSEDE_SKIP_ATOMIC,
    SUPERSEDE_SKIP_CREATE_PRS_OFF,
    SUPERSEDE_SKIP_NO_CHILD_URLS,
    SUPERSEDE_SKIP_PARTIAL,
)
from supersede_source_pr import (  # noqa: E402
    build_supersede_comment_body,
    collect_pr_numbers_from_urls,
    extract_pr_number_from_url,
    format_merge_order,
    resolve_supersede_skip_reason,
    supersede_source_pr,
)

CHILD_PR_URL_ONE = "https://github.com/example/repo/pull/10"
CHILD_PR_URL_TWO = "https://github.com/example/repo/pull/11"
SOURCE_PR_NUMBER = 99
REPO_SLUG = "example/repo"


def test_extract_pr_number_from_url_reads_pull_segment() -> None:
    assert extract_pr_number_from_url(CHILD_PR_URL_ONE) == 10
    assert extract_pr_number_from_url("https://github.com/o/r/pull/42/files") == 42
    assert extract_pr_number_from_url("not-a-url") is None


def test_collect_pr_numbers_from_urls_keeps_order() -> None:
    all_numbers = collect_pr_numbers_from_urls(
        [CHILD_PR_URL_ONE, "not-a-url", CHILD_PR_URL_TWO]
    )
    assert all_numbers == [10, 11]


def test_format_merge_order_joins_hash_numbers() -> None:
    assert format_merge_order([10, 11]) == "#10 → #11"
    assert format_merge_order([42]) == "#42"


def test_build_supersede_comment_body_lists_merge_order_and_urls() -> None:
    body = build_supersede_comment_body(
        all_child_pr_numbers=[10, 11],
        all_child_pr_urls=[CHILD_PR_URL_ONE, CHILD_PR_URL_TWO],
    )
    assert SUPERSEDE_HEADING in body
    assert "#10 → #11" in body
    assert CHILD_PR_URL_ONE in body
    assert CHILD_PR_URL_TWO in body


def test_resolve_supersede_skip_reason_atomic_and_partial() -> None:
    assert (
        resolve_supersede_skip_reason(
            planned_slice_count=1,
            all_child_pr_urls=[CHILD_PR_URL_ONE],
            should_create_prs=True,
            should_supersede=True,
        )
        == SUPERSEDE_SKIP_ATOMIC
    )
    assert (
        resolve_supersede_skip_reason(
            planned_slice_count=2,
            all_child_pr_urls=[CHILD_PR_URL_ONE],
            should_create_prs=True,
            should_supersede=True,
        )
        == SUPERSEDE_SKIP_PARTIAL
    )
    assert (
        resolve_supersede_skip_reason(
            planned_slice_count=2,
            all_child_pr_urls=[],
            should_create_prs=True,
            should_supersede=True,
        )
        == SUPERSEDE_SKIP_NO_CHILD_URLS
    )
    assert (
        resolve_supersede_skip_reason(
            planned_slice_count=2,
            all_child_pr_urls=[CHILD_PR_URL_ONE, CHILD_PR_URL_TWO],
            should_create_prs=False,
            should_supersede=True,
        )
        == SUPERSEDE_SKIP_CREATE_PRS_OFF
    )
    assert (
        resolve_supersede_skip_reason(
            planned_slice_count=2,
            all_child_pr_urls=[CHILD_PR_URL_ONE, CHILD_PR_URL_TWO],
            should_create_prs=True,
            should_supersede=True,
        )
        is None
    )


def _make_gh_runner(
    all_calls: list[list[str]],
    view_payload: dict[str, object] | None = None,
) -> Callable[..., subprocess.CompletedProcess[str]]:
    open_state_payload = view_payload or {"state": "OPEN", "comments": []}

    def fake_run(
        all_command: list[str],
        cwd: str | None = None,
        capture_output: bool = False,
        text: bool = False,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, capture_output, text, check
        all_calls.append(list(all_command))
        if all_command[:3] == [GH_COMMAND, GH_PR, "view"]:
            return subprocess.CompletedProcess(
                args=all_command,
                returncode=0,
                stdout=json.dumps(open_state_payload),
                stderr="",
            )
        return subprocess.CompletedProcess(
            args=all_command,
            returncode=0,
            stdout="",
            stderr="",
        )

    return fake_run


def test_supersede_source_pr_comments_with_body_file_then_closes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    all_calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _make_gh_runner(all_calls))
    result_payload = supersede_source_pr(
        source_pr_number=SOURCE_PR_NUMBER,
        all_child_pr_urls=[CHILD_PR_URL_ONE, CHILD_PR_URL_TWO],
        planned_slice_count=2,
        should_create_prs=True,
        should_supersede=True,
        repo=REPO_SLUG,
        repo_root=tmp_path,
    )
    assert result_payload[PAYLOAD_KEY_COMMENTED] is True
    assert result_payload[PAYLOAD_KEY_CLOSED] is True
    assert result_payload[PAYLOAD_KEY_CHILD_PR_NUMBERS] == [10, 11]
    assert result_payload[PAYLOAD_KEY_SKIPPED] is False

    comment_calls = [
        each for each in all_calls if each[:3] == [GH_COMMAND, GH_PR, GH_COMMENT]
    ]
    close_calls = [
        each for each in all_calls if each[:3] == [GH_COMMAND, GH_PR, GH_CLOSE]
    ]
    assert len(comment_calls) == 1
    assert GH_BODY_FILE in comment_calls[0]
    body_file_index = comment_calls[0].index(GH_BODY_FILE) + 1
    body_path = Path(comment_calls[0][body_file_index])
    assert body_path.is_file()
    body_text = body_path.read_text(encoding="utf-8")
    assert SUPERSEDE_HEADING in body_text
    assert "#10 → #11" in body_text
    assert len(close_calls) == 1
    assert str(SOURCE_PR_NUMBER) in close_calls[0]


def test_supersede_source_pr_skips_when_already_closed_with_heading(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    all_calls: list[list[str]] = []
    already_done = {
        "state": "CLOSED",
        "comments": [{"body": f"{SUPERSEDE_HEADING}\n\nstack done"}],
    }
    monkeypatch.setattr(
        subprocess,
        "run",
        _make_gh_runner(all_calls, view_payload=already_done),
    )
    result_payload = supersede_source_pr(
        source_pr_number=SOURCE_PR_NUMBER,
        all_child_pr_urls=[CHILD_PR_URL_ONE, CHILD_PR_URL_TWO],
        planned_slice_count=2,
        should_create_prs=True,
        should_supersede=True,
        repo=REPO_SLUG,
        repo_root=tmp_path,
    )
    assert result_payload[PAYLOAD_KEY_SKIPPED] is True
    assert result_payload[PAYLOAD_KEY_SKIP_REASON] == SUPERSEDE_SKIP_ALREADY_DONE
    assert result_payload[PAYLOAD_KEY_COMMENTED] is False
    assert result_payload[PAYLOAD_KEY_CLOSED] is False
    mutation_calls = [
        each
        for each in all_calls
        if each[:3]
        in (
            [GH_COMMAND, GH_PR, GH_COMMENT],
            [GH_COMMAND, GH_PR, GH_CLOSE],
        )
    ]
    assert mutation_calls == []


def test_supersede_source_pr_skips_without_closing_on_partial(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    all_calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _make_gh_runner(all_calls))
    result_payload = supersede_source_pr(
        source_pr_number=SOURCE_PR_NUMBER,
        all_child_pr_urls=[CHILD_PR_URL_ONE],
        planned_slice_count=2,
        should_create_prs=True,
        should_supersede=True,
        repo=REPO_SLUG,
        repo_root=tmp_path,
    )
    assert result_payload[PAYLOAD_KEY_SKIPPED] is True
    assert result_payload[PAYLOAD_KEY_SKIP_REASON] == SUPERSEDE_SKIP_PARTIAL
    assert all_calls == []
