"""Constants for the dead config-dataclass field detector in ``code_rules_enforcer``.

Lives under the hooks-tree ``hooks_constants`` package so module-level
UPPER_SNAKE constants satisfy the CODE_RULES "constants live in config"
requirement and share a home with the other hook-tree configuration.
"""

from hooks_constants.dead_module_constant_constants import (
    CONFIG_DIRECTORY_SEGMENT,
    DUNDER_INIT_FILENAME,
    MAX_SCAN_ROOT_FILE_COUNT,
    PYTHON_SOURCE_SUFFIX,
)

CONFIG_CLASS_NAME_SUFFIX: str = "Config"
MAX_DEAD_CONFIG_FIELD_ISSUES: int = 25
DEAD_CONFIG_FIELD_GUIDANCE: str = (
    "config dataclass field is defined but read by no production module in the"
    " enclosing package tree - remove the dead field, or read it where the value"
    " is needed (CODE_RULES §9.8)"
)

__all__ = [
    "CONFIG_CLASS_NAME_SUFFIX",
    "CONFIG_DIRECTORY_SEGMENT",
    "DEAD_CONFIG_FIELD_GUIDANCE",
    "DUNDER_INIT_FILENAME",
    "MAX_DEAD_CONFIG_FIELD_ISSUES",
    "MAX_SCAN_ROOT_FILE_COUNT",
    "PYTHON_SOURCE_SUFFIX",
]
