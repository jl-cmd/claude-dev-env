"""Tests for the shared fixtures this directory's ``conftest.py`` provides."""

from __future__ import annotations

import pathlib

from code_rules_shared import is_hook_infrastructure


def should_yield_a_directory_a_target_inside_it_routes_as_hook_infrastructure(
    hook_blocking_dir: pathlib.Path,
) -> None:
    target_file = hook_blocking_dir / "new_blocker.py"
    assert is_hook_infrastructure(str(target_file)) is True


def should_yield_a_directory_that_exists_on_disk(
    hook_blocking_dir: pathlib.Path,
) -> None:
    assert hook_blocking_dir.is_dir()


def should_keep_the_hook_blocking_dir_explanation_only_on_the_fixture() -> None:
    directory = pathlib.Path(__file__).parent
    exempt_paths = {directory / "conftest.py", pathlib.Path(__file__)}
    explanation_fragment = "tail mirrors a production hook directory"
    offending_files = [
        path.name
        for path in sorted(directory.glob("*.py"))
        if path not in exempt_paths and explanation_fragment in path.read_text(encoding="utf-8")
    ]
    assert offending_files == [], (
        "the hook_blocking_dir fixture's explanation belongs on conftest.py alone, "
        f"got it repeated in: {offending_files}"
    )
