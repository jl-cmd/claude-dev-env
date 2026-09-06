"""Tests for durable GitHub post linter constants."""

from durable_post_lint_config.config.constants import (
    ALL_CONVENTIONAL_TITLE_TYPES,
    ALL_POST_ACTIONS,
    ALL_RELEASE_BODY_MARKERS,
    CONVENTIONAL_TITLE_PATTERN,
    RELEASE_BRANCH_PREFIX,
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


def should_carry_both_markers_release_automation_writes() -> None:
    assert ALL_RELEASE_BODY_MARKERS == (
        ":robot: I have created a release",
        "This PR was generated with [Release Please]",
    )


def should_name_the_branch_prefix_release_automation_pushes() -> None:
    assert RELEASE_BRANCH_PREFIX == "release-please--branches--"
