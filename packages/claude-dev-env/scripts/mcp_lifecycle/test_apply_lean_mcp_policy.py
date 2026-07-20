"""Tests for lean MCP policy filtering and config rewrites."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
from pathlib import Path

import pytest

_SCRIPT_DIR = pathlib.Path(__file__).parent
_SCRIPTS_DIR = _SCRIPT_DIR.parent
for each_path in (str(_SCRIPT_DIR), str(_SCRIPTS_DIR)):
    if each_path not in sys.path:
        sys.path.insert(0, each_path)

module_spec = importlib.util.spec_from_file_location(
    "apply_lean_mcp_policy",
    _SCRIPT_DIR / "apply_lean_mcp_policy.py",
)
assert module_spec is not None
assert module_spec.loader is not None
policy = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(policy)


def test_filter_mcp_servers_removes_mcpvault_and_serena_keeps_http() -> None:
    server_by_name: dict[str, object] = {
        "obsidian": {
            "type": "stdio",
            "command": "cmd",
            "args": ["/c", "npx", "@bitbonsai/mcpvault@latest", "vault"],
        },
        "serena": {
            "type": "stdio",
            "command": "uvx",
            "args": [
                "--from",
                "git+https://github.com/oraios/serena",
                "serena",
                "start-mcp-server",
            ],
            "alwaysLoad": True,
        },
        "neon": {
            "type": "http",
            "url": "https://mcp.neon.tech/mcp?readonly=true",
        },
    }
    filtered_server_by_name, all_removed = policy.filter_mcp_servers(server_by_name)
    assert set(all_removed) == {"obsidian", "serena"}
    assert "neon" in filtered_server_by_name
    assert "obsidian" not in filtered_server_by_name
    assert "serena" not in filtered_server_by_name


def test_filter_mcp_servers_keeps_unrelated_stdio() -> None:
    server_by_name: dict[str, object] = {
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        }
    }
    filtered_server_by_name, all_removed = policy.filter_mcp_servers(server_by_name)
    assert all_removed == []
    assert "filesystem" in filtered_server_by_name


def test_rewrite_json_mcp_servers_clears_always_load_without_removals(
    tmp_path: Path,
) -> None:
    configuration_path = tmp_path / "claude.json"
    configuration_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "filesystem": {
                        "command": "npx",
                        "args": ["-y", "@modelcontextprotocol/server-filesystem"],
                        "alwaysLoad": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    summary = policy.rewrite_json_mcp_servers(
        configuration_path,
        is_dry_run=False,
    )
    assert summary["changed"] is True
    assert summary["removed_servers"] == []
    rewritten_payload = json.loads(configuration_path.read_text(encoding="utf-8"))
    assert "alwaysLoad" not in rewritten_payload["mcpServers"]["filesystem"]


def test_rewrite_json_mcp_servers_applies_backup(tmp_path: Path) -> None:
    configuration_path = tmp_path / "claude.json"
    configuration_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "obsidian": {
                        "command": "cmd",
                        "args": ["npx", "@bitbonsai/mcpvault@latest"],
                    },
                    "neon": {"type": "http", "url": "https://example.test/mcp"},
                }
            }
        ),
        encoding="utf-8",
    )
    summary = policy.rewrite_json_mcp_servers(
        configuration_path,
        is_dry_run=False,
    )
    assert summary["changed"] is True
    assert summary["removed_servers"] == ["obsidian"]
    rewritten_payload = json.loads(configuration_path.read_text(encoding="utf-8"))
    assert "obsidian" not in rewritten_payload["mcpServers"]
    assert "neon" in rewritten_payload["mcpServers"]
    all_backup_paths = list(tmp_path.glob("claude.json.bak-*"))
    assert len(all_backup_paths) == 1


def test_rewrite_settings_plugins_disables_playwright(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "enabledPlugins": {
                    "playwright@claude-plugins-official": True,
                    "neon@claude-plugins-official": True,
                }
            }
        ),
        encoding="utf-8",
    )
    summary = policy.rewrite_settings_plugins(settings_path, is_dry_run=False)
    assert summary["changed"] is True
    rewritten_payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert (
        rewritten_payload["enabledPlugins"]["playwright@claude-plugins-official"]
        is False
    )
    assert rewritten_payload["enabledPlugins"]["neon@claude-plugins-official"] is True


def test_ensure_grok_disables_claude_mcp_compat_appends_block(tmp_path: Path) -> None:
    grok_config_path = tmp_path / "config.toml"
    grok_config_path.write_text("[ui]\nyolo = false\n", encoding="utf-8")
    summary = policy.ensure_grok_disables_claude_mcp_compat(
        grok_config_path,
        is_dry_run=False,
    )
    assert summary["changed"] is True
    configuration_text = grok_config_path.read_text(encoding="utf-8")
    assert "[compat.claude]" in configuration_text
    assert "mcps = false" in configuration_text


def test_apply_lean_mcp_policy_dry_run_returns_summaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration_path = tmp_path / "claude.json"
    configuration_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "obsidian": {
                        "command": "cmd",
                        "args": ["npx", "@bitbonsai/mcpvault@latest"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(policy, "CLAUDE_JSON_PATH", str(configuration_path))
    monkeypatch.setattr(policy, "CLAUDE_DOT_CLAUDE_JSON_PATH", str(tmp_path / "missing1"))
    monkeypatch.setattr(policy, "CLAUDE_DESKTOP_CONFIG_PATH", str(tmp_path / "missing2"))
    monkeypatch.setattr(policy, "CLAUDE_SETTINGS_JSON_PATH", str(tmp_path / "missing3"))
    monkeypatch.setattr(
        policy, "CLAUDE_SETTINGS_LOCAL_JSON_PATH", str(tmp_path / "missing4")
    )
    all_summaries = policy.apply_lean_mcp_policy(
        is_dry_run=True,
        should_disable_grok_claude_mcps=False,
    )
    assert any(each.get("changed") is True for each in all_summaries)
