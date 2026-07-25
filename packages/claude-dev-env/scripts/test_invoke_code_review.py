"""Import bootstrap: the invoker resolves its own constants unaided.

The script sits in ``scripts/`` but reads constants from two packages that live
elsewhere in the tree, so it seeds ``sys.path`` itself at import time. A caller
that runs it as a plain CLI supplies no ``PYTHONPATH``, and these tests run it
that way to prove the seeding covers every package the module imports.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

INVOKER_SCRIPT_FILE_NAME = "invoke_code_review.py"
CLI_HELP_FLAG = "--help"
PYTHONPATH_ENVIRONMENT_NAME = "PYTHONPATH"
HELP_EXIT_CODE = 0
CLI_HELP_TIMEOUT_SECONDS = 60
MISSING_MODULE_ERROR_NAME = "ModuleNotFoundError"
CODE_REVIEW_SLASH_COMMAND_TEXT = "/code-review"


def _environment_without_pythonpath() -> dict[str, str]:
    """Return a copy of the live environment with ``PYTHONPATH`` removed."""
    all_environment_values = dict(os.environ)
    all_environment_values.pop(PYTHONPATH_ENVIRONMENT_NAME, None)
    return all_environment_values


def _run_invoker_help_without_pythonpath() -> subprocess.CompletedProcess[str]:
    """Run the invoker's ``--help`` in a shell that supplies no ``PYTHONPATH``."""
    invoker_script_path = Path(__file__).resolve().parent / INVOKER_SCRIPT_FILE_NAME
    return subprocess.run(
        [sys.executable, str(invoker_script_path), CLI_HELP_FLAG],
        capture_output=True,
        text=True,
        check=False,
        timeout=CLI_HELP_TIMEOUT_SECONDS,
        env=_environment_without_pythonpath(),
    )


def test_cli_imports_its_constants_without_caller_pythonpath() -> None:
    completed_help_run = _run_invoker_help_without_pythonpath()

    assert completed_help_run.returncode == HELP_EXIT_CODE, completed_help_run.stderr
    assert MISSING_MODULE_ERROR_NAME not in completed_help_run.stderr


def test_cli_help_describes_the_review_command_it_runs() -> None:
    completed_help_run = _run_invoker_help_without_pythonpath()

    assert CLI_HELP_FLAG in completed_help_run.stdout
    assert CODE_REVIEW_SLASH_COMMAND_TEXT in completed_help_run.stdout
