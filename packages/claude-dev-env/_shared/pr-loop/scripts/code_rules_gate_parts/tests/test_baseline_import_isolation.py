"""Behavioral tests for the baseline_import_isolation parts module.

The import-root probe runs a real interpreter subprocess and the leak plugin is
written, imported, and called the way pytest calls it, so each test measures the
mechanism the live gate depends on rather than a stand-in for it.
"""

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pytest
from pr_loop_shared_constants.code_rules_gate_constants import (
    BASELINE_LEAK_PLUGIN_MODULE_NAME,
    BASELINE_LEAK_REPORT_ENV_VAR,
    BASELINE_PRIMARY_ROOT_ENV_VAR,
    PYTEST_PLUGINS_ENV_VAR,
    PYTHONPATH_ENV_VAR,
)

from code_rules_gate_parts import baseline_import_isolation

UNREACHABLE_PROBE_TIMEOUT_SECONDS = 0.001


def baseline_environment_for(
    tmp_path: Path,
    staged_environment: dict[str, str],
    all_import_roots: list[Path],
) -> dict[str, str]:
    """Build a baseline environment against a /repo and /baseline pair under *tmp_path*."""
    return baseline_import_isolation.baseline_pytest_environment(
        staged_environment,
        tmp_path / "repo",
        tmp_path / "baseline",
        all_import_roots,
        tmp_path / "plugin",
        tmp_path / "report.json",
    )


def test_rebased_into_baseline_moves_a_repository_path_into_the_worktree(
    tmp_path: Path,
) -> None:
    rebased_path = baseline_import_isolation.rebased_into_baseline(
        tmp_path / "repo" / "packages", tmp_path / "repo", tmp_path / "baseline"
    )

    assert rebased_path == tmp_path / "baseline" / "packages"


def test_rebased_into_baseline_leaves_a_path_outside_the_repository_unclaimed(
    tmp_path: Path,
) -> None:
    rebased_path = baseline_import_isolation.rebased_into_baseline(
        tmp_path / "elsewhere" / "library", tmp_path / "repo", tmp_path / "baseline"
    )

    assert rebased_path is None


def test_baseline_pytest_environment_leads_with_the_rebased_import_roots(
    tmp_path: Path,
) -> None:
    baseline_environment = baseline_environment_for(
        tmp_path, {}, [tmp_path / "repo" / "source", tmp_path / "elsewhere"]
    )

    all_entries = baseline_environment[PYTHONPATH_ENV_VAR].split(os.pathsep)
    assert all_entries[0] == str(tmp_path / "baseline" / "source")
    assert str(tmp_path / "elsewhere") not in all_entries


def test_baseline_pytest_environment_rebases_a_repository_pythonpath_entry(
    tmp_path: Path,
) -> None:
    staged_environment = {PYTHONPATH_ENV_VAR: str(tmp_path / "repo" / "packages")}

    baseline_environment = baseline_environment_for(tmp_path, staged_environment, [])

    all_entries = baseline_environment[PYTHONPATH_ENV_VAR].split(os.pathsep)
    assert str(tmp_path / "baseline" / "packages") in all_entries
    assert str(tmp_path / "repo" / "packages") not in all_entries


def test_baseline_pytest_environment_keeps_an_outside_pythonpath_entry(
    tmp_path: Path,
) -> None:
    staged_environment = {PYTHONPATH_ENV_VAR: str(tmp_path / "vendor")}

    baseline_environment = baseline_environment_for(tmp_path, staged_environment, [])

    assert str(tmp_path / "vendor") in baseline_environment[PYTHONPATH_ENV_VAR].split(
        os.pathsep
    )


def test_baseline_pytest_environment_adds_the_leak_plugin_to_an_existing_list(
    tmp_path: Path,
) -> None:
    staged_environment = {PYTEST_PLUGINS_ENV_VAR: "project_plugin"}

    baseline_environment = baseline_environment_for(tmp_path, staged_environment, [])

    assert baseline_environment[PYTEST_PLUGINS_ENV_VAR] == (
        f"{BASELINE_LEAK_PLUGIN_MODULE_NAME},project_plugin"
    )


def test_discover_import_roots_reports_a_pythonpath_directory(tmp_path: Path) -> None:
    library_directory = tmp_path / "library"
    library_directory.mkdir()
    probe_environment = dict(os.environ)
    probe_environment[PYTHONPATH_ENV_VAR] = str(library_directory)

    all_import_roots = baseline_import_isolation.discover_import_roots(
        sys.executable, probe_environment, tmp_path
    )

    assert library_directory.resolve() in all_import_roots


