"""Constants for the pytest unregistered-test-directory blocker.

A package whose ``pyproject.toml`` declares ``[tool.pytest.ini_options]`` with an
explicit ``testpaths`` list runs only the directories that list names. A
``test_*.py`` file written into a directory that no ``testpaths`` entry covers is
collected by no default ``pytest`` run, so the test silently never executes and a
regression in the code it guards passes the standard suite undetected. This
module holds the marker filename that anchors a pytest package, the key name
that identifies an explicit ``testpaths`` allowlist, the test-file basename
pattern, the package-root entry tokens and glob metacharacters that classify a
``testpaths`` entry, the directory names the upward search prunes, the search
budget, and the block-message text the hook emits.
"""

import re

__all__ = [
    "PYPROJECT_FILENAME",
    "TESTPATHS_KEY",
    "TEST_FILE_BASENAME_PATTERN",
    "PACKAGE_ROOT_ENTRY",
    "PACKAGE_ROOT_ENTRY_PREFIX",
    "GLOB_METACHARACTERS",
    "ALL_PRUNED_PARENT_DIRECTORY_NAMES",
    "MAX_PARENT_DIRECTORIES_SEARCHED",
    "UNREGISTERED_TEST_DIRECTORY_MESSAGE_TEMPLATE",
    "UNREGISTERED_TEST_DIRECTORY_SYSTEM_MESSAGE",
    "UNREGISTERED_TEST_DIRECTORY_ADDITIONAL_CONTEXT",
]

PYPROJECT_FILENAME: str = "pyproject.toml"

TESTPATHS_KEY: str = "testpaths"

TEST_FILE_BASENAME_PATTERN: re.Pattern[str] = re.compile(r"^test_.+\.py$")

PACKAGE_ROOT_ENTRY: str = "."

PACKAGE_ROOT_ENTRY_PREFIX: str = "./"

GLOB_METACHARACTERS: frozenset[str] = frozenset({"*", "?", "["})

ALL_PRUNED_PARENT_DIRECTORY_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".pytest_cache",
        ".ruff_cache",
    }
)

MAX_PARENT_DIRECTORIES_SEARCHED: int = 40

UNREGISTERED_TEST_DIRECTORY_MESSAGE_TEMPLATE: str = (
    "Test file {test_file} lands in a directory that the pytest config at "
    "{pyproject} does not collect. That pyproject declares an explicit testpaths "
    "allowlist, and no entry covers {test_directory} (relative to the package "
    "root). A default `pytest` run from the package root never collects this file, "
    "so the test silently never runs and a regression it would catch passes the "
    "suite undetected. Add the directory to the testpaths list in {pyproject} "
    "(for example `{suggested_entry}`) in the same change that adds the test."
)

UNREGISTERED_TEST_DIRECTORY_SYSTEM_MESSAGE: str = (
    "test file lands outside the pytest testpaths allowlist - add its directory to "
    "testpaths so the default suite collects it"
)

UNREGISTERED_TEST_DIRECTORY_ADDITIONAL_CONTEXT: str = (
    "When a package's pyproject.toml declares [tool.pytest.ini_options] with an "
    "explicit testpaths list, that list is the complete set of directories a "
    "default pytest run collects. A test_*.py file written into a directory no "
    "testpaths entry covers is collected by nobody: the default run skips it and "
    "the regression it guards goes unnoticed. To resolve:\n"
    "  - add the test file's directory (relative to the package root) to the "
    "testpaths list in pyproject.toml, or\n"
    "  - move the test under a directory the testpaths list already covers."
)
