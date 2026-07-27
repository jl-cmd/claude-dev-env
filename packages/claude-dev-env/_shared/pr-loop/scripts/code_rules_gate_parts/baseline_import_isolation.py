"""Make the HEAD baseline run import from the baseline worktree, and prove that it did.

::

    repository_root   = /repo            (working tree, staged edits)
    baseline_worktree = /tmp/base/tree   (detached HEAD, clean)

    ok:   PYTHONPATH=/repo/packages   -> PYTHONPATH=/tmp/base/tree/packages
    ok:   editable root /repo/src     -> /tmp/base/tree/src prepended
    flag: import hook ahead of the path scan still serving /repo/src/foo.py
          -> reported by the leak plugin, baseline discarded

Rebasing the working directory alone does not move imports. An absolute route
into the user's own checkout keeps serving staged code to the baseline run.
Two shapes reach it: a ``PYTHONPATH`` entry under the repository root, and an
editable install pointing at it. The baseline then fails the way the staged run
failed, and the two failures cancel a real regression out.

Two halves close that. Every import root inside the repository is rewritten to
its baseline-worktree equivalent and put at the front of ``PYTHONPATH``. That
beats every ``.pth`` entry and every setuptools editable style. Then the
baseline pytest session loads a plugin that records which modules it imported
out of the user's tree. A route that survives the rewrite is measured, never
assumed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from pr_loop_shared_constants.code_rules_gate_constants import (
    BASELINE_IMPORT_PROBE_REJECTED_MESSAGE,
    BASELINE_IMPORT_PROBE_TIMED_OUT_MESSAGE,
    BASELINE_IMPORT_PROBE_TIMEOUT_SECONDS,
    BASELINE_IMPORT_PROBE_UNSTARTABLE_MESSAGE,
    BASELINE_IMPORT_ROOT_PROBE_SOURCE,
    BASELINE_LEAK_PLUGIN_MODULE_NAME,
    BASELINE_LEAK_PLUGIN_SOURCE,
    BASELINE_LEAK_REPORT_ENV_VAR,
    BASELINE_PRIMARY_ROOT_ENV_VAR,
    PYTEST_PLUGINS_ENV_VAR,
    PYTEST_PLUGINS_SEPARATOR,
    PYTHON_FILE_EXTENSION,
    PYTHON_INTERPRETER_COMMAND_FLAG,
    PYTHONPATH_ENV_VAR,
)


def _resolved_directory(path_text: str) -> Path | None:
    """Return *path_text* resolved to an absolute path, or None when it is unusable."""
    if not path_text:
        return None
    try:
        return Path(path_text).resolve()
    except OSError:
        return None


def _is_under(candidate: Path, root: Path) -> bool:
    """Return True when *candidate* is *root* itself or sits anywhere beneath it."""
    return candidate == root or root in candidate.parents


def rebased_into_baseline(
    original_path: Path, repository_root: Path, baseline_worktree: Path
) -> Path | None:
    """Return *original_path* moved into the baseline worktree, or None when outside the repo.

    ::

        repository_root = /repo
        ok:   /repo/packages -> /tmp/base/tree/packages
        ok:   /repo          -> /tmp/base/tree
        flag: /elsewhere/lib -> None (nothing in the baseline tree answers for it)

    Args:
        original_path: An already-resolved filesystem path.
        repository_root: The user's own repository root.
        baseline_worktree: The detached-HEAD worktree the baseline run uses.

    Returns:
        The same repository-relative location inside *baseline_worktree*, or
        None when *original_path* lies outside the repository.
    """
    if not _is_under(original_path, repository_root):
        return None
    return baseline_worktree / original_path.relative_to(repository_root)


def discover_import_roots(
    python_executable: str,
    all_environment_settings: dict[str, str],
    working_directory: Path,
) -> list[Path]:
    """Return every directory the interpreter would resolve imported packages from.

    Covers ``sys.path`` — which carries ``PYTHONPATH`` and every ``.pth``-added
    entry — plus the package roots an editable install registers through an
    import hook, which never appear on ``sys.path`` at all.

    Args:
        python_executable: The interpreter the staged and baseline runs use.
        all_environment_settings: The environment the probe runs under.
        working_directory: A directory outside the repository, so the probe's
            own working directory never reads as a repository import root.

    Returns:
        The resolved import roots, or an empty list when the probe times out,
        cannot start, or exits non-zero. Each of those says so on stderr, and
        the run continues into the baseline with its leak report still armed.
    """
    probe = _completed_import_root_probe(
        python_executable, all_environment_settings, working_directory
    )
    if probe is None:
        return []
    if probe.returncode != 0:
        sys.stderr.write(
            BASELINE_IMPORT_PROBE_REJECTED_MESSAGE.format(status=probe.returncode) + "\n"
        )
        return []
    return _probed_roots(probe.stdout)


def _completed_import_root_probe(
    python_executable: str,
    all_environment_settings: dict[str, str],
    working_directory: Path,
) -> subprocess.CompletedProcess[str] | None:
    """Run the probe interpreter to completion, or report on stderr why it produced nothing.

    ::

        ok:   probe exits 0        -> CompletedProcess carrying its output
        flag: probe hangs          -> None, "did not finish within 120 seconds"
        flag: interpreter missing  -> None, "did not start (...)"

    A probe that outlives its limit is the same situation as a probe that fails:
    no roots were learned, so the caller carries on without them rather than
    raising a traceback out of a pre-commit hook.
    """
    try:
        return subprocess.run(
            [python_executable, PYTHON_INTERPRETER_COMMAND_FLAG, BASELINE_IMPORT_ROOT_PROBE_SOURCE],
            cwd=str(working_directory),
            env=all_environment_settings,
            capture_output=True,
            text=True,
            check=False,
            timeout=BASELINE_IMPORT_PROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        sys.stderr.write(
            BASELINE_IMPORT_PROBE_TIMED_OUT_MESSAGE.format(
                seconds=BASELINE_IMPORT_PROBE_TIMEOUT_SECONDS
            )
            + "\n"
        )
        return None
    except OSError as probe_failure:
        sys.stderr.write(
            BASELINE_IMPORT_PROBE_UNSTARTABLE_MESSAGE.format(reason=probe_failure) + "\n"
        )
        return None


def _probed_roots(probe_text: str) -> list[Path]:
    """Return the resolved directories named on the probe's final output line."""
    all_probe_lines = probe_text.strip().splitlines()
    if not all_probe_lines:
        return []
    try:
        all_root_texts = json.loads(all_probe_lines[-1])
    except ValueError:
        return []
    all_roots = [_resolved_directory(str(each_text)) for each_text in all_root_texts]
    return [each_root for each_root in all_roots if each_root is not None]


