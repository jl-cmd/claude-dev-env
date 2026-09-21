"""Tests for the pull-request URL query the commit handoff runs."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import pull_request_handoff
from git_hooks_constants import (
    ALL_GH_PR_VIEW_ARGUMENTS,
    GH_EXECUTABLE_NAME,
    GH_PR_VIEW_TIMEOUT_SECONDS,
)


def test_should_query_the_url_through_the_named_executable_and_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_calls: list[tuple[list[str], object]] = []

    def record_call(
        command: list[str], **keyword_arguments: object
    ) -> subprocess.CompletedProcess[str]:
        all_calls.append((command, keyword_arguments["timeout"]))
        return subprocess.CompletedProcess(command, 0, "https://example/pull/1\n", "")

    monkeypatch.setattr(pull_request_handoff.subprocess, "run", record_call)

    url = pull_request_handoff.get_pull_request_url(Path("/repo"))

    assert url == "https://example/pull/1"
    assert all_calls == [
        ([GH_EXECUTABLE_NAME, *ALL_GH_PR_VIEW_ARGUMENTS], GH_PR_VIEW_TIMEOUT_SECONDS)
    ]


def test_should_report_no_url_when_the_query_exits_non_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_call(
        command: list[str], **keyword_arguments: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, "", "no pull request")

    monkeypatch.setattr(pull_request_handoff.subprocess, "run", failing_call)

    assert pull_request_handoff.get_pull_request_url(Path("/repo")) is None
