#!/usr/bin/env python3
"""Tests for AST-based test safety validators."""

import tempfile
from pathlib import Path
from typing import List

import pytest

from test_safety_checks import (
    Violation,
    check_no_skip_decorators,
    check_debug_guard_in_dev_scripts,
    main,
)


class TestNoSkipDecorators:
    """Test detection of skip decorators in test files."""

    def test_detects_pytest_skip_decorator(self) -> None:
        code = """
import pytest

@pytest.mark.skip
def test_something():
    pass
"""
        violations = check_no_skip_decorators(code, "test_file.py")
        assert len(violations) == 1
        assert violations[0].line == 5
        assert "skip decorator" in violations[0].message.lower()

    def test_detects_pytest_skip_with_reason(self) -> None:
        code = """
import pytest

@pytest.mark.skip(reason="not ready")
def test_something():
    pass
"""
        violations = check_no_skip_decorators(code, "test_file.py")
        assert len(violations) == 1
        assert violations[0].line == 5

    def test_detects_unittest_skip(self) -> None:
        code = """
import unittest

class TestCase(unittest.TestCase):
    @unittest.skip("reason")
    def test_something(self):
        pass
"""
        violations = check_no_skip_decorators(code, "test_file.py")
        assert len(violations) == 1
        assert violations[0].line == 6

    def test_detects_skipif_decorator(self) -> None:
        code = """
import pytest

@pytest.mark.skipif(True, reason="reason")
def test_something():
    pass
"""
        violations = check_no_skip_decorators(code, "test_file.py")
        assert len(violations) == 1
        assert violations[0].line == 5

    def test_detects_skipunless_decorator(self) -> None:
        code = """
import unittest

class TestCase(unittest.TestCase):
    @unittest.skipUnless(False, "reason")
    def test_something(self):
        pass
"""
        violations = check_no_skip_decorators(code, "test_file.py")
        assert len(violations) == 1
        assert violations[0].line == 6

    def test_detects_multiple_skip_decorators(self) -> None:
        code = """
import pytest

@pytest.mark.skip
def test_one():
    pass

@pytest.mark.skipif(True, reason="reason")
def test_two():
    pass
"""
        violations = check_no_skip_decorators(code, "test_file.py")
        assert len(violations) == 2
        assert violations[0].line == 5
        assert violations[1].line == 9

    def test_allows_other_decorators(self) -> None:
        code = """
import pytest

@pytest.mark.parametrize("x", [1, 2, 3])
def test_something(x):
    pass

@pytest.fixture
def my_fixture():
    pass
"""
        violations = check_no_skip_decorators(code, "test_file.py")
        assert len(violations) == 0

    def test_allows_tests_without_decorators(self) -> None:
        code = """
def test_something():
    pass
"""
        violations = check_no_skip_decorators(code, "test_file.py")
        assert len(violations) == 0

    def test_detects_case_insensitive_skip_decorator(self) -> None:
        """Test that decorator names are matched case-insensitively."""
        code = """
import pytest

@pytest.mark.Skip
def test_something():
    pass
"""
        violations = check_no_skip_decorators(code, "test_file.py")
        assert len(violations) == 1
        assert violations[0].line == 5
        assert "skip decorator" in violations[0].message.lower()

    def test_detects_case_insensitive_skipif(self) -> None:
        """Test that SkipIf is caught."""
        code = """
import unittest

class TestCase(unittest.TestCase):
    @unittest.SkipIf(True, "reason")
    def test_something(self):
        pass
"""
        violations = check_no_skip_decorators(code, "test_file.py")
        assert len(violations) == 1
        assert violations[0].line == 6


