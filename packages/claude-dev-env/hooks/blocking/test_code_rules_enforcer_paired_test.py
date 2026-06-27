"""Behavioral tests for the public-function paired-test coverage check.

Drives ``check_public_function_missing_paired_test`` over a real temporary
filesystem whose path carries no ``test``/``hooks``/``config`` segment, so the
module under test is classified as ordinary production code while its on-disk
paired test files are read exactly as they would be in a real package.
"""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

_BLOCKING_DIRECTORY = Path(__file__).resolve().parent
if str(_BLOCKING_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_BLOCKING_DIRECTORY))

from code_rules_paired_test import (  # noqa: E402
    check_public_function_missing_paired_test,
)

_TWO_PUBLIC_FUNCTIONS = "def alpha():\n    return 1\n\n\ndef beta():\n    return 2\n"


@pytest.fixture
def neutral_package_directory() -> Iterator[Path]:
    """Yield a ``pkg`` directory under a neutral temp root with a ``tests`` child.

    The root prefix carries no ``test`` segment, so the module path the check
    receives is classified as production code rather than a test file.
    """
    with tempfile.TemporaryDirectory(prefix="paircov_") as root_name:
        package_directory = Path(root_name) / "pkg"
        (package_directory / "tests").mkdir(parents=True)
        yield package_directory


def _write_test_file(package_directory: Path, filename: str, body: str) -> None:
    (package_directory / "tests" / filename).write_text(body, encoding="utf-8")


def test_flags_public_function_absent_from_established_suite(
    neutral_package_directory: Path,
) -> None:
    _write_test_file(
        neutral_package_directory,
        "test_mod.py",
        "from pkg.mod import alpha\n\ndef test_alpha():\n    assert alpha() == 1\n",
    )
    all_issues = check_public_function_missing_paired_test(
        _TWO_PUBLIC_FUNCTIONS, str(neutral_package_directory / "mod.py")
    )
    assert len(all_issues) == 1
    assert "beta" in all_issues[0]
    assert "paired test suite" in all_issues[0]
    assert "alpha" not in all_issues[0]


def test_clean_when_suite_covers_every_public_function(
    neutral_package_directory: Path,
) -> None:
    _write_test_file(
        neutral_package_directory,
        "test_mod.py",
        "from pkg.mod import alpha, beta\n\ndef test_both():\n    assert alpha() and beta()\n",
    )
    all_issues = check_public_function_missing_paired_test(
        _TWO_PUBLIC_FUNCTIONS, str(neutral_package_directory / "mod.py")
    )
    assert all_issues == []


def test_skips_module_without_dedicated_test_file(
    neutral_package_directory: Path,
) -> None:
    all_issues = check_public_function_missing_paired_test(
        _TWO_PUBLIC_FUNCTIONS, str(neutral_package_directory / "mod.py")
    )
    assert all_issues == []


def test_skips_when_suite_covers_no_public_function(
    neutral_package_directory: Path,
) -> None:
    _write_test_file(
        neutral_package_directory,
        "test_mod.py",
        "def test_unrelated():\n    assert 1 + 1 == 2\n",
    )
    all_issues = check_public_function_missing_paired_test(
        _TWO_PUBLIC_FUNCTIONS, str(neutral_package_directory / "mod.py")
    )
    assert all_issues == []


def test_counts_coverage_across_sibling_test_files(
    neutral_package_directory: Path,
) -> None:
    _write_test_file(
        neutral_package_directory,
        "test_mod.py",
        "from pkg.mod import alpha\n\ndef test_alpha():\n    assert alpha() == 1\n",
    )
    _write_test_file(
        neutral_package_directory,
        "test_extra.py",
        "from pkg.mod import beta\n\ndef test_beta():\n    assert beta() == 2\n",
    )
    all_issues = check_public_function_missing_paired_test(
        _TWO_PUBLIC_FUNCTIONS, str(neutral_package_directory / "mod.py")
    )
    assert all_issues == []


def test_main_and_private_functions_are_never_required(
    neutral_package_directory: Path,
) -> None:
    module_source = (
        "def alpha():\n    return 1\n\n\n"
        "def main():\n    return 0\n\n\n"
        "def _helper():\n    return 2\n"
    )
    _write_test_file(
        neutral_package_directory,
        "test_mod.py",
        "from pkg.mod import alpha\n\ndef test_alpha():\n    assert alpha() == 1\n",
    )
    all_issues = check_public_function_missing_paired_test(
        module_source, str(neutral_package_directory / "mod.py")
    )
    assert all_issues == []


def test_exempts_hook_infrastructure_and_test_paths(
    neutral_package_directory: Path,
) -> None:
    _write_test_file(
        neutral_package_directory,
        "test_mod.py",
        "from pkg.mod import alpha\n\ndef test_alpha():\n    assert alpha() == 1\n",
    )
    hook_path = "/repo/hooks/blocking/code_rules_paired_test.py"
    test_path = str(neutral_package_directory / "tests" / "test_mod.py")
    assert check_public_function_missing_paired_test(_TWO_PUBLIC_FUNCTIONS, hook_path) == []
    assert check_public_function_missing_paired_test(_TWO_PUBLIC_FUNCTIONS, test_path) == []
