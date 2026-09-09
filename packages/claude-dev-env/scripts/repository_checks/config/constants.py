"""Stable identifiers, report tokens, and committed-tree exemption tables."""

from policy_lint.config.constants import (
    GIT_FILES_ARGUMENT,
    GIT_ZERO_TERMINATED_FLAG,
    INCOMPLETE_EXIT_CODE,
    INVALID_INPUT_EXIT_CODE,
)

CHECK_ID_CLAUDE_MD_ORPHANS = "claude-md-orphans"
CHECK_ID_ENV_VAR_DOCUMENTATION = "env-var-documentation"
CHECK_ID_PACKAGE_INVENTORY = "package-inventory"
CHECK_ID_PYTEST_TESTPATHS = "pytest-testpaths"
CHECK_ID_TRACKED_PERSONAL_DATA = "tracked-secrets"

ALL_CHECK_IDS = (
    CHECK_ID_CLAUDE_MD_ORPHANS,
    CHECK_ID_ENV_VAR_DOCUMENTATION,
    CHECK_ID_PACKAGE_INVENTORY,
    CHECK_ID_PYTEST_TESTPATHS,
    CHECK_ID_TRACKED_PERSONAL_DATA,
)

SUCCESS_EXIT_CODE = 0
FINDINGS_EXIT_CODE = 1
FAILED_CHECK_EXIT_CODE = INCOMPLETE_EXIT_CODE
USAGE_EXIT_CODE = INVALID_INPUT_EXIT_CODE

REPOSITORY_ROOT_FLAG = "--repository-root"
FINDING_LINE_TEMPLATE = "{check_id}: {relative_path}: {message}"
RULE_FAILED_LINE_TEMPLATE = "error: rule failed: {check_id}"
REPORT_LINE_SEPARATOR = "\n"
EMPTY_REPORT_TEXT = ""
TRACKED_MATCH_MESSAGE_TEMPLATE = "[{category}] {preview}"
CLAUDE_MD_MISSING_FILE_MESSAGE_TEMPLATE = "references missing file {filename}"
PACKAGE_INVENTORY_MESSAGE_TEMPLATE = "production file is absent from package inventory"
PYTEST_TESTPATH_MESSAGE_TEMPLATE = (
    "test file is outside the package testpaths allowlist"
)
ALL_GIT_LS_FILES_ARGUMENTS = (GIT_FILES_ARGUMENT, GIT_ZERO_TERMINATED_FLAG)
PYPROJECT_FILENAME = "pyproject.toml"
WINDOWS_PATH_SEPARATOR = "\\"

CLAUDE_MD_SCAN_MODULE_NAME = "blocking.claude_md_orphan_file_blocker_parts.subtree_scan"
CLAUDE_MD_CONSTANTS_MODULE_NAME = (
    "hooks_constants.claude_md_orphan_file_blocker_constants"
)
ENV_VAR_DRIFT_MODULE_NAME = "blocking.env_var_table_code_drift_blocker"
ENV_VAR_DRIFT_CONSTANTS_MODULE_NAME = (
    "hooks_constants.env_var_table_code_drift_constants"
)
PACKAGE_INVENTORY_DETECTION_MODULE_NAME = (
    "blocking.package_inventory_stale_blocker_parts.inventory_detection"
)
PACKAGE_INVENTORY_CONSTANTS_MODULE_NAME = (
    "hooks_constants.package_inventory_stale_blocker_constants"
)
PYTEST_TESTPATHS_MODULE_NAME = "blocking.pytest_testpaths_orphan_blocker"
PII_SCANNER_MODULE_NAME = "blocking.pii_scanner"
REPOSITORY_EXEMPTION_MODULE_NAME = (
    "blocking.pii_prevention_blocker_parts.repository_exemption"
)

ALL_FAIL_CLOSED_EXCEPTION_TYPES = (
    AttributeError,
    ImportError,
    KeyError,
    OSError,
    RuntimeError,
    SyntaxError,
    TypeError,
    UnicodeError,
    ValueError,
)

ALL_ARCHIVED_SKILL_DIRECTORY_SEGMENTS = (".agents", "skills-archived")
ALL_TRACKED_SECRET_EXACT_EXEMPTIONS: frozenset[tuple[str, str, str]] = frozenset(
    (
        (
            "packages/claude-dev-env/.agents/skills-archived/pr-converge/reference/per-tick.md",
            "email",
            "3de132cd98be7bf26b6f08e81c31c799a891bc32046b61f0b6fe3671ca2e44b5",
        ),
        (
            "packages/claude-dev-env/.agents/skills/_shared/pr-loop/prompts/pr-consistency-audit.xml",
            "home-path",
            "805e3271caeec55a94438e221726e9349e46fa4970592bd03ffd3adac5e0ea8a",
        ),
        (
            "packages/claude-dev-env/.agents/skills/_shared/pr-loop/scripts/skills_pr_loop_constants/path_resolver_constants.py",
            "home-path",
            "a4f1f978f88b601288424144a5f5066cdc9154868cf2aaab6e0869a103be72a5",
        ),
        (
            "packages/claude-dev-env/.agents/skills/_shared/pr-loop/scripts/skills_pr_loop_constants/path_resolver_constants.py",
            "home-path",
            "665e48f1b198dd2a6526e25700fbcb86566d1f8b47d4475a6cc318b1634a4546",
        ),
        (
            "packages/claude-dev-env/_shared/pr-loop/scripts/_claude_permissions_common.py",
            "home-path",
            "f9e409c5c16ecfdd5883da4f3ad045b4af5677740c9e703ad2d47ba231718350",
        ),
        (
            "packages/claude-dev-env/audit-rubrics/prompts/category-n-test-name-scenario-verifier.md",
            "home-path",
            "6b98ff7f0398f06452f19c4a93f3d69186401dab40aaa7077b394ef59b3e730e",
        ),
        (
            "packages/claude-dev-env/bin/expand_home_directory_tokens.mjs",
            "home-path",
            "31e989aa0fbf83d6de5d2f0cd6f08b3cd8151592050b71794ffa180b80385ff2",
        ),
        (
            "packages/claude-dev-env/bin/expand_home_directory_tokens.mjs",
            "home-path",
            "73ff793e488241663bb0c075fd50bd3a18fca8dd79cbd11629c00d2ad7548a8a",
        ),
        (
            "packages/claude-dev-env/bin/expand_home_directory_tokens.mjs",
            "home-path",
            "fd9ba4ae930ef31ebdfc463b231a093656b8eaa1d8fe65f60715ec2b6fee04a9",
        ),
        (
            "packages/claude-dev-env/hooks/hooks_constants/hardcoded_user_path_constants.py",
            "home-path",
            "0967160658d782c558722232cad7d47dc19267943d4667b41d3eff1e605be2f4",
        ),
        (
            "packages/claude-dev-env/hooks/hooks_constants/hardcoded_user_path_constants.py",
            "home-path",
            "5d956228802fbd4a65af8fa7fb4183f5a9f8793dbe218877aefe887b905f726d",
        ),
    )
)
