"""Behavioral tests for validator coverage across every mutation tool.

The PreToolUse gate has to reach a MultiEdit and a Codex apply_patch the same
way it reaches a Write and an Edit. Two things carry that: the hooks.json
matcher the harness dispatches on, and the payload shape the gate reconstructs
post-edit content from.
"""

import json
import subprocess
from pathlib import Path

import pytest

from hooks_constants.pre_tool_use_dispatcher_constants import (
    ALL_WRITE_EDIT_MULTI_EDIT_APPLY_PATCH_TOOL_NAMES,
)

from .run_all_validators import run_validators_entrypoint_subprocess

pytestmark = pytest.mark.usefixtures("ephemeral_exempt_off")

HOOKS_JSON_PATH = Path(__file__).resolve().parents[1] / "hooks.json"
VALIDATORS_RUNNER_COMMAND_MARKER = "validators.run_all_validators"
MATCHER_TOOL_NAME_SEPARATOR = "|"
DENY_DECISION_FRAGMENT = '"permissionDecision": "deny"'
MAGIC_VALUE_VALIDATOR_NAME = "Magic Values"

CLEAN_MODULE_SOURCE = (
    "def clean_marker() -> int:\n    computed_value = 1\n    return computed_value\n"
)
CLEAN_SECOND_MODULE_SOURCE = (
    "def second_marker() -> int:\n    counted_value = 1\n    return counted_value\n"
)
CLEAN_RETURN_LINE = "    return computed_value\n"
MAGIC_VALUE_RETURN_LINE = "    return computed_value * 199\n"
CLEAN_REWRITTEN_RETURN_LINE = "    return computed_value + 1\n"

UPDATE_PATCH_TEMPLATE = (
    "*** Begin Patch\n"
    "*** Update File: {relative_path}\n"
    "@@\n"
    "-{removed_line}"
    "+{added_line}"
    "*** End Patch\n"
)
ADD_VIOLATING_FILE_PATCH_COMMAND = (
    "*** Begin Patch\n"
    "*** Add File: added_module.py\n"
    "+def added_marker() -> int:\n"
    "+    return 199\n"
    "*** End Patch\n"
)
DELETE_FILE_PATCH_COMMAND = (
    "*** Begin Patch\n*** Delete File: legacy_module.py\n*** End of File\n*** End Patch\n"
)
UNPARSEABLE_PATCH_COMMAND = "not a codex patch at all\n"
TWO_FILE_PATCH_COMMAND = (
    "*** Begin Patch\n"
    "*** Update File: first_module.py\n"
    "@@\n"
    "-    return computed_value\n"
    "+    return computed_value + 1\n"
    "*** Update File: second_module.py\n"
    "@@\n"
    "-    return counted_value\n"
    "+    return counted_value * 199\n"
    "*** End Patch\n"
)


def run_gate(payload: dict[str, object]) -> "subprocess.CompletedProcess[str]":
    """Drive the real --pre-tool-use entry point with one payload."""
    return run_validators_entrypoint_subprocess(["--pre-tool-use"], stdin_text=json.dumps(payload))


def json_embedded_path(target_path: Path) -> str:
    """Return the path exactly as a JSON deny payload spells it."""
    return json.dumps(str(target_path))[1:-1]


def update_patch_command(relative_path: str, added_line: str) -> str:
    """Build an Update File patch rewriting the module's return line."""
    return UPDATE_PATCH_TEMPLATE.format(
        relative_path=relative_path,
        removed_line=CLEAN_RETURN_LINE,
        added_line=added_line,
    )


def write_clean_module(target_directory: Path, module_name: str) -> Path:
    """Write the clean Python module the payloads target."""
    target_file = target_directory / module_name
    target_file.write_text(CLEAN_MODULE_SOURCE, encoding="utf-8")
    return target_file


class TestMutationToolRegistration:
    def test_validators_gate_is_registered_on_every_mutation_tool(self) -> None:
        hooks_document = json.loads(HOOKS_JSON_PATH.read_text(encoding="utf-8"))
        all_matchers = [
            each_group["matcher"]
            for each_group in hooks_document["hooks"]["PreToolUse"]
            for each_hook in each_group.get("hooks", [])
            if VALIDATORS_RUNNER_COMMAND_MARKER in each_hook.get("command", "")
        ]
        assert len(all_matchers) == 1, all_matchers
        assert (
            set(all_matchers[0].split(MATCHER_TOOL_NAME_SEPARATOR))
            == ALL_WRITE_EDIT_MULTI_EDIT_APPLY_PATCH_TOOL_NAMES
        )


