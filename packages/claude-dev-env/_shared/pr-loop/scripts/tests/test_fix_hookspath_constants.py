"""Tests for fix_hookspath_constants.

Confirms HOOKS_PATH_SUFFIX is the full 3-component canonical hooks path so
validators cannot accept arbitrary directories that merely end in
``hooks/git-hooks``.
"""

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_constants_module() -> ModuleType:
    module_path = Path(__file__).parent.parent / "config" / "fix_hookspath_constants.py"
    specification = importlib.util.spec_from_file_location(
        "config.fix_hookspath_constants", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


constants_module = _load_constants_module()


def test_hooks_path_suffix_uses_full_three_component_canonical_suffix() -> None:
    assert constants_module.HOOKS_PATH_SUFFIX == "/".join(
        constants_module.ALL_CANONICAL_HOOKS_DIRECTORY_COMPONENTS
    )
    assert constants_module.HOOKS_PATH_SUFFIX == ".claude/hooks/git-hooks"


def test_canonical_hooks_directory_components_remain_three_component_tuple() -> None:
    assert constants_module.ALL_CANONICAL_HOOKS_DIRECTORY_COMPONENTS == (
        ".claude",
        "hooks",
        "git-hooks",
    )


def test_hooks_path_verification_suffix_is_two_component_for_backward_compat() -> None:
    assert constants_module.HOOKS_PATH_VERIFICATION_SUFFIX == "hooks/git-hooks"
    assert constants_module.HOOKS_PATH_VERIFICATION_SUFFIX == "/".join(
        constants_module.ALL_CANONICAL_HOOKS_DIRECTORY_COMPONENTS[-2:]
    )
