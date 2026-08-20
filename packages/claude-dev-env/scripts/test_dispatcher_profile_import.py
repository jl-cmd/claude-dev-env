"""Exercise the installed dispatcher layout in isolated profile trees."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_DISPATCHER_NAMES = ("resolve_worker_spawn.py", "invoke_code_review.py")
_SHARED_DIRECTORY_NAMES = ("advisor", "process-tree")


def _stage_profile_tree(
    source_package_directory: Path, target_profile_directory: Path
) -> Path:
    source_scripts_directory = source_package_directory / "scripts"
    target_scripts_directory = target_profile_directory / "scripts"
    shutil.copytree(source_scripts_directory, target_scripts_directory)
    for each_shared_name in _SHARED_DIRECTORY_NAMES:
        source_shared_directory = (
            source_package_directory / "_shared" / each_shared_name
        )
        target_shared_directory = (
            target_profile_directory / "_shared" / each_shared_name
        )
        shutil.copytree(source_shared_directory, target_shared_directory)
    return target_scripts_directory


@pytest.mark.parametrize("dispatcher_name", _DISPATCHER_NAMES)
def test_installed_dispatcher_help_imports_advisor_constants(
    dispatcher_name: str, tmp_path: Path
) -> None:
    """Each deployed dispatcher imports and serves help from an isolated tree."""
    source_package_directory = Path(__file__).resolve().parent.parent
    target_profile_directory = tmp_path / ".claude"
    target_scripts_directory = _stage_profile_tree(
        source_package_directory, target_profile_directory
    )
    isolated_environment = os.environ.copy()
    isolated_environment.pop("PYTHONPATH", None)
    isolated_environment["PYTHONNOUSERSITE"] = "1"

    completed_process = subprocess.run(
        [
            sys.executable,
            "-S",
            "-E",
            str(target_scripts_directory / dispatcher_name),
            "--help",
        ],
        cwd=target_profile_directory,
        env=isolated_environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed_process.returncode == 0
    assert completed_process.stderr == ""
    assert "usage:" in completed_process.stdout
