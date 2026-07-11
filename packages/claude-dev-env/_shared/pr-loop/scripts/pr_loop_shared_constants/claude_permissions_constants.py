"""Constants shared by grant_project_claude_permissions and revoke_project_claude_permissions."""

from pathlib import Path

from pr_loop_shared_constants.preflight_constants import GIT_DIRECTORY_NAME

__all__ = (
    "ALL_AGENT_CONFIG_DENY_TOOLS",
    "ALL_AGENT_CONFIG_PATH_PATTERNS",
    "ALL_PERMISSION_ALLOW_TOOLS",
    "ALL_TRUST_ENTRY_PROJECT_PATH_BOUNDARY_QUOTE_CHARACTERS",
    "AUTO_MODE_ENVIRONMENT_ENTRY_PREFIX",
    "AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE",
    "CLAUDE_SETTINGS_DIRECTORY_NAME",
    "CLAUDE_SETTINGS_FILENAME",
    "GIT_DIRECTORY_NAME",
    "TEXT_FILE_ENCODING",
    "UNIQUE_TEMPORARY_SUFFIX_BYTE_LENGTH",
    "get_claude_user_settings_path",
)


ALL_PERMISSION_ALLOW_TOOLS: tuple[str, ...] = ("Edit", "Write", "Read")

ALL_AGENT_CONFIG_DENY_TOOLS: tuple[str, ...] = ("Edit", "Write", "Read", "Glob")

ALL_AGENT_CONFIG_PATH_PATTERNS: tuple[str, ...] = (
    "settings*.json",
    "hooks/**",
    "commands/**",
    "agents/**",
    "skills/**",
    "mcp.json",
    "CLAUDE.md",
)

AUTO_MODE_ENVIRONMENT_ENTRY_PREFIX: str = "Trusted local workspace:"


def _describe_agent_config_pattern_for_humans(agent_config_path_pattern: str) -> str:
    glob_suffix_under_directory = "/**"
    file_name_for_special_phrasing = "mcp.json"
    if agent_config_path_pattern.endswith(glob_suffix_under_directory):
        directory_name = agent_config_path_pattern[
            : -len(glob_suffix_under_directory)
        ]
        return f"anything under {directory_name}/"
    if agent_config_path_pattern == file_name_for_special_phrasing:
        return f"the {file_name_for_special_phrasing} file"
    return agent_config_path_pattern


def _build_agent_config_pattern_phrase(
    all_agent_config_path_patterns: tuple[str, ...],
) -> str:
    all_described_patterns: list[str] = [
        _describe_agent_config_pattern_for_humans(each_pattern)
        for each_pattern in all_agent_config_path_patterns
    ]
    if len(all_described_patterns) <= 1:
        return ", ".join(all_described_patterns)
    leading_phrase_parts = ", ".join(all_described_patterns[:-1])
    final_phrase_part = all_described_patterns[-1]
    return f"{leading_phrase_parts}, and {final_phrase_part}"


_AGENT_CONFIG_PATTERN_PHRASE: str = _build_agent_config_pattern_phrase(
    ALL_AGENT_CONFIG_PATH_PATTERNS
)

AUTO_MODE_ENVIRONMENT_ENTRY_TEMPLATE: str = (
    f"Trusted local workspace: Files under {{project_path}}/.claude/** inherit "
    f"the workspace's trust for Edit, Write, Read, and Glob operations EXCEPT "
    f"for agent-config files: {_AGENT_CONFIG_PATTERN_PHRASE}. Edits to those "
    f"agent-config files always require explicit per-edit user approval."
)

ALL_TRUST_ENTRY_PROJECT_PATH_BOUNDARY_QUOTE_CHARACTERS: tuple[str, ...] = ('"', "'")

CLAUDE_SETTINGS_DIRECTORY_NAME: str = ".claude"

CLAUDE_SETTINGS_FILENAME: str = "settings.json"

TEXT_FILE_ENCODING: str = "utf-8"

UNIQUE_TEMPORARY_SUFFIX_BYTE_LENGTH: int = 8


def get_claude_user_settings_path() -> Path:
    return Path.home() / CLAUDE_SETTINGS_DIRECTORY_NAME / CLAUDE_SETTINGS_FILENAME
