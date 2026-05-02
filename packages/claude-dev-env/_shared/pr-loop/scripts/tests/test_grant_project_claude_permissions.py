"""Smoke tests for grant_project_claude_permissions wiring.

Confirms the module imports cleanly with the constants now sourced from
config/claude_permissions_constants.py and config/claude_settings_keys_constants.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_grant_module() -> ModuleType:
    scripts_directory = Path(__file__).parent.parent
    parent_directory = str(scripts_directory.resolve())
    if parent_directory not in sys.path:
        sys.path.insert(0, parent_directory)
    sys.modules.pop("config", None)
    module_path = scripts_directory / "grant_project_claude_permissions.py"
    specification = importlib.util.spec_from_file_location(
        "grant_project_claude_permissions", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_module_imports_constants_from_config_modules() -> None:
    grant_module = _load_grant_module()
    assert grant_module.ALL_PERMISSION_ALLOW_TOOLS == ("Edit", "Write", "Read")
    assert "{project_path}" in grant_module.AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE
    assert grant_module.CLAUDE_SETTINGS_PERMISSIONS_KEY == "permissions"


def test_grant_module_guards_sys_path_insert_against_duplicates() -> None:
    """grant_project_claude_permissions.py must guard its sys.path.insert with a
    membership check so re-imports under test harnesses do not push duplicate
    entries (matching the pattern used by every other module in the directory)."""
    module_source = (
        Path(__file__).parent.parent / "grant_project_claude_permissions.py"
    ).read_text(encoding="utf-8")
    assert "if str(Path(__file__).resolve().parent) not in sys.path:" in module_source, (
        "grant_project_claude_permissions.py must guard sys.path.insert against "
        "duplicate entries on reload (consistent with sibling modules)"
    )
