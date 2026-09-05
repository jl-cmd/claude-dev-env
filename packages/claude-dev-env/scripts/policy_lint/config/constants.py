import re

INCOMPLETE_EXIT_CODE = 3
INVALID_INPUT_EXIT_CODE = 2
GIT_EXECUTABLE = "git"
UTF8_ENCODING = "utf-8"
PATH_SEPARATOR = "/"
ARCHIVED_SKILLS_DIRECTORY_NAME = "skill-archive"
NUL_BYTE = b"\0"
ALL_GIT_ROOT_ARGUMENTS = ("rev-parse", "--show-toplevel")
ALL_GIT_HEAD_ARGUMENTS = ("rev-parse", "--verify", "HEAD")
ALL_UNBORN_HEAD_ERROR_FRAGMENTS = ("needed a single revision",)
GIT_MERGE_BASE_ARGUMENT = "merge-base"
GIT_HEAD_REFERENCE = "HEAD"
GIT_INDEX_REFERENCE_PREFIX = ""
GIT_ENVIRONMENT_VARIABLE_PREFIX = "GIT_"
ALL_GIT_BLOB_ARGUMENTS = ("cat-file", "blob")
ALL_MISSING_BLOB_ERROR_FRAGMENTS = (
    "does not exist in",
    "does not exist (at stage",
    "exists on disk, but not in",
)
GIT_DIFF_ARGUMENT = "diff"
GIT_CACHED_FLAG = "--cached"
GIT_NAME_STATUS_FLAG = "--name-status"
GIT_FIND_RENAMES_FLAG = "--find-renames"
GIT_ZERO_TERMINATED_FLAG = "-z"
GIT_FILES_ARGUMENT = "ls-files"
GIT_SEPARATOR = "--"
ALL_DIFF_CHANGED_TAGS = frozenset({"replace", "insert"})
NEW_DOCUMENT_ORIGIN_LINE = 1
RENAME_PATH_COUNT = 2
PYTHON_SUFFIX = ".py"
ALL_CODE_SUFFIXES = frozenset({".py", ".js", ".jsx", ".ts", ".tsx", ".mjs"})
ALL_MARKDOWN_SUFFIXES = frozenset({".md", ".mdx"})
ALL_STORED_PROMPT_SEGMENTS = (
    "/.agents/",
    "/commands/",
    "/rules/",
    "/system-prompts/",
)
ALL_HOOK_REGISTRATION_KEYS = frozenset({"command", "path", "script", "entrypoint"})
ALL_DECISION_REGISTRATION_KEYS = frozenset(
    {"permissionDecision", "permission_decision", "decision"}
)
ALL_ACTION_BOUNDARY_SEGMENTS = frozenset(
    {
        "deny",
        "block",
        "ask",
        "blocking",
        "blocker",
        "permissiondecision",
        "permission_decision",
        "pre_tool_use_dispatcher",
    }
)
ALL_ACTION_BOUNDARY_PREFIXES = ("deny_", "block_", "ask_")
ALL_TEST_DIRECTORY_NAMES = frozenset({"tests"})
ALL_TEST_FILE_PREFIXES = ("test_",)
ALL_TEST_FILE_SUFFIXES = ("_test.py",)
POLICY_LINT_DIRECTORY_NAME = "policy_lint"
POLICY_LINT_RULES_TEST_PREFIX = "test_policy_lint_rules"
POLICY_LINT_SELECTION_TEST_PREFIX = "test_policy_lint_selection"
RUN_ALL_VALIDATORS_STEM = "run_all_validators"
FAST_SAVE_VALIDATORS_STEM = "fast_save_validators"
ALL_OVERLAPPING_VALIDATOR_NAMES = frozenset(
    {"Python Style", "Magic Values", "Type Safety", "Test Safety", "React"}
)
ALL_PR_LOOP_SCRIPTS_PATH_SEGMENTS = ("_shared", "pr-loop", "scripts")
TERMINOLOGY_SWEEP_MODULE_NAME = "terminology_sweep"
TERMINOLOGY_SWEEP_RULE_ID = "terminology-sweep"
TERMINOLOGY_FINDING_PATTERN = re.compile(
    r"^(?P<path>.+):(?P<line_number>\d+): (?P<message>.+)$"
)
TERMINOLOGY_PATH_GROUP = "path"
TERMINOLOGY_LINE_NUMBER_GROUP = "line_number"
TERMINOLOGY_MESSAGE_GROUP = "message"
