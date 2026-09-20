"""Behavior tests for the agent-config carve-out and stale-trust-entry purge.

Covers two Bugbot findings on PR #467:
  - Deny rules must be written to permissions.deny so agent-config edits
    require explicit per-edit user approval.
  - Trust entries in autoMode.environment must be purged on grant
    (preventing accumulation across template revisions) and removed on
    revoke regardless of the exact template wording.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_module_from_path(module_name: str, module_path: Path) -> ModuleType:
    specification = importlib.util.spec_from_file_location(module_name, module_path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _scripts_directory() -> Path:
    return Path(__file__).parent.parent


def _load_common_module() -> ModuleType:
    scripts_directory = _scripts_directory()
    scripts_directory_str = str(scripts_directory.resolve())
    if scripts_directory_str not in sys.path:
        sys.path.insert(0, scripts_directory_str)
    return _load_module_from_path(
        "_claude_permissions_common",
        scripts_directory / "_claude_permissions_common.py",
    )


def _load_constants_module() -> ModuleType:
    return _load_module_from_path(
        "pr_loop_shared_constants.claude_permissions_constants",
        _scripts_directory()
        / "pr_loop_shared_constants"
        / "claude_permissions_constants.py",
    )


def test_template_constant_documents_agent_config_carveout() -> None:
    constants_module = _load_constants_module()
    template_text = constants_module.AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE
    assert "agent-config files always require explicit per-edit user approval" in (
        template_text
    )


def test_is_trust_entry_for_project_predicate_filters_by_prefix_and_project_path() -> (
    None
):
    common_module = _load_common_module()
    project_path_posix = "/fake/proj"
    trust_prefix = "Trusted local workspace:"
    wrong_prefix_entry = (
        f"Something else: {project_path_posix}/.claude/** with marker token"
    )
    different_project_entry = (
        "Trusted local workspace: /other/project/.claude/** unrelated"
    )
    matching_entry = (
        f"Trusted local workspace: {project_path_posix}/.claude/** any wording form"
    )
    predicate_cases: list[tuple[object, bool]] = [
        (42, False),
        (wrong_prefix_entry, False),
        (different_project_entry, False),
        (matching_entry, True),
    ]
    for candidate_entry, expected_result in predicate_cases:
        assert (
            common_module.is_trust_entry_for_project(
                candidate_entry, project_path_posix, trust_prefix
            )
            is expected_result
        )


def test_is_trust_entry_for_project_rejects_cross_project_suffix_collision() -> None:
    """When the project_path is a path suffix of an unrelated entry's path,
    the predicate must reject the unrelated entry (the boundary anchor case)."""
    common_module = _load_common_module()
    short_project_path = "/projects/foo"
    trust_prefix = "Trusted local workspace:"
    longer_unrelated_path_entry = (
        "Trusted local workspace: /Users/example/projects/foo/.claude/** unrelated path"
    )
    assert (
        common_module.is_trust_entry_for_project(
            longer_unrelated_path_entry, short_project_path, trust_prefix
        )
        is False
    )
    quoted_matching_entry = (
        f'Trusted local workspace: "{short_project_path}/.claude/**" quoted form'
    )
    assert (
        common_module.is_trust_entry_for_project(
            quoted_matching_entry, short_project_path, trust_prefix
        )
        is True
    )
