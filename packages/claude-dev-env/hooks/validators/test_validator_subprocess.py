"""Tests for the validator subprocess helpers and stderr surfacing."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from .branch_scoped_runners import run_git_checks
from .file_scoped_runners import run_python_style_checks
from .validator_subprocess import _hooks_subprocess_working_directory_and_environment


class TestStderrSurfacing:
    """Verify that validator stderr is surfaced when stdout is empty."""

    def test_python_style_check_surfaces_stderr_when_stdout_empty(self) -> None:
        """When a validator crashes with no stdout, stderr must appear in output."""
        with patch(
            "validators.file_scoped_runners.invoke_validator_module"
        ) as mock_invoke:
            crashed_result = MagicMock()
            crashed_result.returncode = 1
            crashed_result.stdout = ""
            crashed_result.stderr = (
                "ImportError: No module named validators.python_style_checks"
            )
            mock_invoke.return_value = crashed_result

            validator_result = run_python_style_checks([Path("foo.py")])

            assert "ImportError" in validator_result.output

    def test_git_check_surfaces_stderr_when_stdout_empty(self) -> None:
        """When git validator crashes with no stdout, stderr must appear in output."""
        with patch(
            "validators.branch_scoped_runners.invoke_validator_module"
        ) as mock_invoke:
            crashed_result = MagicMock()
            crashed_result.returncode = 1
            crashed_result.stdout = ""
            crashed_result.stderr = "SyntaxError: invalid syntax in git_checks.py"
            mock_invoke.return_value = crashed_result

            validator_result = run_git_checks()

            assert "SyntaxError" in validator_result.output

    def test_output_falls_back_to_all_checks_passed_when_both_empty(self) -> None:
        """When both stdout and stderr are empty and returncode is 0, use fallback."""
        with patch(
            "validators.branch_scoped_runners.invoke_validator_module"
        ) as mock_invoke:
            clean_result = MagicMock()
            clean_result.returncode = 0
            clean_result.stdout = ""
            clean_result.stderr = ""
            mock_invoke.return_value = clean_result

            validator_result = run_git_checks()

            assert validator_result.output == "All checks passed"


class TestHooksSubprocessWorkingDirectory:
    def test_unc_path_fallback_on_windows_uses_tempdir_when_temp_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_hooks_directory = MagicMock()
        mock_hooks_directory.resolve = MagicMock(
            return_value=Path("\\\\server\\share\\hooks")
        )
        monkeypatch.delenv("TEMP", raising=False)
        monkeypatch.delenv("TMP", raising=False)
        monkeypatch.setattr(
            "validators.validator_subprocess.hooks_dir", mock_hooks_directory
        )
        monkeypatch.setattr("validators.validator_subprocess.sys.platform", "win32")

        working_directory_string, _environment = (
            _hooks_subprocess_working_directory_and_environment()
        )

        assert working_directory_string == tempfile.gettempdir()
        assert not working_directory_string.startswith("\\\\")
