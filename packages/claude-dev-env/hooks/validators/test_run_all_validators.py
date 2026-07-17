"""Tests for the run_all_validators entry module: CLI flags and report helpers."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from .run_all_validators import (
    add_timing,
    build_json_output,
    create_timing_metrics,
    format_timing_report,
    main,
    print_header,
)


class TestFixFlag:
    """Test --fix flag functionality."""

    def test_fix_flag_is_accepted(self) -> None:
        """Verify --fix flag is recognized without error."""
        with (
            patch("validators.run_all_validators.get_changed_files") as mock_get_files,
            patch(
                "validators.run_all_validators.run_file_structure_checks"
            ) as mock_file,
            patch("validators.run_all_validators.run_git_checks") as mock_git,
        ):
            mock_get_files.return_value = []

            mock_result = MagicMock()
            mock_result.passed = True
            mock_result.name = "Test"
            mock_result.checks = "test"
            mock_result.output = ""

            mock_file.return_value = mock_result
            mock_git.return_value = mock_result

            original_argv = sys.argv
            try:
                sys.argv = ["run_all_validators.py", "--fix"]
                result = main()
                assert result == 0
            finally:
                sys.argv = original_argv

    def test_fix_flag_calls_fix_python_style(self) -> None:
        """Verify --fix flag triggers fix_python_style when files exist."""
        with (
            patch("validators.run_all_validators.get_changed_files") as mock_get_files,
            patch("validators.run_all_validators.fix_python_style") as mock_fix,
            patch(
                "validators.run_all_validators.run_python_style_checks"
            ) as mock_style,
            patch("validators.run_all_validators.run_test_safety_checks") as mock_test,
            patch("validators.run_all_validators.run_react_checks") as mock_react,
            patch("validators.run_all_validators.run_comment_checks") as mock_comment,
            patch(
                "validators.run_all_validators.run_file_structure_checks"
            ) as mock_file,
            patch("validators.run_all_validators.run_git_checks") as mock_git,
        ):
            mock_get_files.return_value = [Path("test.py")]
            mock_fix.return_value = ["test.py"]

            mock_result = MagicMock()
            mock_result.passed = True
            mock_result.name = "Test"
            mock_result.checks = "test"
            mock_result.output = ""

            mock_style.return_value = mock_result
            mock_test.return_value = mock_result
            mock_react.return_value = mock_result
            mock_comment.return_value = mock_result
            mock_file.return_value = mock_result
            mock_git.return_value = mock_result

            original_argv = sys.argv
            try:
                sys.argv = ["run_all_validators.py", "--fix"]
                main()
            finally:
                sys.argv = original_argv

            mock_fix.assert_called_once()

    def test_no_fix_flag_skips_fixes(self) -> None:
        """Verify fixes are skipped when --fix flag is not provided."""
        with (
            patch("validators.run_all_validators.get_changed_files") as mock_get_files,
            patch("validators.run_all_validators.fix_python_style") as mock_fix,
            patch(
                "validators.run_all_validators.run_python_style_checks"
            ) as mock_style,
            patch("validators.run_all_validators.run_test_safety_checks") as mock_test,
            patch("validators.run_all_validators.run_react_checks") as mock_react,
            patch("validators.run_all_validators.run_comment_checks") as mock_comment,
            patch(
                "validators.run_all_validators.run_file_structure_checks"
            ) as mock_file,
            patch("validators.run_all_validators.run_git_checks") as mock_git,
        ):
            mock_get_files.return_value = [Path("test.py")]

            mock_result = MagicMock()
            mock_result.passed = True
            mock_result.name = "Test"
            mock_result.checks = "test"
            mock_result.output = ""

            mock_style.return_value = mock_result
            mock_test.return_value = mock_result
            mock_react.return_value = mock_result
            mock_comment.return_value = mock_result
            mock_file.return_value = mock_result
            mock_git.return_value = mock_result

            original_argv = sys.argv
            try:
                sys.argv = ["run_all_validators.py"]
                main()
            finally:
                sys.argv = original_argv

            mock_fix.assert_not_called()


class TestTimingMetrics:
    def test_create_timing_metrics_empty(self) -> None:
        metrics = create_timing_metrics({})
        assert metrics.total_seconds == 0.0
        assert metrics.validator_times == {}

    def test_create_timing_metrics_with_data(self) -> None:
        timings = {"Validator A": 1.5, "Validator B": 2.0}
        metrics = create_timing_metrics(timings)
        assert metrics.total_seconds == 3.5
        assert metrics.validator_times == timings

    def test_add_timing_returns_new_instance(self) -> None:
        metrics1 = create_timing_metrics({})
        metrics2 = add_timing(metrics1, "Test", 1.5)

        assert metrics1.total_seconds == 0.0
        assert metrics2.total_seconds == 1.5
        assert "Test" not in metrics1.validator_times
        assert metrics2.validator_times["Test"] == 1.5

    def test_format_report_includes_all_timings(self) -> None:
        metrics = create_timing_metrics({"Fast": 0.1, "Slow": 2.5})
        report = format_timing_report(metrics)

        assert "Fast" in report
        assert "Slow" in report
        assert "2.6" in report


class TestVersionHeader:
    def test_print_header_includes_version(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        print_header()
        captured = capsys.readouterr()

        assert "PRE-PUSH VALIDATOR RESULTS" in captured.out
        assert "(v" in captured.out

    def test_build_json_output_includes_version(self) -> None:
        json_output = build_json_output(
            results=[],
            metrics=create_timing_metrics({}),
            include_timing=False,
        )

        assert "version" in json_output
        assert "timestamp" in json_output
        assert isinstance(json_output["version"], str)
