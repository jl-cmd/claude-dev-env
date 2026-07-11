from __future__ import annotations

import importlib
import sys
from pathlib import Path


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
_git_hooks_directory_string = str(SCRIPT_DIRECTORY)
while _git_hooks_directory_string in sys.path:
    sys.path.remove(_git_hooks_directory_string)
sys.path.insert(0, _git_hooks_directory_string)
for each_module_name in list(sys.modules):
    if each_module_name == "config" or each_module_name.startswith("config."):
        del sys.modules[each_module_name]
importlib.invalidate_caches()

import git_hooks_constants


def test_pre_push_gate_script_not_found_message_contains_path_placeholder() -> None:
    assert "{path}" in git_hooks_constants.PRE_PUSH_GATE_SCRIPT_NOT_FOUND_MESSAGE


def test_no_parseable_stdin_lines_message_exists_and_describes_problem() -> None:
    assert "no parseable stdin lines" in git_hooks_constants.NO_PARSEABLE_STDIN_LINES_MESSAGE


def test_no_parseable_stdin_lines_sentinel_is_distinct_sentinel_value() -> None:
    assert git_hooks_constants.NO_PARSEABLE_STDIN_LINES_SENTINEL is not None
    assert git_hooks_constants.NO_PARSEABLE_STDIN_LINES_SENTINEL != git_hooks_constants.DEFAULT_REMOTE_BASE_REFERENCE
