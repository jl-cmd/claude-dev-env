"""Constants for the worktree/cwd preflight guard shared by pr-loop skills."""

import re

OUTCOME_SAME_REPO = "same_repo"
OUTCOME_DIFFERENT_REPO = "different_repo"
OUTCOME_RE_ROOTED = "re_rooted"

MODE_STRICT = "strict"
MODE_CLASSIFY = "classify"
ALL_PREFLIGHT_MODES = (MODE_STRICT, MODE_CLASSIFY)

EXIT_PREFLIGHT_OK = 0
EXIT_PREFLIGHT_ABORT = 1

GIT_EXECUTABLE = "git"
GIT_DIRECTORY_FLAG = "-C"
ALL_GIT_IS_INSIDE_WORK_TREE_ARGS = ("rev-parse", "--is-inside-work-tree")
ALL_GIT_REMOTE_GET_URL_ARGS = ("remote", "get-url", "origin")
ALL_GIT_WORKTREE_LIST_ARGS = ("worktree", "list")
GIT_INSIDE_WORK_TREE_TRUE = "true"
GIT_SUBPROCESS_TIMEOUT_SECONDS = 30

REMOTE_URL_IDENTITY_PATTERN = re.compile(
    r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)

CWD_IDENTITY_UNKNOWN = "unknown"

OWNER_ARG_FLAG = "--owner"
REPO_ARG_FLAG = "--repo"
MODE_ARG_FLAG = "--mode"

PREFLIGHT_CLI_DESCRIPTION = (
    "Verify the working directory and worktree before a PR-convergence run."
)

OUTCOME_MARKER_TEMPLATE = "PREFLIGHT_OUTCOME={outcome}"

SUMMARY_SAME_REPO_TEMPLATE = (
    "OK: the working directory is the PR repo {owner}/{repo}; EnterWorktree can "
    "create and enter the branch worktree."
)
SUMMARY_DIFFERENT_REPO_TEMPLATE = (
    "The working directory repo {cwd_owner}/{cwd_repo} differs from the PR repo "
    "{owner}/{repo}."
)
SUMMARY_RE_ROOTED_TEMPLATE = (
    "The working directory {cwd} is not a usable checkout of a GitHub repo "
    "(no git work tree, or no readable origin remote)."
)
ABORT_DIFFERENT_REPO_STRICT_TEMPLATE = (
    "ABORT: autoconverge runs inside the PR's own repo, but this session is "
    "rooted in {cwd_owner}/{cwd_repo}. Start the session from a checkout of "
    "{owner}/{repo} and re-run."
)
ABORT_RE_ROOTED_TEMPLATE = (
    "ABORT: this session is not rooted in a git checkout (a resumed or "
    "background session can re-root to the home directory). Start the session "
    "from a checkout of {owner}/{repo} and re-run."
)
ABORT_WORKTREE_BROKEN_TEMPLATE = (
    "ABORT: the git worktree machinery in {cwd} is broken (git worktree list "
    "failed), so EnterWorktree cannot create the branch worktree. Run "
    "'git worktree prune' in {cwd} and re-run."
)
ROUTE_DIFFERENT_REPO_TEMPLATE = (
    "ROUTE: resolve the PR worktree for {owner}/{repo} and cd into it before "
    "any local work (cross-repo PR)."
)
