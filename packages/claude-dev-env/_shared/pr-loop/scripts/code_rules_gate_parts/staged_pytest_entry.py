"""Run staged pytest after isolating import paths from the live worktree."""

import importlib
import os
import sys
from pathlib import Path

from pr_loop_shared_constants.code_rules_gate_constants import (
    ALL_EDITABLE_MAPPING_ATTRIBUTE_NAMES,
    ALL_VENV_DIRECTORY_NAMES,
    STAGED_TEST_ORIGINAL_ROOT_ENV_VAR,
    STAGED_TEST_PROVENANCE_FAILURE_EXIT_CODE,
    STAGED_TEST_PROVENANCE_FAILURE_MESSAGE,
    STAGED_TEST_SNAPSHOT_ROOT_ENV_VAR,
)


def _mapped_snapshot_path(candidate_path: Path, original_root: Path, snapshot_root: Path) -> Path:
    try:
        return snapshot_root / candidate_path.resolve().relative_to(original_root)
    except ValueError:
        return candidate_path


def _rewrite_sys_path(original_root: Path, snapshot_root: Path) -> None:
    all_rewritten_paths: list[str] = []
    for each_path_text in sys.path:
        if not each_path_text:
            all_rewritten_paths.append(each_path_text)
            continue
        rewritten_path = _mapped_snapshot_path(Path(each_path_text), original_root, snapshot_root)
        all_rewritten_paths.append(str(rewritten_path))
    sys.path[:] = all_rewritten_paths


def _rewrite_editable_finder_mappings(original_root: Path, snapshot_root: Path) -> None:
    for each_finder in sys.meta_path:
        for each_attribute_name in ALL_EDITABLE_MAPPING_ATTRIBUTE_NAMES:
            maybe_mapping = getattr(each_finder, each_attribute_name, None)
            if not isinstance(maybe_mapping, dict):
                continue
            for each_module_name, each_path_text in tuple(maybe_mapping.items()):
                if not isinstance(each_path_text, str):
                    continue
                mapped_path = _mapped_snapshot_path(
                    Path(each_path_text), original_root, snapshot_root
                )
                maybe_mapping[each_module_name] = str(mapped_path)


def _is_allowed_original_path(module_path: Path, original_root: Path) -> bool:
    if module_path == Path(__file__).resolve():
        return True
    for each_venv_name in ALL_VENV_DIRECTORY_NAMES:
        venv_root = original_root / each_venv_name
        try:
            module_path.relative_to(venv_root)
            return True
        except ValueError:
            continue
    return False


def _live_worktree_module_path(original_root: Path) -> Path | None:
    for each_module in tuple(sys.modules.values()):
        module_file_text = getattr(each_module, "__file__", None)
        if not isinstance(module_file_text, str):
            continue
        module_path = Path(module_file_text).resolve()
        try:
            module_path.relative_to(original_root)
        except ValueError:
            continue
        if not _is_allowed_original_path(module_path, original_root):
            return module_path
    return None


def main(all_arguments: list[str]) -> int:
    """Run pytest and fail when project imports resolve to the live worktree.

    Args:
        all_arguments: Arguments forwarded to pytest.

    Returns:
        Pytest's exit code, or the provenance failure code for a live import.
    """
    original_root = Path(os.environ[STAGED_TEST_ORIGINAL_ROOT_ENV_VAR]).resolve()
    snapshot_root = Path(os.environ[STAGED_TEST_SNAPSHOT_ROOT_ENV_VAR]).resolve()
    _rewrite_sys_path(original_root, snapshot_root)
    _rewrite_editable_finder_mappings(original_root, snapshot_root)

    pytest_module = importlib.import_module("pytest")
    pytest_exit_code = int(pytest_module.main(all_arguments))
    live_module_path = _live_worktree_module_path(original_root)
    if live_module_path is None:
        return pytest_exit_code
    print(STAGED_TEST_PROVENANCE_FAILURE_MESSAGE.format(path=live_module_path), file=sys.stderr)
    return STAGED_TEST_PROVENANCE_FAILURE_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
