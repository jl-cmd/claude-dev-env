"""Constants for resolving directories inside the installed shared tree.

These name the shape of the installed tree itself, not any one worker or
skill that reads it, so every caller of shared_tree_paths shares them.
"""

from __future__ import annotations

CLAUDE_CONFIG_DIR_ENV_VAR: str = "CLAUDE_CONFIG_DIR"

SHARED_PACKAGE_DIRECTORY_NAME: str = "_shared"

SCRIPTS_DIRECTORY_NAME: str = "scripts"

PROCESS_TREE_DIRECTORY_NAME: str = "process-tree"

PROCESS_TREE_KILL_MODULE_FILENAME: str = "process_tree_kill.py"
