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
DEAD_MODULE_CONSTANT_GUIDANCE: str = (
    "module-level constant is defined here but never imported or read by any"
    " module in the enclosing package tree - remove the constant, or reference it"
    " where its value is needed (CODE_RULES §9.8)"
)
