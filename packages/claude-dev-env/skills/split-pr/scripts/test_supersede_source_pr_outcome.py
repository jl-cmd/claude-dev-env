"""Behavioral tests for the supersede comment body, close order, and temp files."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import supersede_source_pr  # noqa: E402
from split_pr_scripts_constants.config.execute_constants import (  # noqa: E402
    GH_BODY_FILE,
    GH_CLOSE,
    GH_COMMENT,
    GH_VIEW,
    PAYLOAD_KEY_CLOSED,
    PAYLOAD_KEY_COMMENTED,
    SUPERSEDE_UNKNOWN_PR_NUMBER,
)
from supersede_source_pr import (  # noqa: E402
    build_supersede_comment_body,
    supersede_source_pr as run_supersede,
)

SOURCE_PR_NUMBER = 99
FIRST_CHILD_URL = "https://github.com/owner/name/pull/10"
SECOND_CHILD_URL = "https://github.com/owner/name/pull/11"
UNPARSEABLE_CHILD_URL = "https://github.com/owner/name/pull/not-a-number"
OPEN_PR_VIEW_PAYLOAD = {"state": "OPEN", "comments": []}
CLOSURE_CLAIM_PHRASES = ("is closed", "was closed", "closed as superseded")


def install_recording_gh(
    monkeypatch: pytest.MonkeyPatch,
    view_stdout: str,
    close_return_code: int,
) -> tuple[list[list[str]], list[str]]:
    all_recorded_commands: list[list[str]] = []
    all_posted_bodies: list[str] = []

    def fake_run(
        all_command: list[str],
        **_keyword_arguments: object,
    ) -> subprocess.CompletedProcess[str]:
        all_recorded_commands.append(all_command)
        if GH_VIEW in all_command:
            return subprocess.CompletedProcess(all_command, 0, view_stdout, "")
        if GH_COMMENT in all_command:
            body_path = all_command[all_command.index(GH_BODY_FILE) + 1]
            all_posted_bodies.append(Path(body_path).read_text(encoding="utf-8"))
            return subprocess.CompletedProcess(all_command, 0, "", "")
        return subprocess.CompletedProcess(all_command, close_return_code, "", "denied")

    monkeypatch.setattr(supersede_source_pr.subprocess, "run", fake_run)
    return all_recorded_commands, all_posted_bodies


def test_an_unparseable_child_url_still_produces_a_comment_body() -> None:
    body = build_supersede_comment_body(
        all_child_pr_numbers=[10],
        all_child_pr_urls=[FIRST_CHILD_URL, UNPARSEABLE_CHILD_URL],
    )

    assert FIRST_CHILD_URL in body
    assert UNPARSEABLE_CHILD_URL in body
    assert SUPERSEDE_UNKNOWN_PR_NUMBER in body


def test_non_json_gh_view_output_raises_a_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_recording_gh(monkeypatch, "notice: gh update available\n{bad", 0)

    with pytest.raises(RuntimeError):
        run_supersede(
            source_pr_number=SOURCE_PR_NUMBER,
            all_child_pr_urls=[FIRST_CHILD_URL, SECOND_CHILD_URL],
            planned_slice_count=2,
            should_create_prs=True,
            should_supersede=True,
        )


def test_a_successful_supersede_reports_commented_and_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_recorded_commands, all_posted_bodies = install_recording_gh(
        monkeypatch,
        json.dumps(OPEN_PR_VIEW_PAYLOAD),
        0,
    )

    outcome = run_supersede(
        source_pr_number=SOURCE_PR_NUMBER,
        all_child_pr_urls=[FIRST_CHILD_URL, SECOND_CHILD_URL],
        planned_slice_count=2,
        should_create_prs=True,
        should_supersede=True,
    )

    assert outcome[PAYLOAD_KEY_COMMENTED] is True
    assert outcome[PAYLOAD_KEY_CLOSED] is True
    assert any(GH_CLOSE in each for each in all_recorded_commands)
    assert len(all_posted_bodies) == 1


def test_the_posted_comment_never_claims_the_pr_is_already_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, all_posted_bodies = install_recording_gh(
        monkeypatch,
        json.dumps(OPEN_PR_VIEW_PAYLOAD),
        1,
    )

    with pytest.raises(RuntimeError):
        run_supersede(
            source_pr_number=SOURCE_PR_NUMBER,
            all_child_pr_urls=[FIRST_CHILD_URL, SECOND_CHILD_URL],
            planned_slice_count=2,
            should_create_prs=True,
            should_supersede=True,
        )

    posted_body = all_posted_bodies[0].lower()
    for each_phrase in CLOSURE_CLAIM_PHRASES:
        assert each_phrase not in posted_body


def test_the_comment_body_file_is_removed_after_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    all_body_paths: list[str] = []

    def fake_run(
        all_command: list[str],
        **_keyword_arguments: object,
    ) -> subprocess.CompletedProcess[str]:
        if GH_VIEW in all_command:
            return subprocess.CompletedProcess(
                all_command, 0, json.dumps(OPEN_PR_VIEW_PAYLOAD), ""
            )
        if GH_COMMENT in all_command:
            all_body_paths.append(all_command[all_command.index(GH_BODY_FILE) + 1])
        return subprocess.CompletedProcess(all_command, 0, "", "")

    monkeypatch.setattr(supersede_source_pr.subprocess, "run", fake_run)

    run_supersede(
        source_pr_number=SOURCE_PR_NUMBER,
        all_child_pr_urls=[FIRST_CHILD_URL, SECOND_CHILD_URL],
        planned_slice_count=2,
        should_create_prs=True,
        should_supersede=True,
    )

    assert all_body_paths
    assert not Path(all_body_paths[0]).exists()
