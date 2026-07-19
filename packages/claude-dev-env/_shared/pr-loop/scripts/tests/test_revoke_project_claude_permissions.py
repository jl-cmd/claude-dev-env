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

import pytest


def _load_revoke_module() -> ModuleType:
    scripts_directory = Path(__file__).parent.parent
    parent_directory = str(scripts_directory.resolve())
    if parent_directory in sys.path:
        sys.path.remove(parent_directory)
    sys.path.insert(0, parent_directory)
    for each_module_name in list(sys.modules):
        if each_module_name == "pr_loop_shared_constants" or each_module_name.startswith(
            "pr_loop_shared_constants."
        ):
            del sys.modules[each_module_name]
        if each_module_name in {
            "_claude_permissions_common",
            "revoke_project_claude_permissions",
            "stale_worktree_rule_sweep",
        }:
            del sys.modules[each_module_name]
    module_path = scripts_directory / "revoke_project_claude_permissions.py"
    specification = importlib.util.spec_from_file_location(
        "revoke_project_claude_permissions", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _write_legacy_form_settings_file(
    settings_path: Path, revoke_module: ModuleType, project_path: str
) -> None:
    """Seed a settings file with only pre-#158 legacy Write()/Glob() rules.

    One Write(/.claude/**) allow rule, and a Write(/.claude/<pattern>) plus
    a Glob(/.claude/<pattern>) deny rule for every agent-config path
    pattern -- the exact stranded-rule shapes issue #233 describes."""
    legacy_allow_rule = f"Write({project_path}/.claude/**)"
    legacy_deny_rules = [
        f"Write({project_path}/.claude/{each_pattern})"
        for each_pattern in revoke_module.ALL_AGENT_CONFIG_PATH_PATTERNS
    ] + [
        f"Glob({project_path}/.claude/{each_pattern})"
        for each_pattern in revoke_module.ALL_AGENT_CONFIG_PATH_PATTERNS
    ]
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(
            {
                "permissions": {
                    "allow": [legacy_allow_rule],
                    "deny": legacy_deny_rules,
                }
            }
        ),
        encoding="utf-8",
    )


def test_revoke_reaps_legacy_write_and_glob_rules_leaving_no_dead_structure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A revoke run reaps the legacy Write()/Glob() rules an older grant left.

    No current-form Edit/Read rule is present, so a revoke run that reaps
    only the mint set would remove nothing and leave every legacy rule
    stranded. After revoke runs, the permissions section is gone entirely,
    matching the module's "no dead structure" contract."""
    revoke_module = _load_revoke_module()
    project_directory = tmp_path / "project"
    project_directory.mkdir()
    (project_directory / ".git").mkdir()
    settings_path = tmp_path / "home" / ".claude" / "settings.json"
    project_path = str(project_directory).replace("\\", "/")
    _write_legacy_form_settings_file(settings_path, revoke_module, project_path)

    monkeypatch.setattr(
        revoke_module, "get_claude_user_settings_path", lambda: settings_path
    )
    monkeypatch.chdir(project_directory)
    revoke_module.revoke_permissions_for_current_directory()

    saved_settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "permissions" not in saved_settings


