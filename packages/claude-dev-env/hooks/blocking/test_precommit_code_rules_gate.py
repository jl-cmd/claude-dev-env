"""Behavior tests for the precommit_code_rules_gate library module.

The module carries no hook entry point of its own; it exports
``resolve_repository_root`` for its importers (``pii_prevention_blocker.py``,
``pii_payload_scan.py``, ``session_edit_stage_gate.py``).
"""

import subprocess
import sys
from pathlib import Path

try:
    import precommit_code_rules_gate as gate_module
    from precommit_code_rules_gate import resolve_repository_root
except ModuleNotFoundError:
    _BLOCKING_DIR = str(Path(__file__).resolve().parent)
    if _BLOCKING_DIR not in sys.path:
        sys.path.insert(0, _BLOCKING_DIR)
    import precommit_code_rules_gate as gate_module
    from precommit_code_rules_gate import resolve_repository_root


def run_git(repository_root: Path, *git_arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository_root), *git_arguments],
        check=True,
        capture_output=True,
    )


def initialize_repository(repository_root: Path) -> None:
    run_git(repository_root, "init")
    run_git(repository_root, "config", "user.email", "tests@example.com")
    run_git(repository_root, "config", "user.name", "Gate Tests")
    run_git(repository_root, "commit", "--allow-empty", "-m", "initial")


def test_resolve_repository_root_returns_root_for_directory_inside_repository(
    tmp_path: Path,
) -> None:
    initialize_repository(tmp_path)
    nested_directory = tmp_path / "nested"
    nested_directory.mkdir()
    resolved_root = resolve_repository_root(str(nested_directory))
    assert resolved_root == tmp_path.resolve()


def test_resolve_repository_root_returns_none_outside_a_repository(
    tmp_path: Path,
) -> None:
    non_repository_directory = tmp_path / "not_a_repo"
    non_repository_directory.mkdir()
    assert resolve_repository_root(str(non_repository_directory)) is None


def test_module_carries_no_main_entry_point() -> None:
    """The module has no dispatcher-facing hook entry point."""
    assert not hasattr(gate_module, "main")


def test_module_carries_no_commit_invocation_detector() -> None:
    """The commit-detection helper lives in block_main_commit, not duplicated here."""
    assert not hasattr(gate_module, "is_git_commit_invocation")
