"""Tests for action-aware durable GitHub post linting."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY))

import durable_post_lint

SCRIPT_PATH = _SCRIPTS_DIRECTORY / "durable_post_lint.py"
VALID_PR_BODY = """## Summary

Summary text.

## Description

Description text.

## Why

Why text.

## How

How text.

## Verification

Verification text.
"""


@pytest.mark.parametrize(
    ("action", "title", "body_text"),
    [
        ("pr-create", "feat: add durable post linting", VALID_PR_BODY),
        ("pr-edit", "fix(cli): validate post input", None),
        ("pr-comment", None, "Comment body."),
        ("pr-review", None, "Review body."),
        ("issue-create", None, "Issue body."),
        ("issue-edit", None, "Updated issue body."),
        ("issue-comment", None, "Issue comment."),
        ("github-mcp-post", None, "MCP body."),
    ],
)
def test_all_actions_accept_valid_inputs(
    action: str, title: str | None, body_text: str | None
) -> None:
    all_findings = durable_post_lint.lint_durable_post(
        action=action,
        title=title,
        body_text=body_text,
    )
    assert all_findings == ()


def test_unknown_action_raises_usage_error() -> None:
    with pytest.raises(durable_post_lint.DurablePostUsageError):
        durable_post_lint.lint_durable_post(
            action="release-create",
            title=None,
            body_text="Release body.",
        )


@pytest.mark.parametrize(
    ("title", "body_text"),
    [
        (None, VALID_PR_BODY),
        ("feat: add durable post linting", None),
    ],
)
def test_pr_create_requires_title_and_body(
    title: str | None, body_text: str | None
) -> None:
    with pytest.raises(durable_post_lint.DurablePostUsageError):
        durable_post_lint.lint_durable_post(
            action="pr-create",
            title=title,
            body_text=body_text,
        )


def test_pr_edit_requires_one_edit_field() -> None:
    with pytest.raises(durable_post_lint.DurablePostUsageError):
        durable_post_lint.lint_durable_post(
            action="pr-edit",
            title=None,
            body_text=None,
        )


@pytest.mark.parametrize(
    "action",
    [
        "pr-comment",
        "pr-review",
        "issue-create",
        "issue-edit",
        "issue-comment",
        "github-mcp-post",
    ],
)
def test_body_actions_require_body(action: str) -> None:
    with pytest.raises(durable_post_lint.DurablePostUsageError):
        durable_post_lint.lint_durable_post(
            action=action,
            title=None,
            body_text=None,
        )


@pytest.mark.parametrize(
    "title",
    [
        "feat: add durable post linting",
        "fix(cli): validate body files",
        "refactor!: replace post validation",
        "docs(skill)!: explain durable posts",
    ],
)
def test_pr_titles_accept_repository_conventional_forms(title: str) -> None:
    all_findings = durable_post_lint.lint_durable_post(
        action="pr-edit",
        title=title,
        body_text=None,
    )
    assert all_findings == ()


@pytest.mark.parametrize(
    "title",
    [
        "Add durable post linting",
        "feature: add durable post linting",
        "fix(): add durable post linting",
        "fix:add durable post linting",
        "fix: ",
    ],
)
def test_pr_titles_reject_nonconventional_forms(title: str) -> None:
    all_findings = durable_post_lint.lint_durable_post(
        action="pr-edit",
        title=title,
        body_text=None,
    )
    assert [each_finding.code for each_finding in all_findings] == ["invalid-pr-title"]


@pytest.mark.parametrize(
    "missing_heading",
    ["Summary", "Description", "Why", "How", "Verification"],
)
def test_pr_body_reports_each_missing_heading(missing_heading: str) -> None:
    body_text = VALID_PR_BODY.replace(f"## {missing_heading}\n", "")
    all_findings = durable_post_lint.lint_durable_post(
        action="pr-create",
        title="feat: add durable post linting",
        body_text=body_text,
    )
    assert [each_finding.message for each_finding in all_findings] == [
        f"body is missing required heading: {missing_heading}"
    ]


def test_non_pr_body_needs_no_pr_headings() -> None:
    all_findings = durable_post_lint.lint_durable_post(
        action="issue-comment",
        title=None,
        body_text="A concise issue comment.",
    )
    assert all_findings == ()


@pytest.mark.parametrize(
    ("body_text", "expected_marker"),
    [
        (
            r"See C:\Users\example\.claude-profile-a\jobs\job-1\artifact.png",
            ".claude-profile-a/jobs/",
        ),
        (
            r"Edited C:\Users\example\.claude\worktrees\feature\file.py",
            ".claude/worktrees/",
        ),
        (
            r"Saved in C:\Users\example\AppData\Local\Temp\report.txt",
            "appdata/local/temp",
        ),
        ("Saved in /tmp/report.txt", "/tmp/"),
        (r"Saved in %TEMP%\report.txt", "%temp%"),
        (r"Saved in $env:TEMP\report.txt", "$env:temp"),
        ("Saved in $CLAUDE_JOB_DIR/report.txt", "$claude_job_dir"),
    ],
)
def test_volatile_path_markers_match_hook_behavior(
    body_text: str, expected_marker: str
) -> None:
    assert durable_post_lint.find_volatile_path_marker(body_text) == expected_marker


@pytest.mark.parametrize(
    "body_text",
    [
        "the `.claude/worktrees/` prefix is a manifest key",
        ".claude/worktrees/ entries are skipped by the manifest",
        "(.claude-profile-a/jobs/) is a directory name",
        "worktrees live under `.claude/worktrees/<name>`",
        "the constant is `.claude/worktrees/`. Next.",
    ],
)
def test_anchored_marker_near_misses_remain_allowed(body_text: str) -> None:
    assert durable_post_lint.find_volatile_path_marker(body_text) is None


def test_volatile_body_returns_content_finding() -> None:
    all_findings = durable_post_lint.lint_durable_post(
        action="issue-comment",
        title=None,
        body_text="Saved in /tmp/report.txt",
    )
    assert [each_finding.code for each_finding in all_findings] == [
        "volatile-local-path"
    ]


def test_read_body_file_accepts_utf8(tmp_path: Path) -> None:
    body_file = tmp_path / "body.md"
    body_file.write_text("Café", encoding="utf-8")
    assert durable_post_lint.read_body_file(body_file) == "Café"


def test_read_body_file_rejects_missing_file(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing.md"
    with pytest.raises(durable_post_lint.DurablePostInputError):
        durable_post_lint.read_body_file(missing_file)


def test_read_body_file_rejects_invalid_utf8(tmp_path: Path) -> None:
    body_file = tmp_path / "body.md"
    body_file.write_bytes(b"\xff\xfe")
    with pytest.raises(durable_post_lint.DurablePostInputError):
        durable_post_lint.read_body_file(body_file)


def test_cli_returns_clean_exit_for_valid_pr_create(tmp_path: Path) -> None:
    body_file = tmp_path / "body.md"
    body_file.write_text(VALID_PR_BODY, encoding="utf-8")
    completed_process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--action",
            "pr-create",
            "--title",
            "feat: add durable post linting",
            "--body-file",
            str(body_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed_process.returncode == 0
    assert completed_process.stdout == ""
    assert completed_process.stderr == ""


def test_cli_returns_content_exit_without_echoing_body(tmp_path: Path) -> None:
    body_text = "private body words saved in /tmp/report.txt"
    body_file = tmp_path / "body.md"
    body_file.write_text(body_text, encoding="utf-8")
    completed_process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--action",
            "issue-comment",
            "--body-file",
            str(body_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed_process.returncode == 1
    assert "volatile local artifact path" in completed_process.stderr
    assert body_text not in completed_process.stderr


def test_cli_returns_usage_exit_for_missing_body_file(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing.md"
    completed_process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--action",
            "issue-comment",
            "--body-file",
            str(missing_file),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed_process.returncode == 2
    assert "body file is not readable" in completed_process.stderr


def test_cli_has_no_inline_body_flag() -> None:
    completed_process = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--action",
            "issue-comment",
            "--body",
            "Inline body.",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed_process.returncode == 2
    assert "unrecognized arguments" in completed_process.stderr
