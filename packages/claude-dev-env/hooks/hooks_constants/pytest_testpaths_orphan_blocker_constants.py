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
    "Place test file {test_file} in a directory listed by the pytest config at "
    "{pyproject}. The explicit testpaths list defines the directories collected "
    "by a default pytest run. Add {test_directory} with an entry such as "
    "`{suggested_entry}` in the same change that adds the test."
)

UNREGISTERED_TEST_DIRECTORY_SYSTEM_MESSAGE: str = (
    "Add the test file's directory to pytest testpaths so the default suite "
    "collects it"
)

UNREGISTERED_TEST_DIRECTORY_ADDITIONAL_CONTEXT: str = (
    "The explicit `testpaths` list defines the directories collected by a default "
    "pytest run. Place each `test_*.py` file in a listed directory. Add its "
    "directory to `testpaths`, or move the file under a listed directory."
)
