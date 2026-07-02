"""Tests for reviewer_availability_constants.py extracted constant set."""

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_constants_module() -> ModuleType:
    module_path = (
        Path(__file__).parent.parent
        / "pr_loop_shared_constants"
        / "reviewer_availability_constants.py"
    )
    specification = importlib.util.spec_from_file_location(
        "pr_loop_shared_constants.reviewer_availability_constants", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


constants_module = _load_constants_module()


def test_available_exit_code_matches_the_posix_success_convention() -> None:
    assert constants_module.EXIT_CODE_REVIEWER_AVAILABLE == 0


def test_down_exit_code_is_distinct_from_the_available_exit_code() -> None:
    assert (
        constants_module.EXIT_CODE_REVIEWER_DOWN
        != constants_module.EXIT_CODE_REVIEWER_AVAILABLE
    )
    assert constants_module.EXIT_CODE_REVIEWER_DOWN != 0
