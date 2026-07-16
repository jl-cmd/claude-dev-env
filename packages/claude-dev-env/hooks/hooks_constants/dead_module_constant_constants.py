"""Constants for the dead module-level constant detector in ``code_rules_enforcer``.

Lives under the hooks-tree ``hooks_constants`` package so module-level
UPPER_SNAKE constants satisfy the CODE_RULES "constants live in config"
requirement and share a home with the other hook-tree configuration.
"""

PYTHON_SOURCE_SUFFIX: str = ".py"
DUNDER_INIT_FILENAME: str = "__init__.py"
CONSTANTS_MODULE_SUFFIX: str = "_constants.py"
CONFIG_DIRECTORY_SEGMENT: str = "config"
DUNDER_ALL_NAME: str = "__all__"
GIT_DIRECTORY_NAME: str = ".git"
MINIMUM_UPPER_SNAKE_LENGTH: int = 2
MAX_DEAD_MODULE_CONSTANT_ISSUES: int = 25
MAX_SCAN_ROOT_FILE_COUNT: int = 2000
MAX_SCAN_ROOT_READ_COUNT: int = 20000
DEAD_MODULE_CONSTANT_GUIDANCE: str = (
    "module-level constant is defined here but never imported or read by any"
    " module in the enclosing package tree - remove the constant, or reference it"
    " where its value is needed (CODE_RULES §9.8)"
)
DEAD_MODULE_CONSTANT_RETRY_GUIDANCE: str = (
    "To land a constant a consumer will read, break the write-order deadlock by"
    " writing the consumer that reads it first: that write completes even though a"
    " transient mypy attr-defined advisory flags the not-yet-defined name (a"
    " non-blocking post-write check), then re-issue this write, which passes once"
    " the consumer is on disk. A constant no module ever reads stays flagged on"
    " every attempt."
)
