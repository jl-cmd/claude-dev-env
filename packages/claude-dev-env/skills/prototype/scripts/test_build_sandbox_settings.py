"""Tests for the sandbox safety-settings builder."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

from prototype_scripts_constants.config.build_sandbox_settings_constants import (
    ALL_DESTRUCTIVE_REQUIRED_MATCHERS,
    ALL_PII_REQUIRED_MATCHERS,
    ALL_SAFETY_HOOK_SCRIPT_BASENAMES,
    BUILD_SUCCESS_EXIT_CODE,
    COMMAND_KEY,
    HOOKS_KEY,
    MATCHER_KEY,
    PRE_TOOL_USE_KEY,
    SETTINGS_MISSING_SAFETY_HOOK_EXIT_CODE,
)

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
BUILDER_PATH = SCRIPTS_DIRECTORY / "build_sandbox_settings.py"

PII_HOOK_BASENAME = ALL_SAFETY_HOOK_SCRIPT_BASENAMES[0]
DESTRUCTIVE_HOOK_BASENAME = ALL_SAFETY_HOOK_SCRIPT_BASENAMES[1]

CODE_RULES_HOOK_BASENAME = "code_rules_enforcer.py"
TDD_HOOK_BASENAME = "tdd_enforcer.py"
PLAIN_LANGUAGE_HOOK_BASENAME = "plain_language_blocker.py"

BASH_MATCHER = "Bash"
WRITE_MATCHER = "Write"
EDIT_MATCHER = "Edit"
MULTI_EDIT_MATCHER = "MultiEdit"
NARROW_PII_MATCHER = "mcp__plugin_github_github__.*"

SUBHOOK_TIMEOUT = 15
PII_COMMAND = f"python hooks/blocking/{PII_HOOK_BASENAME}"
DESTRUCTIVE_COMMAND = f"python hooks/blocking/{DESTRUCTIVE_HOOK_BASENAME}"
CODE_RULES_COMMAND = f"python hooks/blocking/{CODE_RULES_HOOK_BASENAME}"


def load_builder_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "build_sandbox_settings", BUILDER_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    builder_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder_module)
    return builder_module


def make_subhook(command: str) -> dict:
    return {"type": "command", "command": command, "timeout": SUBHOOK_TIMEOUT}


def sample_settings_document() -> dict:
    """Build a settings document that registers pii on a narrow matcher only.

    ::

        Write block  -> [code_rules_enforcer]
        Bash block   -> [destructive_command_blocker]
        GitHub block -> [pii_prevention_blocker]   (narrow matcher)

    The live pii gate is scoped to the GitHub MCP tool family, so a
    presence-only copy would leave disk writes ungated.
    """
    write_block = {
        MATCHER_KEY: WRITE_MATCHER,
        HOOKS_KEY: [make_subhook(CODE_RULES_COMMAND)],
    }
    bash_block = {
        MATCHER_KEY: BASH_MATCHER,
        HOOKS_KEY: [make_subhook(DESTRUCTIVE_COMMAND)],
    }
    github_block = {
        MATCHER_KEY: NARROW_PII_MATCHER,
        HOOKS_KEY: [make_subhook(PII_COMMAND)],
    }
    return {HOOKS_KEY: {PRE_TOOL_USE_KEY: [write_block, bash_block, github_block]}}


def document_without_destructive() -> dict:
    """Build a settings document that registers pii but no destructive hook."""
    github_block = {
        MATCHER_KEY: NARROW_PII_MATCHER,
        HOOKS_KEY: [make_subhook(PII_COMMAND)],
    }
    return {HOOKS_KEY: {PRE_TOOL_USE_KEY: [github_block]}}


def minimal_settings_for(builder: ModuleType, settings_document: dict) -> dict:
    entry_by_basename = builder.resolve_safety_hook_entries(settings_document)
    return builder.build_minimal_settings(entry_by_basename)


def blocks_of(minimal_settings: dict) -> list[dict]:
    return minimal_settings[HOOKS_KEY][PRE_TOOL_USE_KEY]


def commands_by_matcher(minimal_settings: dict) -> dict[str, list[str]]:
    commands_by_each_matcher: dict[str, list[str]] = {}
    for each_block in blocks_of(minimal_settings):
        commands_by_each_matcher[each_block[MATCHER_KEY]] = [
            each_subhook[COMMAND_KEY] for each_subhook in each_block[HOOKS_KEY]
        ]
    return commands_by_each_matcher


def test_read_settings_document_parses_the_source_json(tmp_path: Path) -> None:
    builder = load_builder_module()
    source_path = tmp_path / "settings.json"
    source_path.write_text(json.dumps(sample_settings_document()), encoding="utf-8")
    parsed_document = builder.read_settings_document(source_path)
    assert parsed_document == sample_settings_document()


def test_resolve_safety_hook_entries_copies_each_live_command_through() -> None:
    builder = load_builder_module()
    entry_by_basename = builder.resolve_safety_hook_entries(sample_settings_document())
    assert set(entry_by_basename) == set(ALL_SAFETY_HOOK_SCRIPT_BASENAMES)
    assert entry_by_basename[PII_HOOK_BASENAME][COMMAND_KEY] == PII_COMMAND
    assert (
        entry_by_basename[DESTRUCTIVE_HOOK_BASENAME][COMMAND_KEY] == DESTRUCTIVE_COMMAND
    )
    assert entry_by_basename[PII_HOOK_BASENAME]["timeout"] == SUBHOOK_TIMEOUT


def test_find_unresolved_safety_hook_basenames_names_the_missing_hook() -> None:
    builder = load_builder_module()
    entry_by_basename = builder.resolve_safety_hook_entries(
        document_without_destructive()
    )
    assert builder.find_unresolved_safety_hook_basenames(entry_by_basename) == [
        DESTRUCTIVE_HOOK_BASENAME
    ]


def test_find_unresolved_safety_hook_basenames_empty_when_both_resolve() -> None:
    builder = load_builder_module()
    entry_by_basename = builder.resolve_safety_hook_entries(sample_settings_document())
    assert builder.find_unresolved_safety_hook_basenames(entry_by_basename) == []


def test_build_registers_pii_on_every_required_write_and_command_matcher() -> None:
    builder = load_builder_module()
    commands = commands_by_matcher(
        minimal_settings_for(builder, sample_settings_document())
    )
    assert set(commands) == set(ALL_PII_REQUIRED_MATCHERS)
    for each_matcher in ALL_PII_REQUIRED_MATCHERS:
        assert PII_COMMAND in commands[each_matcher]


def test_build_registers_destructive_on_the_command_matcher_only() -> None:
    builder = load_builder_module()
    commands = commands_by_matcher(
        minimal_settings_for(builder, sample_settings_document())
    )
    for each_matcher, each_command_list in commands.items():
        has_destructive = DESTRUCTIVE_COMMAND in each_command_list
        assert has_destructive == (each_matcher in ALL_DESTRUCTIVE_REQUIRED_MATCHERS)


def test_build_bash_block_carries_both_safety_hooks() -> None:
    builder = load_builder_module()
    commands = commands_by_matcher(
        minimal_settings_for(builder, sample_settings_document())
    )
    assert commands[BASH_MATCHER] == [PII_COMMAND, DESTRUCTIVE_COMMAND]


def test_build_excludes_every_non_safety_hook() -> None:
    builder = load_builder_module()
    commands = commands_by_matcher(
        minimal_settings_for(builder, sample_settings_document())
    )
    all_commands = [
        each_command
        for each_command_list in commands.values()
        for each_command in each_command_list
    ]
    for each_excluded in (
        CODE_RULES_HOOK_BASENAME,
        TDD_HOOK_BASENAME,
        PLAIN_LANGUAGE_HOOK_BASENAME,
    ):
        assert all(each_excluded not in each_command for each_command in all_commands)


def test_narrow_live_pii_matcher_does_not_leak_into_output() -> None:
    builder = load_builder_module()
    all_matchers = set(
        commands_by_matcher(minimal_settings_for(builder, sample_settings_document()))
    )
    assert NARROW_PII_MATCHER not in all_matchers
    assert all_matchers.issuperset(
        {WRITE_MATCHER, EDIT_MATCHER, MULTI_EDIT_MATCHER, BASH_MATCHER}
    )


def test_build_emits_blocks_in_sorted_matcher_order() -> None:
    builder = load_builder_module()
    minimal_settings = minimal_settings_for(builder, sample_settings_document())
    emitted_matchers = [
        each_block[MATCHER_KEY] for each_block in blocks_of(minimal_settings)
    ]
    assert emitted_matchers == sorted(emitted_matchers)


def test_build_emits_the_deny_mode_env_block() -> None:
    builder = load_builder_module()
    minimal_settings = minimal_settings_for(builder, sample_settings_document())
    assert minimal_settings[builder.ENV_KEY] == {
        builder.DESTRUCTIVE_DENY_MODE_ENV_VAR: builder.DESTRUCTIVE_DENY_MODE_ENV_VALUE
    }


def test_write_minimal_settings_round_trips_the_document(tmp_path: Path) -> None:
    builder = load_builder_module()
    minimal_settings = minimal_settings_for(builder, sample_settings_document())
    out_path = tmp_path / "sandbox-settings.json"
    builder.write_minimal_settings(minimal_settings, out_path)
    assert json.loads(out_path.read_text(encoding="utf-8")) == minimal_settings


def test_main_writes_minimal_settings_and_succeeds(tmp_path: Path) -> None:
    builder = load_builder_module()
    source_path = tmp_path / "settings.json"
    source_path.write_text(json.dumps(sample_settings_document()), encoding="utf-8")
    out_path = tmp_path / "sandbox-settings.json"
    exit_code = builder.main(
        ["--out", str(out_path), "--settings-source", str(source_path)]
    )
    assert exit_code == BUILD_SUCCESS_EXIT_CODE
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert set(commands_by_matcher(written)) == set(ALL_PII_REQUIRED_MATCHERS)


def test_main_exits_when_a_safety_hook_is_missing(tmp_path: Path) -> None:
    builder = load_builder_module()
    source_path = tmp_path / "settings.json"
    source_path.write_text(json.dumps(document_without_destructive()), encoding="utf-8")
    out_path = tmp_path / "sandbox-settings.json"
    exit_code = builder.main(
        ["--out", str(out_path), "--settings-source", str(source_path)]
    )
    assert exit_code == SETTINGS_MISSING_SAFETY_HOOK_EXIT_CODE
    assert not out_path.exists()