class TestMultiEditPayloadLane:
    def test_multi_edit_introducing_a_violation_denies(self, tmp_path: Path) -> None:
        target_file = write_clean_module(tmp_path, "legacy_module.py")
        completed = run_gate(
            {
                "tool_name": "MultiEdit",
                "tool_input": {
                    "file_path": str(target_file),
                    "edits": [
                        {
                            "old_string": CLEAN_RETURN_LINE,
                            "new_string": MAGIC_VALUE_RETURN_LINE,
                        }
                    ],
                },
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert DENY_DECISION_FRAGMENT in completed.stdout
        assert MAGIC_VALUE_VALIDATOR_NAME in completed.stdout

    def test_multi_edit_leaving_clean_content_allows(self, tmp_path: Path) -> None:
        target_file = write_clean_module(tmp_path, "clean_module.py")
        completed = run_gate(
            {
                "tool_name": "MultiEdit",
                "tool_input": {
                    "file_path": str(target_file),
                    "edits": [
                        {
                            "old_string": CLEAN_RETURN_LINE,
                            "new_string": CLEAN_REWRITTEN_RETURN_LINE,
                        }
                    ],
                },
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert DENY_DECISION_FRAGMENT not in completed.stdout


class TestApplyPatchPayloadLane:
    def test_apply_patch_introducing_a_violation_denies(self, tmp_path: Path) -> None:
        write_clean_module(tmp_path, "legacy_module.py")
        completed = run_gate(
            {
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": update_patch_command("legacy_module.py", MAGIC_VALUE_RETURN_LINE)
                },
                "cwd": str(tmp_path),
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert DENY_DECISION_FRAGMENT in completed.stdout
        assert MAGIC_VALUE_VALIDATOR_NAME in completed.stdout

    def test_apply_patch_deny_reason_names_the_patched_file(self, tmp_path: Path) -> None:
        target_file = write_clean_module(tmp_path, "legacy_module.py")
        completed = run_gate(
            {
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": update_patch_command("legacy_module.py", MAGIC_VALUE_RETURN_LINE)
                },
                "cwd": str(tmp_path),
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert target_file.name in completed.stdout

    def test_apply_patch_leaving_clean_content_allows(self, tmp_path: Path) -> None:
        write_clean_module(tmp_path, "clean_module.py")
        completed = run_gate(
            {
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": update_patch_command("clean_module.py", CLEAN_REWRITTEN_RETURN_LINE)
                },
                "cwd": str(tmp_path),
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert DENY_DECISION_FRAGMENT not in completed.stdout

    def test_apply_patch_adding_a_violating_file_denies(self, tmp_path: Path) -> None:
        completed = run_gate(
            {
                "tool_name": "apply_patch",
                "tool_input": {"command": ADD_VIOLATING_FILE_PATCH_COMMAND},
                "cwd": str(tmp_path),
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert DENY_DECISION_FRAGMENT in completed.stdout
        assert MAGIC_VALUE_VALIDATOR_NAME in completed.stdout

    def test_apply_patch_deleting_a_file_allows(self, tmp_path: Path) -> None:
        write_clean_module(tmp_path, "legacy_module.py")
        completed = run_gate(
            {
                "tool_name": "apply_patch",
                "tool_input": {"command": DELETE_FILE_PATCH_COMMAND},
                "cwd": str(tmp_path),
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert DENY_DECISION_FRAGMENT not in completed.stdout

    def test_unparseable_apply_patch_command_allows(self, tmp_path: Path) -> None:
        """A patch this lane cannot read is the enforcer's to deny, not this gate's.

        ``code_rules_enforcer`` denies a payload whose patch markers it cannot
        parse. Both hooks run on the same call and any denial wins, so this lane
        allows rather than raising a second denial for one cause. Moving that
        denial out of the enforcer leaves a malformed patch with no reader.
        """
        completed = run_gate(
            {
                "tool_name": "apply_patch",
                "tool_input": {"command": UNPARSEABLE_PATCH_COMMAND},
                "cwd": str(tmp_path),
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert DENY_DECISION_FRAGMENT not in completed.stdout

    def test_apply_patch_denies_a_violation_in_its_second_file(self, tmp_path: Path) -> None:
        write_clean_module(tmp_path, "first_module.py")
        second_file = tmp_path / "second_module.py"
        second_file.write_text(CLEAN_SECOND_MODULE_SOURCE, encoding="utf-8")
        completed = run_gate(
            {
                "tool_name": "apply_patch",
                "tool_input": {"command": TWO_FILE_PATCH_COMMAND},
                "cwd": str(tmp_path),
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert DENY_DECISION_FRAGMENT in completed.stdout
        assert second_file.name in completed.stdout
