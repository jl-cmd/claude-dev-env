"""Tests for Python anti-pattern detection."""

import ast
import sys
from pathlib import Path

import pytest

from .python_antipattern_checks import (
    check_mutable_default_args,
    check_bare_except,
    check_print_in_production,
    validate_file,
)
from .run_all_validators import ValidatorResult, validate_proposed_file

_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent.parent / "blocking")
for each_candidate_directory in (_HOOKS_DIRECTORY, _BLOCKING_DIRECTORY):
    if each_candidate_directory not in sys.path:
        sys.path.insert(0, each_candidate_directory)

from code_rules_imports_logging import check_library_print  # noqa: E402


GOOD_NONE_DEFAULT = '''
def process(items=None):
    if items is None:
        items = []
    return items
'''

BAD_MUTABLE_DEFAULT = '''
def process(items=[]):
    return items
'''

BAD_DICT_DEFAULT = '''
def process(config={}):
    return config
'''

GOOD_SPECIFIC_EXCEPT = '''
def process():
    try:
        do_work()
    except ValueError:
        handle_error()
'''

BAD_BARE_EXCEPT = '''
def process():
    try:
        do_work()
    except:
        handle_error()
'''

GOOD_LOGGING = '''
import logging

def process():
    logging.info("Processing")
'''

BAD_PRINT = '''
def process():
    print("Debug info")
'''

TEST_FILE_WITH_PRINT = '''
def test_something():
    print("Test output")
    assert True
'''


class TestMutableDefaultArgs:
    def test_none_default_passes(self) -> None:
        tree = ast.parse(GOOD_NONE_DEFAULT)
        violations = check_mutable_default_args(tree, "test.py")
        assert violations == []

    def test_list_default_fails(self) -> None:
        tree = ast.parse(BAD_MUTABLE_DEFAULT)
        violations = check_mutable_default_args(tree, "test.py")
        assert len(violations) == 1
        assert "mutable" in violations[0].message.lower()

    def test_dict_default_fails(self) -> None:
        tree = ast.parse(BAD_DICT_DEFAULT)
        violations = check_mutable_default_args(tree, "test.py")
        assert len(violations) == 1


class TestBareExcept:
    def test_specific_except_passes(self) -> None:
        tree = ast.parse(GOOD_SPECIFIC_EXCEPT)
        violations = check_bare_except(tree, "test.py")
        assert violations == []

    def test_bare_except_fails(self) -> None:
        tree = ast.parse(BAD_BARE_EXCEPT)
        violations = check_bare_except(tree, "test.py")
        assert len(violations) == 1
        assert "bare" in violations[0].message.lower() or "except" in violations[0].message.lower()


class TestPrintInProduction:
    def test_logging_passes(self) -> None:
        tree = ast.parse(GOOD_LOGGING)
        violations = check_print_in_production(tree, "utils.py")
        assert violations == []

    def test_print_fails(self) -> None:
        tree = ast.parse(BAD_PRINT)
        violations = check_print_in_production(tree, "utils.py")
        assert len(violations) == 1
        assert "print" in violations[0].message.lower()

    def test_print_in_test_file_allowed(self) -> None:
        tree = ast.parse(TEST_FILE_WITH_PRINT)
        violations = check_print_in_production(tree, "test_utils.py")
        assert violations == []


CLI_ENTRY_POINT_WITH_PRINTS = '''
def main():
    print("line one")
    print("line two")
    print("line three")
    print("line four")
    print("line five")
'''

NEAR_MISS_WITH_PRINT = '''
def render():
    print("output")
'''


class TestPrintInCliEntryPoint:
    def test_cli_py_path_allows_print(self) -> None:
        tree = ast.parse(CLI_ENTRY_POINT_WITH_PRINTS)
        assert check_print_in_production(tree, "stp_preview/cli.py") == []

    def test_cli_suffix_path_allows_print(self) -> None:
        tree = ast.parse(CLI_ENTRY_POINT_WITH_PRINTS)
        assert check_print_in_production(tree, "stp_preview/report_cli.py") == []

    def test_scripts_path_allows_print(self) -> None:
        tree = ast.parse(CLI_ENTRY_POINT_WITH_PRINTS)
        assert check_print_in_production(tree, "packages/foo/scripts/run_job.py") == []

    def test_near_miss_name_still_flagged(self) -> None:
        tree = ast.parse(NEAR_MISS_WITH_PRINT)
        assert len(check_print_in_production(tree, "publicli.py")) == 1

    def test_non_cli_production_file_still_flagged(self) -> None:
        tree = ast.parse(NEAR_MISS_WITH_PRINT)
        assert len(check_print_in_production(tree, "stp_preview/renderer.py")) == 1


class TestValidateFile:
    def test_validate_file_flags_bare_except(self, tmp_path: Path) -> None:
        source_file = tmp_path / "worker.py"
        source_file.write_text(
            "def run():\n    try:\n        do_work()\n    except:\n        pass\n",
            encoding="utf-8",
        )
        violations = validate_file(source_file)
        assert len(violations) == 1
        assert "except" in violations[0].message.lower()


class TestCrossSurfaceConsistency:
    def test_matches_library_print_surface(self) -> None:
        source = "def main():\n    print('x')\n"
        tree = ast.parse(source)
        for path in (
            "stp_preview/cli.py",
            "stp_preview/renderer.py",
            "publicli.py",
            "packages/foo/scripts/run_job.py",
        ):
            production_allows = check_print_in_production(tree, path) == []
            library_allows = check_library_print(source, path) == []
            assert production_allows == library_allows


CLI_BASENAME = "cli.py"
ANTIPATTERN_VALIDATOR_NAME = "Python Anti-patterns"
PRINT_FINDING_FRAGMENT = "print() in production"

PIPELINE_PRINT_SOURCE = '''
def emit_status(message):
    print(message)
'''


def _antipattern_result_for(file_path: str, content: str) -> ValidatorResult:
    """Return the Python Anti-patterns result for content proposed at file_path."""
    all_results = validate_proposed_file(file_path, content)
    return next(
        each_result
        for each_result in all_results
        if each_result.name == ANTIPATTERN_VALIDATOR_NAME
    )


class TestPrintCliExemptionThroughPipeline:
    """Pin the CLI-marker print exemption through the validate_proposed_file pipeline.

    A basename of cli.py lands in the system temp dir as .../cli.py, so the
    marker /cli.py matches and the print check stays silent. Near-miss basenames
    (publicli.py) are covered at the unit surface; the pipeline stages under a
    temp root that often contains the substring 'test', which short-circuits the
    print check before the CLI-marker path runs.
    """

    def test_pins_cli_basename_allows_print_through_pipeline(self) -> None:
        antipattern_result = _antipattern_result_for(CLI_BASENAME, PIPELINE_PRINT_SOURCE)
        assert antipattern_result.passed
        assert PRINT_FINDING_FRAGMENT not in antipattern_result.output
