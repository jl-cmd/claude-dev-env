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
    check_test_file_omits_module_public_function,
)

_TWO_PUBLIC_FUNCTIONS = "def alpha():\n    return 1\n\n\ndef beta():\n    return 2\n"
_THREE_PUBLIC_FUNCTIONS = (
    "def alpha():\n    return 1\n\n\n"
    "def beta():\n    return 2\n\n\n"
    "def gamma():\n    return 3\n"
)


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


def test_flags_public_surface_when_suite_exercises_only_private_helper(
    neutral_package_directory: Path,
) -> None:
    module_source = (
        "def _aarrggbb_to_css(value):\n    return value\n\n\n"
        "def render_table():\n    return _aarrggbb_to_css('x')\n\n\n"
        "def render_summary():\n    return 2\n"
    )
    _write_test_file(
        neutral_package_directory,
        "test_mod.py",
        "from pkg.mod import _aarrggbb_to_css\n\n"
        "def test_helper():\n    assert _aarrggbb_to_css('x') == 'x'\n",
    )
    all_issues = check_public_function_missing_paired_test(
        module_source, str(neutral_package_directory / "mod.py")
    )
    assert len(all_issues) == 2
    flagged_names = " ".join(all_issues)
    assert "render_table" in flagged_names
    assert "render_summary" in flagged_names


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


def _write_module(package_directory: Path, body: str) -> None:
    (package_directory / "mod.py").write_text(body, encoding="utf-8")


_SUITE_COVERS_ALPHA_BETA = (
    "from pkg.mod import alpha, beta\n\n"
    "def test_pair():\n    assert alpha() == 1 and beta() == 2\n"
)


def test_flags_module_public_function_when_test_suite_omits_it(
    neutral_package_directory: Path,
) -> None:
    _write_module(neutral_package_directory, _THREE_PUBLIC_FUNCTIONS)
    test_path = str(neutral_package_directory / "tests" / "test_mod.py")
    all_issues = check_test_file_omits_module_public_function(
        _SUITE_COVERS_ALPHA_BETA, test_path
    )
    assert len(all_issues) == 1
    assert "gamma" in all_issues[0]
    assert "mod.py" in all_issues[0]
    assert "alpha" not in all_issues[0]
    assert "beta" not in all_issues[0]


def test_clean_when_test_suite_covers_every_module_public_function(
    neutral_package_directory: Path,
) -> None:
    _write_module(neutral_package_directory, _THREE_PUBLIC_FUNCTIONS)
    test_path = str(neutral_package_directory / "tests" / "test_mod.py")
    suite_covers_all = (
        "from pkg.mod import alpha, beta, gamma\n\n"
        "def test_all():\n    assert alpha() and beta() and gamma()\n"
    )
    all_issues = check_test_file_omits_module_public_function(suite_covers_all, test_path)
    assert all_issues == []


def test_skips_when_test_suite_covers_no_module_public_function(
    neutral_package_directory: Path,
) -> None:
    _write_module(neutral_package_directory, _THREE_PUBLIC_FUNCTIONS)
    test_path = str(neutral_package_directory / "tests" / "test_mod.py")
    all_issues = check_test_file_omits_module_public_function(
        "def test_unrelated():\n    assert 1 + 1 == 2\n", test_path
    )
    assert all_issues == []


def test_skips_test_file_with_no_paired_production_module(
    neutral_package_directory: Path,
) -> None:
    test_path = str(neutral_package_directory / "tests" / "test_mod.py")
    all_issues = check_test_file_omits_module_public_function(
        _SUITE_COVERS_ALPHA_BETA, test_path
    )
    assert all_issues == []


def test_ignores_a_non_stem_matched_written_file(
    neutral_package_directory: Path,
) -> None:
    _write_module(neutral_package_directory, _THREE_PUBLIC_FUNCTIONS)
    helper_path = str(neutral_package_directory / "helper.py")
    all_issues = check_test_file_omits_module_public_function(
        _SUITE_COVERS_ALPHA_BETA, helper_path
    )
    assert all_issues == []


def test_resolves_production_module_beside_the_test_file(
    neutral_package_directory: Path,
) -> None:
    _write_module(neutral_package_directory, _THREE_PUBLIC_FUNCTIONS)
    beside_test_path = str(neutral_package_directory / "test_mod.py")
    all_issues = check_test_file_omits_module_public_function(
        _SUITE_COVERS_ALPHA_BETA, beside_test_path
    )
    assert len(all_issues) == 1
    assert "gamma" in all_issues[0]


def test_judges_post_edit_content_over_stale_on_disk_test(
    neutral_package_directory: Path,
) -> None:
    _write_module(neutral_package_directory, _THREE_PUBLIC_FUNCTIONS)
    _write_test_file(
        neutral_package_directory,
        "test_mod.py",
        _SUITE_COVERS_ALPHA_BETA,
    )
    test_path = str(neutral_package_directory / "tests" / "test_mod.py")
    post_edit_covers_all = (
        "from pkg.mod import alpha, beta, gamma\n\n"
        "def test_all():\n    assert alpha() and beta() and gamma()\n"
    )
    all_issues = check_test_file_omits_module_public_function(
        post_edit_covers_all, test_path
    )
    assert all_issues == []


def test_counts_coverage_across_sibling_test_files_on_test_write(
    neutral_package_directory: Path,
) -> None:
    _write_module(neutral_package_directory, _THREE_PUBLIC_FUNCTIONS)
    _write_test_file(
        neutral_package_directory,
        "test_extra.py",
        "from pkg.mod import gamma\n\ndef test_gamma():\n    assert gamma() == 3\n",
    )
    test_path = str(neutral_package_directory / "tests" / "test_mod.py")
    all_issues = check_test_file_omits_module_public_function(
        _SUITE_COVERS_ALPHA_BETA, test_path
    )
    assert all_issues == []


def test_test_side_message_names_module_and_function_without_line_prefix(
    neutral_package_directory: Path,
) -> None:
    _write_module(neutral_package_directory, _THREE_PUBLIC_FUNCTIONS)
    test_path = str(neutral_package_directory / "tests" / "test_mod.py")
    all_issues = check_test_file_omits_module_public_function(
        _SUITE_COVERS_ALPHA_BETA, test_path
    )
    assert len(all_issues) == 1
    assert not all_issues[0].startswith("Line ")
    assert "mod.py" in all_issues[0]
    assert "gamma" in all_issues[0]


def test_test_side_omission_blocks_on_any_test_file_edit(
    neutral_package_directory: Path,
) -> None:
    _write_module(neutral_package_directory, _THREE_PUBLIC_FUNCTIONS)
    test_path = str(neutral_package_directory / "tests" / "test_mod.py")
    all_issues = check_test_file_omits_module_public_function(
        _SUITE_COVERS_ALPHA_BETA, test_path
    )
    assert len(all_issues) == 1
    assert "gamma" in all_issues[0]


def test_skips_when_paired_production_module_is_exempt(
    neutral_package_directory: Path,
) -> None:
    (neutral_package_directory / "__init__.py").write_text(
        _THREE_PUBLIC_FUNCTIONS, encoding="utf-8"
    )
    beside_test_path = str(neutral_package_directory / "test___init__.py")
    suite_covers_all = (
        "from pkg import alpha, beta, gamma\n\n"
        "def test_all():\n    assert alpha() and beta() and gamma()\n"
    )
    all_issues = check_test_file_omits_module_public_function(
        suite_covers_all, beside_test_path
    )
    assert all_issues == []
