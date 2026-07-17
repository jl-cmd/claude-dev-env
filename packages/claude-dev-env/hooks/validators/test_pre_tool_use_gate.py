"""Behavioral tests for the run_all_validators PreToolUse gate mode.

The gate mode validates the proposed post-edit content of the single file a
Write, Edit, or MultiEdit would produce and emits a PreToolUse deny decision
when that content violates a validator, rather than grading the whole branch.
"""

import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from . import file_scoped_runners, pre_tool_use_gate
from .run_all_validators import (
    ValidatorResult,
    main,
    run_pre_tool_use_gate,
    run_validators_entrypoint_subprocess,
)

GATE_PROBE_CLEAN_SOURCE = "def gate_probe() -> int:\n    return 1\n"


def _run_gate_in_process(
    payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> str:
    """Drive the PreToolUse gate in-process against *payload*, returning its stdout."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    exit_code = run_pre_tool_use_gate()
    assert exit_code == 0
    return capsys.readouterr().out


class TestGateFailsClosedOnFault:
    def test_faulted_file_scoped_validator_denies_naming_it(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def raise_validator_fault(_files: list[Path]) -> ValidatorResult:
            raise RuntimeError("anti-pattern check crashed")

        monkeypatch.setattr(
            file_scoped_runners,
            "run_python_antipattern_checks",
            raise_validator_fault,
        )
        gate_stdout = _run_gate_in_process(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "gate_probe_module.py",
                    "content": GATE_PROBE_CLEAN_SOURCE,
                },
            },
            monkeypatch,
            capsys,
        )
        assert '"permissionDecision": "deny"' in gate_stdout
        assert "Python Anti-patterns" in gate_stdout

    def test_top_level_fault_denies_rather_than_allowing_silently(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def raise_reconstruction_fault(
            _tool_name: str, _tool_input: dict[str, object]
        ) -> str:
            raise RuntimeError("payload evaluation crashed")

        monkeypatch.setattr(
            pre_tool_use_gate,
            "reconstruct_proposed_content",
            raise_reconstruction_fault,
        )
        gate_stdout = _run_gate_in_process(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "gate_probe_module.py",
                    "content": GATE_PROBE_CLEAN_SOURCE,
                },
            },
            monkeypatch,
            capsys,
        )
        assert '"permissionDecision": "deny"' in gate_stdout
        assert "gate faulted" in gate_stdout


CLEAN_PYTHON_SOURCE = (
    "def add_two_numbers(first_number: int, second_number: int) -> int:\n"
    "    return first_number + second_number\n"
)
VIOLATING_PYTHON_SOURCE = (
    "def calculate_total_price(unit_price: int, quantity: int) -> int:\n"
    "    return unit_price * quantity * 199 * 42\n"
)


def run_gate(payload: dict[str, object]) -> "subprocess.CompletedProcess[str]":
    return run_validators_entrypoint_subprocess(
        ["--pre-tool-use"], stdin_text=json.dumps(payload)
    )


class TestPreToolUseGate:
    def test_write_with_violating_content_denies(self) -> None:
        completed = run_gate(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "calculate.py",
                    "content": VIOLATING_PYTHON_SOURCE,
                },
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert '"permissionDecision": "deny"' in completed.stdout
        assert "Magic Values" in completed.stdout

    def test_write_violating_content_to_ephemeral_scratch_path_is_allowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT", raising=False)
        completed = run_gate(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "/tmp/scratch_calculate.py",
                    "content": VIOLATING_PYTHON_SOURCE,
                },
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert "deny" not in completed.stdout

    def test_write_with_clean_content_allows(self) -> None:
        completed = run_gate(
            {
                "tool_name": "Write",
                "tool_input": {
                    "file_path": "add.py",
                    "content": CLEAN_PYTHON_SOURCE,
                },
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert "deny" not in completed.stdout

    def test_edit_validates_reconstructed_post_edit_content(
        self, tmp_path: Path
    ) -> None:
        target_file = tmp_path / "calculate.py"
        target_file.write_text(CLEAN_PYTHON_SOURCE, encoding="utf-8")
        completed = run_gate(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(target_file),
                    "old_string": "    return first_number + second_number\n",
                    "new_string": "    return first_number + second_number + 199 * 42\n",
                },
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert '"permissionDecision": "deny"' in completed.stdout

    def test_unparseable_payload_exits_silently(self) -> None:
        completed = run_validators_entrypoint_subprocess(
            ["--pre-tool-use"], stdin_text="not json at all"
        )
        assert completed.returncode == 0, completed.stderr
        assert "deny" not in completed.stdout


class TestCliModeRegression:
    def test_cli_mode_reports_violations_and_exits_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        violating_file = tmp_path / "calculate.py"
        violating_file.write_text(VIOLATING_PYTHON_SOURCE, encoding="utf-8")
        with patch(
            "validators.run_all_validators.get_changed_files",
            return_value=[violating_file],
        ):
            original_argv = sys.argv
            try:
                sys.argv = ["run_all_validators.py"]
                exit_code = main()
            finally:
                sys.argv = original_argv
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "PRE-PUSH VALIDATOR RESULTS" in captured.out


def _over_long_function_source(function_name: str) -> str:
    """Return a syntactically clean function whose only defect is exceeding 30 lines."""
    body_lines = "".join("    running_total = running_total + 1\n" for _ in range(35))
    return (
        f"def {function_name}(running_total: int) -> int:\n"
        f"{body_lines}"
        "    return running_total\n"
    )


CLEAN_MARKER_FUNCTION = "def clean_marker() -> int:\n    return 1\n"
CLEAN_MARKER_EDITED = (
    "def clean_marker() -> int:\n    computed_value = 1\n    return computed_value\n"
)
MAGIC_VALUE_MARKER_FUNCTION = "def clean_marker() -> int:\n    return 199\n"
PRE_EXISTING_VIOLATION_SOURCE = (
    _over_long_function_source("over_long_function") + "\n" + CLEAN_MARKER_FUNCTION
)
MAGIC_VALUE_FUNCTION_SOURCE = "def compute_total() -> int:\n    return 199\n"
RUFF_DIRTY_FUNCTION_SOURCE = (
    "def compute_total() -> int:\n    unused_intermediate = 1\n    return 1\n"
)


class TestBaselineScopedGate:
    def test_clean_edit_to_violating_file_is_allowed_with_warning(
        self, tmp_path: Path
    ) -> None:
        target_file = tmp_path / "legacy_module.py"
        target_file.write_text(PRE_EXISTING_VIOLATION_SOURCE, encoding="utf-8")
        completed = run_gate(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(target_file),
                    "old_string": CLEAN_MARKER_FUNCTION,
                    "new_string": CLEAN_MARKER_EDITED,
                },
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert '"permissionDecision": "deny"' not in completed.stdout
        assert "Code Quality" in completed.stderr

    def test_edit_introducing_new_violation_denies_naming_only_the_new_one(
        self, tmp_path: Path
    ) -> None:
        target_file = tmp_path / "legacy_module.py"
        target_file.write_text(PRE_EXISTING_VIOLATION_SOURCE, encoding="utf-8")
        completed = run_gate(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(target_file),
                    "old_string": CLEAN_MARKER_FUNCTION,
                    "new_string": MAGIC_VALUE_MARKER_FUNCTION,
                },
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert '"permissionDecision": "deny"' in completed.stdout
        assert "Magic Values" in completed.stdout
        assert "Code Quality" not in completed.stdout

    def test_new_violation_in_clean_file_denies(self, tmp_path: Path) -> None:
        target_file = tmp_path / "clean_module.py"
        target_file.write_text(CLEAN_MARKER_FUNCTION, encoding="utf-8")
        completed = run_gate(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(target_file),
                    "old_string": "    return 1\n",
                    "new_string": "    return 199\n",
                },
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert '"permissionDecision": "deny"' in completed.stdout
        assert "Magic Values" in completed.stdout

    def test_clean_edit_to_clean_file_is_allowed(self, tmp_path: Path) -> None:
        target_file = tmp_path / "clean_module.py"
        target_file.write_text(CLEAN_MARKER_FUNCTION, encoding="utf-8")
        completed = run_gate(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(target_file),
                    "old_string": "    return 1\n",
                    "new_string": "    computed_value = 1\n    return computed_value\n",
                },
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert "deny" not in completed.stdout

    def test_growing_a_function_with_existing_length_violation_is_allowed_with_warning(
        self, tmp_path: Path
    ) -> None:
        target_file = tmp_path / "legacy_module.py"
        target_file.write_text(
            _over_long_function_source("over_long_function"), encoding="utf-8"
        )
        completed = run_gate(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(target_file),
                    "old_string": "    return running_total\n",
                    "new_string": (
                        "    running_total = running_total + 1\n"
                        "    running_total = running_total + 1\n"
                        "    return running_total\n"
                    ),
                },
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert '"permissionDecision": "deny"' not in completed.stdout
        assert "Code Quality" in completed.stderr

    def test_new_same_validator_violation_in_dirty_function_denies(
        self, tmp_path: Path
    ) -> None:
        target_file = tmp_path / "legacy_module.py"
        target_file.write_text(MAGIC_VALUE_FUNCTION_SOURCE, encoding="utf-8")
        completed = run_gate(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(target_file),
                    "old_string": "    return 199\n",
                    "new_string": "    threshold = 42\n    return 199 + threshold\n",
                },
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert '"permissionDecision": "deny"' in completed.stdout
        assert "Magic Values" in completed.stdout

    def test_new_module_scope_ruff_violation_with_dirty_function_denies(
        self, tmp_path: Path
    ) -> None:
        target_file = tmp_path / "legacy_module.py"
        target_file.write_text(RUFF_DIRTY_FUNCTION_SOURCE, encoding="utf-8")
        completed = run_gate(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(target_file),
                    "old_string": "def compute_total",
                    "new_string": "import os\n\n\ndef compute_total",
                },
            }
        )
        assert completed.returncode == 0, completed.stderr
        assert '"permissionDecision": "deny"' in completed.stdout
        assert "F401" in completed.stdout
        assert "F841" not in completed.stdout
