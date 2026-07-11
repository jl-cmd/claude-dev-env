"""Behavior tests for the code_rules_path_utils code-rules check module."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_path_utils import is_config_file  # noqa: E402
from validators.exempt_paths import (  # noqa: E402
    is_config_file as exempt_paths_is_config_file,
)

code_rules_enforcer = SimpleNamespace(
    is_config_file=is_config_file,
)


def test_is_config_file_rejects_filename_only_config_pattern() -> None:
    """Paths where 'config' appears only in the filename (not as a directory segment) must return False."""
    assert code_rules_enforcer.is_config_file("scripts/db/config.py") is False, (
        "scripts/db/config.py — filename is config.py but parent dir is db, must be False"
    )
    assert code_rules_enforcer.is_config_file("lib/myconfig.py") is False, (
        "lib/myconfig.py — config appears only in the filename stem, must be False"
    )
    assert code_rules_enforcer.is_config_file("src/app_config.py") is False, (
        "src/app_config.py — config appears only in the filename stem, must be False"
    )


def test_is_config_file_reexported_by_exempt_paths_matches_canonical() -> None:
    """The exempt_paths re-export of is_config_file must agree with the canonical code_rules_path_utils implementation on all sample paths."""
    all_sample_paths = [
        "scripts/db/config.py",
        "config/timing.py",
        "settings.py",
    ]
    for each_path in all_sample_paths:
        canonical_result = code_rules_enforcer.is_config_file(each_path)
        exempt_paths_result = exempt_paths_is_config_file(each_path)
        assert canonical_result == exempt_paths_result, (
            f"is_config_file diverged for {each_path!r}: "
            f"code_rules_path_utils={canonical_result}, exempt_paths={exempt_paths_result}"
        )
