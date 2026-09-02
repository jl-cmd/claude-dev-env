"""Add hooks/blocking and hooks/ to sys.path for every test collected under this directory."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(_BLOCKING_DIRECTORY).parent)
for each_directory in (_BLOCKING_DIRECTORY, _HOOKS_DIRECTORY):
    if each_directory not in sys.path:
        sys.path.insert(0, each_directory)


@pytest.fixture
def three_operation_patch() -> str:
    """Build a patch naming one update, one add, and one delete section."""
    return (
        "*** Begin Patch\n"
        "*** Update File: updated.py\n"
        "@@\n"
        "-before\n"
        "+after\n"
        " keep\n"
        "*** Add File: added.py\n"
        "+new\n"
        "*** Delete File: deleted.py\n"
        "*** End of File\n"
        "*** End Patch"
    )


@pytest.fixture
def init_bare_git_repo() -> Callable[[Path], None]:
    """Return a helper that initializes an empty git repository at a given path.

    The PII scanner reads an apply_patch payload's ``cwd`` as a git
    repository root, so a dispatcher-level apply_patch test needs a real
    repository there rather than a bare temp directory.
    """

    def _init_bare_git_repo(repository_root: Path) -> None:
        repository_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=repository_root, check=True, capture_output=True)

    return _init_bare_git_repo


@pytest.fixture
def synthetic_github_token() -> str:
    """Return a fixture-only GitHub token shape, safe to embed in test payloads."""
    return "ghp_" + ("C" * 36)


@pytest.fixture
def multi_edit_payload() -> Callable[[str, list[dict[str, str]]], str]:
    """Return a helper that builds a MultiEdit tool payload JSON string."""

    def _multi_edit_payload(file_path: str, all_edits: list[dict[str, str]]) -> str:
        return json.dumps(
            {
                "tool_name": "MultiEdit",
                "tool_input": {"file_path": file_path, "edits": all_edits},
            }
        )

    return _multi_edit_payload
