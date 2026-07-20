#!/usr/bin/env python3
"""Apply lean MCP policy: drop heavy stdio servers and disable playwright plugin.

Heavy per-session stdio MCP (mcpvault/obsidian, serena, playwright) multiplies
cmd/node/python trees across Claude Code, Claude Desktop, and Grok (which
imports ``~/.claude.json`` MCP by default). This CLI rewrites known config
paths to keep HTTP MCP only for those names, disables the playwright plugin
flag, and optionally turns off Grok Claude MCP compat via grok_config_path.

::

    python apply_lean_mcp_policy.py --dry-run
    python apply_lean_mcp_policy.py --apply --disable-grok-claude-mcps
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

_scripts_dir = str(Path(__file__).resolve().parent.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from dev_env_scripts_constants.mcp_lifecycle_constants import (  # noqa: E402
    ALL_HEAVY_STDIO_COMMAND_MARKERS,
    ALL_HEAVY_STDIO_MCP_NAME_MARKERS,
    ALL_PLAYWRIGHT_PLUGIN_KEYS,
    BACKUP_SUFFIX_SEPARATOR,
    BACKUP_TIMESTAMP_FORMAT,
    CLAUDE_DESKTOP_CONFIG_PATH,
    CLAUDE_DOT_CLAUDE_JSON_PATH,
    CLAUDE_JSON_PATH,
    CLAUDE_SETTINGS_JSON_PATH,
    CLAUDE_SETTINGS_LOCAL_JSON_PATH,
    COMMAND_LINE_JOIN_SEPARATOR,
    ENABLED_PLUGINS_KEY,
    GROK_COMPAT_CLAUDE_BLOCK,
    GROK_COMPAT_CLAUDE_MCPS_DISABLED_LINE,
    GROK_COMPAT_CLAUDE_SECTION_HEADER,
    GROK_CONFIG_TOML_PATH,
    HTTP_SERVER_TYPE,
    JSON_INDENT_SPACES,
    MCP_SERVERS_KEY,
    SERVER_ALWAYS_LOAD_KEY,
    SERVER_ARGS_KEY,
    SERVER_COMMAND_KEY,
    SERVER_TYPE_KEY,
    SERVER_URL_KEY,
    UTF8_ENCODING,
)


def _build_command_line_text(all_server_fields: dict[str, object]) -> str:
    all_parts: list[str] = []
    command_text = all_server_fields.get(SERVER_COMMAND_KEY)
    if isinstance(command_text, str):
        all_parts.append(command_text)
    all_arguments = all_server_fields.get(SERVER_ARGS_KEY)
    if isinstance(all_arguments, list):
        for each_argument in all_arguments:
            all_parts.append(str(each_argument))
    return COMMAND_LINE_JOIN_SEPARATOR.join(all_parts).casefold()


def _is_http_mcp_server(all_server_fields: dict[str, object]) -> bool:
    server_type = all_server_fields.get(SERVER_TYPE_KEY)
    if isinstance(server_type, str) and server_type.casefold() == HTTP_SERVER_TYPE:
        return True
    server_url = all_server_fields.get(SERVER_URL_KEY)
    return isinstance(server_url, str) and bool(server_url.strip())


def _is_heavy_stdio_mcp_server(
    server_name: str,
    all_server_fields: dict[str, object],
) -> bool:
    if _is_http_mcp_server(all_server_fields):
        return False
    lowered_server_name = server_name.casefold()
    for each_name_marker in ALL_HEAVY_STDIO_MCP_NAME_MARKERS:
        if each_name_marker.casefold() in lowered_server_name:
            return True
    command_line_text = _build_command_line_text(all_server_fields)
    for each_command_marker in ALL_HEAVY_STDIO_COMMAND_MARKERS:
        if each_command_marker.casefold() in command_line_text:
            return True
    return False


def filter_mcp_servers(
    server_by_name: dict[str, object],
) -> tuple[dict[str, object], list[str]]:
    """Drop heavy stdio servers; clear alwaysLoad on any remaining entry.

    Args:
        server_by_name: Original mcpServers map.

    Returns:
        (filtered map, removed server names).
    """
    filtered_server_by_name: dict[str, object] = {}
    all_removed_server_names: list[str] = []
    for each_server_name, each_server_fields in server_by_name.items():
        if not isinstance(each_server_fields, dict):
            filtered_server_by_name[each_server_name] = each_server_fields
            continue
        if _is_heavy_stdio_mcp_server(
            server_name=each_server_name,
            all_server_fields=each_server_fields,
        ):
            all_removed_server_names.append(each_server_name)
            continue
        cleaned_server_fields = dict(each_server_fields)
        cleaned_server_fields.pop(SERVER_ALWAYS_LOAD_KEY, None)
        filtered_server_by_name[each_server_name] = cleaned_server_fields
    return filtered_server_by_name, all_removed_server_names


def _disable_playwright_plugins(
    all_plugin_enabled_by_name: dict[str, object],
) -> tuple[dict[str, object], list[str]]:
    updated_plugins = dict(all_plugin_enabled_by_name)
    all_changed_plugin_keys: list[str] = []
    for each_plugin_key in ALL_PLAYWRIGHT_PLUGIN_KEYS:
        if each_plugin_key not in updated_plugins:
            continue
        if updated_plugins.get(each_plugin_key) is False:
            continue
        updated_plugins[each_plugin_key] = False
        all_changed_plugin_keys.append(each_plugin_key)
    return updated_plugins, all_changed_plugin_keys


def _backup_file(target_path: Path) -> Path:
    timestamp_text = datetime.now(timezone.utc).strftime(BACKUP_TIMESTAMP_FORMAT)
    backup_path = target_path.with_name(
        f"{target_path.name}{BACKUP_SUFFIX_SEPARATOR}{timestamp_text}"
    )
    shutil.copy2(target_path, backup_path)
    return backup_path


def _rewrite_json_top_level_key(
    configuration_path: Path,
    *,
    top_level_key: str,
    changed_names_summary_key: str,
    transform_fn: Callable[[dict[str, object]], tuple[dict[str, object], list[str]]],
    is_dry_run: bool,
) -> dict[str, object]:
    """Rewrite one top-level dict key of a JSON config file via transform_fn.

    Args:
        configuration_path: Path to a JSON config file.
        top_level_key: Top-level dict key to read and rewrite.
        changed_names_summary_key: Summary key holding transform_fn's changed names.
        transform_fn: Maps the current top-level dict to (updated dict, changed names).
        is_dry_run: When True, do not write.

    Returns:
        Summary dictionary for the file.
    """
    summary: dict[str, object] = {
        "path": str(configuration_path),
        "changed": False,
        changed_names_summary_key: [],
        "skipped": False,
    }
    if not configuration_path.is_file():
        summary["skipped"] = True
        summary["reason"] = "missing"
        return summary
    try:
        configuration_payload = json.loads(
            configuration_path.read_text(encoding=UTF8_ENCODING)
        )
    except (OSError, json.JSONDecodeError, UnicodeError):
        summary["skipped"] = True
        summary["reason"] = "unreadable"
        return summary
    if not isinstance(configuration_payload, dict):
        summary["skipped"] = True
        summary["reason"] = "root-not-object"
        return summary
    top_level_mapping = configuration_payload.get(top_level_key)
    if not isinstance(top_level_mapping, dict):
        summary["skipped"] = True
        summary["reason"] = f"no-{top_level_key}"
        return summary
    updated_mapping, all_changed_names = transform_fn(top_level_mapping)
    summary[changed_names_summary_key] = all_changed_names
    if not all_changed_names:
        return summary
    summary["changed"] = True
    if is_dry_run:
        return summary
    _backup_file(configuration_path)
    configuration_payload[top_level_key] = updated_mapping
    configuration_path.write_text(
        json.dumps(configuration_payload, indent=JSON_INDENT_SPACES) + "\n",
        encoding=UTF8_ENCODING,
    )
    return summary


def rewrite_json_mcp_servers(
    configuration_path: Path,
    *,
    is_dry_run: bool,
) -> dict[str, object]:
    """Remove heavy stdio MCP servers from a JSON config file.

    Args:
        configuration_path: Path to a Claude JSON config.
        is_dry_run: When True, do not write.

    Returns:
        Summary dictionary for the file.
    """
    return _rewrite_json_top_level_key(
        configuration_path,
        top_level_key=MCP_SERVERS_KEY,
        changed_names_summary_key="removed_servers",
        transform_fn=filter_mcp_servers,
        is_dry_run=is_dry_run,
    )


def rewrite_settings_plugins(
    settings_path: Path,
    *,
    is_dry_run: bool,
) -> dict[str, object]:
    """Disable playwright plugin flags in a settings JSON file.

    Args:
        settings_path: Path to settings.json or settings.local.json.
        is_dry_run: When True, do not write.

    Returns:
        Summary dictionary for the file.
    """
    return _rewrite_json_top_level_key(
        settings_path,
        top_level_key=ENABLED_PLUGINS_KEY,
        changed_names_summary_key="disabled_plugins",
        transform_fn=_disable_playwright_plugins,
        is_dry_run=is_dry_run,
    )


def ensure_grok_disables_claude_mcp_compat(
    grok_config_path: Path,
    *,
    is_dry_run: bool,
) -> dict[str, object]:
    """Ensure grok_config_path disables Claude MCP import (heavy stdio source).

    Args:
        grok_config_path: Path to the Grok user config file.
        is_dry_run: When True, do not write.

    Returns:
        Summary dictionary for the file.
    """
    summary: dict[str, object] = {
        "path": str(grok_config_path),
        "changed": False,
        "skipped": False,
    }
    if not grok_config_path.is_file():
        summary["skipped"] = True
        summary["reason"] = "missing"
        return summary
    try:
        configuration_text = grok_config_path.read_text(encoding=UTF8_ENCODING)
    except (OSError, UnicodeError):
        summary["skipped"] = True
        summary["reason"] = "unreadable"
        return summary
    has_compat_section = GROK_COMPAT_CLAUDE_SECTION_HEADER in configuration_text
    has_mcps_disabled = GROK_COMPAT_CLAUDE_MCPS_DISABLED_LINE in configuration_text
    if has_compat_section and has_mcps_disabled:
        return summary
    summary["changed"] = True
    if is_dry_run:
        return summary
    _backup_file(grok_config_path)
    if has_compat_section and not has_mcps_disabled:
        updated_text = configuration_text.replace(
            GROK_COMPAT_CLAUDE_SECTION_HEADER,
            (
                f"{GROK_COMPAT_CLAUDE_SECTION_HEADER}\n"
                f"{GROK_COMPAT_CLAUDE_MCPS_DISABLED_LINE}"
            ),
            1,
        )
    else:
        separator = "" if configuration_text.endswith("\n") else "\n"
        updated_text = (
            f"{configuration_text}{separator}\n{GROK_COMPAT_CLAUDE_BLOCK}"
        )
    grok_config_path.write_text(updated_text, encoding=UTF8_ENCODING)
    return summary


def apply_lean_mcp_policy(
    *,
    is_dry_run: bool,
    should_disable_grok_claude_mcps: bool,
) -> list[dict[str, object]]:
    """Apply lean MCP rewrites across known config surfaces.

    Args:
        is_dry_run: Preview changes without writing.
        should_disable_grok_claude_mcps: Also update grok_config_path.

    Returns:
        List of per-file summary dictionaries.
    """
    all_configuration_targets: list[
        tuple[Path, Callable[..., dict[str, object]]]
    ] = [
        (Path(CLAUDE_JSON_PATH), rewrite_json_mcp_servers),
        (Path(CLAUDE_DOT_CLAUDE_JSON_PATH), rewrite_json_mcp_servers),
        (Path(CLAUDE_DESKTOP_CONFIG_PATH), rewrite_json_mcp_servers),
        (Path(CLAUDE_SETTINGS_JSON_PATH), rewrite_settings_plugins),
        (Path(CLAUDE_SETTINGS_LOCAL_JSON_PATH), rewrite_settings_plugins),
    ]
    all_summaries: list[dict[str, object]] = [
        each_handler(each_path, is_dry_run=is_dry_run)
        for each_path, each_handler in all_configuration_targets
    ]
    if should_disable_grok_claude_mcps:
        all_summaries.append(
            ensure_grok_disables_claude_mcp_compat(
                Path(GROK_CONFIG_TOML_PATH),
                is_dry_run=is_dry_run,
            )
        )
    return all_summaries


def main() -> int:
    """CLI entrypoint.

    Returns:
        Process exit code (0 on success).
    """
    argument_parser = argparse.ArgumentParser(
        description=(
            "Remove heavy stdio MCP servers and disable playwright plugin flags."
        )
    )
    mode_group = argument_parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without writing files.",
    )
    mode_group.add_argument(
        "--apply",
        action="store_true",
        help="Write backups and apply lean MCP policy.",
    )
    argument_parser.add_argument(
        "--disable-grok-claude-mcps",
        action="store_true",
        help="Set [compat.claude] mcps=false in grok_config_path.",
    )
    parsed_arguments = argument_parser.parse_args()
    is_dry_run = bool(parsed_arguments.dry_run)
    is_apply = bool(parsed_arguments.apply)
    if not is_dry_run and not is_apply:
        return 2
    all_summaries = apply_lean_mcp_policy(
        is_dry_run=is_dry_run,
        should_disable_grok_claude_mcps=bool(
            parsed_arguments.disable_grok_claude_mcps
        ),
    )
    print(json.dumps(all_summaries, indent=JSON_INDENT_SPACES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
