"""Behavior tests for the code_rules_boolean_mustcheck code-rules check module."""

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

from code_rules_boolean_mustcheck import (  # noqa: E402
    check_ignored_must_check_return,
)

code_rules_enforcer = SimpleNamespace(
    check_ignored_must_check_return=check_ignored_must_check_return,
)


def test_ignored_must_check_return_flags_bare_awaited_call() -> None:
    """A bare ``await find_and_click(...)`` statement discards its only failure signal.

    The curated must-check functions are async, so the common real call site is a
    bare ``await``-wrapped call. Unwrapping ``ast.Await`` before the Call check is
    required for this case to be flagged.
    """
    source = "async def step() -> None:\n    await find_and_click('#x')\n"
    issues = code_rules_enforcer.check_ignored_must_check_return(
        source, "/project/src/clicker.py"
    )
    assert any("find_and_click" in each_issue for each_issue in issues), (
        f"a bare awaited must-check call must be flagged; got: {issues!r}"
    )
    assert len(issues) == 1


def test_ignored_must_check_return_exempts_consumed_awaited_call() -> None:
    """An assigned or branched-on awaited must-check call consumes its outcome."""
    assigned = "async def step() -> None:\n    clicked = await find_and_click('#x')\n    print(clicked)\n"
    branched = "async def step() -> None:\n    if await find_and_click('#x'):\n        pass\n"
    assert (
        code_rules_enforcer.check_ignored_must_check_return(assigned, "/project/src/clicker.py")
        == []
    )
    assert (
        code_rules_enforcer.check_ignored_must_check_return(branched, "/project/src/clicker.py")
        == []
    )


def test_ignored_must_check_return_flags_edited_line_past_a_cap_of_earlier_violations() -> None:
    """The cap must apply after scoping so the edited-line violation is never dropped.

    Collecting only a cap's worth of violations in ``ast.walk`` order, then scoping,
    fills the cap with earlier out-of-scope calls and discards the edited-line one —
    the very violation the scoped enforcer exists to block. Every violation must be
    collected before scoping so the edited line survives the diff filter.
    """
    pre_existing_call_count = 5
    edited_call_line_number = pre_existing_call_count + 2
    all_pre_existing_call_lines = [
        f"    await find_and_click('#x{each_index}')"
        for each_index in range(pre_existing_call_count)
    ]
    all_lines = (
        ["async def step() -> None:"]
        + all_pre_existing_call_lines
        + ["    await find_and_click('#edited')"]
    )
    source = "\n".join(all_lines) + "\n"
    issues = code_rules_enforcer.check_ignored_must_check_return(
        source,
        "/project/src/clicker.py",
        {edited_call_line_number},
        False,
    )
    assert len(issues) == 1, (
        f"the edited-line violation must survive a cap's worth of earlier calls; got: {issues!r}"
    )
    assert f"Line {edited_call_line_number}:" in issues[0], (
        f"the single issue must name the edited line {edited_call_line_number}; got: {issues!r}"
    )
