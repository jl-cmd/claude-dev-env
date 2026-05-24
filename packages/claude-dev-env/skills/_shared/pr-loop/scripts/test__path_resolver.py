"""Tests for _path_resolver.per_pr_workspace typed structure."""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _load_path_resolver() -> ModuleType:
    module_path = _SCRIPTS_DIR / "_path_resolver.py"
    spec = importlib.util.spec_from_file_location("_path_resolver", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_path_resolver"] = module
    spec.loader.exec_module(module)
    return module


path_resolver = _load_path_resolver()


def test_per_pr_workspace_returns_typed_structure_with_concrete_fields() -> None:
    run_temp_dir = Path("/tmp/bugteam-pr-422")
    workspace = path_resolver.per_pr_workspace(
        run_temp_dir, "jl-cmd", "claude-code-config", 422
    )
    assert isinstance(workspace, path_resolver.PerPrWorkspace)
    assert isinstance(workspace.worktree, Path)
    assert workspace.worktree == run_temp_dir / "pr-422" / "worktree"
    assert isinstance(workspace.diff_patch_template, str)
    assert isinstance(workspace.outcome_xml_template, str)
    assert isinstance(workspace.fix_outcome_xml_template, str)


def test_per_pr_workspace_diff_patch_template_carries_loop_placeholder() -> None:
    run_temp_dir = Path("/tmp/bugteam-pr-7")
    workspace = path_resolver.per_pr_workspace(run_temp_dir, "owner", "repo", 7)
    rendered = workspace.diff_patch_template.format(loop=3)
    assert rendered.endswith("loop-3.patch")
    assert "owner-repo-pr-7" in rendered.replace("\\", "/")


def test_per_pr_workspace_is_frozen() -> None:
    run_temp_dir = Path("/tmp/bugteam-pr-9")
    workspace = path_resolver.per_pr_workspace(run_temp_dir, "owner", "repo", 9)
    with pytest.raises(dataclasses.FrozenInstanceError):
        workspace.worktree = Path("/tmp/other")
