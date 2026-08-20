"""Exercise the installed dispatcher layout in isolated profile trees."""

from __future__ import annotations

import json
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


def _stage_shadow_import_root(
    target_profile_directory: Path, dispatcher_module_name: str
) -> Path:
    shadow_import_root = (
        target_profile_directory / f"shadow-import-root-{dispatcher_module_name}"
    )
    shadow_import_root.mkdir()
    (shadow_import_root / "tier_model_ids.py").write_text(
        "raise RuntimeError('shadow tier_model_ids imported')\n",
        encoding="utf-8",
    )
    (shadow_import_root / "claude_chain_runner.py").write_text(
        "raise RuntimeError('shadow claude_chain_runner imported')\n",
        encoding="utf-8",
    )
    shadow_constants_root = shadow_import_root / "advisor_scripts_constants"
    shadow_constants_root.mkdir()
    (shadow_constants_root / "__init__.py").write_text(
        "raise RuntimeError('shadow advisor constants imported')\n",
        encoding="utf-8",
    )
    shadow_scripts_constants_root = shadow_import_root / "dev_env_scripts_constants"
    shadow_scripts_constants_root.mkdir()
    (shadow_scripts_constants_root / "__init__.py").write_text(
        "raise RuntimeError('shadow dev-env constants imported')\n",
        encoding="utf-8",
    )
    return shadow_import_root


@pytest.fixture(scope="module")
def installed_dispatcher_scripts(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Stage one installed profile for both dispatcher import checks."""
    source_package_directory = Path(__file__).resolve().parent.parent
    target_profile_directory = tmp_path_factory.mktemp("dispatcher_profile") / ".claude"
    return _stage_profile_tree(source_package_directory, target_profile_directory)


@pytest.mark.parametrize("dispatcher_name", _DISPATCHER_NAMES)
def test_installed_dispatcher_help_imports_advisor_constants(
    dispatcher_name: str, installed_dispatcher_scripts: Path
) -> None:
    """Each deployed dispatcher imports and serves help from an isolated tree."""
    target_scripts_directory = installed_dispatcher_scripts
    target_profile_directory = target_scripts_directory.parent

    completed_process = subprocess.run(
        [
            sys.executable,
            "-S",
            "-E",
            str(target_scripts_directory / dispatcher_name),
            "--help",
        ],
        cwd=target_profile_directory,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed_process.returncode == 0
    assert completed_process.stderr == ""
    assert "usage:" in completed_process.stdout


@pytest.mark.parametrize("dispatcher_name", _DISPATCHER_NAMES)
def test_imported_dispatcher_promotes_all_profile_owned_roots(
    dispatcher_name: str, installed_dispatcher_scripts: Path
) -> None:
    """Fresh imported-module loading selects every installed profile root."""
    dispatcher_module_name = dispatcher_name.rsplit(".", maxsplit=1)[0]
    target_profile_directory = installed_dispatcher_scripts.parent
    shadow_import_root = _stage_shadow_import_root(
        target_profile_directory, dispatcher_module_name
    )
    advisor_scripts_root = target_profile_directory / "_shared" / "advisor" / "scripts"
    advisor_config_root = advisor_scripts_root / "config"
    process_tree_scripts_root = (
        target_profile_directory / "_shared" / "process-tree" / "scripts"
    )
    process_tree_config_root = process_tree_scripts_root / "config"
    all_expected_roots = [
        str(advisor_config_root),
        str(advisor_scripts_root),
        str(installed_dispatcher_scripts),
        str(shadow_import_root),
    ]
    if dispatcher_module_name == "resolve_worker_spawn":
        all_expected_roots = [
            str(process_tree_config_root),
            str(process_tree_scripts_root),
            *all_expected_roots,
        ]
    child_code = "\n".join(
        (
            "import importlib",
            "import json",
            "import sys",
            "from pathlib import Path",
            f"dispatcher_module_name = {dispatcher_module_name!r}",
            "shadow_import_root, scripts_root, advisor_scripts_root, advisor_config_root = (",
            f"    {str(shadow_import_root)!r},",
            f"    {str(installed_dispatcher_scripts)!r},",
            f"    {str(advisor_scripts_root)!r},",
            f"    {str(advisor_config_root)!r},",
            ")",
            "sys.path[:0] = [",
            "    shadow_import_root,",
            "    scripts_root,",
            "    advisor_scripts_root,",
            "    advisor_config_root,",
            "]",
            "assert all(each_name not in sys.modules for each_name in (",
            "    dispatcher_module_name,",
            "    'tier_model_ids',",
            "    'advisor_scripts_constants',",
            "))",
            "dispatcher = importlib.import_module(dispatcher_module_name)",
            "tier_model_ids = importlib.import_module('tier_model_ids')",
            "advisor_scripts_constants = importlib.import_module('advisor_scripts_constants')",
            "print(json.dumps({",
            "    'dispatcher': str(Path(dispatcher.__file__).resolve()),",
            "    'tier_model_ids': str(Path(tier_model_ids.__file__).resolve()),",
            "    'advisor_scripts_constants': str(Path(advisor_scripts_constants.__file__).resolve()),",
            "    'roots': sys.path[:6],",
            "}))",
        )
    )
    completed_process = subprocess.run(
        [sys.executable, "-S", "-E", "-c", child_code],
        cwd=target_profile_directory,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed_process.returncode == 0, completed_process.stderr
    assert completed_process.stderr == ""
    all_import_results = json.loads(completed_process.stdout)
    assert all_import_results["dispatcher"] == str(
        installed_dispatcher_scripts / dispatcher_name
    )
    assert all_import_results["tier_model_ids"] == str(
        advisor_scripts_root / "tier_model_ids.py"
    )
    assert all_import_results["advisor_scripts_constants"] == str(
        advisor_config_root / "advisor_scripts_constants" / "__init__.py"
    )
    assert all_import_results["roots"][: len(all_expected_roots)] == all_expected_roots
