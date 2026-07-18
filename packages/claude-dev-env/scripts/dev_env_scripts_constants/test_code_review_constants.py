"""Behavioral tests for the host-aware code-review invoker constants module.

These assert the single-source wiring: the effort tokens and the record-stamp
flag the invoker exposes are the exact values the hooks enforcement module
holds, so a threshold change in one place cannot drift the other.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from dev_env_scripts_constants import code_review_constants as review_constants

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent
_ENFORCEMENT_CONSTANTS_PATH = (
    _PACKAGE_ROOT
    / "hooks"
    / "blocking"
    / "config"
    / "code_review_enforcement_constants.py"
)


def _load_enforcement_module() -> ModuleType:
    module_spec = importlib.util.spec_from_file_location(
        "code_review_enforcement_constants_under_test", _ENFORCEMENT_CONSTANTS_PATH
    )
    assert module_spec is not None
    assert module_spec.loader is not None
    enforcement_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(enforcement_module)
    return enforcement_module


def test_effort_tokens_reexport_the_enforcement_source() -> None:
    enforcement_module = _load_enforcement_module()
    assert review_constants.ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER == getattr(
        enforcement_module, "ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER"
    )


def test_record_stamp_flag_matches_sanctioned_minter_flag() -> None:
    enforcement_module = _load_enforcement_module()
    assert review_constants.RECORD_STAMP_FLAG == getattr(
        enforcement_module, "SANCTIONED_STAMP_MINTER_FLAG"
    )


def test_default_effort_is_a_known_token() -> None:
    assert (
        review_constants.DEFAULT_CODE_REVIEW_EFFORT
        in review_constants.ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER
    )
