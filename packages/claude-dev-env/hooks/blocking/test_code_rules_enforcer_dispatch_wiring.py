"""Meta-test asserting every check_* function is dispatched from validate_content.

The per-check test modules each prove one ``check_*`` function flags the right
violation, but none proves the enforcer actually calls that function. A refactor
that drops a dispatch line from ``validate_content`` leaves every per-check test
green while the check stops firing at Write/Edit time — the precise failure mode
that would let a dead module-level constant (the ``MEDIUM_TEXT`` class) or an
orphan CSS class slip past the gate again.

This module reads ``validate_content``'s source and asserts every ``check_*``
attribute on the enforcer module appears in it. A check that is intentionally
not wired must be listed in ``KNOWN_UNDISPATCHED_CHECKS`` with a reason in this
docstring. ``check_unanchored_command_dispatch`` is listed there: it guards a
``hooks/blocking`` command classifier, and the whole ``validate_content`` verdict
stays off hook-infrastructure files, so the enforcer dispatches it from
``_hook_infrastructure_blocking_issues`` instead. The companion
``test_code_rules_enforcer_cap_meta.py`` guards the payload-cap convention; this
module guards the wiring.
"""

from __future__ import annotations

import importlib.util
import inspect
import pathlib
import sys

_HOOK_DIRECTORY = pathlib.Path(__file__).parent
if str(_HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIRECTORY))

_hook_specification = importlib.util.spec_from_file_location(
    "code_rules_enforcer",
    _HOOK_DIRECTORY / "code_rules_enforcer.py",
)
assert _hook_specification is not None
assert _hook_specification.loader is not None
_hook_module = importlib.util.module_from_spec(_hook_specification)
_hook_specification.loader.exec_module(_hook_module)

KNOWN_UNDISPATCHED_CHECKS: frozenset[str] = frozenset(
    {"check_unanchored_command_dispatch"}
)


def _all_check_function_names() -> list[str]:
    return [
        each_attribute_name
        for each_attribute_name in dir(_hook_module)
        if each_attribute_name.startswith("check_")
        and callable(getattr(_hook_module, each_attribute_name))
    ]


def _validate_content_source() -> str:
    return inspect.getsource(_hook_module.validate_content)


def test_every_check_function_is_called_in_validate_content() -> None:
    all_check_names = set(_all_check_function_names())
    validate_content_source = _validate_content_source()
    undispatched_check_names = {
        each_name for each_name in all_check_names if each_name not in validate_content_source
    }
    unexpected_undispatched = undispatched_check_names - KNOWN_UNDISPATCHED_CHECKS
    assert unexpected_undispatched == set(), (
        f"check_* functions are imported but never called in validate_content: "
        f"{sorted(unexpected_undispatched)}. Wire each into validate_content so the "
        f"check fires at Write/Edit time, or list it in KNOWN_UNDISPATCHED_CHECKS "
        f"with a reason in the test header docstring."
    )


def test_dead_module_constant_check_stays_wired() -> None:
    validate_content_source = _validate_content_source()
    assert "check_dead_module_constants" in validate_content_source, (
        "check_dead_module_constants must stay dispatched from validate_content so a "
        "dead exported constant (the MEDIUM_TEXT class) is blocked at Write/Edit time."
    )


def test_known_undispatched_set_lists_only_existing_checks() -> None:
    all_check_names = set(_all_check_function_names())
    stale_names = KNOWN_UNDISPATCHED_CHECKS - all_check_names
    assert stale_names == set(), (
        f"KNOWN_UNDISPATCHED_CHECKS lists functions that no longer exist: "
        f"{sorted(stale_names)}. Restore the function or remove it from the set."
    )
