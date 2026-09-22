"""Names and values ``merge_gate_checks.py`` reads a merge policy with.

The fenced block marker and the ruleset field names describe a document and a
GitHub payload that both live outside this package, so they sit here rather
than inside the module that reads them.
"""

from dev_env_scripts_constants.github_http_constants import (  # noqa: F401
    UTF8_ENCODING,
)
from dev_env_scripts_constants.github_http_constants import (
    GITHUB_ACCEPT_TYPE as RULESET_API_ACCEPT_HEADER,
)

REQUIRED_CHECK_BLOCK_INFO_STRING: str = "required-status-checks"
FENCE_MARKER: str = "```"
RULESET_API_TEMPLATE: str = (
    "https://api.github.com/repos/{repository}/rules/branches/{branch}"
)
RULESET_REQUEST_TIMEOUT_SECONDS: int = 30
REQUIRED_STATUS_CHECKS_RULE_TYPE: str = "required_status_checks"
RULE_TYPE_KEY: str = "type"
RULE_PARAMETERS_KEY: str = "parameters"
RULE_CONTEXT_KEY: str = "context"
ALL_GITHUB_TOKEN_VARIABLES: tuple[str, ...] = ("GITHUB_TOKEN", "GH_TOKEN")
MERGE_GATE_CLEAN_EXIT_CODE: int = 0
MERGE_GATE_MISSING_CHECK_EXIT_CODE: int = 1
JSON_INDENT_WIDTH: int = 2
