"""Swap a defective variant over a module and report whether the work directory's tests notice.

Exit 0: the tests failed on the variant, so they detect the defect.
Exit 1: the tests passed on the variant.
Exit 3: the check could not run (missing file, or pytest ended with a usage or collection-free exit).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from config.tests_kill_variant_constants import (
    ALL_PYTEST_HARNESS_EXITS,
    EXPECTED_ARGUMENT_COUNT,
    HARNESS_EXIT,
    PYTEST_TIMEOUT_SECONDS,
)


def main(all_arguments: list[str]) -> int:
    """Grade a test suite by whether it fails on a defective variant of a module.

    ::

        arguments: catalog/paging.py variants/original_defect.py
        pytest fails on the variant   ->   exit 0
        pytest passes on the variant  ->   exit 1

    The variant stands in for the module through one pytest run. The module
    carries its own bytes again once the run ends.

    Args:
        all_arguments: The path of the module to swap, relative to the work
            directory, then the path of the variant file to swap over it.

    Returns:
        0 when pytest reports a failure on the variant, 1 when pytest passes,
        and the harness exit code when the arguments are wrong, either path is
        missing, pytest runs past its timeout, or pytest reports a usage error
        or a collection with no tests.
    """
    if len(all_arguments) != EXPECTED_ARGUMENT_COUNT:
        return HARNESS_EXIT
    target_path = Path.cwd() / all_arguments[0]
    variant_path = Path(all_arguments[1])
    if not target_path.is_file() or not variant_path.is_file():
        return HARNESS_EXIT
    original_bytes = target_path.read_bytes()
    shutil.copyfile(variant_path, target_path)
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "tests"],
            cwd=Path.cwd(),
            capture_output=True,
            timeout=PYTEST_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return HARNESS_EXIT
    finally:
        target_path.write_bytes(original_bytes)
    if completed.returncode in ALL_PYTEST_HARNESS_EXITS:
        return HARNESS_EXIT
    return 0 if completed.returncode != 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
