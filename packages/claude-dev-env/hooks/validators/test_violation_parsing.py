"""Tests for validator output-line location parsing."""

from .violation_parsing import _violation_line_number


class TestViolationLineNumber:
    def test_ruff_line_col_prefix_returns_line_not_column(self) -> None:
        ruff_shaped_line = "/pkg/legacy_module.py:37:5: F401 `os` imported but unused"

        assert _violation_line_number(ruff_shaped_line) == 37

    def test_windows_drive_prefix_returns_line(self) -> None:
        windows_shaped_line = r"C:\repo\tmp\legacy_module.py:37:5: F401 unused import"

        assert _violation_line_number(windows_shaped_line) == 37

    def test_check_module_line_prefix_returns_line(self) -> None:
        check_module_line = "/pkg/legacy_module.py:37: magic number 199"

        assert _violation_line_number(check_module_line) == 37

    def test_summary_line_without_location_returns_zero(self) -> None:
        assert _violation_line_number("Found 3 errors.") == 0

    def test_code_frame_line_quoting_colon_digits_returns_zero(self) -> None:
        frame_line = '4 | message = "err:37: bad"'

        assert _violation_line_number(frame_line) == 0

    def test_code_frame_source_line_returns_zero(self) -> None:
        assert _violation_line_number("17 | import os") == 0

    def test_path_with_spaces_returns_line(self) -> None:
        spaced_path_line = "/tmp/my dir/legacy module.py:37: magic number 199"

        assert _violation_line_number(spaced_path_line) == 37
