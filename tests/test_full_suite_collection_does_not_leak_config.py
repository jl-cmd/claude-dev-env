"""Regression tests: full-suite collection must not leak the ``config`` binding.

Three different objects share the top-level name ``config`` in this repo:

* ``config/`` at the repo root (package, e.g. ``config.sync_ai_rules_paths``)
* ``packages/claude-dev-env/hooks/config/`` (hook-local package)
* ``packages/claude-dev-env/hooks/git-hooks/config.py`` (flat module)

When ``git-hooks/test_config.py`` runs first during full-suite collection, it
inserts ``git-hooks/`` at ``sys.path[0]`` and imports the flat ``config.py``.
If that path entry leaks into collection of any later test that expects
``config`` to resolve to a package (for example
``session/test_untracked_repo_detector.py`` or
``scripts/test_groq_bugteam.py``), the later test fails with
``'config' is not a package`` or a ``ModuleNotFoundError``.

These tests reproduce that leak as a subprocess collection check and also
exercise the ``tests/test_conftest_collect_hooks.py`` file in context of the
full suite, which previously broke because ``import conftest`` at module
scope could resolve to ``packages/claude-dev-env/hooks/validators/conftest.py``
under ``--import-mode=importlib``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT_PATH = Path(__file__).resolve().parent.parent
PYTEST_SUBPROCESS_TIMEOUT_SECONDS = 120
PYTEST_ADDOPTS_ENV_VAR = "PYTEST_ADDOPTS"
PYTEST_DISABLE_PLUGIN_AUTOLOAD_ENV_VAR = "PYTEST_DISABLE_PLUGIN_AUTOLOAD"
PLUGIN_AUTOLOAD_DISABLED_FLAG = "1"


def _build_isolated_subprocess_env() -> dict[str, str]:
    isolated_env = os.environ.copy()
    isolated_env.pop(PYTEST_ADDOPTS_ENV_VAR, None)
    isolated_env[PYTEST_DISABLE_PLUGIN_AUTOLOAD_ENV_VAR] = PLUGIN_AUTOLOAD_DISABLED_FLAG
    return isolated_env


def _run_pytest_from_repo_root(
    pytest_arguments: list[str],
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [sys.executable, "-m", "pytest", *pytest_arguments],
            cwd=REPOSITORY_ROOT_PATH,
            capture_output=True,
            text=True,
            check=False,
            timeout=PYTEST_SUBPROCESS_TIMEOUT_SECONDS,
            env=_build_isolated_subprocess_env(),
        )
    except subprocess.TimeoutExpired as timeout_error:
        stdout_output = timeout_error.stdout or ""
        stderr_output = timeout_error.stderr or ""
        if isinstance(stdout_output, bytes):
            stdout_output = stdout_output.decode("utf-8", errors="replace")
        if isinstance(stderr_output, bytes):
            stderr_output = stderr_output.decode("utf-8", errors="replace")
        raise AssertionError(
            f"pytest subprocess exceeded {PYTEST_SUBPROCESS_TIMEOUT_SECONDS}s timeout "
            f"(arguments={pytest_arguments!r}); "
            f"stdout={stdout_output!r} stderr={stderr_output!r}"
        ) from timeout_error


class TestFullSuiteCollectionCleanliness:
    def should_collect_problem_files_without_errors(self) -> None:
        problem_files = [
            "packages/claude-dev-env/hooks/session/test_untracked_repo_detector.py",
            "packages/claude-dev-env/scripts/test_groq_bugteam.py",
            "tests/test_conftest_collect_hooks.py",
        ]
        completed = _run_pytest_from_repo_root(["--collect-only", "-q", *problem_files])

        combined_output = completed.stdout + completed.stderr
        assert "ERROR collecting" not in combined_output, combined_output
        assert "errors during collection" not in combined_output, combined_output
        assert completed.returncode == 0, combined_output


class TestConftestCollectHooksPassesInFullSuite:
    def should_pass_conftest_collect_hooks_tests_when_run_after_validators(
        self,
    ) -> None:
        completed = _run_pytest_from_repo_root(
            [
                "--collect-only",
                "-q",
                "packages/claude-dev-env/hooks/validators/test_abbreviation_checks.py",
                "tests/test_conftest_collect_hooks.py",
            ]
        )

        combined_output = completed.stdout + completed.stderr
        assert "AttributeError" not in combined_output, combined_output
        assert "_pending_sys_path_restores" not in combined_output, combined_output
        assert completed.returncode == 0, combined_output

    def should_pass_session_hook_tests_when_run_after_git_hooks(self) -> None:
        completed = _run_pytest_from_repo_root(
            [
                "--collect-only",
                "-q",
                "packages/claude-dev-env/hooks/git-hooks/test_config.py",
                "packages/claude-dev-env/hooks/session/test_untracked_repo_detector.py",
            ]
        )

        combined_output = completed.stdout + completed.stderr
        assert "'config' is not a package" not in combined_output, combined_output
        assert completed.returncode == 0, combined_output
