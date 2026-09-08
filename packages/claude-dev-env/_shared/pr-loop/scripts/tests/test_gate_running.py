"""Tests for gate_running.py file eligibility."""

import sys
from pathlib import Path

_SCRIPTS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _SCRIPTS_DIRECTORY not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIRECTORY)

from code_rules_gate_parts import gate_running


def _eligible_relative_paths(repository_root: Path, all_relative_paths: list[str]) -> list[str]:
    return [
        each_relative_path
        for each_relative_path in all_relative_paths
        if gate_running._path_is_eligible_for_validation(
            (repository_root / each_relative_path).resolve(), repository_root, False
        )
    ]


def test_gate_skips_a_root_vendored_tree_and_keeps_a_nested_vendor_directory(
    tmp_path: Path,
) -> None:
    for each_relative_path in (
        "src/live.ts",
        "vendor/pstack/skills/watch-pr/github.ts",
        "skill-archive/old.py",
        "src/vendor/nested.py",
    ):
        file_path = tmp_path / each_relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("const value = 1\n", encoding="utf-8")

    assert _eligible_relative_paths(
        tmp_path,
        [
            "src/live.ts",
            "vendor/pstack/skills/watch-pr/github.ts",
            "skill-archive/old.py",
            "src/vendor/nested.py",
        ],
    ) == ["src/live.ts", "src/vendor/nested.py"]
