from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / "packages"
    / "claude-dev-env"
    / "_shared"
    / "pr-loop"
    / "scripts"
    / "preflight.py"
)


def _load_preflight_module():
    specification = importlib.util.spec_from_file_location("bugteam_preflight", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    assert specification.loader is not None
    specification.loader.exec_module(module)
    return module


def test_find_repository_root_returns_git_root(tmp_path: Path) -> None:
    preflight = _load_preflight_module()
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True)
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert preflight.find_repository_root(nested) == tmp_path.resolve()


def test_load_preflight_moves_script_directory_to_front() -> None:
    script_directory_resolved = str(SCRIPT.parent.resolve())
    script_directory_absolute = str(SCRIPT.parent.absolute())
    original_sys_path = list(sys.path)
    try:
        sys.path.insert(0, script_directory_resolved)
        sys.path.insert(0, str(REPO_ROOT))
        _load_preflight_module()
        assert os.path.samefile(sys.path[0], script_directory_resolved)
        assert sys.path[0] == script_directory_absolute
        equivalent_count = sum(
            1
            for each_entry in sys.path
            if os.path.exists(each_entry)
            and os.path.samefile(each_entry, SCRIPT.parent)
        )
        assert equivalent_count == 1
    finally:
        sys.path[:] = original_sys_path


def test_main_help_exits_zero() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "pytest" in (completed.stdout or "").lower()
