"""Behavior tests for pending-sidecar discovery and cleanup."""

import sys
from pathlib import Path

_hooks_directory = str(Path(__file__).resolve().parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from pending_sidecars import pending_sidecar_paths, remove_pending_sidecars


def test_pending_sidecar_paths_and_remove_pending_sidecars(tmp_path: Path) -> None:
    main_file = tmp_path / "state.json"
    first_pending = tmp_path / "state.json.pending-first.json"
    second_pending = tmp_path / "state.json.pending-second.json"
    unrelated_file = tmp_path / "other.json"
    for each_file in (first_pending, second_pending, unrelated_file):
        each_file.write_text("state", encoding="utf-8")

    all_pending_files = pending_sidecar_paths(main_file, ".pending-", ".json")
    remove_pending_sidecars(all_pending_files)

    assert sorted(all_pending_files) == sorted((first_pending, second_pending))
    assert unrelated_file.is_file()