def _baseline_path_entries(
    all_import_roots: list[Path], repository_root: Path, baseline_worktree: Path
) -> list[str]:
    """Return the baseline-worktree equivalent of every import root inside the repository."""
    all_entries: list[str] = []
    for each_root in all_import_roots:
        rebased_root = rebased_into_baseline(each_root, repository_root, baseline_worktree)
        if rebased_root is not None:
            all_entries.append(str(rebased_root))
    return all_entries


def _rebased_pythonpath_entries(
    all_staged_environment_settings: dict[str, str],
    repository_root: Path,
    baseline_worktree: Path,
) -> list[str]:
    """Return the staged ``PYTHONPATH`` with every repository entry moved into the baseline."""
    all_entries: list[str] = []
    staged_pythonpath = all_staged_environment_settings.get(PYTHONPATH_ENV_VAR, "")
    for each_entry in staged_pythonpath.split(os.pathsep):
        resolved_entry = _resolved_directory(each_entry)
        rebased_entry = (
            None
            if resolved_entry is None
            else rebased_into_baseline(resolved_entry, repository_root, baseline_worktree)
        )
        all_entries.append(each_entry if rebased_entry is None else str(rebased_entry))
    return [each_entry for each_entry in all_entries if each_entry]


def install_leak_plugin(plugin_directory: Path) -> None:
    """Write the import-origin reporting pytest plugin into its own directory.

    Args:
        plugin_directory: The directory the plugin module is written to, which
            the baseline run puts on its ``PYTHONPATH`` so pytest loads it.
    """
    plugin_directory.mkdir(parents=True, exist_ok=True)
    plugin_path = plugin_directory / f"{BASELINE_LEAK_PLUGIN_MODULE_NAME}{PYTHON_FILE_EXTENSION}"
    plugin_path.write_text(
        BASELINE_LEAK_PLUGIN_SOURCE.format(
            primary_root_env_var=BASELINE_PRIMARY_ROOT_ENV_VAR,
            report_path_env_var=BASELINE_LEAK_REPORT_ENV_VAR,
        ),
        encoding="utf-8",
    )


