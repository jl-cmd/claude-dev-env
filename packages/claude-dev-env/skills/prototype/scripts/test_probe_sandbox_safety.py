"""Tests for the sandbox safety-hook probe.

The block-detection unit tests drive fixture hook scripts, and the
integration tests point a settings file at the real installed safety hooks
to prove they block their probe payloads end to end.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

from prototype_scripts_constants.config.build_sandbox_settings_constants import (
    ALL_SAFETY_HOOK_SCRIPT_BASENAMES,
    COMMAND_KEY,
    HOOKS_KEY,
    MATCHER_KEY,
    PRE_TOOL_USE_KEY,
)
from prototype_scripts_constants.config.probe_sandbox_safety_constants import (
    DESTRUCTIVE_PROBE_COMMAND,
    ENVELOPE_TOOL_INPUT_KEY,
    ENVELOPE_TOOL_NAME_KEY,
    PII_PROBE_TOKEN_PREFIX,
    PII_PROBE_TOOL_NAME,
    PROBE_FAILURE_EXIT_CODE,
    PROBE_SUCCESS_EXIT_CODE,
    TOOL_INPUT_COMMAND_KEY,
    TOOL_INPUT_CONTENT_KEY,
)

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
PROBE_PATH = SCRIPTS_DIRECTORY / "probe_sandbox_safety.py"
HOOKS_BLOCKING_DIRECTORY = SCRIPTS_DIRECTORY.parents[2] / "hooks" / "blocking"

PII_HOOK_BASENAME = ALL_SAFETY_HOOK_SCRIPT_BASENAMES[0]
DESTRUCTIVE_HOOK_BASENAME = ALL_SAFETY_HOOK_SCRIPT_BASENAMES[1]

DENY_HOOK_SOURCE = (
    "import json, sys\n"
    "sys.stdout.write(json.dumps("
    '{"hookSpecificOutput": {"permissionDecision": "deny"}}))\n'
)
ASK_HOOK_SOURCE = (
    "import json, sys\n"
    "sys.stdout.write(json.dumps("
    '{"hookSpecificOutput": {"permissionDecision": "ask"}}))\n'
)
ALLOW_HOOK_SOURCE = "import sys\nsys.exit(0)\n"


def load_probe_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("probe_sandbox_safety", PROBE_PATH)
    assert spec is not None
    assert spec.loader is not None
    probe_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe_module)
    return probe_module


def quoted_command(script_path: Path) -> str:
    return f'"{sys.executable}" "{script_path}"'


def real_hook_settings_document() -> dict:
    pii_hook_path = HOOKS_BLOCKING_DIRECTORY / PII_HOOK_BASENAME
    destructive_hook_path = HOOKS_BLOCKING_DIRECTORY / DESTRUCTIVE_HOOK_BASENAME
    return {
        HOOKS_KEY: {
            PRE_TOOL_USE_KEY: [
                {
                    MATCHER_KEY: "Write",
                    HOOKS_KEY: [{COMMAND_KEY: quoted_command(pii_hook_path)}],
                },
                {
                    MATCHER_KEY: "Bash",
                    HOOKS_KEY: [{COMMAND_KEY: quoted_command(destructive_hook_path)}],
                },
            ]
        }
    }


def real_hook_deny_mode_settings_document() -> dict:
    settings_document = real_hook_settings_document()
    settings_document["env"] = {"CLAUDE_DESTRUCTIVE_DENY_MODE": "1"}
    return settings_document


def write_settings_file(tmp_path: Path, settings_document: dict) -> Path:
    settings_path = tmp_path / "sandbox-settings.json"
    settings_path.write_text(json.dumps(settings_document), encoding="utf-8")
    return settings_path


def test_settings_environment_overrides_reads_the_env_block() -> None:
    probe = load_probe_module()
    environment_overrides = probe.settings_environment_overrides(
        real_hook_deny_mode_settings_document()
    )
    assert environment_overrides == {"CLAUDE_DESTRUCTIVE_DENY_MODE": "1"}


def test_settings_environment_overrides_empty_without_an_env_block() -> None:
    probe = load_probe_module()
    environment_overrides = probe.settings_environment_overrides(
        real_hook_settings_document()
    )
    assert environment_overrides == {}


def test_main_exits_zero_when_the_real_destructive_hook_denies_in_deny_mode(
    tmp_path: Path,
) -> None:
    probe = load_probe_module()
    settings_path = write_settings_file(
        tmp_path, real_hook_deny_mode_settings_document()
    )
    exit_code = probe.main(["--settings", str(settings_path)])
    assert exit_code == PROBE_SUCCESS_EXIT_CODE


def test_pii_basename_probe_payload_carries_the_secret() -> None:
    probe = load_probe_module()
    probe_payload = probe.build_probe_payload_for_basename(PII_HOOK_BASENAME)
    assert probe_payload[ENVELOPE_TOOL_NAME_KEY] == PII_PROBE_TOOL_NAME
    content = probe_payload[ENVELOPE_TOOL_INPUT_KEY][TOOL_INPUT_CONTENT_KEY]
    assert PII_PROBE_TOKEN_PREFIX in content


def test_destructive_basename_probe_payload_carries_the_command() -> None:
    probe = load_probe_module()
    probe_payload = probe.build_probe_payload_for_basename(DESTRUCTIVE_HOOK_BASENAME)
    command = probe_payload[ENVELOPE_TOOL_INPUT_KEY][TOOL_INPUT_COMMAND_KEY]
    assert command == DESTRUCTIVE_PROBE_COMMAND


def test_find_hook_command_for_basename_returns_the_matching_command() -> None:
    probe = load_probe_module()
    settings_document = real_hook_settings_document()
    command = probe.find_hook_command_for_basename(settings_document, PII_HOOK_BASENAME)
    assert command is not None
    assert PII_HOOK_BASENAME in command
    assert probe.find_hook_command_for_basename(settings_document, "absent.py") is None


def test_parse_command_argv_splits_and_unquotes_the_command() -> None:
    probe = load_probe_module()
    command_argv = probe.parse_command_argv('"/usr/bin/python" "/a/b hook.py"')
    assert command_argv == ["/usr/bin/python", "/a/b hook.py"]


def test_hook_blocks_probe_reports_true_for_a_deny_hook(tmp_path: Path) -> None:
    probe = load_probe_module()
    deny_hook_path = tmp_path / "deny_hook.py"
    deny_hook_path.write_text(DENY_HOOK_SOURCE, encoding="utf-8")
    command_argv = [sys.executable, str(deny_hook_path)]
    probe_payload = probe.build_probe_payload_for_basename(DESTRUCTIVE_HOOK_BASENAME)
    assert probe.hook_blocks_probe(command_argv, probe_payload, {}) is True


def test_hook_blocks_probe_reports_false_for_an_ask_hook(tmp_path: Path) -> None:
    probe = load_probe_module()
    ask_hook_path = tmp_path / "ask_hook.py"
    ask_hook_path.write_text(ASK_HOOK_SOURCE, encoding="utf-8")
    command_argv = [sys.executable, str(ask_hook_path)]
    probe_payload = probe.build_probe_payload_for_basename(DESTRUCTIVE_HOOK_BASENAME)
    assert probe.hook_blocks_probe(command_argv, probe_payload, {}) is False


def test_hook_blocks_probe_reports_false_for_an_allow_hook(tmp_path: Path) -> None:
    probe = load_probe_module()
    allow_hook_path = tmp_path / "allow_hook.py"
    allow_hook_path.write_text(ALLOW_HOOK_SOURCE, encoding="utf-8")
    command_argv = [sys.executable, str(allow_hook_path)]
    probe_payload = probe.build_probe_payload_for_basename(DESTRUCTIVE_HOOK_BASENAME)
    assert probe.hook_blocks_probe(command_argv, probe_payload, {}) is False


def test_probe_safety_hook_blocks_against_the_real_pii_hook() -> None:
    probe = load_probe_module()
    settings_document = real_hook_settings_document()
    assert probe.probe_safety_hook(settings_document, PII_HOOK_BASENAME) is True


def test_main_exits_three_when_the_real_destructive_hook_only_asks(
    tmp_path: Path,
) -> None:
    probe = load_probe_module()
    settings_path = write_settings_file(tmp_path, real_hook_settings_document())
    exit_code = probe.main(["--settings", str(settings_path)])
    assert exit_code == PROBE_FAILURE_EXIT_CODE


def test_main_exits_zero_when_both_real_hooks_hard_deny(tmp_path: Path) -> None:
    probe = load_probe_module()
    deny_pii_hook_path = tmp_path / PII_HOOK_BASENAME
    deny_pii_hook_path.write_text(DENY_HOOK_SOURCE, encoding="utf-8")
    deny_destructive_hook_path = tmp_path / DESTRUCTIVE_HOOK_BASENAME
    deny_destructive_hook_path.write_text(DENY_HOOK_SOURCE, encoding="utf-8")
    settings_document = {
        HOOKS_KEY: {
            PRE_TOOL_USE_KEY: [
                {
                    MATCHER_KEY: "Write",
                    HOOKS_KEY: [{COMMAND_KEY: quoted_command(deny_pii_hook_path)}],
                },
                {
                    MATCHER_KEY: "Bash",
                    HOOKS_KEY: [
                        {COMMAND_KEY: quoted_command(deny_destructive_hook_path)}
                    ],
                },
            ]
        }
    }
    settings_path = write_settings_file(tmp_path, settings_document)
    exit_code = probe.main(["--settings", str(settings_path)])
    assert exit_code == PROBE_SUCCESS_EXIT_CODE


def test_main_exits_three_when_a_hook_allows(tmp_path: Path) -> None:
    probe = load_probe_module()
    allow_pii_hook_path = tmp_path / PII_HOOK_BASENAME
    allow_pii_hook_path.write_text(ALLOW_HOOK_SOURCE, encoding="utf-8")
    destructive_hook_path = HOOKS_BLOCKING_DIRECTORY / DESTRUCTIVE_HOOK_BASENAME
    settings_document = {
        HOOKS_KEY: {
            PRE_TOOL_USE_KEY: [
                {
                    MATCHER_KEY: "Write",
                    HOOKS_KEY: [{COMMAND_KEY: quoted_command(allow_pii_hook_path)}],
                },
                {
                    MATCHER_KEY: "Bash",
                    HOOKS_KEY: [{COMMAND_KEY: quoted_command(destructive_hook_path)}],
                },
            ]
        }
    }
    settings_path = write_settings_file(tmp_path, settings_document)
    exit_code = probe.main(["--settings", str(settings_path)])
    assert exit_code == PROBE_FAILURE_EXIT_CODE


def test_main_exits_three_when_a_hook_script_is_bogus(tmp_path: Path) -> None:
    probe = load_probe_module()
    bogus_pii_hook_path = tmp_path / PII_HOOK_BASENAME
    destructive_hook_path = HOOKS_BLOCKING_DIRECTORY / DESTRUCTIVE_HOOK_BASENAME
    settings_document = {
        HOOKS_KEY: {
            PRE_TOOL_USE_KEY: [
                {
                    MATCHER_KEY: "Write",
                    HOOKS_KEY: [{COMMAND_KEY: quoted_command(bogus_pii_hook_path)}],
                },
                {
                    MATCHER_KEY: "Bash",
                    HOOKS_KEY: [{COMMAND_KEY: quoted_command(destructive_hook_path)}],
                },
            ]
        }
    }
    settings_path = write_settings_file(tmp_path, settings_document)
    exit_code = probe.main(["--settings", str(settings_path)])
    assert exit_code == PROBE_FAILURE_EXIT_CODE
