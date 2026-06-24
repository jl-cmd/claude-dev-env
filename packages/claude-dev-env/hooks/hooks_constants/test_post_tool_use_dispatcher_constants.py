"""Tests for the PostToolUse dispatcher constants module."""

import pathlib
import sys

_HOOKS_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

_VALIDATION_DIR = _HOOKS_ROOT / "validation"
if str(_VALIDATION_DIR) not in sys.path:
    sys.path.insert(0, str(_VALIDATION_DIR))

from post_tool_use_dispatcher import (
    PostHostedHookResult,
    aggregate_post_hosted_hook_results,
)

from hooks_constants.post_tool_use_dispatcher_constants import (
    BLOCKING_CRASH_DENY_REASON,
)


def test_blocking_hook_crash_block_reason_surfaces_the_constant() -> None:
    crash_result = PostHostedHookResult(
        captured_stdout="",
        did_crash=True,
        is_blocking=True,
    )
    decision = aggregate_post_hosted_hook_results([crash_result])
    assert decision.should_block
    assert BLOCKING_CRASH_DENY_REASON in decision.all_block_reasons


def test_non_blocking_hook_crash_does_not_surface_the_constant() -> None:
    crash_result = PostHostedHookResult(
        captured_stdout="",
        did_crash=True,
        is_blocking=False,
    )
    decision = aggregate_post_hosted_hook_results([crash_result])
    assert not decision.should_block
    assert BLOCKING_CRASH_DENY_REASON not in decision.all_block_reasons
