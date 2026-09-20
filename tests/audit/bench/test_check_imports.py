"""Direct check scripts retain their missing-argument exit contract."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def copied_checks(tmp_path: Path) -> Path:
    source_directory = Path(__file__).resolve().parent / "checks"
    return Path(shutil.copytree(source_directory, tmp_path / "checks"))


@pytest.fixture(params=("empty", "colliding-config"))
def child_environment(request: pytest.FixtureRequest, tmp_path: Path) -> dict[str, str]:
    import_directory = tmp_path / request.param
    import_directory.mkdir()
    if request.param == "colliding-config":
        package_directory = import_directory / "config"
        package_directory.mkdir()
        (package_directory / "__init__.py").write_text("", encoding="utf-8")
    environment_by_name = {
        each_name: each_setting
        for each_name, each_setting in os.environ.items()
        if not each_name.upper().startswith("PYTHON")
    }
    environment_by_name["PYTHONPATH"] = str(import_directory)
    return environment_by_name


@pytest.mark.parametrize(
    "script_name",
    ("json_stdout_equals.py", "max_function_length.py", "tests_kill_variant.py"),
)
def test_direct_check_returns_harness_exit_for_missing_arguments(
    copied_checks: Path, child_environment: dict[str, str], script_name: str
) -> None:
    completed_check = subprocess.run(
        [sys.executable, "-S", str(copied_checks / script_name)],
        cwd=copied_checks.parent,
        env=child_environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed_check.returncode == 3, completed_check.stderr
