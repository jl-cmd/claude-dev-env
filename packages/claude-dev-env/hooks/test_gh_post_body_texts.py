"""Tests for durable GitHub post body extraction."""

from pathlib import Path

import pytest

from gh_post_body_texts import (
    extract_gh_post_body_texts_for_privacy_gate,
    extract_mcp_body_texts,
)


@pytest.mark.parametrize(
    ("command", "expected_text"),
    [
        ('gh pr create --body "pull request text"', "pull request text"),
        ('gh pr comment 12 --body="comment text"', "comment text"),
        ('gh issue edit 7 -b "issue text"', "issue text"),
        ('GH_HOST=github.example gh pr review 8 --body "review text"', "review text"),
    ],
)
def test_inline_post_bodies_are_extracted(command: str, expected_text: str) -> None:
    all_body_texts, deny_reason = extract_gh_post_body_texts_for_privacy_gate(command)
    assert all_body_texts == [expected_text]
    assert deny_reason is None


def test_relative_body_file_uses_supplied_working_directory(tmp_path: Path) -> None:
    body_file = tmp_path / "body.md"
    body_file.write_text("body file text", encoding="utf-8")
    all_body_texts, deny_reason = extract_gh_post_body_texts_for_privacy_gate(
        "gh pr comment 12 --body-file body.md",
        str(tmp_path),
    )
    assert all_body_texts == ["body file text"]
    assert deny_reason is None


@pytest.mark.parametrize("body_file_text", ["missing.md", "$BODY_FILE", "-"])
def test_unreadable_body_file_fails_closed(body_file_text: str) -> None:
    all_body_texts, deny_reason = extract_gh_post_body_texts_for_privacy_gate(
        f"gh pr comment 12 --body-file {body_file_text}"
    )
    assert all_body_texts == []
    assert deny_reason is not None
    assert "could not be read" in deny_reason


def test_invalid_utf8_body_file_fails_closed(tmp_path: Path) -> None:
    body_file = tmp_path / "body.md"
    body_file.write_bytes(b"\xff")
    all_body_texts, deny_reason = extract_gh_post_body_texts_for_privacy_gate(
        f'gh issue create --body-file "{body_file}"'
    )
    assert all_body_texts == []
    assert deny_reason is not None


@pytest.mark.parametrize(
    "command",
    [
        "gh pr view 12",
        'echo "gh pr comment 12 --body text"',
        "git status",
        "",
    ],
)
def test_non_post_commands_have_no_body(command: str) -> None:
    assert extract_gh_post_body_texts_for_privacy_gate(command) == ([], None)


def test_mcp_body_and_comment_values_are_extracted() -> None:
    assert extract_mcp_body_texts(
        {"body": "body text", "comment": "comment text", "title": "ignored"}
    ) == ["body text", "comment text"]


def test_mcp_non_string_and_empty_values_are_ignored() -> None:
    assert extract_mcp_body_texts({"body": "", "comment": 7}) == []
