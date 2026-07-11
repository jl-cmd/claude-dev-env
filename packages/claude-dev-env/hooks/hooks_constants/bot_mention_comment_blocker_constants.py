"""Configuration constants for the bot_mention_comment_blocker PreToolUse hook."""

TOOL_NAME: str = "mcp__plugin_github_github__add_issue_comment"

CURSOR_MENTION_TOKEN: str = "@cursor"
COPILOT_MENTION_TOKEN: str = "@copilot"

CORRECTIVE_MESSAGE_CURSOR: str = (
    "BLOCKED [bot-mention]: Invalid comment. "
    "Post exactly ``bugbot run`` with no other text as your issue comment "
    "to trigger Bugbot."
)

CORRECTIVE_MESSAGE_COPILOT: str = (
    "BLOCKED [bot-mention]: Invalid comment. "
    "To request a Copilot review, use the GitHub REST API:\n"
    "  gh api --method POST repos/<owner>/<repo>/pulls/<number>/requested_reviewers \\\n"
    "    -f 'reviewers[]=copilot-pull-request-reviewer[bot]'\n"
    "See ~/.claude/skills/pr-converge/reference/convergence-gates.md."
)
