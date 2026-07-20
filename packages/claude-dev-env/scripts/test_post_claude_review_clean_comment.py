"""Behavioral tests for the clean claude-review PR issue-comment poster."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import post_claude_review_clean_comment as poster  # noqa: E402
from dev_env_scripts_constants.code_review_constants import (  # noqa: E402
    CODE_REVIEW_PROMPT,
)
from dev_env_scripts_constants.post_claude_review_clean_comment_constants import (  # noqa: E402
    CLEAN_COMMENT_MARKER_TITLE,
    CLI_CWD_FLAG,
    CLI_DRY_RUN_FLAG,
    CLI_HEAD_SHA_FLAG,
    CLI_MODE_FLAG,
    CLI_SERVED_COMMAND_FLAG,
    EXIT_SUCCESS,
    GH_API_TOKEN,
    GH_BINARY_NAME,
    GH_BODY_FILE_FLAG,
    GH_COMMENT_SUBCOMMAND,
    GH_PR_TOKEN,
    GH_REPO_TOKEN,
    GH_VIEW_SUBCOMMAND,
    MESSAGE_ALREADY_POSTED,
    MESSAGE_DRY_RUN,
    MESSAGE_POST_FAILED,
    MESSAGE_POSTED,
    MESSAGE_PR_RESOLVE_FAILED,
    RESULT_KEY_BODY,
    RESULT_KEY_DRY_RUN,
    RESULT_KEY_HEAD_SHA,
    RESULT_KEY_MESSAGE,
    RESULT_KEY_POSTED,
    RESULT_KEY_SKIPPED,
)

FIXTURE_HEAD_SHA = "abcdef0123456789abcdef0123456789abcdef01"
FIXTURE_PR_NUMBER = 264
FIXTURE_OWNER = "owner"
FIXTURE_REPO = "repo"
FIXTURE_PR_URL = "https://github.com/owner/repo/pull/264"
FIXTURE_MODE_CHAIN = "chain"
FIXTURE_SERVED_COMMAND = "claude.exe"
FIXTURE_WORKDIR_NAME = "worktree"


def _pr_view_stdout() -> str:
    return json.dumps(
        {
            "number": FIXTURE_PR_NUMBER,
            "url": FIXTURE_PR_URL,
            "headRefOid": FIXTURE_HEAD_SHA,
        }
    )


def _repo_view_stdout() -> str:
    return json.dumps(
        {"nameWithOwner": f"{FIXTURE_OWNER}/{FIXTURE_REPO}"}
    )


def _make_gh_runner(
    *,
    all_comment_bodies: list[str] | None = None,
    is_pr_view_ok: bool = True,
    is_repo_view_ok: bool = True,
    is_list_ok: bool = True,
    is_comment_ok: bool = True,
    recorded_calls: list[list[str]] | None = None,
) -> Callable[..., subprocess.CompletedProcess[str]]:
    comment_bodies = (
        [] if all_comment_bodies is None else list(all_comment_bodies)
    )
    calls = recorded_calls if recorded_calls is not None else []

    def fake_run(
        all_arguments: list[str],
        **_keyword_arguments: object,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(all_arguments))
        if not all_arguments:
            return subprocess.CompletedProcess(all_arguments, 1, "", "empty")
        if all_arguments[0] != GH_BINARY_NAME:
            return subprocess.CompletedProcess(all_arguments, 1, "", "not gh")
        if GH_PR_TOKEN in all_arguments and GH_VIEW_SUBCOMMAND in all_arguments:
            if not is_pr_view_ok:
                return subprocess.CompletedProcess(
                    all_arguments, 1, "", "pr view failed"
                )
            return subprocess.CompletedProcess(
                all_arguments, 0, _pr_view_stdout(), ""
            )
        if (
            GH_REPO_TOKEN in all_arguments
            and GH_VIEW_SUBCOMMAND in all_arguments
        ):
            if not is_repo_view_ok:
                return subprocess.CompletedProcess(
                    all_arguments, 1, "", "repo view failed"
                )
            return subprocess.CompletedProcess(
                all_arguments, 0, _repo_view_stdout(), ""
            )
        if GH_API_TOKEN in all_arguments:
            if not is_list_ok:
                return subprocess.CompletedProcess(
                    all_arguments, 1, "", "list failed"
                )
            all_entries = [{"body": each_body} for each_body in comment_bodies]
            return subprocess.CompletedProcess(
                all_arguments, 0, json.dumps(all_entries), ""
            )
        if GH_COMMENT_SUBCOMMAND in all_arguments:
            if not is_comment_ok:
                return subprocess.CompletedProcess(
                    all_arguments, 1, "", "comment failed"
                )
            return subprocess.CompletedProcess(all_arguments, 0, "", "")
        return subprocess.CompletedProcess(all_arguments, 1, "", "unknown")

    return fake_run


def test_build_head_sha_line_embeds_sha() -> None:
    head_line = poster.build_head_sha_line(FIXTURE_HEAD_SHA)
    assert head_line == f"head_sha: {FIXTURE_HEAD_SHA}"


def test_build_comment_body_contains_marker_sha_and_prompt() -> None:
    comment_body = poster.build_comment_body(
        head_sha=FIXTURE_HEAD_SHA,
        mode=FIXTURE_MODE_CHAIN,
        served_command=FIXTURE_SERVED_COMMAND,
    )
    assert comment_body.startswith(CLEAN_COMMENT_MARKER_TITLE)
    assert f"head_sha: {FIXTURE_HEAD_SHA}" in comment_body
    assert CODE_REVIEW_PROMPT in comment_body
    assert f"mode: {FIXTURE_MODE_CHAIN}" in comment_body
    assert f"served_command: {FIXTURE_SERVED_COMMAND}" in comment_body


def test_has_existing_clean_comment_matches_same_head() -> None:
    matching_body = poster.build_comment_body(
        head_sha=FIXTURE_HEAD_SHA,
        mode=FIXTURE_MODE_CHAIN,
        served_command=FIXTURE_SERVED_COMMAND,
    )
    other_body = poster.build_comment_body(
        head_sha="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        mode=FIXTURE_MODE_CHAIN,
        served_command=FIXTURE_SERVED_COMMAND,
    )
    assert (
        poster.has_existing_clean_comment(
            [other_body, matching_body],
            head_sha=FIXTURE_HEAD_SHA,
        )
        is True
    )
    assert (
        poster.has_existing_clean_comment(
            [other_body],
            head_sha=FIXTURE_HEAD_SHA,
        )
        is False
    )


def test_post_skips_when_existing_comment_same_sha(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_body = poster.build_comment_body(
        head_sha=FIXTURE_HEAD_SHA,
        mode=FIXTURE_MODE_CHAIN,
        served_command=FIXTURE_SERVED_COMMAND,
    )
    recorded_calls: list[list[str]] = []
    monkeypatch.setattr(
        subprocess,
        "run",
        _make_gh_runner(
            all_comment_bodies=[existing_body],
            recorded_calls=recorded_calls,
        ),
    )
    worktree = tmp_path / FIXTURE_WORKDIR_NAME
    worktree.mkdir()
    outcome = poster.post_clean_review_comment(
        working_directory=worktree,
        head_sha=FIXTURE_HEAD_SHA,
        mode=FIXTURE_MODE_CHAIN,
        served_command=FIXTURE_SERVED_COMMAND,
        is_dry_run=False,
    )
    assert outcome.is_skipped is True
    assert outcome.is_posted is False
    assert outcome.message == MESSAGE_ALREADY_POSTED
    assert not any(
        GH_COMMENT_SUBCOMMAND in each_call for each_call in recorded_calls
    )


def test_post_succeeds_and_uses_body_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_calls: list[list[str]] = []
    monkeypatch.setattr(
        subprocess,
        "run",
        _make_gh_runner(recorded_calls=recorded_calls),
    )
    worktree = tmp_path / FIXTURE_WORKDIR_NAME
    worktree.mkdir()
    outcome = poster.post_clean_review_comment(
        working_directory=worktree,
        head_sha=FIXTURE_HEAD_SHA,
        mode=FIXTURE_MODE_CHAIN,
        served_command=FIXTURE_SERVED_COMMAND,
        is_dry_run=False,
    )
    assert outcome.is_posted is True
    assert outcome.is_skipped is False
    assert outcome.message == MESSAGE_POSTED
    assert CLEAN_COMMENT_MARKER_TITLE in outcome.body
    all_comment_calls = [
        each_call
        for each_call in recorded_calls
        if GH_COMMENT_SUBCOMMAND in each_call
    ]
    assert len(all_comment_calls) == 1
    comment_call = all_comment_calls[0]
    assert GH_BODY_FILE_FLAG in comment_call
    assert "--body" not in comment_call


def test_post_soft_fails_when_gh_comment_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        _make_gh_runner(is_comment_ok=False),
    )
    worktree = tmp_path / FIXTURE_WORKDIR_NAME
    worktree.mkdir()
    outcome = poster.post_clean_review_comment(
        working_directory=worktree,
        head_sha=FIXTURE_HEAD_SHA,
        mode=FIXTURE_MODE_CHAIN,
        served_command=FIXTURE_SERVED_COMMAND,
        is_dry_run=False,
    )
    assert outcome.is_posted is False
    assert outcome.is_skipped is False
    assert outcome.message == MESSAGE_POST_FAILED


def test_post_soft_fails_when_pr_unresolved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        _make_gh_runner(is_pr_view_ok=False),
    )
    worktree = tmp_path / FIXTURE_WORKDIR_NAME
    worktree.mkdir()
    outcome = poster.post_clean_review_comment(
        working_directory=worktree,
        head_sha=FIXTURE_HEAD_SHA,
        mode=None,
        served_command=None,
        is_dry_run=False,
    )
    assert outcome.is_posted is False
    assert outcome.message == MESSAGE_PR_RESOLVE_FAILED


def test_dry_run_prints_body_without_posting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_calls: list[list[str]] = []
    monkeypatch.setattr(
        subprocess,
        "run",
        _make_gh_runner(recorded_calls=recorded_calls),
    )
    worktree = tmp_path / FIXTURE_WORKDIR_NAME
    worktree.mkdir()
    outcome = poster.post_clean_review_comment(
        working_directory=worktree,
        head_sha=FIXTURE_HEAD_SHA,
        mode=FIXTURE_MODE_CHAIN,
        served_command=FIXTURE_SERVED_COMMAND,
        is_dry_run=True,
    )
    assert outcome.is_dry_run is True
    assert outcome.is_posted is False
    assert outcome.message == MESSAGE_DRY_RUN
    assert CLEAN_COMMENT_MARKER_TITLE in outcome.body
    assert f"head_sha: {FIXTURE_HEAD_SHA}" in outcome.body
    assert recorded_calls == []


def test_main_always_exits_success_on_soft_fail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        _make_gh_runner(is_pr_view_ok=False),
    )
    worktree = tmp_path / FIXTURE_WORKDIR_NAME
    worktree.mkdir()
    exit_code = poster.main(
        [
            CLI_CWD_FLAG,
            str(worktree),
            CLI_HEAD_SHA_FLAG,
            FIXTURE_HEAD_SHA,
            CLI_MODE_FLAG,
            FIXTURE_MODE_CHAIN,
            CLI_SERVED_COMMAND_FLAG,
            FIXTURE_SERVED_COMMAND,
        ]
    )
    assert exit_code == EXIT_SUCCESS
    printed_payload = json.loads(capsys.readouterr().out)
    assert printed_payload[RESULT_KEY_POSTED] is False
    assert printed_payload[RESULT_KEY_HEAD_SHA] == FIXTURE_HEAD_SHA
    assert printed_payload[RESULT_KEY_MESSAGE] == MESSAGE_PR_RESOLVE_FAILED


def test_main_dry_run_includes_body_in_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        _make_gh_runner(),
    )
    worktree = tmp_path / FIXTURE_WORKDIR_NAME
    worktree.mkdir()
    exit_code = poster.main(
        [
            CLI_CWD_FLAG,
            str(worktree),
            CLI_HEAD_SHA_FLAG,
            FIXTURE_HEAD_SHA,
            CLI_DRY_RUN_FLAG,
        ]
    )
    assert exit_code == EXIT_SUCCESS
    printed_payload = json.loads(capsys.readouterr().out)
    assert printed_payload[RESULT_KEY_DRY_RUN] is True
    assert printed_payload[RESULT_KEY_SKIPPED] is False
    assert CLEAN_COMMENT_MARKER_TITLE in printed_payload[RESULT_KEY_BODY]
