"""Prove every deployed subprocess-window shim reaches the packaged helpers.

Each shim sits beside the scripts of one deployed directory. A deployed
profile carries no installed Python distribution, and the repository runs its
scripts under ``python -S -E``, which hides installed packages from the child.
So each check below drives a real ``-S -E`` child, imports the shim by the name
its callers use, and reads back where the helper came from.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_SHIM_MODULE_NAME = "subprocess_window_access"
_SHIM_FILE_NAME = f"{_SHIM_MODULE_NAME}.py"
_PACKAGED_HELPER_PATH = (
    _PACKAGE_ROOT / "hooks" / "hooks_constants" / "subprocess_window.py"
)
_ALL_EXPORTED_HELPER_NAMES = (
    "HiddenWindowStartupInfo",
    "detached_hidden_window_creation_flags",
    "hidden_window_creation_flags",
    "inherited_stream_startup_info",
)
_ALL_SHIM_DIRECTORY_PATHS = (
    "scripts",
    "_shared/pr-loop/scripts",
    "_shared/process-tree/scripts",
    "hooks/git-hooks",
    "hooks/validators",
    ".agents/skills/fresh-branch/scripts",
    ".agents/skills/syncing-submodules/scripts",
    ".agents/skills/test-runner/scripts",
)

_IMPORT_PROBE_SOURCE = "\n".join(
    (
        "import json",
        "import sys",
        "shim_directory = sys.argv[1]",
        "sys.path.insert(0, shim_directory)",
        "head_before_import = sys.path[0]",
        f"import {_SHIM_MODULE_NAME} as shim",
        "print(json.dumps({",
        "    'helper_path': sys.modules[",
        "        shim.hidden_window_creation_flags.__module__",
        "    ].__file__,",
        "    'head_after_import': sys.path[0],",
        "    'head_before_import': head_before_import,",
        "    'exported_names': sorted(shim.__all__),",
        "}))",
    )
)


def _import_probe_results(shim_directory: Path) -> dict[str, object]:
    """Import one shim in a ``-S -E`` child and read back what it resolved."""
    completed_process = subprocess.run(
        [
            sys.executable,
            "-S",
            "-E",
            "-c",
            _IMPORT_PROBE_SOURCE,
            str(shim_directory),
        ],
        cwd=str(_PACKAGE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed_process.returncode == 0, completed_process.stderr
    return json.loads(completed_process.stdout)


@pytest.mark.parametrize("shim_directory_path", _ALL_SHIM_DIRECTORY_PATHS)
def test_every_deployed_directory_carries_a_shim(shim_directory_path: str) -> None:
    """Each directory whose scripts import the shim also ships one."""
    assert (_PACKAGE_ROOT / shim_directory_path / _SHIM_FILE_NAME).is_file()


@pytest.mark.parametrize("shim_directory_path", _ALL_SHIM_DIRECTORY_PATHS)
def test_shim_resolves_the_packaged_helper_without_an_installed_package(
    shim_directory_path: str,
) -> None:
    """A ``-S -E`` child reaches the packaged helper through the shim alone."""
    all_probe_results = _import_probe_results(_PACKAGE_ROOT / shim_directory_path)

    assert Path(str(all_probe_results["helper_path"])) == _PACKAGED_HELPER_PATH


@pytest.mark.parametrize("shim_directory_path", _ALL_SHIM_DIRECTORY_PATHS)
def test_shim_leaves_the_head_of_the_search_path_alone(
    shim_directory_path: str,
) -> None:
    """A caller that prepended its own roots keeps them ahead of the hooks tree."""
    all_probe_results = _import_probe_results(_PACKAGE_ROOT / shim_directory_path)

    assert (
        all_probe_results["head_after_import"]
        == (all_probe_results["head_before_import"])
    )


@pytest.mark.parametrize("shim_directory_path", _ALL_SHIM_DIRECTORY_PATHS)
def test_shim_re_exports_every_hidden_window_helper(
    shim_directory_path: str,
) -> None:
    """Every caller finds the name it needs on the shim it imports."""
    all_probe_results = _import_probe_results(_PACKAGE_ROOT / shim_directory_path)

    assert all_probe_results["exported_names"] == sorted(_ALL_EXPORTED_HELPER_NAMES)
