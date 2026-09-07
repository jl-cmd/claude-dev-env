from __future__ import annotations

NOTICE_EVENT_COMMIT: str = "commit"
NOTICE_EVENT_PUSH: str = "push"
ALL_NOTICE_EVENTS: frozenset[str] = frozenset({NOTICE_EVENT_COMMIT, NOTICE_EVENT_PUSH})
TARGET_REPOSITORY_REMOTE: str = "jonecho/python-automation"
GIT_CONFIG_SUBCOMMAND: str = "config"
GIT_REV_PARSE_SUBCOMMAND: str = "rev-parse"
ALL_GIT_REMOTE_URL_QUERY: tuple[str, ...] = (GIT_CONFIG_SUBCOMMAND, "--get", "remote.origin.url")
ALL_GIT_REPOSITORY_ROOT_QUERY: tuple[str, ...] = (GIT_REV_PARSE_SUBCOMMAND, "--show-toplevel")
ALL_GIT_HEAD_QUERY: tuple[str, ...] = (GIT_REV_PARSE_SUBCOMMAND, "--verify", "HEAD")
ALL_GIT_ABSOLUTE_DIRECTORY_QUERY: tuple[str, ...] = (
    GIT_REV_PARSE_SUBCOMMAND,
    "--absolute-git-dir",
)
GIT_COMMAND_SUCCESS_EXIT_CODE: int = 0
LOCAL_VERIFICATION_DIRECTORY_NAME: str = "local-verification"
MANIFEST_DIRECTORY_NAME: str = "config"
MANIFEST_FILE_NAME: str = "local-verification.json"
REPORT_FILE_NAME: str = "report.json"
GIT_DIRECTORY_NAME: str = ".git"
REPOSITORY_ARGUMENT: str = "--repo"
BASE_ARGUMENT: str = "--base"
BASE_REFERENCE: str = "origin/main"
OUTPUT_ARGUMENT: str = "--output"
PYTHON_COMMAND: str = "python"
SCOPED_VERIFICATION_SCRIPT_PATH: str = ".github/ci/local_verify.py"
EXECUTOR_ARGUMENT: str = "--executor"
EXECUTOR_DIRECTORY_NAME: str = "scripts"
LOCAL_VERIFICATION_PACKAGE_DIRECTORY_NAME: str = "local_verification"
EXECUTOR_FILE_NAME: str = "cli.py"
PACKAGE_ROOT_PARENT_INDEX: int = 2
POWERSHELL_QUOTE: str = "'"
POWERSHELL_ESCAPED_QUOTE: str = "''"
NOTICE_HEADER: str = "=== LOCAL VERIFICATION ADVISORY ==="
UNKNOWN_SHA: str = "unknown"
NO_VERIFIED_SHA: str = "none"
STATUS_PENDING: str = "pending"
STATUS_UNVERIFIED: str = "unverified"
STATUS_STALE: str = "stale"
STATUS_FAILED: str = "failed"
STATUS_PASSED: str = "passed"
MINIMUM_REMOTE_PART_COUNT: int = 2
OWNER_PART_INDEX: int = -2
REPOSITORY_PART_INDEX: int = -1
REPORT_HEAD_FIELD: str = "head"
REPORT_BASE_FIELD: str = "base"
REPORT_MANIFEST_DIGEST_FIELD: str = "manifest_digest"
REPORT_STATUS_FIELD: str = "status"
REPORT_AGGREGATE_FIELD: str = "aggregate"
REPORT_TOTAL_FIELD: str = "total"
REPORT_PASSED_FIELD: str = "passed"
REPORT_FAILED_FIELD: str = "failed"
REPORT_INCOMPLETE_FIELD: str = "incomplete"
REPORT_EXIT_CODE_FIELD: str = "exit_code"
REPORT_WORKTREE_CLEAN_FIELD: str = "worktree_clean"
REPORT_INPUTS_UNCHANGED_FIELD: str = "inputs_unchanged"
REPORT_PUBLISHABLE_FIELD: str = "publishable"
RESOLVED_SHA_LENGTH: int = 40
HEX_DIGITS: str = "0123456789abcdef"
JSON_ENCODING: str = "utf-8"
SHA256_ALGORITHM: str = "sha256"
NOTICE_LINE_SEPARATOR: str = "\n"
NOTICE_ADVISORY_LINE: str = "Advisory only. This notice does not block commit or push."
NOTICE_SETUP_PENDING_LINE: str = "Setup status: pending. The manifest is missing or unreadable."
NOTICE_NO_PASS_LINE: str = (
    "Do not carry local-checks:passed to this revision. No complete current pass is recorded."
)
NOTICE_STALE_LINE: str = "Existing verification evidence belongs to another SHA. Do not carry local-checks:passed forward."
NOTICE_FAILED_LINE: str = "The recorded local checks failed. This advisory does not block commit or push. Fix the failure before reporting a pass."
NOTICE_PASSED_LINE: str = (
    "local-checks:passed is valid only for this exact current SHA and manifest."
)
NOTICE_RUN_LINE: str = "Run the complete local checks with this canonical command:"
PROTECTED_BRANCH_PUSH_ADVISORY_MESSAGE: str = (
    "Advisory: push would send local branch {local_branch!r} to protected remote "
    "branch {remote_branch!r}. The native hook permits the push."
)
MANIFEST_VERSION_KEY: str = "version"
MANIFEST_CHECKS_KEY: str = "checks"
MANIFEST_EXCLUSIONS_KEY: str = "exclusions"
CHECK_ID_KEY: str = "id"
CHECK_ARGUMENTS_KEY: str = "argv"
CHECK_DIRECTORY_KEY: str = "cwd"
CHECK_TIMEOUT_KEY: str = "timeout_seconds"
CHECK_MINIMUM_TESTS_KEY: str = "minimum_tests"
EXCLUSION_SELECTOR_KEY: str = "selector"
EXCLUSION_REASON_KEY: str = "reason"
ALL_MANIFEST_DIGEST_SEPARATORS: tuple[str, str] = (",", ":")
WINDOWS_DIRECTORY_SEPARATOR: str = "\\"
POSIX_DIRECTORY_SEPARATOR: str = "/"
PARENT_DIRECTORY_NAME: str = ".."
ALL_GIT_STATUS_QUERY: tuple[str, ...] = (
    "status",
    "--porcelain=v1",
    "--untracked-files=all",
)
ALL_GIT_BASE_QUERY_PREFIX: tuple[str, ...] = ("rev-parse", "--verify")
GIT_COMMIT_OBJECT_SUFFIX: str = "^{commit}"
SELECTION_FIELD: str = "selection"
SELECTED_MANIFEST_PATH_FIELD: str = "selected_manifest_path"
COMMAND_SEPARATOR: str = " "
RUNNER_FILE_NAME: str = "runner.json"
RUNNER_PYTHON_FIELD: str = "python"
RUNNER_SETTINGS_FIELD: str = "settings"
ALL_RUNNER_FIELDS: frozenset[str] = frozenset(
    {
        RUNNER_PYTHON_FIELD,
        RUNNER_SETTINGS_FIELD,
    }
)
AUTOMATIC_ADVISORY_DIRECTORY_NAME: str = "automatic_advisory"
AUTOMATIC_ADVISORY_CLI_FILE_NAME: str = "cli.py"
WINDOWS_PLATFORM: str = "win32"
CREATE_NO_WINDOW_ATTRIBUTE: str = "CREATE_NO_WINDOW"
POWERSHELL_CALL_OPERATOR: str = "& "
