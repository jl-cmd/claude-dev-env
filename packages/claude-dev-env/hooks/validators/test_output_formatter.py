"""Tests for output formatting."""

import os
import sys

import pytest

from .output_formatter import (
    OutputFormatter,
    OutputMode,
    format_violation_with_context,
    colorize,
    group_violations_by_file,
    format_grouped_violations,
    ViolationDict,
    ValidatorResultDict,
)


class TestColorize:
    def test_colorize_pass(self) -> None:
        result = colorize("PASS", "green")
        assert "PASS" in result

    def test_colorize_fail(self) -> None:
        result = colorize("FAIL", "red")
        assert "FAIL" in result

    def test_colorize_disabled(self) -> None:
        result = colorize("PASS", "green", enabled=False)
        assert result == "PASS"


class TestFormatViolationWithContext:
    def test_shows_surrounding_lines(self) -> None:
        source = '''line 1
line 2
line 3 with error
line 4
line 5'''
        result = format_violation_with_context(
            source=source,
            line_num=3,
            message="Error on line 3",
            context_lines=1,
        )
        assert "line 2" in result
        assert "line 3 with error" in result
        assert "line 4" in result

    def test_highlights_error_line(self) -> None:
        source = '''line 1
line 2
line 3 with error
line 4'''
        result = format_violation_with_context(
            source=source,
            line_num=3,
            message="Error",
            context_lines=1,
        )
        assert ">" in result or "3" in result


class TestOutputFormatter:
    def test_json_mode_output(self) -> None:
        formatter = OutputFormatter(mode=OutputMode.JSON)
        results: list[ValidatorResultDict] = [
            {"name": "Test", "checks": "1", "passed": True, "output": "OK"}
        ]
        output = formatter.format_results(results)
        assert '"name"' in output
        assert '"passed"' in output

    def test_text_mode_output(self) -> None:
        formatter = OutputFormatter(mode=OutputMode.TEXT)
        results: list[ValidatorResultDict] = [
            {"name": "Test", "checks": "1", "passed": True, "output": "OK"}
        ]
        output = formatter.format_results(results)
        assert "Test" in output
        assert "PASS" in output or "OK" in output

    def test_effective_use_colors_false_when_disabled(self) -> None:
        formatter = OutputFormatter(mode=OutputMode.TEXT, use_colors=False)
        assert formatter.effective_use_colors is False

    def test_formatter_is_immutable(self) -> None:
        formatter = OutputFormatter(mode=OutputMode.TEXT)
        with pytest.raises(AttributeError):
            formatter.mode = OutputMode.JSON


class TestJsonFlag:
    def test_json_flag_produces_valid_json(self) -> None:
        import json
        import subprocess

        validators_directory = os.path.dirname(os.path.abspath(__file__))
        hooks_directory = os.path.normpath(
            os.path.join(validators_directory, os.pardir)
        )
        result = subprocess.run(
            [sys.executable, "-m", "validators.run_all_validators", "--json"],
            capture_output=True,
            text=True,
            cwd=hooks_directory,
        )

        output = result.stdout.strip()
        parsed = json.loads(output)
        assert "results" in parsed
        assert isinstance(parsed["results"], list)


class TestGroupViolationsByFile:
    def test_groups_violations_by_file_path(self) -> None:
        violations: list[ViolationDict] = [
            {"file": "a.py", "line": 1, "message": "error 1"},
            {"file": "b.py", "line": 2, "message": "error 2"},
            {"file": "a.py", "line": 3, "message": "error 3"},
        ]
        grouped = group_violations_by_file(violations)

        assert len(grouped) == 2
        assert len(grouped["a.py"]) == 2
        assert len(grouped["b.py"]) == 1

    def test_empty_list_returns_empty_dict(self) -> None:
        grouped = group_violations_by_file([])
        assert grouped == {}


class TestFormatGroupedViolations:
    def test_formats_with_file_headers(self) -> None:
        violations: list[ViolationDict] = [
            {"file": "a.py", "line": 1, "message": "error 1"},
            {"file": "a.py", "line": 3, "message": "error 2"},
        ]
        grouped = group_violations_by_file(violations)
        output = format_grouped_violations(grouped, use_colors=False)

        assert "a.py" in output
        assert "Line 1:" in output
        assert "Line 3:" in output

    def test_sorts_violations_by_line_number(self) -> None:
        violations: list[ViolationDict] = [
            {"file": "a.py", "line": 10, "message": "later"},
            {"file": "a.py", "line": 2, "message": "earlier"},
        ]
        grouped = group_violations_by_file(violations)
        output = format_grouped_violations(grouped, use_colors=False)

        earlier_pos = output.find("Line 2:")
        later_pos = output.find("Line 10:")
        assert earlier_pos < later_pos
