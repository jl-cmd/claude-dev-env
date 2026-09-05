"""Configuration constants for GitHub post body extraction."""

ALL_GH_POST_SUBCOMMANDS: dict[str, frozenset[str]] = {
    "issue": frozenset({"comment", "create", "edit"}),
    "pr": frozenset({"comment", "create", "edit", "review"}),
}
ALL_MCP_BODY_PARAM_NAMES: tuple[str, ...] = ("body", "comment")
BODY_FILE_ENCODING = "utf-8"
BODY_FLAG_WITH_VALUE_STEP = 2
GH_COMMAND_NAME = "gh"
MINIMUM_POST_SUBCOMMAND_TOKEN_COUNT = 2
TOKEN_JOIN_SEPARATOR = " "