def _pytest_plugins_setting(all_staged_environment_settings: dict[str, str]) -> str:
    """Return the ``PYTEST_PLUGINS`` value with the leak plugin added to any existing list."""
    existing_setting = all_staged_environment_settings.get(PYTEST_PLUGINS_ENV_VAR, "")
    if not existing_setting:
        return BASELINE_LEAK_PLUGIN_MODULE_NAME
    return PYTEST_PLUGINS_SEPARATOR.join([BASELINE_LEAK_PLUGIN_MODULE_NAME, existing_setting])


def baseline_pytest_environment(
    all_staged_environment_settings: dict[str, str],
    repository_root: Path,
    baseline_worktree: Path,
    all_import_roots: list[Path],
    plugin_directory: Path,
    leak_report_path: Path,
) -> dict[str, str]:
    """Return the environment the baseline pytest run uses.

    Every repository import root leads with its baseline-worktree equivalent,
    the plugin directory follows, and the staged ``PYTHONPATH`` (itself rebased
    entry by entry) trails behind, so a module that exists at HEAD always
    resolves out of the baseline tree.

    Args:
        all_staged_environment_settings: The environment the staged run used.
        repository_root: The user's own repository root.
        baseline_worktree: The detached-HEAD worktree the baseline run uses.
        all_import_roots: The import roots ``discover_import_roots`` found.
        plugin_directory: The directory holding the leak-reporting plugin.
        leak_report_path: Where the plugin writes its import-origin report.

    Returns:
        A copy of *all_staged_environment_settings* carrying the baseline
        import path and the leak plugin's three settings.
    """
    baseline_environment = dict(all_staged_environment_settings)
    all_entries = [
        *_baseline_path_entries(all_import_roots, repository_root, baseline_worktree),
        str(plugin_directory),
        *_rebased_pythonpath_entries(
            all_staged_environment_settings, repository_root, baseline_worktree
        ),
    ]
    baseline_environment[PYTHONPATH_ENV_VAR] = os.pathsep.join(dict.fromkeys(all_entries))
    baseline_environment[PYTEST_PLUGINS_ENV_VAR] = _pytest_plugins_setting(
        all_staged_environment_settings
    )
    baseline_environment[BASELINE_PRIMARY_ROOT_ENV_VAR] = str(repository_root)
    baseline_environment[BASELINE_LEAK_REPORT_ENV_VAR] = str(leak_report_path)
    return baseline_environment


def modules_imported_from_primary_tree(leak_report_path: Path) -> list[Path] | None:
    """Return the user's-tree modules the baseline run imported, or None when unreported.

    ::

        ok:   []                       -> the baseline measured HEAD alone
        flag: [/repo/packages/foo.py]  -> the baseline read staged code
        flag: None                     -> the run left no report; nothing is proven

    Args:
        leak_report_path: The report path the baseline run was given.

    Returns:
        The resolved module paths, empty when the baseline stayed clean, or None
        when the report is missing or unreadable.
    """
    try:
        report_text = leak_report_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        all_module_texts = json.loads(report_text)
    except ValueError:
        return None
    return [Path(str(each_text)) for each_text in all_module_texts]
