"""Smoke tests for revoke_project_claude_permissions wiring.

Confirms the module imports cleanly with the constants now sourced from
pr_loop_shared_constants/claude_permissions_constants.py and
pr_loop_shared_constants/claude_settings_keys_constants.py.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_revoke_module() -> ModuleType:
    scripts_directory = Path(__file__).parent.parent
    parent_directory = str(scripts_directory.resolve())
    if parent_directory not in sys.path:
        sys.path.insert(0, parent_directory)
    module_path = scripts_directory / "revoke_project_claude_permissions.py"
    specification = importlib.util.spec_from_file_location(
        "revoke_project_claude_permissions", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_module_imports_constants_from_config_modules() -> None:
    revoke_module = _load_revoke_module()
    assert revoke_module.ALL_REVOKE_PERMISSION_TOOLS == (
        "Edit",
        "Write",
        "Read",
        "Glob",
        "NotebookEdit",
    )
    assert revoke_module.AUTO_MODE_ENVIRONMENT_ENTRY_PREFIX == (
        "Trusted local workspace:"
    )
    assert revoke_module.CLAUDE_SETTINGS_PERMISSIONS_KEY == "permissions"


def test_revoke_removes_legacy_permission_rules(
    monkeypatch, tmp_path: Path
) -> None:
    revoke_module = _load_revoke_module()
    project_path = tmp_path / "project"
    project_path.mkdir()
    (project_path / ".git").mkdir()
    settings_path = tmp_path / "settings.json"
    legacy_allow_rules = [
        f"{tool_name}({project_path}/.claude/**)"
        for tool_name in ("Write", "Glob", "NotebookEdit")
    ]
    legacy_deny_rules = [
        f"{tool_name}({project_path}/.claude/{path_pattern})"
        for tool_name in ("Write", "Glob", "NotebookEdit")
        for path_pattern in ("settings*.json", "hooks/**")
    ]
    unrelated_allow_rule = "Glob(/other-project/.claude/**)"
    settings_path.write_text(
        json.dumps(
            {
                "permissions": {
                    "allow": [*legacy_allow_rules, unrelated_allow_rule],
                    "deny": legacy_deny_rules,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(project_path)
    monkeypatch.setattr(
        revoke_module, "get_claude_user_settings_path", lambda: settings_path
    )

    revoke_module.revoke_permissions_for_current_directory()

    saved_settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert saved_settings == {"permissions": {"allow": [unrelated_allow_rule]}}


def test_revoke_module_guards_sys_path_insert_against_duplicates() -> None:
    """revoke_project_claude_permissions.py must guard its sys.path.insert with a
    membership check so re-imports under test harnesses do not push duplicate
    entries (consistent with sibling modules in the same directory)."""
    module_source = (
        Path(__file__).parent.parent / "revoke_project_claude_permissions.py"
    ).read_text(encoding="utf-8")
    assert "if parent_directory not in sys.path:" in module_source, (
        "revoke_project_claude_permissions.py must guard sys.path.insert against "
        "duplicate entries on reload (consistent with sibling modules)"
    )