def test_discover_import_roots_gives_up_on_a_probe_that_runs_out_of_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        baseline_import_isolation,
        "BASELINE_IMPORT_PROBE_TIMEOUT_SECONDS",
        UNREACHABLE_PROBE_TIMEOUT_SECONDS,
    )

    all_import_roots = baseline_import_isolation.discover_import_roots(
        sys.executable, dict(os.environ), tmp_path
    )

    assert all_import_roots == []
    assert "import-root probe" in capsys.readouterr().err


def test_discover_import_roots_gives_up_on_an_interpreter_that_cannot_start(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    all_import_roots = baseline_import_isolation.discover_import_roots(
        str(tmp_path / "no_such_interpreter"), dict(os.environ), tmp_path
    )

    assert all_import_roots == []
    assert "import-root probe" in capsys.readouterr().err


def test_discover_import_roots_reports_an_editable_install_package_root(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    (project_root / "widget").mkdir(parents=True)
    finder_directory = tmp_path / "finder"
    finder_directory.mkdir()
    (finder_directory / "sitecustomize.py").write_text(
        "import sys\n"
        f"MAPPING = {{'widget': r'{project_root / 'widget'}'}}\n\n\n"
        "class EditableFinder:\n"
        "    @classmethod\n"
        "    def find_spec(cls, fullname, path=None, target=None):\n"
        "        return None\n\n\n"
        "sys.meta_path.append(EditableFinder)\n",
        encoding="utf-8",
    )
    probe_environment = dict(os.environ)
    probe_environment[PYTHONPATH_ENV_VAR] = str(finder_directory)

    all_import_roots = baseline_import_isolation.discover_import_roots(
        sys.executable, probe_environment, tmp_path
    )

    assert project_root.resolve() in all_import_roots


def test_modules_imported_from_primary_tree_is_unknown_without_a_report(
    tmp_path: Path,
) -> None:
    assert (
        baseline_import_isolation.modules_imported_from_primary_tree(
            tmp_path / "missing.json"
        )
        is None
    )


def test_modules_imported_from_primary_tree_reads_the_reported_paths(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps([str(tmp_path / "repo" / "foo.py")]), encoding="utf-8")

    assert baseline_import_isolation.modules_imported_from_primary_tree(report_path) == [
        tmp_path / "repo" / "foo.py"
    ]


def load_installed_plugin(plugin_directory: Path) -> types.ModuleType:
    """Import the plugin module ``install_leak_plugin`` wrote into *plugin_directory*."""
    plugin_path = plugin_directory / f"{BASELINE_LEAK_PLUGIN_MODULE_NAME}.py"
    module_specification = importlib.util.spec_from_file_location(
        BASELINE_LEAK_PLUGIN_MODULE_NAME, plugin_path
    )
    assert module_specification is not None and module_specification.loader is not None
    plugin_module = importlib.util.module_from_spec(module_specification)
    module_specification.loader.exec_module(plugin_module)
    return plugin_module


def test_installed_plugin_reports_a_module_loaded_from_the_primary_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin_directory = tmp_path / "plugin"
    baseline_import_isolation.install_leak_plugin(plugin_directory)
    plugin_module = load_installed_plugin(plugin_directory)
    primary_root = tmp_path / "repo"
    leaked_module = types.ModuleType("leaked_widget")
    leaked_module.__file__ = str(primary_root / "widget" / "__init__.py")
    monkeypatch.setitem(sys.modules, "leaked_widget", leaked_module)
    report_path = tmp_path / "report.json"
    monkeypatch.setenv(BASELINE_PRIMARY_ROOT_ENV_VAR, str(primary_root))
    monkeypatch.setenv(BASELINE_LEAK_REPORT_ENV_VAR, str(report_path))

    plugin_module.pytest_sessionfinish(None, 0)

    assert baseline_import_isolation.modules_imported_from_primary_tree(report_path) == [
        primary_root / "widget" / "__init__.py"
    ]


def test_installed_plugin_reports_nothing_when_no_module_came_from_the_primary_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin_directory = tmp_path / "plugin"
    baseline_import_isolation.install_leak_plugin(plugin_directory)
    plugin_module = load_installed_plugin(plugin_directory)
    report_path = tmp_path / "report.json"
    monkeypatch.setenv(BASELINE_PRIMARY_ROOT_ENV_VAR, str(tmp_path / "repo"))
    monkeypatch.setenv(BASELINE_LEAK_REPORT_ENV_VAR, str(report_path))

    plugin_module.pytest_sessionfinish(None, 0)

    assert baseline_import_isolation.modules_imported_from_primary_tree(report_path) == []
