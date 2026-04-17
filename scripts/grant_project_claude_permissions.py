"""Grant Edit/Write/Read permissions on the current directory's .claude tree.

Run from the project root whose .claude/** you want a Claude Code session
(including spawned subagents) to edit without prompting. Writes idempotent
entries into the user-scope settings at ~/.claude/settings.json and prints
the four changes applied.
"""

import json
from pathlib import Path
from typing import Any


CLAUDE_USER_SETTINGS_PATH: Path = Path.home() / ".claude" / "settings.json"
PERMISSION_ALLOW_TOOLS: tuple[str, ...] = ("Edit", "Write", "Read")
AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE: str = (
    "Trusted local workspace: {project_path}/.claude/** is the user's "
    "project Claude Code config tree; edits inside are routine"
)
JSON_INDENT_SPACES: int = 2


def get_current_project_path() -> str:
    return str(Path.cwd()).replace("\\", "/")


def build_permission_rule(tool_name: str, project_path: str) -> str:
    return f"{tool_name}({project_path}/.claude/**)"


def build_permission_rules(project_path: str) -> list[str]:
    return [
        build_permission_rule(each_tool, project_path)
        for each_tool in PERMISSION_ALLOW_TOOLS
    ]


def load_settings(settings_path: Path) -> dict[str, Any]:
    if not settings_path.exists():
        return {}
    return json.loads(settings_path.read_text(encoding="utf-8"))


def save_settings(settings_path: Path, settings: dict[str, Any]) -> None:
    settings_path.write_text(
        json.dumps(settings, indent=JSON_INDENT_SPACES), encoding="utf-8"
    )


def append_if_missing(target_list: list[str], new_value: str) -> bool:
    if new_value in target_list:
        return False
    target_list.append(new_value)
    return True


def add_rules_to_allow_list(settings: dict[str, Any], rules_to_add: list[str]) -> int:
    permissions_section = settings.setdefault("permissions", {})
    existing_allow_list = permissions_section.setdefault("allow", [])
    return sum(
        1
        for each_rule in rules_to_add
        if append_if_missing(existing_allow_list, each_rule)
    )


def add_directory_to_additional_directories(
    settings: dict[str, Any], directory_path: str
) -> bool:
    permissions_section = settings.setdefault("permissions", {})
    existing_directories = permissions_section.setdefault("additionalDirectories", [])
    return append_if_missing(existing_directories, directory_path)


def add_auto_mode_environment_entry(settings: dict[str, Any], entry_text: str) -> bool:
    auto_mode_section = settings.setdefault("autoMode", {})
    existing_environment = auto_mode_section.setdefault("environment", [])
    return append_if_missing(existing_environment, entry_text)


def grant_permissions_for_current_directory() -> None:
    project_path = get_current_project_path()
    permission_rules = build_permission_rules(project_path)
    environment_entry = AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE.format(
        project_path=project_path
    )
    settings = load_settings(CLAUDE_USER_SETTINGS_PATH)
    rules_added_count = add_rules_to_allow_list(settings, permission_rules)
    directory_added = add_directory_to_additional_directories(settings, project_path)
    environment_added = add_auto_mode_environment_entry(settings, environment_entry)
    save_settings(CLAUDE_USER_SETTINGS_PATH, settings)
    print(f"Project path: {project_path}")
    print(f"Settings file: {CLAUDE_USER_SETTINGS_PATH}")
    print(f"Allow rules added: {rules_added_count} of {len(permission_rules)}")
    print(f"Additional directory added: {directory_added}")
    print(f"Auto-mode environment entry added: {environment_added}")


if __name__ == "__main__":
    grant_permissions_for_current_directory()
