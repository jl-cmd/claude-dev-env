"""Constants for the claude-dev-env git-hook entry points.

Co-located with ``pre_commit.py`` and ``pre_push.py`` so the installed shim
directory is self-contained at runtime: the shim prepends its own directory
to ``sys.path`` before importing the hook module, which makes ``from config
import ...`` resolve against this file both inside the repo and under
``~/.claude/hooks/git-hooks/`` after installation.
"""

from __future__ import annotations

STAGED_SCOPE_ARGUMENT: str = "--staged"
BASE_REFERENCE_ARGUMENT: str = "--base"
DEFAULT_REMOTE_BASE_REFERENCE: str = "origin/HEAD"
ALL_ZEROS_OBJECT_NAME_CHARACTER: str = "0"
STDIN_LINE_FIELD_COUNT: int = 4
STDIN_REMOTE_OBJECT_FIELD_INDEX: int = 3
LOCAL_REFERENCE_FIELD_INDEX: int = 0
REMOTE_REFERENCE_FIELD_INDEX: int = 2
GATE_PATH_OVERRIDE_ENV_VAR: str = "CODE_RULES_GATE_PATH"
CLAUDE_HOME_ENV_VAR: str = "CLAUDE_HOME"
CLAUDE_HOME_DEFAULT_SUBDIRECTORY: str = ".claude"
ALL_GATE_SCRIPT_RELATIVE_PATH: tuple[str, ...] = (
    "_shared",
    "pr-loop",
    "scripts",
    "code_rules_gate.py",
)
GATE_INFRASTRUCTURE_FAILURE_EXIT_CODE: int = 2
GATE_SCRIPT_NOT_FOUND_MESSAGE: str = (
    "claude-dev-env pre-commit: gate script not found at {path}, skipping enforcement"
)
PRE_PUSH_GATE_SCRIPT_NOT_FOUND_MESSAGE: str = (
    "claude-dev-env pre-push: gate script not found at {path}, skipping enforcement"
)
STDIN_READ_FAILURE_MESSAGE: str = (
    "claude-dev-env pre-push: could not read stdin ({error}), aborting"
)
INVOKE_GATE_FAILURE_MESSAGE: str = (
    "claude-dev-env: could not launch gate script ({error}), aborting"
)
MALFORMED_STDIN_LINE_MESSAGE: str = (
    "claude-dev-env pre-push: ignoring malformed stdin line: {line!r}"
)
LOCAL_SHA_FIELD_INDEX: int = 1
NO_PARSEABLE_STDIN_LINES_MESSAGE: str = (
    "claude-dev-env pre-push: no parseable stdin lines; aborting"
)
NO_PARSEABLE_STDIN_LINES_SENTINEL: str = "__no_parseable_stdin_lines__"
LOCAL_BRANCH_REFERENCE_PREFIX: str = "refs/heads/"
CODE_REVIEW_PUSH_GATE_PATH_OVERRIDE_ENV_VAR: str = "CODE_REVIEW_PUSH_GATE_PATH"
CODE_REVIEW_PUSH_GATE_MODULE_NAME: str = "code_review_push_gate"
CODE_REVIEW_PUSH_GATE_SCRIPT_FILENAME: str = "code_review_push_gate.py"
CODE_REVIEW_DENY_REASON_FUNCTION_NAME: str = "deny_reason_for_directory"
BLOCKING_DIRECTORY_NAME: str = "blocking"
CODE_REVIEW_STAMP_BLOCK_EXIT_CODE: int = 1
ALL_PROTECTED_BRANCH_PUSH_NAMES: tuple[str, ...] = ("main", "master")
PROTECTED_BRANCH_PUSH_BLOCK_EXIT_CODE: int = 1
PROTECTED_BRANCH_PUSH_BLOCK_MESSAGE: str = (
    "claude-dev-env pre-push: blocked a push of local branch {local_branch!r} "
    "onto protected remote branch {remote_branch!r}.\n"
    "A local branch that tracks origin/{remote_branch}, with push.default=upstream, "
    "resolves a bare 'git push' to {remote_branch}.\n"
    "To push the feature branch to its own ref, name the destination: "
    "git push origin {local_branch}:refs/heads/{local_branch}"
)
GIT_EXECUTABLE_NAME: str = "git"
GIT_COMMAND_SUCCESS_EXIT_CODE: int = 0
EMPTY_GIT_COMMAND_OUTPUT: str = ""
GIT_REV_PARSE_SUBCOMMAND: str = "rev-parse"
GIT_REV_PARSE_VERIFY_FLAG: str = "--verify"
GIT_QUIET_FLAG: str = "--quiet"
GIT_SYMBOLIC_REFERENCE_SUBCOMMAND: str = "symbolic-ref"
GIT_COMMAND_TIMEOUT_SECONDS: int = 30
GIT_FOR_EACH_REF_SUBCOMMAND: str = "for-each-ref"
GIT_REFERENCE_SHORT_NAME_FORMAT_ARGUMENT: str = "--format=%(refname:short)"
COMMIT_OBJECT_NAME_SUFFIX: str = "^{commit}"
REMOTE_REFERENCE_NAME_PREFIX: str = "refs/remotes/"
REMOTE_HEAD_SYMBOLIC_REFERENCE_TEMPLATE: str = "refs/remotes/{remote}/HEAD"
REMOTE_BRANCH_REFERENCE_TEMPLATE: str = "refs/remotes/{remote}/{branch}"
REMOTE_BRANCH_SHORT_NAME_TEMPLATE: str = "{remote}/{branch}"
DEFAULT_REMOTE_NAME: str = "origin"
REMOTE_NAME_ARGUMENT_INDEX: int = 1
ALL_REMOTE_URL_MARKERS: tuple[str, ...] = (":", "/")
ALL_FALLBACK_REMOTE_DEFAULT_BRANCH_NAMES: tuple[str, ...] = (
    "main",
    "master",
    "trunk",
    "develop",
)
UNRESOLVABLE_BASE_REFERENCE_MESSAGE: str = (
    "claude-dev-env pre-push: no usable gate base -- {reference} names no commit and "
    "the default branch of remote {remote!r} could not be read.\n"
    "Set the remote head so the gate has a base: git remote set-head {remote} --auto"
)
