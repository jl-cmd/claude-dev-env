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
    assert "owner-repo-pr-7" in rendered


def test_per_pr_workspace_diff_patch_template_uses_forward_slashes() -> None:
    run_temp_dir = Path("C:/Users/example/AppData/Local/Temp/bugteam-pr-376")
    workspace = path_resolver.per_pr_workspace(run_temp_dir, "owner", "repo", 376)
    assert "\\" not in workspace.diff_patch_template
    assert workspace.diff_patch_template == (
        "C:/Users/example/AppData/Local/Temp/bugteam-pr-376/"
        "pr-376/owner-repo-pr-376/loop-{loop}.patch"
    )


def test_per_pr_workspace_is_frozen() -> None:
    run_temp_dir = Path("/tmp/bugteam-pr-9")
    workspace = path_resolver.per_pr_workspace(run_temp_dir, "owner", "repo", 9)
    with pytest.raises(dataclasses.FrozenInstanceError):
        workspace.worktree = Path("/tmp/other")


def test_sanitize_branch_name_replaces_filesystem_unsafe_characters() -> None:
    assert path_resolver.sanitize_branch_name("feat/my-branch") == "feat-my-branch"


def test_build_run_name_uses_pr_number_for_single_pr() -> None:
    assert path_resolver.build_run_name(422, "feat/x", is_multi_pr=False) == "bugteam-pr-422"


def test_build_run_name_uses_sanitized_branch_for_multi_pr() -> None:
    assert path_resolver.build_run_name(422, "feat/x", is_multi_pr=True) == "bugteam-feat-x"


def test_slugify_pr_identity_joins_owner_repo_and_number() -> None:
    assert (
        path_resolver.slugify_pr_identity("jl-cmd", "claude-code-config", 422)
        == "jl-cmd-claude-code-config-pr-422"
    )


def test_outcome_xml_path_embeds_pr_and_loop() -> None:
    worktree_path = Path("/tmp/worktree")
    outcome_path = path_resolver.outcome_xml_path(worktree_path, 422, 3)
    assert outcome_path == worktree_path / ".bugteam-pr422-loop3.outcomes.xml"


def test_fix_outcome_xml_path_embeds_pr_and_loop() -> None:
    worktree_path = Path("/tmp/worktree")
    fix_outcome_path = path_resolver.fix_outcome_xml_path(worktree_path, 422, 3)
    assert fix_outcome_path == worktree_path / ".bugteam-pr422-loop3.fix-outcomes.xml"


def test_diff_patch_path_joins_slug_and_loop_filename() -> None:
    run_temp_dir = Path("/tmp/run")
    patch_path = path_resolver.diff_patch_path(
        run_temp_dir, "owner", "repo", 7, 2
    )
    assert patch_path == run_temp_dir / "owner-repo-pr-7" / "loop-2.patch"
