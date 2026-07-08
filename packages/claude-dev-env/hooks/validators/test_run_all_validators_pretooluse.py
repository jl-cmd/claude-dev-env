"""Behavioral tests for the run_all_validators PreToolUse gate mode.

The gate mode validates the proposed post-edit content of the single file a
Write, Edit, or MultiEdit would produce and emits a PreToolUse deny decision
when that content violates a validator, rather than grading the whole branch.
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from .run_all_validators import main, run_validators_entrypoint_subprocess

CLEAN_PYTHON_SOURCE = (
    "def add_two_numbers(first_number: int, second_number: int) -> int:\n"
    "    return first_number + second_number\n"
)
VIOLATING_PYTHON_SOURCE = (
    "def calculate_total_price(unit_price: int, quantity: int) -> int:\n"
    "    return unit_price * quantity * 199 * 42\n"
)


def run_gate(payload: dict[str, object]) -> "subprocess.CompletedProcess[str]":
    return run_validators_entrypoint_subprocess(["--pre-tool-use"], stdin_text=json.dumps(payload))


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

    def test_edit_validates_reconstructed_post_edit_content(self, tmp_path: Path) -> None:
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
