"""Constants for the stuttering ``all_``/``ALL_`` AST import-binding scan.

Lives under the hooks-tree ``config/`` package so module-level
UPPER_SNAKE constants satisfy the CODE_RULES "constants live in config"
requirement and share a home with the other hook-tree configuration
(``messages``, ``stuttering_check_config``, ``project_paths_reader``).
"""

WILDCARD_IMPORT_SENTINEL = "*"
MODULE_PATH_SEPARATOR = "."
AST_LINENO_ATTRIBUTE = "lineno"
