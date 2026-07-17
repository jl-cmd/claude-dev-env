"""Run sibling validator modules as Windows-safe subprocesses."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from .config import MODULE_PATH_SEPARATOR
from .validator_env import hooks_dir, package_name


def _windows_non_unc_working_directory_string(
    all_candidate_directory_strings: list[str | None],
) -> str:
    """Return the first candidate cwd that is not a UNC path (Windows only)."""
    for each_candidate in all_candidate_directory_strings:
        if each_candidate is None:
            continue
        expanded_candidate = str(Path(each_candidate).expanduser())
        if expanded_candidate.startswith("\\\\"):
            continue
        return expanded_candidate
    current_working_directory = os.getcwd()
    expanded_current_working_directory = str(Path(current_working_directory).expanduser())
    if not expanded_current_working_directory.startswith("\\\\"):
        return expanded_current_working_directory
    raise RuntimeError(
        "Cannot find a non-UNC working directory for hook validator subprocesses."
    )


def _hooks_subprocess_working_directory_and_environment() -> tuple[str, dict[str, str]]:
    """Return cwd and env for validator subprocesses.

    On Windows, ``CreateProcess`` rejects some UNC working directories (invalid
    directory name). When the hooks tree resolves to UNC, use a local temp cwd
    and put the hooks directory on ``PYTHONPATH`` so ``python -m validators.*``
    still resolves.
    """
    hooks_directory_string = str(hooks_dir.resolve())
    environment = os.environ.copy()
    previous_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        hooks_directory_string
        + (os.pathsep + previous_pythonpath if previous_pythonpath else "")
    )
    working_directory_string = hooks_directory_string
    if sys.platform == "win32" and working_directory_string.startswith("\\\\"):
        windows_temp_fallback_directory = str(Path(r"C:\Windows\Temp"))
        working_directory_string = _windows_non_unc_working_directory_string(
            [
                os.environ.get("TEMP"),
                os.environ.get("TMP"),
                tempfile.gettempdir(),
                windows_temp_fallback_directory,
            ]
        )
    return working_directory_string, environment


def invoke_validator_module(module_stem: str, forwarded_file_paths: List[str]) -> subprocess.CompletedProcess[str]:  # pragma: no-tdd-gate
    """Run a sibling validator as ``python -m validators.<module_stem>``.

    The subprocess uses the hooks tree on ``PYTHONPATH`` (and normally ``cwd``
    there). On Windows, if that path is UNC, ``cwd`` falls back to a local temp
    directory so ``CreateProcess`` succeeds.
    """
    qualified_module = MODULE_PATH_SEPARATOR.join([package_name, module_stem])
    working_directory_string, environment = (
        _hooks_subprocess_working_directory_and_environment()
    )
    return subprocess.run(
        [sys.executable, "-m", qualified_module, *forwarded_file_paths],
        capture_output=True,
        text=True,
        cwd=working_directory_string,
        env=environment,
        check=False,
    )


def run_validators_entrypoint_subprocess(
    extra_arguments: List[str],
    stdin_text: Optional[str] = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``python -m validators.run_all_validators`` with a Windows-safe cwd.

    Args:
        extra_arguments: Argument vector appended after the module name.
        stdin_text: Text replayed as the subprocess stdin, or None to leave
            stdin empty. The PreToolUse gate mode reads its payload from stdin,
            so a caller exercising ``--pre-tool-use`` passes the payload here.

    Returns:
        The completed subprocess carrying its captured stdout and stderr.
    """
    working_directory_string, environment = (
        _hooks_subprocess_working_directory_and_environment()
    )
    entry_module = f"{package_name}.run_all_validators"
    return subprocess.run(
        [sys.executable, "-m", entry_module, *extra_arguments],
        capture_output=True,
        text=True,
        cwd=working_directory_string,
        env=environment,
        check=False,
        input=stdin_text,
    )
