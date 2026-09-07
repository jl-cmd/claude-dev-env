from __future__ import annotations

import re
from typing import Literal

MANIFEST_VERSION = 1
MANIFEST_VERSION_KEY = "version"
MANIFEST_CHECKS_KEY = "checks"
MANIFEST_EXCLUSIONS_KEY = "exclusions"
CHECK_ID_KEY = "id"
CHECK_ARGUMENTS_KEY = "argv"
CHECK_DIRECTORY_KEY = "cwd"
CHECK_TIMEOUT_KEY = "timeout_seconds"
CHECK_MINIMUM_TESTS_KEY = "minimum_tests"
EXCLUSION_SELECTOR_KEY = "selector"
EXCLUSION_REASON_KEY = "reason"
MANIFEST_DIGEST_ALGORITHM = "sha256"
ALL_MANIFEST_DIGEST_SEPARATORS = (",", ":")
SUCCESS_EXIT_CODE = 0
CHECK_FAILED_EXIT_CODE = 1
INVALID_INPUT_EXIT_CODE = 2
INCOMPLETE_EXIT_CODE = 3
UTF8_ENCODING = "utf-8"
JSON_INDENT_SPACES = 2
PASSED_STATUS = "passed"
FAILED_STATUS = "failed"
INCOMPLETE_STATUS = "incomplete"
MINIMUM_TESTS_ERROR_KIND = "minimum_tests"
MISSING_TOOL_ERROR_KIND = "missing_tool"
TIMEOUT_ERROR_KIND = "timeout"
CRASH_ERROR_KIND = "crash"
START_ERROR_KIND = "start_error"
COLLECTION_ERROR_KIND = "collection_error"
NONZERO_EXIT_ERROR_KIND = "nonzero_exit"
SKIPPED_TESTS_ERROR_KIND = "skipped_tests"
PYTEST_COLLECTION_FLAG = "--collect-only"
PYTEST_QUIET_FLAG = "-q"
COLLECTED_TESTS_PATTERN = re.compile(r"(?P<count>\d+) tests? collected")
SKIPPED_TESTS_PATTERN = re.compile(r"(?P<count>\d+) skipped")
SAFE_LOG_NAME_PATTERN = re.compile(r"[^A-Za-z0-9_.-]+")
PYTHON_PLACEHOLDER = "{python}"
REPOSITORY_PLACEHOLDER = "{repo}"
BASE_PLACEHOLDER = "{base}"
CDE_LINT_PLACEHOLDER = "{cde_lint}"
REPOSITORY_POLICY_PLACEHOLDER = "{repository_policy}"
LOGS_DIRECTORY_SUFFIX = ".logs"
STDOUT_LOG_SUFFIX = ".stdout.log"
STDERR_LOG_SUFFIX = ".stderr.log"
COLLECTION_STDOUT_LOG_SUFFIX = ".collection.stdout.log"
COLLECTION_STDERR_LOG_SUFFIX = ".collection.stderr.log"
REPORT_NEWLINE = "\n"
GIT_EXECUTABLE = "git"
ALL_GIT_ROOT_ARGUMENTS = ("rev-parse", "--show-toplevel")
ALL_GIT_HEAD_ARGUMENTS = ("rev-parse", "--verify", "HEAD")
ALL_GIT_TREE_ARGUMENTS = ("rev-parse", "--verify", "HEAD^{tree}")
ALL_GIT_BASE_ARGUMENT_PREFIX = ("rev-parse", "--verify")
ALL_GIT_STATUS_ARGUMENTS = (
    "status",
    "--porcelain=v1",
    "--untracked-files=all",
)
ALL_GIT_CHANGED_FILES_ARGUMENTS = ("diff", "--name-only", "-z")
ALL_GIT_INDEX_CHANGED_FILES_ARGUMENTS = (
    "diff",
    "--cached",
    "--name-only",
    "-z",
)
ALL_GIT_UNTRACKED_FILES_ARGUMENTS = (
    "ls-files",
    "--others",
    "--exclude-standard",
    "-z",
)
GIT_COMMIT_OBJECT_SUFFIX = "^{commit}"
GIT_PATH_SEPARATOR = b"\0"
DIGEST_LENGTH_BYTES = 8
DIGEST_BYTE_ORDER: Literal["big"] = "big"
CLI_START_MESSAGE_TEMPLATE = "verification start: {report_path}"
CLI_CHECK_START_MESSAGE_TEMPLATE = "check start: {check_id}"
CLI_CHECK_FINISH_MESSAGE_TEMPLATE = "check finish: {check_id} status={status}"
CLI_AGGREGATE_MESSAGE_TEMPLATE = "aggregate: {status}"
CLI_REVISION_MESSAGE_TEMPLATE = "revision: head={head} base={base}"
CLI_ELIGIBILITY_MESSAGE_TEMPLATE = "eligibility: clean={worktree_clean} unchanged={inputs_unchanged} publishable={publishable}"
CLI_REPORT_MESSAGE_TEMPLATE = "report: {report_path}"
CLI_FAILURE_MESSAGE_TEMPLATE = "verification {status}: required checks did not pass"
UNRESOLVED_REVISION = "unresolved"
RUN_LOG_FILENAME = "run.log"
RUN_CHECK_LOG_TEMPLATE = "check {check_id} status={status}"
