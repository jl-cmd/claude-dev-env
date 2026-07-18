"""Tests for run_all_validators.py."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from .run_all_validators import (
    ValidatorResult,
    _hooks_subprocess_working_directory_and_environment,
    _temporary_path_preserving_directory_signal,
    add_timing,
    build_json_output,
    create_timing_metrics,
    format_timing_report,
    main,
    print_header,
    run_git_checks,
    run_python_style_checks,
    run_with_fallback,
)


def _passing_mock_result() -> MagicMock:
    """Return a mock validator result that reports a passing check."""
    mock_result = MagicMock()
    mock_result.passed = True
    mock_result.name = "Test"
    mock_result.checks = "test"
    mock_result.output = ""
    return mock_result


def _run_main_with_argv(command_line_arguments: list[str]) -> int | None:
    """Run ``main`` under the given argv and always restore the original argv."""
    original_argv = sys.argv
    try:
        sys.argv = command_line_arguments
        return main()
    finally:
        sys.argv = original_argv


class TestFixFlag:
    """Test --fix flag functionality."""

    def test_fix_flag_is_accepted(self) -> None:
        """Verify --fix flag is recognized without error."""
        with patch("validators.run_all_validators.get_changed_files") as mock_get_files, \
             patch("validators.run_all_validators.run_file_structure_checks") as mock_file, \
             patch("validators.run_all_validators.run_git_checks") as mock_git:
            mock_get_files.return_value = []
            mock_file.return_value = _passing_mock_result()
            mock_git.return_value = _passing_mock_result()

            assert _run_main_with_argv(["run_all_validators.py", "--fix"]) == 0

    def test_fix_flag_calls_fix_python_style(self) -> None:
        """Verify --fix flag triggers fix_python_style when files exist."""
        with patch("validators.run_all_validators.get_changed_files") as mock_get_files, \
             patch("validators.run_all_validators.fix_python_style") as mock_fix, \
             patch("validators.run_all_validators.run_python_style_checks") as mock_style, \
             patch("validators.run_all_validators.run_test_safety_checks") as mock_test, \
             patch("validators.run_all_validators.run_react_checks") as mock_react, \
             patch("validators.run_all_validators.run_comment_checks") as mock_comment, \
             patch("validators.run_all_validators.run_file_structure_checks") as mock_file, \
             patch("validators.run_all_validators.run_git_checks") as mock_git:
            mock_get_files.return_value = [Path("test.py")]
            mock_fix.return_value = ["test.py"]
            for each_mock in (mock_style, mock_test, mock_react, mock_comment, mock_file, mock_git):
                each_mock.return_value = _passing_mock_result()

            _run_main_with_argv(["run_all_validators.py", "--fix"])

            mock_fix.assert_called_once()

    def test_no_fix_flag_skips_fixes(self) -> None:
        """Verify fixes are skipped when --fix flag is not provided."""
        with patch("validators.run_all_validators.get_changed_files") as mock_get_files, \
             patch("validators.run_all_validators.fix_python_style") as mock_fix, \
             patch("validators.run_all_validators.run_python_style_checks") as mock_style, \
             patch("validators.run_all_validators.run_test_safety_checks") as mock_test, \
             patch("validators.run_all_validators.run_react_checks") as mock_react, \
             patch("validators.run_all_validators.run_comment_checks") as mock_comment, \
             patch("validators.run_all_validators.run_file_structure_checks") as mock_file, \
             patch("validators.run_all_validators.run_git_checks") as mock_git:
            mock_get_files.return_value = [Path("test.py")]
            for each_mock in (mock_style, mock_test, mock_react, mock_comment, mock_file, mock_git):
                each_mock.return_value = _passing_mock_result()

            _run_main_with_argv(["run_all_validators.py"])

            mock_fix.assert_not_called()


class TestStagedPathContainment:
    """Staged validation paths must never escape the temporary root."""

    def test_parent_traversal_path_stays_inside_temp_root(self, tmp_path: Path) -> None:
        temporary_root = tmp_path / "staging"
        temporary_root.mkdir()
        traversal_path = "scripts/../../../../escaped_evil.py"

        staged_file = _temporary_path_preserving_directory_signal(
            temporary_root, traversal_path
        )
        staged_file.write_text("payload", encoding="utf-8")

        assert staged_file.resolve().is_relative_to(temporary_root.resolve())
        assert staged_file.read_text(encoding="utf-8") == "payload"

    def test_absolute_component_path_stays_inside_temp_root(self, tmp_path: Path) -> None:
        temporary_root = tmp_path / "staging"
        temporary_root.mkdir()
        absolute_style_path = "/etc/cron.d/evil.py"

        staged_file = _temporary_path_preserving_directory_signal(
            temporary_root, absolute_style_path
        )
        staged_file.write_text("payload", encoding="utf-8")

        assert staged_file.resolve().is_relative_to(temporary_root.resolve())


class TestGracefulDegradation:
    def test_missing_validator_returns_skipped_result(self) -> None:
        def failing_validator() -> ValidatorResult:
            raise FileNotFoundError("validator.py not found")

        skipped_result = run_with_fallback(
            failing_validator,
            "Missing Validator",
            "99",
        )

        assert skipped_result.skipped is True
        assert "skipped" in skipped_result.output.lower()
        assert skipped_result.passed is False

    def test_validator_exception_returns_skipped_result(self) -> None:
        def crashing_validator() -> ValidatorResult:
            raise RuntimeError("Unexpected crash")

        skipped_result = run_with_fallback(
            crashing_validator,
            "Crashing Validator",
            "99",
        )

        assert skipped_result.skipped is True
        assert "skipped" in skipped_result.output.lower()

    def test_successful_validator_returns_normal_result(self) -> None:
        def working_validator() -> ValidatorResult:
            return ValidatorResult(
                name="Working",
                checks="1",
                passed=True,
                output="All good",
            )

        normal_result = run_with_fallback(
            working_validator,
            "Working",
            "1",
        )

        assert normal_result.skipped is False
        assert normal_result.passed is True


class TestStderrSurfacing:
    """Verify that validator stderr is surfaced when stdout is empty."""

    def test_python_style_check_surfaces_stderr_when_stdout_empty(self) -> None:
        """When a validator crashes with no stdout, stderr must appear in output."""
        with patch("validators.run_all_validators.invoke_validator_module") as mock_invoke:
            crashed_result = MagicMock()
            crashed_result.returncode = 1
            crashed_result.stdout = ""
            crashed_result.stderr = "ImportError: No module named validators.python_style_checks"
            mock_invoke.return_value = crashed_result

            validator_result = run_python_style_checks([Path("foo.py")])

            assert "ImportError" in validator_result.output

    def test_git_check_surfaces_stderr_when_stdout_empty(self) -> None:
        """When git validator crashes with no stdout, stderr must appear in output."""
        with patch("validators.run_all_validators.invoke_validator_module") as mock_invoke:
            crashed_result = MagicMock()
            crashed_result.returncode = 1
            crashed_result.stdout = ""
            crashed_result.stderr = "SyntaxError: invalid syntax in git_checks.py"
            mock_invoke.return_value = crashed_result

            validator_result = run_git_checks()

            assert "SyntaxError" in validator_result.output

    def test_output_falls_back_to_all_checks_passed_when_both_empty(self) -> None:
        """When both stdout and stderr are empty and returncode is 0, use fallback."""
        with patch("validators.run_all_validators.invoke_validator_module") as mock_invoke:
            clean_result = MagicMock()
            clean_result.returncode = 0
            clean_result.stdout = ""
            clean_result.stderr = ""
            mock_invoke.return_value = clean_result

            validator_result = run_git_checks()

            assert validator_result.output == "All checks passed"


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


class TestHooksSubprocessWorkingDirectory:
    def test_unc_path_fallback_on_windows_uses_tempdir_when_temp_unset(self) -> None:
        mock_hooks_directory = MagicMock()
        mock_hooks_directory.resolve.return_value = Path("\\\\server\\share\\hooks")
        environment_without_temp = {
            each_key: each_value
            for each_key, each_value in os.environ.items()
            if each_key not in ("TEMP", "TMP")
        }
        with patch("validators.run_all_validators.hooks_dir", mock_hooks_directory), patch(
            "validators.run_all_validators.sys.platform", "win32"
        ), patch("validators.run_all_validators.os.environ", environment_without_temp):
            working_directory_string, _environment = (
                _hooks_subprocess_working_directory_and_environment()
            )
        assert working_directory_string == tempfile.gettempdir()
        assert not working_directory_string.startswith("\\\\")
