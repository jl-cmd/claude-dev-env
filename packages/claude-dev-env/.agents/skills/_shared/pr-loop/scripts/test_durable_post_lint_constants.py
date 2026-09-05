"""Tests for durable GitHub post linter constants."""

from skills_pr_loop_constants.durable_post_lint_constants import (
    ALL_CONVENTIONAL_TITLE_TYPES,
    ALL_POST_ACTIONS,
    CONVENTIONAL_TITLE_PATTERN,
)


def test_action_inventory_covers_pull_request_issue_and_tool_posts() -> None:
    assert ALL_POST_ACTIONS == {
        "github-mcp-post",
        "issue-comment",
        "issue-create",
        "issue-edit",
        "pr-comment",
        "pr-create",
        "pr-edit",
        "pr-review",
    }


def test_title_pattern_uses_every_configured_type() -> None:
    for each_title_type in ALL_CONVENTIONAL_TITLE_TYPES:
        assert CONVENTIONAL_TITLE_PATTERN.fullmatch(f"{each_title_type}: one change")
