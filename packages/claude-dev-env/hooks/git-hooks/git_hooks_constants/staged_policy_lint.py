"""Constants for the native pre-commit policy-lint step."""

POLICY_LINT_PACKAGE_PARENT_INDEX = 2
POLICY_LINT_SCRIPT_RELATIVE_PATH = "scripts/cde_lint.py"
POLICY_LINT_STAGED_ARGUMENT = "--staged"
POLICY_LINT_TIMEOUT_SECONDS = 240
POLICY_LINT_INFRASTRUCTURE_EXIT_CODE = 2
POLICY_LINT_UNAVAILABLE_MESSAGE = (
    "cde lint is missing from this hook installation; reinstall claude-dev-env "
    "before committing"
)
POLICY_LINT_FAILED_MESSAGE = "cde lint could not complete: {error}"
