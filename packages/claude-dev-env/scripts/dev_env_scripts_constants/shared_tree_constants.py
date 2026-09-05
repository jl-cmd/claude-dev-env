"""Directory names for the installed shared tree.

Every caller of shared_tree_paths uses these names.
"""

from __future__ import annotations

CLAUDE_CONFIG_DIR_ENV_VAR: str = "CLAUDE_CONFIG_DIR"

SHARED_PACKAGE_DIRECTORY_NAME: str = "_shared"

SCRIPTS_DIRECTORY_NAME: str = "scripts"

PROCESS_TREE_DIRECTORY_NAME: str = "process-tree"

PROCESS_TREE_KILL_MODULE_FILENAME: str = "process_tree_kill.py"

AGENTS_DIRECTORY_SUFFIX: str = ".agents"
DEFAULT_MANAGED_ROOT_NAME: str = ".claude"
