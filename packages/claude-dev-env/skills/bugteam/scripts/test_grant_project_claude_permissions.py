"""Regression tests for grant_project_claude_permissions module-import behavior.

Pins the loop1-2 fix: a defensive cache pop above sys.path.insert evicts every
cached `config` and `config.<submodule>` entry so the from-import binds against
scripts/config/ rather than a stale parent package shadowing it.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType


_script_directory = str(Path(__file__).resolve().parent)
if _script_directory not in sys.path:
    sys.path.insert(0, _script_directory)


def _reload_grant_with_stale_config_cache() -> ModuleType:
    fake_submodule_name = "config.claude_permissions_common_constants"
    fake_parent_name = "config"
    sentinel_module_a = ModuleType(fake_parent_name)
    sentinel_module_b = ModuleType(fake_submodule_name)
    sys.modules[fake_parent_name] = sentinel_module_a
    sys.modules[fake_submodule_name] = sentinel_module_b
    try:
        target_module = sys.modules.get("grant_project_claude_permissions")
        if target_module is None:
            target_module = importlib.import_module("grant_project_claude_permissions")
        else:
            target_module = importlib.reload(target_module)
    finally:
        sys.modules.pop(fake_parent_name, None)
        sys.modules.pop(fake_submodule_name, None)
    return target_module


def test_grant_module_imports_when_config_is_already_cached(tmp_path: Path) -> None:
    """Module import must succeed even when sys.modules carries a stale `config`.

    Regression for loop1-2 — invokes is_valid_project_root after reload to
    prove the binding came from scripts/config/ rather than the sentinel.
    """
    reloaded_module = _reload_grant_with_stale_config_cache()
    not_a_project_root = tmp_path / "empty_dir"
    not_a_project_root.mkdir()
    assert reloaded_module.is_valid_project_root(not_a_project_root) is False, (
        "is_valid_project_root must run normally after the reload — proof that "
        "the from-import bound real constants, not the stale cached ones"
    )
    a_git_project_root = tmp_path / "git_project"
    (a_git_project_root / ".git").mkdir(parents=True)
    assert reloaded_module.is_valid_project_root(a_git_project_root) is True
