#!/usr/bin/env python3
"""SessionStart hook: detect git repos not present in ~/.claude/project-paths.json.

When Claude Code opens inside a git repo that is not registered, emits an
additionalContext instruction asking Claude to confirm the mapping with the
user via AskUserQuestion before persisting anything. The hook itself never
writes to the config file.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path


def _insert_hooks_tree_for_imports() -> None:
    hooks_tree = Path(__file__).resolve().parent.parent
    hooks_tree_string = str(hooks_tree)
    if hooks_tree_string not in sys.path:
        sys.path.insert(0, hooks_tree_string)


_insert_hooks_tree_for_imports()

from config.dynamic_stderr_handler import DynamicStderrHandler
from config.project_paths_reader import (
    load_registry,
    registry_contains_path,
    registry_file_path,
)
from config.setup_project_paths_constants import GIT_DIRECTORY_SEGMENT_NAME


_logger = logging.getLogger("untracked_repo_detector")
if not _logger.handlers:
    _stderr_handler = DynamicStderrHandler()
    _stderr_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    _logger.addHandler(_stderr_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def current_working_directory() -> str:
    """Return the process working directory as a string."""
    return os.getcwd()


def find_git_root(start_path: str) -> str | None:
    """Walk upward from start_path looking for a .git directory.

    The walk is bounded by the user's home directory: once the candidate
    reaches the home directory without finding ``.git``, the search stops.
    This prevents a stray ``.git`` above the user's home (for example a
    parent dotfiles repo) from being falsely reported as the session's repo.

    Returns the absolute path of the repo root, or None if not found.
    """
    home_directory = Path.home().resolve()
    candidate = Path(start_path).resolve()
    while True:
        if (candidate / GIT_DIRECTORY_SEGMENT_NAME).exists():
            return str(candidate)
        if candidate == home_directory:
            return None
        parent = candidate.parent
        if parent == candidate:
            return None
        candidate = parent


def _build_confirm_instruction(repo_root: str) -> str:
    config_file_path = str(registry_file_path())
    return (
        f"UNTRACKED REPO DETECTED: The current session is running inside a git "
        f"repository at '{repo_root}' that is not present in {config_file_path}. "
        f"Use AskUserQuestion with two options — 'Save mapping' (recommended) and "
        f"'Skip for this session' — to confirm whether to persist this repo path. "
        f"On approval, append a new entry to {config_file_path} mapping the "
        f"repository leaf name to '{repo_root}'. This hook has written nothing."
    )


def main() -> None:
    try:
        session_cwd = current_working_directory()
        git_root = find_git_root(session_cwd)
        if git_root is None:
            sys.exit(0)
        known_registry = load_registry()
        if registry_contains_path(known_registry, git_root):
            sys.exit(0)
        instruction = _build_confirm_instruction(git_root)
        print(json.dumps({"additionalContext": instruction}))
    except Exception as e:
        _logger.error("%s", e)
    sys.exit(0)


if __name__ == "__main__":
    main()
