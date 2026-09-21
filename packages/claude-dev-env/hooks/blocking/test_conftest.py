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
