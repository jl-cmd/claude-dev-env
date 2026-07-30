"""Constants for the issue-tracker SessionStart injector hook.

Holds the environment toggle name that gates the injector, the directive text it
injects, the ``.claude`` config directory name and the skill and agent path
fragments the injector probes for presence, and the git command pieces and
GitHub marker the injector uses to confirm the session's repository has a GitHub
origin remote.
"""

from __future__ import annotations

__all__ = [
    "ISSUE_TRACKER_ENV_VAR_NAME",
    "ISSUE_TRACKER_START_DIRECTIVE",
    "CLAUDE_CONFIG_DIRECTORY_NAME",
    "ALL_ISSUE_TRACKER_PRESENCE_PATH_FRAGMENTS",
    "GIT_EXECUTABLE_NAME",
    "GIT_DIRECTORY_FLAG",
    "ALL_GIT_ORIGIN_REMOTE_URL_ARGUMENTS",
    "GITHUB_REMOTE_HOST_MARKER",
    "GIT_REMOTE_PROBE_TIMEOUT_SECONDS",
]

ISSUE_TRACKER_ENV_VAR_NAME = "CLAUDE_ISSUE_TRACKER"

ISSUE_TRACKER_START_DIRECTIVE = (
    "ISSUE TRACKER: This session records its work as GitHub issues. Start the "
    "issue-tracker skill or agent now, then use it to create, update in place, "
    "and close issues one consistent way as the session's work moves forward."
)

CLAUDE_CONFIG_DIRECTORY_NAME = ".claude"

ALL_ISSUE_TRACKER_PRESENCE_PATH_FRAGMENTS: tuple[str, ...] = (
    "skills/issue-tracker/SKILL.md",
    "agents/issue-tracker.md",
)

GIT_EXECUTABLE_NAME = "git"
GIT_DIRECTORY_FLAG = "-C"
ALL_GIT_ORIGIN_REMOTE_URL_ARGUMENTS: tuple[str, ...] = ("remote", "get-url", "origin")
GITHUB_REMOTE_HOST_MARKER = "github"
GIT_REMOTE_PROBE_TIMEOUT_SECONDS = 5
