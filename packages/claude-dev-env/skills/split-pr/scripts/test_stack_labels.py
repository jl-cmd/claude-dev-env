"""Behavioral tests for stack discovery labels on split PRs."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from split_pr_scripts_constants.config.execute_constants import (  # noqa: E402
    GH_ADD_LABEL,
    GH_COMMAND,
    GH_EDIT,
    GH_LABEL,
    GH_LABEL_CREATE,
    GH_PR,
    LABEL_SPLIT_PR,
    LABEL_STACK_PREFIX,
    PAYLOAD_KEY_LABELED,
    PAYLOAD_KEY_LABELED_PR_NUMBERS,
    PAYLOAD_KEY_LABELS,
    PAYLOAD_KEY_SKIPPED,
    PAYLOAD_KEY_SKIP_REASON,
    STACK_LABELS_SKIP_CREATE_PRS_OFF,
    STACK_LABELS_SKIP_NO_CHILD_URLS,
    STACK_LABELS_SKIP_PARTIAL,
)
from stack_labels import (  # noqa: E402
    apply_stack_labels,
    build_stack_label_names,
    resolve_stack_labels_skip_reason,
)

CHILD_PR_URL_ONE = "https://github.com/example/repo/pull/10"
CHILD_PR_URL_TWO = "https://github.com/example/repo/pull/11"
SOURCE_PR_NUMBER = 99
REPO_SLUG = "example/repo"


def test_build_stack_label_names_includes_global_and_stack() -> None:
    all_names = build_stack_label_names(SOURCE_PR_NUMBER)
    assert all_names == [LABEL_SPLIT_PR, f"{LABEL_STACK_PREFIX}{SOURCE_PR_NUMBER}"]


def test_resolve_stack_labels_skip_reason_gates() -> None:
    assert (
        resolve_stack_labels_skip_reason(
            planned_slice_count=2,
            all_child_pr_urls=[CHILD_PR_URL_ONE, CHILD_PR_URL_TWO],
            should_create_prs=False,
        )
        == STACK_LABELS_SKIP_CREATE_PRS_OFF
    )
    assert (
        resolve_stack_labels_skip_reason(
            planned_slice_count=2,
            all_child_pr_urls=[],
            should_create_prs=True,
        )
        == STACK_LABELS_SKIP_NO_CHILD_URLS
    )
    assert (
        resolve_stack_labels_skip_reason(
            planned_slice_count=2,
            all_child_pr_urls=[CHILD_PR_URL_ONE],
            should_create_prs=True,
        )
        == STACK_LABELS_SKIP_PARTIAL
    )
    assert (
        resolve_stack_labels_skip_reason(
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


def test_apply_stack_labels_ensures_and_adds_on_source_and_children(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    all_calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _make_gh_runner(all_calls))
    result_payload = apply_stack_labels(
        source_pr_number=SOURCE_PR_NUMBER,
        all_child_pr_urls=[CHILD_PR_URL_ONE, CHILD_PR_URL_TWO],
        planned_slice_count=2,
        should_create_prs=True,
        repo=REPO_SLUG,
        repo_root=tmp_path,
    )
    assert result_payload[PAYLOAD_KEY_LABELED] is True
    assert result_payload[PAYLOAD_KEY_SKIPPED] is False
    assert result_payload[PAYLOAD_KEY_LABELS] == [
        LABEL_SPLIT_PR,
        f"{LABEL_STACK_PREFIX}{SOURCE_PR_NUMBER}",
    ]
    assert result_payload[PAYLOAD_KEY_LABELED_PR_NUMBERS] == [99, 10, 11]

    label_creates = [
        each for each in all_calls if each[:3] == [GH_COMMAND, GH_LABEL, GH_LABEL_CREATE]
    ]
    assert len(label_creates) == 2
    assert LABEL_SPLIT_PR in label_creates[0]
    assert f"{LABEL_STACK_PREFIX}{SOURCE_PR_NUMBER}" in label_creates[1]

    edit_calls = [
        each for each in all_calls if each[:3] == [GH_COMMAND, GH_PR, GH_EDIT]
    ]
    assert len(edit_calls) == 3
    for each_call in edit_calls:
        assert GH_ADD_LABEL in each_call
        assert LABEL_SPLIT_PR in each_call
        assert f"{LABEL_STACK_PREFIX}{SOURCE_PR_NUMBER}" in each_call


def test_apply_stack_labels_skips_partial_without_gh(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    all_calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _make_gh_runner(all_calls))
    result_payload = apply_stack_labels(
        source_pr_number=SOURCE_PR_NUMBER,
        all_child_pr_urls=[CHILD_PR_URL_ONE],
        planned_slice_count=2,
        should_create_prs=True,
        repo=REPO_SLUG,
        repo_root=tmp_path,
    )
    assert result_payload[PAYLOAD_KEY_SKIPPED] is True
    assert result_payload[PAYLOAD_KEY_SKIP_REASON] == STACK_LABELS_SKIP_PARTIAL
    assert result_payload[PAYLOAD_KEY_LABELED] is False
    assert all_calls == []
