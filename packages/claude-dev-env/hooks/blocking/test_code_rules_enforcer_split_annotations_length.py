"""Behavior tests for the code_rules_annotations_length code-rules check module."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_annotations_length import (  # noqa: E402
    FUNCTION_LENGTH_BLOCKING_MESSAGE_SUFFIX,
    check_function_length,
    is_hook_infrastructure,
)

code_rules_enforcer = SimpleNamespace(
    FUNCTION_LENGTH_BLOCKING_MESSAGE_SUFFIX=FUNCTION_LENGTH_BLOCKING_MESSAGE_SUFFIX,
    check_function_length=check_function_length,
    is_hook_infrastructure=is_hook_infrastructure,
)


def test_should_treat_repo_relative_hook_path_as_hook_infrastructure() -> None:
    relative_hook_path = "packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py"
    assert code_rules_enforcer.is_hook_infrastructure(relative_hook_path) is True


def test_should_treat_backslash_repo_relative_hook_path_as_hook_infrastructure() -> None:
    relative_hook_path = "packages\\claude-dev-env\\hooks\\blocking\\code_rules_enforcer.py"
    assert code_rules_enforcer.is_hook_infrastructure(relative_hook_path) is True


def test_should_not_treat_unrelated_repo_relative_path_as_hook_infrastructure() -> None:
    relative_source_path = "packages/claude-dev-env/skills/bugteam/scripts/runner.py"
    assert code_rules_enforcer.is_hook_infrastructure(relative_source_path) is False


def test_should_exempt_repo_relative_hook_file_from_function_length() -> None:
    body_lines = "\n".join(f"    bound_{each_index} = {each_index}" for each_index in range(70))
    grown_function_source = "def grown_function() -> None:\n" + body_lines + "\n"
    relative_hook_path = "packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py"
    assert code_rules_enforcer.check_function_length(grown_function_source, relative_hook_path) == []


def test_function_length_message_does_not_cite_file_length_section() -> None:
    """The blocking message must cite a function-length basis, not the
    advisory file-length section (CODE_RULES §6.5)."""
    assert "6.5" not in code_rules_enforcer.FUNCTION_LENGTH_BLOCKING_MESSAGE_SUFFIX
    assert "Clean Code" in code_rules_enforcer.FUNCTION_LENGTH_BLOCKING_MESSAGE_SUFFIX
