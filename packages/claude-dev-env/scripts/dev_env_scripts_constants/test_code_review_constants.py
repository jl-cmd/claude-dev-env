"""Behavioral tests for the host-aware code-review invoker constants module."""

from __future__ import annotations

from dev_env_scripts_constants import code_review_constants as review_constants


def test_default_effort_is_a_known_token() -> None:
    assert (
        review_constants.DEFAULT_CODE_REVIEW_EFFORT
        in review_constants.ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER
    )
