"""Session-scoped cleanup fixture for the md_to_html_blocker test suites.

The md_to_html_blocker suites share one lazily-created sandbox parent
directory under the home directory. This fixture tears that sandbox down once
the session ends so the suites leave no residue regardless of which split file
pytest collects first.
"""

import sys
from pathlib import Path

import pytest

_BLOCKING_DIRECTORY = Path(__file__).resolve().parent

if str(_BLOCKING_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_BLOCKING_DIRECTORY))

from _md_to_html_blocker_test_support import (  # noqa: E402
    _force_rmtree,
    _get_sandbox_parent_directory,
)


@pytest.fixture(scope="session", autouse=True)
def _cleanup_sandbox_parent_directory():
    yield
    if _get_sandbox_parent_directory.cache_info().currsize:
        _force_rmtree(_get_sandbox_parent_directory())
        _get_sandbox_parent_directory.cache_clear()
