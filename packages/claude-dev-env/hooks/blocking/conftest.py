"""Pytest fixture that reproduces foreign-``config`` shadowing for the gate family.

The verified-commit gate hooks import shared constants as
``from config.verified_commit_constants import ...``. This fixture mirrors the
installed layout that breaks that import -- a real ``hooks/blocking`` package
beside a decoy ``hooks/config`` regular package -- and runs a caller-supplied
driver as a subprocess whose ``sys.path`` places the decoy ahead of
``blocking``, the ordering under which the wrong ``config`` wins resolution.
"""

import shutil
import subprocess
import sys
import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest

_BLOCKING_SOURCE_DIRECTORY = Path(__file__).resolve().parent
_HOOKS_CONSTANTS_SOURCE_DIRECTORY = _BLOCKING_SOURCE_DIRECTORY.parent / "hooks_constants"
_SUBPROCESS_TIMEOUT_SECONDS = 60
_MIRRORED_BLOCKING_FILE_NAMES = (
    "verified_commit_gate.py",
    "verification_verdict_store.py",
    "verifier_verdict_minter.py",
    "verdict_directory_write_blocker.py",
    "verified_commit_config_bootstrap.py",
    "code_review_enforcement_config_bootstrap.py",
    "code_review_stamp_store.py",
)
_DECOY_CONFIG_INIT_SOURCE = '"""Foreign config package that must never win resolution."""\n'
_DECOY_CONFIG_CONSTANTS_SOURCE = (
    '"""Stale stand-in carrying none of the real gate constants."""\n\nIS_DECOY_CONFIG = True\n'
)

_BLOCKING_TEST_BOOTSTRAP_DIRECTORIES = (
    str(_BLOCKING_SOURCE_DIRECTORY),
    str(_BLOCKING_SOURCE_DIRECTORY.parent),
)
for each_bootstrap_directory in _BLOCKING_TEST_BOOTSTRAP_DIRECTORIES:
    if each_bootstrap_directory not in sys.path:
        sys.path.insert(0, each_bootstrap_directory)


def _copy_mirrored_packages(mirrored_hooks_directory: Path, mirrored_blocking_directory: Path) -> None:
    """Copy the ``config``, gate-parts, and ``hooks_constants`` packages into the mirror."""
    shutil.copytree(_BLOCKING_SOURCE_DIRECTORY / "config", mirrored_blocking_directory / "config")
    shutil.copytree(
        _BLOCKING_SOURCE_DIRECTORY / "verified_commit_gate_parts",
        mirrored_blocking_directory / "verified_commit_gate_parts",
        ignore=shutil.ignore_patterns("tests", "__pycache__"),
    )
    shutil.copytree(_HOOKS_CONSTANTS_SOURCE_DIRECTORY, mirrored_hooks_directory / "hooks_constants")


def _write_decoy_config_package(mirrored_hooks_directory: Path) -> None:
    """Write the decoy ``config`` package that must never win resolution."""
    decoy_config_directory = mirrored_hooks_directory / "config"
    decoy_config_directory.mkdir()
    (decoy_config_directory / "__init__.py").write_text(_DECOY_CONFIG_INIT_SOURCE, encoding="utf-8")
    (decoy_config_directory / "verified_commit_constants.py").write_text(
        _DECOY_CONFIG_CONSTANTS_SOURCE, encoding="utf-8"
    )


def _build_shadowed_hook_tree(tmp_path: Path) -> tuple[Path, Path]:
    """Mirror the hook tree with a decoy ``config`` package beside ``blocking``.

    Args:
        tmp_path: The directory the mirrored tree is built under.

    Returns:
        The mirrored ``hooks`` directory and its ``blocking`` subdirectory.
    """
    mirrored_hooks_directory = tmp_path / "hooks"
    mirrored_blocking_directory = mirrored_hooks_directory / "blocking"
    mirrored_blocking_directory.mkdir(parents=True)

    for each_file_name in _MIRRORED_BLOCKING_FILE_NAMES:
        source_file = _BLOCKING_SOURCE_DIRECTORY / each_file_name
        if source_file.exists():
            shutil.copy2(source_file, mirrored_blocking_directory / each_file_name)

    _copy_mirrored_packages(mirrored_hooks_directory, mirrored_blocking_directory)
    _write_decoy_config_package(mirrored_hooks_directory)
    return mirrored_hooks_directory, mirrored_blocking_directory


def _probe_command(mirrored_hooks_directory: Path, mirrored_blocking_directory: Path) -> str:
    """Build the ``sys.path`` preamble that shadows ``blocking`` with the decoy config."""
    return textwrap.dedent(
        f"""\
        import sys
        sys.path.insert(0, {str(mirrored_blocking_directory)!r})
        sys.path.insert(0, {str(mirrored_hooks_directory)!r})
        """
    )


@pytest.fixture
def run_under_config_shadow(
    tmp_path: Path,
) -> Callable[[str], subprocess.CompletedProcess[str]]:
    """Return a runner that executes a driver under a foreign-``config`` sys.path.

    ``run_under_config_shadow("import verified_commit_gate")`` returns 0 once
    the bootstrap seeds the real module, nonzero while the decoy config wins.

    Args:
        tmp_path: Pytest's per-test temporary directory, fixture-injected.

    Returns:
        A function taking driver source text and returning the finished
        subprocess result.
    """
    mirrored_hooks_directory, mirrored_blocking_directory = _build_shadowed_hook_tree(tmp_path)
    sys_path_preamble = _probe_command(mirrored_hooks_directory, mirrored_blocking_directory)

    def run_driver(driver_body: str) -> subprocess.CompletedProcess[str]:
        probe_script = tmp_path / "probe.py"
        probe_script.write_text(sys_path_preamble + textwrap.dedent(driver_body), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(probe_script)],
            check=False,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )

    return run_driver
