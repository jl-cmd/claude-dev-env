"""Tests for GitHub post body extraction constants."""

from hooks_constants import gh_post_body_texts_constants as constants


def test_post_actions_cover_pull_requests_and_issues() -> None:
    assert constants.ALL_GH_POST_SUBCOMMANDS == {
        "issue": frozenset({"comment", "create", "edit"}),
        "pr": frozenset({"comment", "create", "edit", "review"}),
    }
    assert constants.ALL_MCP_BODY_PARAM_NAMES == ("body", "comment")


def test_parser_constants_are_stable() -> None:
    assert constants.BODY_FILE_ENCODING == "utf-8"
    assert constants.BODY_FLAG_WITH_VALUE_STEP == 2
    assert constants.GH_COMMAND_NAME == "gh"
    assert constants.MINIMUM_POST_SUBCOMMAND_TOKEN_COUNT == 2
    assert constants.TOKEN_JOIN_SEPARATOR == " "
