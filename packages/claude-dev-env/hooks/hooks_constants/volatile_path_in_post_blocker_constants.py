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

ALL_VOLATILE_PATH_MARKERS: tuple[str, ...] = (
    ".claude-editor/jobs/",
    ".claude/worktrees/",
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
    "BLOCKED [durable-post-artifacts]: this post body references a volatile path "
    "(a job scratch dir, worktree, or system temp location). The post is durable "
    "and outlives that scratch, so the reference breaks the moment the directory "
    "is cleaned.\n\n"
    "Fix it before posting:\n"
    "  1. Text data (logs, tables, diffs): paste the actual content inline in the "
    "post instead of linking a scratch file path.\n"
    "  2. Binary artifacts (images, archives): upload the file to the repo's "
    "durable 'artifacts' release and link the permanent asset URL it prints:\n"
    f"       {GH_ARTIFACT_UPLOAD_INVOCATION}\n\n"
    "See ~/.claude/rules/durable-post-artifacts.md for the full contract."
)
