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

HARNESS_EXIT = 3
ALL_PYTEST_HARNESS_EXITS = (3, 4, 5)


def main(all_arguments: list[str]) -> int:
    if len(all_arguments) != 2:
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
            timeout=110,
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
