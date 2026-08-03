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

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.dynamic_stderr_handler import DynamicStderrHandler  # noqa: E402
from hooks_constants.project_paths_reader import (  # noqa: E402
    find_git_root,
    load_registry,
    registry_contains_path,
    registry_file_path,
)

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
