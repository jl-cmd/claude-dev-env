"""Behavior tests for the mypy_validator config-discovery fix and caching.

The hook runs mypy from the project root, so without handing mypy the project's
own ``[tool.mypy]`` config a module that imports its siblings by name draws a
spurious ``import-not-found`` error. These tests drive the real production
functions: ``discover_mypy_config`` walks up to the nearest configuring
``pyproject.toml`` and ``run_mypy`` passes it through so the project's
``ignore_missing_imports`` setting applies.

The caching tests drive the real per-session caches: the config-walk cache that
keeps ``discover_mypy_config`` from walking ancestors twice under one project
root, and the content-hash cache that lets a clean file's mypy run be skipped
while a changed file still re-runs. Both run through the production path with
the cache directory redirected to a temporary directory.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

HOOK_PATH = Path(__file__).resolve().parent / "mypy_validator.py"

MODULE_WITH_SIBLING_IMPORT = (
    "from sibling_only_resolvable_at_runtime import value\n\nx: int = value\n"
)
TOOL_MYPY_PYPROJECT = "[tool.mypy]\nignore_missing_imports = true\n"
NON_MYPY_PYPROJECT = "[tool.ruff]\nline-length = 100\n"

CLEAN_MODULE_SOURCE = "value: int = 1\n"
TYPE_ERROR_MODULE_SOURCE = 'value: int = "not an integer"\n'

UNTYPED_DEF_MODULE_SOURCE = "def passthrough(supplied):\n    return supplied\n"
LOOSE_TOOL_MYPY_PYPROJECT = "[tool.mypy]\nignore_missing_imports = true\n"
STRICT_TOOL_MYPY_PYPROJECT = (
    "[tool.mypy]\nignore_missing_imports = true\ndisallow_untyped_defs = true\n"
)


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mypy_validator_under_test", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def isolate_cache_directory(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolated_cache_directory = tmp_path_factory.mktemp("mypy-validator-cache")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "isolated-test-session")
    monkeypatch.setattr(
        "hooks_constants.mypy_validator_cache_constants.HOOK_STATE_CACHE_DIRECTORY",
        str(isolated_cache_directory),
        raising=True,
    )


def test_discover_mypy_config_finds_nearest_tool_mypy_pyproject(tmp_path: Path) -> None:
    validator = _load_validator()
    (tmp_path / "pyproject.toml").write_text(TOOL_MYPY_PYPROJECT, encoding="utf-8")
    nested_module = tmp_path / "package" / "module.py"
    nested_module.parent.mkdir(parents=True)
    nested_module.write_text("value: int = 1\n", encoding="utf-8")

    discovered = validator.discover_mypy_config(nested_module)

    assert discovered is not None
    assert discovered.resolve() == (tmp_path / "pyproject.toml").resolve()


def test_discover_mypy_config_returns_none_without_tool_mypy(tmp_path: Path) -> None:
    validator = _load_validator()
    (tmp_path / "pyproject.toml").write_text(NON_MYPY_PYPROJECT, encoding="utf-8")
    standalone_module = tmp_path / "module.py"
    standalone_module.write_text("value: int = 1\n", encoding="utf-8")

    assert validator.discover_mypy_config(standalone_module) is None


def test_build_mypy_command_includes_config_file_when_present(tmp_path: Path) -> None:
    validator = _load_validator()
    config_file = tmp_path / "pyproject.toml"

    command = validator.build_mypy_command("package/module.py", config_file)

    assert "--config-file" in command
    assert command[command.index("--config-file") + 1] == str(config_file)
    assert command[-1] == "package/module.py"


def test_build_mypy_command_omits_config_file_when_absent(tmp_path: Path) -> None:
    validator = _load_validator()

    command = validator.build_mypy_command("package/module.py", None)

    assert "--config-file" not in command
    assert command[-1] == "package/module.py"


def test_run_mypy_suppresses_sibling_import_error_with_tool_mypy_config(tmp_path: Path) -> None:
    validator = _load_validator()
    (tmp_path / "pyproject.toml").write_text(TOOL_MYPY_PYPROJECT, encoding="utf-8")
    importer_module = tmp_path / "importer.py"
    importer_module.write_text(MODULE_WITH_SIBLING_IMPORT, encoding="utf-8")

    exit_code, output = validator.run_mypy(str(importer_module), str(tmp_path))

    assert exit_code == 0, output
    assert "import-not-found" not in output


def test_run_mypy_reports_import_error_without_tool_mypy_config(tmp_path: Path) -> None:
    validator = _load_validator()
    importer_module = tmp_path / "importer.py"
    importer_module.write_text(MODULE_WITH_SIBLING_IMPORT, encoding="utf-8")

    exit_code, output = validator.run_mypy(str(importer_module), str(tmp_path))

    assert exit_code != 0
    assert "import-not-found" in output


def test_config_walk_runs_once_per_root_across_two_edits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    validator = _load_validator()
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "pyproject.toml").write_text(TOOL_MYPY_PYPROJECT, encoding="utf-8")
    first_module = project_root / "first.py"
    first_module.write_text(CLEAN_MODULE_SOURCE, encoding="utf-8")
    second_module = project_root / "second.py"
    second_module.write_text(CLEAN_MODULE_SOURCE, encoding="utf-8")

    walk_call_count = 0
    real_walk = validator.find_pyproject_with_mypy_config

    def _counting_walk(starting_file: Path) -> Path | None:
        nonlocal walk_call_count
        walk_call_count += 1
        return real_walk(starting_file)

    monkeypatch.setattr(validator, "find_pyproject_with_mypy_config", _counting_walk)

    validator.run_mypy(str(first_module), str(project_root))
    walk_count_after_first_edit = walk_call_count
    validator.run_mypy(str(second_module), str(project_root))
    walk_count_after_second_edit = walk_call_count

    assert walk_count_after_first_edit == 1
    assert walk_count_after_second_edit == walk_count_after_first_edit


def test_sibling_subtrees_each_resolve_their_own_nested_config(
    tmp_path: Path,
) -> None:
    validator = _load_validator()
    git_root = tmp_path / "monorepo"
    first_subtree = git_root / "first_package"
    second_subtree = git_root / "second_package"
    first_subtree.mkdir(parents=True)
    second_subtree.mkdir(parents=True)
    first_config = first_subtree / "pyproject.toml"
    second_config = second_subtree / "pyproject.toml"
    first_config.write_text(TOOL_MYPY_PYPROJECT, encoding="utf-8")
    second_config.write_text(TOOL_MYPY_PYPROJECT, encoding="utf-8")
    first_module = first_subtree / "first.py"
    second_module = second_subtree / "second.py"
    first_module.write_text(CLEAN_MODULE_SOURCE, encoding="utf-8")
    second_module.write_text(CLEAN_MODULE_SOURCE, encoding="utf-8")

    first_discovered = validator.discover_mypy_config(first_module)
    second_discovered = validator.discover_mypy_config(second_module)

    assert first_discovered is not None
    assert second_discovered is not None
    assert first_discovered.resolve() == first_config.resolve()
    assert second_discovered.resolve() == second_config.resolve()


def test_warm_cache_still_blocks_file_edited_to_introduce_type_error(
    tmp_path: Path,
) -> None:
    validator = _load_validator()
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "pyproject.toml").write_text(TOOL_MYPY_PYPROJECT, encoding="utf-8")
    edited_module = project_root / "edited.py"
    edited_module.write_text(CLEAN_MODULE_SOURCE, encoding="utf-8")

    clean_exit_code, _clean_output = validator.run_mypy(
        str(edited_module), str(project_root)
    )
    assert clean_exit_code == 0

    edited_module.write_text(TYPE_ERROR_MODULE_SOURCE, encoding="utf-8")
    error_exit_code, error_output = validator.run_mypy(
        str(edited_module), str(project_root)
    )

    assert error_exit_code != 0
    assert ": error:" in error_output


def test_warm_cache_skips_mypy_run_when_content_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    validator = _load_validator()
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "pyproject.toml").write_text(TOOL_MYPY_PYPROJECT, encoding="utf-8")
    unchanged_module = project_root / "unchanged.py"
    unchanged_module.write_text(CLEAN_MODULE_SOURCE, encoding="utf-8")

    validator.run_mypy(str(unchanged_module), str(project_root))

    subprocess_run_call_count = 0
    real_subprocess_run = validator.subprocess.run

    def _counting_subprocess_run(*positional: object, **keyword: object) -> object:
        nonlocal subprocess_run_call_count
        subprocess_run_call_count += 1
        return real_subprocess_run(*positional, **keyword)

    monkeypatch.setattr(validator.subprocess, "run", _counting_subprocess_run)

    second_exit_code, _second_output = validator.run_mypy(
        str(unchanged_module), str(project_root)
    )

    assert second_exit_code == 0
    assert subprocess_run_call_count == 0


def test_content_hash_skip_invalidated_when_mypy_config_tightens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    validator = _load_validator()
    project_root = tmp_path / "project"
    project_root.mkdir()
    config_path = project_root / "pyproject.toml"
    config_path.write_text(LOOSE_TOOL_MYPY_PYPROJECT, encoding="utf-8")
    checked_module = project_root / "checked.py"
    checked_module.write_text(UNTYPED_DEF_MODULE_SOURCE, encoding="utf-8")

    loose_exit_code, _loose_output = validator.run_mypy(
        str(checked_module), str(project_root)
    )
    assert loose_exit_code == 0

    config_path.write_text(STRICT_TOOL_MYPY_PYPROJECT, encoding="utf-8")
    validator.reset_session_config_cache()

    subprocess_run_call_count = 0
    real_subprocess_run = validator.subprocess.run

    def _counting_subprocess_run(*positional: object, **keyword: object) -> object:
        nonlocal subprocess_run_call_count
        subprocess_run_call_count += 1
        return real_subprocess_run(*positional, **keyword)

    monkeypatch.setattr(validator.subprocess, "run", _counting_subprocess_run)

    tightened_exit_code, tightened_output = validator.run_mypy(
        str(checked_module), str(project_root)
    )

    assert subprocess_run_call_count == 1, (
        "A tightened mypy config must invalidate the content-hash skip and re-run mypy"
    )
    assert tightened_exit_code != 0
    assert ": error:" in tightened_output
