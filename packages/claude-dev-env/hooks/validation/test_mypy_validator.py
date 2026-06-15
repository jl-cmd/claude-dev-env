"""Behavior tests for the mypy_validator config-discovery fix.

The hook runs mypy from the project root, so without handing mypy the project's
own ``[tool.mypy]`` config a module that imports its siblings by name draws a
spurious ``import-not-found`` error. These tests drive the real production
functions: ``discover_mypy_config`` walks up to the nearest configuring
``pyproject.toml`` and ``run_mypy`` passes it through so the project's
``ignore_missing_imports`` setting applies.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

HOOK_PATH = Path(__file__).resolve().parent / "mypy_validator.py"

MODULE_WITH_SIBLING_IMPORT = (
    "from sibling_only_resolvable_at_runtime import value\n\nx: int = value\n"
)
TOOL_MYPY_PYPROJECT = "[tool.mypy]\nignore_missing_imports = true\n"
NON_MYPY_PYPROJECT = "[tool.ruff]\nline-length = 100\n"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mypy_validator_under_test", HOOK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