class TestDebugGuardInDevScripts:
    """Test detection of missing DEBUG checks in management commands."""

    def test_detects_missing_debug_check(self) -> None:
        code = """
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    def handle(self, *args, **options):
        print("Doing dangerous thing")
"""
        violations = check_debug_guard_in_dev_scripts(
            code, "management/commands/dev_tool.py"
        )
        assert len(violations) == 1
        assert "DEBUG" in violations[0].message

    def test_allows_debug_check_at_start(self) -> None:
        code = """
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Only for development")
        print("Doing thing")
"""
        violations = check_debug_guard_in_dev_scripts(
            code, "management/commands/dev_tool.py"
        )
        assert len(violations) == 0

    def test_allows_debug_check_with_return(self) -> None:
        code = """
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    def handle(self, *args, **options):
        if not settings.DEBUG:
            return
        print("Doing thing")
"""
        violations = check_debug_guard_in_dev_scripts(
            code, "management/commands/dev_tool.py"
        )
        assert len(violations) == 0

    def test_ignores_non_management_commands(self) -> None:
        code = """
def some_function():
    print("Doing thing")
"""
        violations = check_debug_guard_in_dev_scripts(code, "utils/helper.py")
        assert len(violations) == 0

    def test_ignores_files_outside_management_commands(self) -> None:
        code = """
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    def handle(self, *args, **options):
        print("Doing thing")
"""
        violations = check_debug_guard_in_dev_scripts(code, "some/other/path.py")
        assert len(violations) == 0

    def test_allows_positive_debug_check_with_else_raise(self) -> None:
        """Test that 'if settings.DEBUG: ... else: raise' is a valid guard."""
        code = """
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    def handle(self, *args, **options):
        if settings.DEBUG:
            print("OK")
        else:
            raise CommandError("Development only")
        print("Doing thing")
"""
        violations = check_debug_guard_in_dev_scripts(
            code, "management/commands/dev_tool.py"
        )
        assert len(violations) == 0

    def test_allows_positive_debug_check_with_else_return(self) -> None:
        """Test that 'if settings.DEBUG: ... else: return' is a valid guard."""
        code = """
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    def handle(self, *args, **options):
        if settings.DEBUG:
            pass
        else:
            return
        print("Doing thing")
"""
        violations = check_debug_guard_in_dev_scripts(
            code, "management/commands/dev_tool.py"
        )
        assert len(violations) == 0


class TestViolation:
    """Test Violation dataclass."""

    def test_violation_creation(self) -> None:
        v = Violation("test.py", 42, "Test message")
        assert v.file == "test.py"
        assert v.line == 42
        assert v.message == "Test message"

    def test_violation_str(self) -> None:
        v = Violation("test.py", 42, "Test message")
        assert str(v) == "test.py:42: Test message"


class TestMainFunction:
    """Test main CLI function."""

    def test_main_with_no_violations(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_good.py"
        test_file.write_text("def test_something():\n    pass\n")

        exit_code = main([str(test_file)])
        assert exit_code == 0

    def test_main_with_violations(self, tmp_path: Path, capsys) -> None:
        test_file = tmp_path / "test_bad.py"
        test_file.write_text("import pytest\n\n@pytest.mark.skip\ndef test_x():\n    pass\n")

        exit_code = main([str(test_file)])
        assert exit_code == 1

        captured = capsys.readouterr()
        assert ":4:" in captured.out
        assert "skip decorator" in captured.out.lower()

    def test_main_with_multiple_files(self, tmp_path: Path) -> None:
        file1 = tmp_path / "test_good.py"
        file1.write_text("def test_something():\n    pass\n")

        file2 = tmp_path / "test_bad.py"
        file2.write_text("import pytest\n\n@pytest.mark.skip\ndef test_x():\n    pass\n")

        exit_code = main([str(file1), str(file2)])
        assert exit_code == 1

    def test_main_with_management_command(self, tmp_path: Path, capsys) -> None:
        mgmt_dir = tmp_path / "management" / "commands"
        mgmt_dir.mkdir(parents=True)
        cmd_file = mgmt_dir / "dev_tool.py"
        cmd_file.write_text("""
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    def handle(self, *args, **options):
        print("Dangerous")
""")

        exit_code = main([str(cmd_file)])
        assert exit_code == 1

        captured = capsys.readouterr()
        assert "DEBUG" in captured.out
