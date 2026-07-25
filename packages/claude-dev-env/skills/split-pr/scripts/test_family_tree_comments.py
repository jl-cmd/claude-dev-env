"""Behavioral tests for family-tree comments on every stack PR."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from family_tree_comments import (  # noqa: E402
    build_family_tree_comment_body,
    post_family_tree_comments,
    resolve_family_tree_skip_reason,
)
from split_pr_scripts_constants.config.execute_constants import (  # noqa: E402
    FAMILY_TREE_HEADING,
    FAMILY_TREE_SKIP_CREATE_PRS_OFF,
    FAMILY_TREE_SKIP_NO_CHILD_URLS,
    FAMILY_TREE_SKIP_PARTIAL,
    GH_BODY_FILE,
    GH_COMMAND,
    GH_COMMENT,
    GH_PR,
    PAYLOAD_KEY_COMMENTED,
    PAYLOAD_KEY_COMMENTED_PR_NUMBERS,
    PAYLOAD_KEY_SKIPPED,
    PAYLOAD_KEY_SKIP_REASON,
)

CHILD_PR_URL_ONE = "https://github.com/example/repo/pull/10"
CHILD_PR_URL_TWO = "https://github.com/example/repo/pull/11"
SOURCE_PR_NUMBER = 99
REPO_SLUG = "example/repo"


def test_build_family_tree_comment_body_marks_this_pr() -> None:
    body = build_family_tree_comment_body(
        source_pr_number=SOURCE_PR_NUMBER,
        all_child_pr_numbers=[10, 11],
        all_child_pr_urls=[CHILD_PR_URL_ONE, CHILD_PR_URL_TWO],
        this_pr_number=11,
    )
    assert FAMILY_TREE_HEADING in body
    assert f"**Source:** #{SOURCE_PR_NUMBER}" in body
    assert "#10 → #11" in body
    assert "← **this PR**" in body
    assert "position 2 of 2" in body
    assert CHILD_PR_URL_ONE in body
    assert CHILD_PR_URL_TWO in body


def test_resolve_family_tree_skip_reason_gates() -> None:
    assert (
        resolve_family_tree_skip_reason(
            planned_slice_count=2,
            all_child_pr_urls=[CHILD_PR_URL_ONE, CHILD_PR_URL_TWO],
            should_create_prs=False,
        )
        == FAMILY_TREE_SKIP_CREATE_PRS_OFF
    )
    assert (
        resolve_family_tree_skip_reason(
            planned_slice_count=2,
            all_child_pr_urls=[],
            should_create_prs=True,
        )
        == FAMILY_TREE_SKIP_NO_CHILD_URLS
    )
    assert (
        resolve_family_tree_skip_reason(
            planned_slice_count=2,
            all_child_pr_urls=[CHILD_PR_URL_ONE],
            should_create_prs=True,
        )
        == FAMILY_TREE_SKIP_PARTIAL
    )
    assert (
        resolve_family_tree_skip_reason(
            planned_slice_count=2,
            all_child_pr_urls=[CHILD_PR_URL_ONE, CHILD_PR_URL_TWO],
            should_create_prs=True,
        )
        is None
    )


def _make_gh_runner(
    all_calls: list[list[str]],
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def fake_run(
        all_command: list[str],
        cwd: str | None = None,
        capture_output: bool = False,
        text: bool = False,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, capture_output, text, check
        all_calls.append(list(all_command))
        return subprocess.CompletedProcess(
            args=all_command,
            returncode=0,
            stdout="",
            stderr="",
        )

    return fake_run


def test_post_family_tree_comments_posts_body_file_on_each_child(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    all_calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _make_gh_runner(all_calls))
    result_payload = post_family_tree_comments(
        source_pr_number=SOURCE_PR_NUMBER,
        all_child_pr_urls=[CHILD_PR_URL_ONE, CHILD_PR_URL_TWO],
        planned_slice_count=2,
        should_create_prs=True,
        repo=REPO_SLUG,
        repo_root=tmp_path,
    )
    assert result_payload[PAYLOAD_KEY_COMMENTED] is True
    assert result_payload[PAYLOAD_KEY_COMMENTED_PR_NUMBERS] == [10, 11]
    assert result_payload[PAYLOAD_KEY_SKIPPED] is False

    comment_calls = [
        each for each in all_calls if each[:3] == [GH_COMMAND, GH_PR, GH_COMMENT]
    ]
    assert len(comment_calls) == 2
    assert "10" in comment_calls[0]
    assert "11" in comment_calls[1]
    for each_call in comment_calls:
        assert GH_BODY_FILE in each_call
        body_path = Path(each_call[each_call.index(GH_BODY_FILE) + 1])
        assert body_path.is_file()
        body_text = body_path.read_text(encoding="utf-8")
        assert FAMILY_TREE_HEADING in body_text
        assert "#10 → #11" in body_text


def test_post_family_tree_comments_skips_partial_without_gh(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    all_calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _make_gh_runner(all_calls))
    result_payload = post_family_tree_comments(
        source_pr_number=SOURCE_PR_NUMBER,
        all_child_pr_urls=[CHILD_PR_URL_ONE],
        planned_slice_count=2,
        should_create_prs=True,
        repo=REPO_SLUG,
        repo_root=tmp_path,
    )
    assert result_payload[PAYLOAD_KEY_SKIPPED] is True
    assert result_payload[PAYLOAD_KEY_SKIP_REASON] == FAMILY_TREE_SKIP_PARTIAL
    assert all_calls == []