def test_revoke_strips_inert_write_glob_notebookedit_on_foreign_worktree_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Global inert strip removes Write/Glob/NotebookEdit for any path.

    Foreign worktree rules are outside the cwd project's exact path, so
    project-scoped #315 reap alone leaves them; revoke must strip by tool."""
    revoke_module = _load_revoke_module()
    project_directory = tmp_path / "operator_project"
    project_directory.mkdir()
    (project_directory / ".git").mkdir()
    settings_path = tmp_path / "home" / ".claude" / "settings.json"
    foreign_worktree = (
        "c:/Users/jon/.claude/worktrees/claude-dev-env-702a0c2055d2/other-wt"
    )
    live_other_project = "C:/dev/live-other-project"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(
            {
                "permissions": {
                    "allow": [
                        f"Write({foreign_worktree}/**)",
                        f"NotebookEdit(**/.claude/worktrees/**)",
                        f"Edit({live_other_project}/.claude/**)",
                        f"Read({live_other_project}/.claude/**)",
                        "Bash(echo hi)",
                    ],
                    "deny": [
                        f"Glob({foreign_worktree}/.claude/hooks/**)",
                        f"Write({foreign_worktree}/.claude/skills/**)",
                        f"Edit({live_other_project}/.claude/hooks/**)",
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        revoke_module, "get_claude_user_settings_path", lambda: settings_path
    )
    monkeypatch.chdir(project_directory)
    revoke_module.revoke_permissions_for_current_directory()

    saved_settings = json.loads(settings_path.read_text(encoding="utf-8"))
    permissions_section = saved_settings["permissions"]
    allow_rules = permissions_section["allow"]
    deny_rules = permissions_section["deny"]
    assert allow_rules == [
        f"Edit({live_other_project}/.claude/**)",
        f"Read({live_other_project}/.claude/**)",
        "Bash(echo hi)",
    ]
    assert deny_rules == [f"Edit({live_other_project}/.claude/hooks/**)"]
    for each_rule in allow_rules + deny_rules:
        tool_name = each_rule.split("(", 1)[0]
        assert tool_name not in ("Write", "Glob", "NotebookEdit")


def test_revoke_from_home_reaps_dollar_home_grant_shapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When cwd is the user home, Edit($HOME/.claude/**) shapes are reaped."""
    revoke_module = _load_revoke_module()
    home_directory = tmp_path / "fake_home"
    home_directory.mkdir()
    (home_directory / ".git").mkdir()
    (home_directory / ".claude").mkdir()
    settings_path = tmp_path / "settings_home" / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    live_other_project = "C:/dev/unrelated-live"
    settings_path.write_text(
        json.dumps(
            {
                "permissions": {
                    "allow": [
                        "Edit($HOME/.claude/**)",
                        "Write($HOME/.claude/**)",
                        "Read($HOME/.claude/**)",
                        f"Edit({live_other_project}/.claude/**)",
                    ],
                    "deny": [
                        "Edit($HOME/.claude/hooks/**)",
                        "Glob($HOME/.claude/skills/**)",
                        f"Read({live_other_project}/.claude/hooks/**)",
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        revoke_module, "get_claude_user_settings_path", lambda: settings_path
    )
    monkeypatch.setattr(
        Path, "home", classmethod(lambda _cls: home_directory), raising=True
    )
    monkeypatch.chdir(home_directory)
    revoke_module.revoke_permissions_for_current_directory()

    saved_settings = json.loads(settings_path.read_text(encoding="utf-8"))
    permissions_section = saved_settings["permissions"]
    allow_rules = permissions_section["allow"]
    deny_rules = permissions_section["deny"]
    assert allow_rules == [f"Edit({live_other_project}/.claude/**)"]
    assert deny_rules == [f"Read({live_other_project}/.claude/hooks/**)"]
    assert not any("$HOME" in each_rule for each_rule in allow_rules + deny_rules)


def test_module_imports_constants_from_config_modules() -> None:
    revoke_module = _load_revoke_module()
    assert revoke_module.ALL_PERMISSION_ALLOW_TOOLS == ("Edit", "Read")
    assert revoke_module.AUTO_MODE_ENVIRONMENT_ENTRY_PREFIX == (
        "Trusted local workspace:"
    )
    assert revoke_module.CLAUDE_SETTINGS_PERMISSIONS_KEY == "permissions"


def test_remove_inert_file_permission_rules_strips_only_inert_tools() -> None:
    revoke_module = _load_revoke_module()
    settings: dict[str, object] = {
        "permissions": {
            "allow": [
                "Write(/foreign/.claude/**)",
                "NotebookEdit(**/.claude/worktrees/**)",
                "Edit(/live/.claude/**)",
            ],
            "deny": ["Glob(/foreign/.claude/hooks/**)", "Read(/live/.claude/hooks/**)"],
        }
    }
    removed_count = revoke_module.remove_inert_file_permission_rules(settings)
    assert removed_count == 3
    permissions_section = _section_of(settings, "permissions")
    assert permissions_section["allow"] == ["Edit(/live/.claude/**)"]
    assert permissions_section["deny"] == ["Read(/live/.claude/hooks/**)"]


def test_strip_inert_rules_from_settings_file_missing_path_is_noop(
    tmp_path: Path,
) -> None:
    revoke_module = _load_revoke_module()
    missing_path = revoke_module.get_claude_project_local_settings_path(tmp_path)
    assert not missing_path.is_file()
    assert revoke_module.strip_inert_rules_from_settings_file(missing_path) == 0
    assert not missing_path.is_file()


def test_strip_inert_rules_from_settings_file_updates_project_local_file(
    tmp_path: Path,
) -> None:
    revoke_module = _load_revoke_module()
    local_settings_path = revoke_module.get_claude_project_local_settings_path(tmp_path)
    local_settings_path.parent.mkdir(parents=True, exist_ok=True)
    local_settings_path.write_text(
        json.dumps(
            {
                "permissions": {
                    "allow": [
                        "Write(//**/.claude/**)",
                        r"Write(C:\\**\\.claude\\**)",
                        "Edit(C:/dev/live/.claude/**)",
                        "Bash(echo hi)",
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    removed_count = revoke_module.strip_inert_rules_from_settings_file(
        local_settings_path
    )
    assert removed_count == 2
    saved_settings = json.loads(local_settings_path.read_text(encoding="utf-8"))
    allow_rules = saved_settings["permissions"]["allow"]
    assert allow_rules == ["Edit(C:/dev/live/.claude/**)", "Bash(echo hi)"]


def test_revoke_strips_inert_rules_from_project_settings_local_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """User settings may already be clean; project settings.local still warns.

    Claude loads .claude/settings.local.json for the cwd project; revoke must
    strip inert Write/Glob/NotebookEdit there too."""
    revoke_module = _load_revoke_module()
    project_directory = tmp_path / "project"
    project_directory.mkdir()
    (project_directory / ".git").mkdir()
    user_settings_path = tmp_path / "home" / ".claude" / "settings.json"
    user_settings_path.parent.mkdir(parents=True, exist_ok=True)
    user_settings_path.write_text(json.dumps({"permissions": {"allow": []}}), encoding="utf-8")
    local_settings_path = revoke_module.get_claude_project_local_settings_path(
        project_directory
    )
    local_settings_path.parent.mkdir(parents=True, exist_ok=True)
    local_settings_path.write_text(
        json.dumps(
            {
                "permissions": {
                    "allow": [
                        "Write(//**/.claude/**)",
                        r"Write(C:\\**\\.claude\\**)",
                        "Read(C:/other/.claude/**)",
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        revoke_module, "get_claude_user_settings_path", lambda: user_settings_path
    )
    monkeypatch.chdir(project_directory)
    revoke_module.revoke_permissions_for_current_directory()

    local_settings = json.loads(local_settings_path.read_text(encoding="utf-8"))
    allow_rules = local_settings["permissions"]["allow"]
    assert allow_rules == ["Read(C:/other/.claude/**)"]
    assert not any(
        each_rule.split("(", 1)[0] in ("Write", "Glob", "NotebookEdit")
        for each_rule in allow_rules
        if isinstance(each_rule, str) and "(" in each_rule
    )


def test_build_project_scoped_allow_rules_for_reap_includes_legacy_tools() -> None:
    revoke_module = _load_revoke_module()
    all_allow_rules = revoke_module.build_project_scoped_allow_rules_for_reap(
        "/repo/project"
    )
    assert "Edit(/repo/project/.claude/**)" in all_allow_rules
    assert "Write(/repo/project/.claude/**)" in all_allow_rules
    assert "Read(/repo/project/.claude/**)" in all_allow_rules
    assert "Glob(/repo/project/.claude/**)" in all_allow_rules


def test_build_project_scoped_deny_rules_for_reap_includes_legacy_tools() -> None:
    revoke_module = _load_revoke_module()
    all_deny_rules = revoke_module.build_project_scoped_deny_rules_for_reap(
        "/repo/project"
    )
    assert "Edit(/repo/project/.claude/hooks/**)" in all_deny_rules
    assert "Write(/repo/project/.claude/hooks/**)" in all_deny_rules
    assert "Glob(/repo/project/.claude/skills/**)" in all_deny_rules


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


def _section_of(settings: dict[str, object], section_key: str) -> dict[str, object]:
    section = settings[section_key]
    assert isinstance(section, dict)
    return section


def test_remove_values_from_list_removes_matching_strings() -> None:
    revoke_module = _load_revoke_module()
    target_list: list[object] = ["keep", "drop", 7, "drop"]
    removed_count = revoke_module.remove_values_from_list(target_list, {"drop"})
    assert removed_count == 2
    assert target_list == ["keep", 7]


def test_remove_rules_from_allow_list_removes_named_rules() -> None:
    revoke_module = _load_revoke_module()
    settings: dict[str, object] = {
        "permissions": {
            "allow": ["Edit(/proj/.claude/**)", "Read(/proj/.claude/**)"],
        },
    }
    removed_count = revoke_module.remove_rules_from_allow_list(
        settings, ["Edit(/proj/.claude/**)"]
    )
    assert removed_count == 1
    assert _section_of(settings, "permissions")["allow"] == ["Read(/proj/.claude/**)"]


def test_remove_rules_from_deny_list_removes_named_rules() -> None:
    revoke_module = _load_revoke_module()
    settings: dict[str, object] = {
        "permissions": {
            "deny": ["Edit(/proj/.claude/hooks/**)", "Read(/proj/.claude/hooks/**)"],
        },
    }
    removed_count = revoke_module.remove_rules_from_deny_list(
        settings, ["Edit(/proj/.claude/hooks/**)"]
    )
    assert removed_count == 1
    assert _section_of(settings, "permissions")["deny"] == [
        "Read(/proj/.claude/hooks/**)"
    ]


def test_remove_directory_from_additional_directories_removes_entry() -> None:
    revoke_module = _load_revoke_module()
    settings: dict[str, object] = {
        "permissions": {
            "additionalDirectories": ["/proj", "/other"],
        },
    }
    removed_count = revoke_module.remove_directory_from_additional_directories(
        settings, "/proj"
    )
    assert removed_count == 1
    assert _section_of(settings, "permissions")["additionalDirectories"] == ["/other"]


def test_remove_trust_entries_for_project_removes_every_project_entry() -> None:
    revoke_module = _load_revoke_module()
    trust_prefix = revoke_module.AUTO_MODE_ENVIRONMENT_ENTRY_PREFIX
    project_entry_a = "Trusted local workspace: /proj/.claude/** wording A"
    project_entry_b = "Trusted local workspace: /proj/.claude/** wording B"
    other_project_entry = "Trusted local workspace: /other/.claude/** unrelated"
    settings: dict[str, object] = {
        "autoMode": {
            "environment": [project_entry_a, project_entry_b, other_project_entry],
        },
    }
    removed_count = revoke_module.remove_trust_entries_for_project(
        settings, "/proj", trust_prefix
    )
    assert removed_count == 2
    assert _section_of(settings, "autoMode")["environment"] == [other_project_entry]


def test_prune_settings_after_revoke_drops_empty_sections() -> None:
    revoke_module = _load_revoke_module()
    settings: dict[str, object] = {
        "permissions": {"allow": [], "deny": []},
        "autoMode": {"environment": []},
    }
    revoke_module.prune_settings_after_revoke(settings)
    assert "permissions" not in settings
    assert "autoMode" not in settings
