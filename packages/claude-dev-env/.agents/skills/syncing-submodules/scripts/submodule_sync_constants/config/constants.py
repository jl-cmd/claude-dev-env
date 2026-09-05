"""Constants used by the parent-pointer synchronization command."""

from __future__ import annotations

DECODE_ERRORS_POLICY: str = "replace"
DEFAULT_REPOSITORY_ARGUMENT: str = "."
DIAGNOSTIC_PREFIX: str = "syncing-submodules: "
EXIT_CODE_FAILURE: int = 1
EXIT_CODE_INVALID_ARGUMENTS: int = 2
EXIT_CODE_SUCCESS: int = 0
GIT_COMMAND_TIMEOUT_SECONDS: int = 30
GIT_EXECUTABLE_NAME: str = "git"
GIT_HEAD_REFERENCE: str = "HEAD"
GIT_LATEST_COMMIT_ARGUMENT: str = "-1"
GIT_LITERAL_PATHSPEC_PREFIX: str = ":(literal)"
GIT_REV_PARSE_SUBCOMMAND: str = "rev-parse"
GIT_SHOW_SUPERPROJECT_ARGUMENT: str = "--show-superproject-working-tree"
GIT_SHOW_TOP_LEVEL_ARGUMENT: str = "--show-toplevel"
GIT_LOG_SUBCOMMAND: str = "log"
GIT_SUBJECT_FORMAT_ARGUMENT: str = "--pretty=%s"
GIT_ADD_SUBCOMMAND: str = "add"
GIT_ARGUMENT_SEPARATOR: str = "--"
GIT_DIFF_SUBCOMMAND: str = "diff"
GIT_CACHED_ARGUMENT: str = "--cached"
GIT_QUIET_ARGUMENT: str = "--quiet"
GIT_COMMIT_SUBCOMMAND: str = "commit"
GIT_ONLY_ARGUMENT: str = "--only"
GIT_MESSAGE_ARGUMENT: str = "-m"
GIT_LAUNCH_FAILURE_MESSAGE_TEMPLATE: str = "git command could not run: {error}"
GIT_TIMEOUT_MESSAGE_TEMPLATE: str = "git command timed out after {seconds} seconds"
GIT_EXIT_FAILURE_MESSAGE_TEMPLATE: str = (
    "git command exited with status {status}: {command}"
)
GH_EXECUTABLE_NAME: str = "gh"
ALL_GH_PULL_REQUEST_ARGUMENTS: tuple[str, ...] = (
    "pr",
    "view",
    "--json",
    "url",
    "--jq",
    ".url",
)
GH_COMMAND_TIMEOUT_SECONDS: int = 5
PARENT_COMMIT_MESSAGE_TEMPLATE: str = (
    "chore: update {repository_name} submodule to {commit_hash}"
)
SUBMODULE_COMMIT_MESSAGE_TEMPLATE: str = (
    "{parent_message}\n\nSubmodule commit: {subject}"
)
INVALID_ARGUMENT_MESSAGE_TEMPLATE: str = "invalid command arguments: {error}"
SUBMODULE_PATH_FAILURE_MESSAGE: str = (
    "could not resolve the submodule path in its parent repository"
)
REPOSITORY_RESOLUTION_FAILURE_MESSAGE: str = (
    "git did not return a repository top-level path"
)
REPOSITORY_NOT_DIRECTORY_MESSAGE_TEMPLATE: str = (
    "repository path is not a directory: {path}"
)
REPOSITORY_ARGUMENT_NAME: str = "--repository"
SYNC_STATUS_UPDATED: str = "updated"
SYNC_STATUS_UNCHANGED: str = "unchanged"
SYNC_STATUS_NOT_SUBMODULE: str = "not_submodule"
SYNC_STATUS_ERROR: str = "error"
JSON_LINE_SEPARATOR: str = "\n"
UTF8_ENCODING: str = "utf-8"
