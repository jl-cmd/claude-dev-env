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
            "9c48917645524d03ea0a4f4d8755aa8f0d59f3108e1aa976202a02e613c1444d",
        ),
        (
            "packages/claude-dev-env/_shared/pr-loop/scripts/_claude_permissions_common.py",
            "home-path",
            "07ba214cb23325675bc68e5513c030e968eccf2760cb5917d932ae5da29d5af1",
        ),
        (
            "packages/claude-dev-env/_shared/pr-loop/scripts/_claude_permissions_common.py",
            "home-path",
            "d41ce8d0f21de2d5320bdd8cd4e8693a2f3d6ea59db6df5ea102a7d2be4b2c22",
        ),
        (
            "packages/claude-dev-env/audit-rubrics/prompts/category-n-test-name-scenario-verifier.md",
            "home-path",
            "550c7b16a2a04e1d05a8a6b4f5b764b8d4fdef65e9d79d09e5dbb3a15a855812",
        ),
        (
            "packages/claude-dev-env/audit-rubrics/prompts/category-n-test-name-scenario-verifier.md",
            "home-path",
            "b8bbdd1a7ebdad16f4e51377a3f21d05dd35992d89e35971b28b05f53245c69d",
        ),
        (
            "packages/claude-dev-env/bin/expand_home_directory_tokens.mjs",
            "home-path",
            "10d5571e7126d2018ee7fb06aa29c72a9d503cac79a4e52d6848602ee10e8832",
        ),
        (
            "packages/claude-dev-env/bin/expand_home_directory_tokens.mjs",
            "home-path",
            "09f83c224a02c370d3d63de5c330e1a830fc92866330fc7963b5b5fd20ffcb91",
        ),
        (
            "packages/claude-dev-env/hooks/hooks_constants/hardcoded_user_path_constants.py",
            "home-path",
            "0967160658d782c558722232cad7d47dc19267943d4667b41d3eff1e605be2f4",
        ),
        (
            "packages/claude-dev-env/hooks/hooks_constants/hardcoded_user_path_constants.py",
            "home-path",
            "a541acfac2e649581bca0cd03e4c3dcf306344915017d9cd6be4ad57a8fd7379",
        ),
    )
)
