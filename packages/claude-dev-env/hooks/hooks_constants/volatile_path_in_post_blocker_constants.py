"""Configuration constants for the volatile_path_in_post_blocker PreToolUse hook."""

BASH_TOOL_NAME: str = "Bash"

MCP_GITHUB_TOOL_PREFIX: str = "mcp__plugin_github_github__"

ALL_MCP_BODY_PARAM_NAMES: tuple[str, ...] = ("body", "comment")

GH_COMMAND_NAME: str = "gh"

MINIMUM_POST_SUBCOMMAND_TOKEN_COUNT: int = 2

TOKEN_JOIN_SEPARATOR: str = " "

BODY_FILE_ENCODING: str = "utf-8"

ALL_GH_POST_SUBCOMMANDS: dict[str, frozenset[str]] = {
    "pr": frozenset({"create", "comment", "edit", "review"}),
    "issue": frozenset({"create", "comment", "edit"}),
}

PATH_ANCHOR_CHARACTER: str = "/"

PATH_SEGMENT_START_CHARACTERS: str = "_-"

ALL_PATH_ANCHORED_VOLATILE_PATH_MARKERS: tuple[str, ...] = (
    ".claude-profile-a/jobs/",
    ".claude/worktrees/",
)

ALL_BARE_VOLATILE_PATH_MARKERS: tuple[str, ...] = (
    "appdata/local/temp",
    "/tmp/",
    "%temp%",
    "$env:temp",
    "$claude_job_dir",
)

GH_ARTIFACT_UPLOAD_INVOCATION: str = (
    "python3 ~/.claude/scripts/gh_artifact_upload.py <file-path> <owner/repo>"
)

CORRECTIVE_MESSAGE: str = (
    "BLOCKED [durable-post-artifacts]: Durable posts use durable references. "
    "Paste text data inline. Upload binary artifacts to the durable artifacts "
    "release with "
    f"{GH_ARTIFACT_UPLOAD_INVOCATION}. Link the permanent asset URL. See "
    "~/.claude/rules/durable-post-artifacts.md for the full contract."
)
