"""Specifications for the accepted-key set on a batch worker entry.

The batch launcher rejects a worker entry carrying any key outside
``ALL_KNOWN_WORKER_SPEC_KEYS``. That makes the set a gate on the published
JSON contract: a worker key the module defines but the set omits is rejected
from every spec that uses it, and a member the module declares nowhere keeps
accepting a key the launcher drops. Both drifts are silent, so they are
pinned here.
"""

from __future__ import annotations

from dev_env_scripts_constants import grok_worker_constants

WORKER_SPEC_KEY_NAME_PREFIX: str = "WORKER_SPEC_"
WORKER_SPEC_KEY_NAME_SUFFIX: str = "_KEY"


def _all_declared_worker_key_values() -> set[str]:
    """Read every ``WORKER_SPEC_*_KEY`` value the constants module declares."""
    return {
        getattr(grok_worker_constants, each_name)
        for each_name in dir(grok_worker_constants)
        if each_name.startswith(WORKER_SPEC_KEY_NAME_PREFIX)
        and each_name.endswith(WORKER_SPEC_KEY_NAME_SUFFIX)
    }


def test_should_accept_every_declared_worker_spec_key() -> None:
    all_declared_key_values = _all_declared_worker_key_values()
    all_missing_key_values = (
        all_declared_key_values - grok_worker_constants.ALL_KNOWN_WORKER_SPEC_KEYS
    )

    assert not all_missing_key_values, (
        "worker key constants missing from the accepted set: "
        f"{sorted(all_missing_key_values)}"
    )


def test_should_accept_only_keys_the_module_declares() -> None:
    all_declared_key_values = _all_declared_worker_key_values()
    all_stale_key_values = (
        grok_worker_constants.ALL_KNOWN_WORKER_SPEC_KEYS - all_declared_key_values
    )

    assert not all_stale_key_values, (
        f"accepted keys with no worker key constant: {sorted(all_stale_key_values)}"
    )


def test_should_name_both_placeholders_in_the_unknown_key_message() -> None:
    formatted_message = grok_worker_constants.UNKNOWN_WORKER_KEY_ERROR_TEMPLATE.format(
        unknown_keys="timeout_second",
        accepted_keys="timeout_seconds",
    )

    assert "timeout_second;" in formatted_message
    assert formatted_message.endswith("timeout_seconds")
