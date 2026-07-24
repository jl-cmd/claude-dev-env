"""Behavioral tests for the grok worker constants module.

These assert the module's computed values derive from their source parts:
the readonly disallowed-tools argument round-trips to its tuple, the
binary-not-found message names the binary, the default role maps to a
known agent set, and the known tool profiles hold readonly and build.
"""

from __future__ import annotations

from dev_env_scripts_constants import grok_worker_constants as worker_constants


def test_readonly_disallowed_value_round_trips_to_the_tool_tuple() -> None:
    joined_tools = worker_constants.READONLY_DISALLOWED_TOOLS_VALUE
    assert (
        tuple(joined_tools.split(",")) == worker_constants.ALL_READONLY_DISALLOWED_TOOLS
    )


def test_binary_not_found_message_names_the_binary() -> None:
    assert (
        worker_constants.GROK_BINARY_NAME
        in worker_constants.GROK_BINARY_NOT_FOUND_STDERR
    )


def test_default_role_maps_to_a_known_agent_file_set() -> None:
    charter_filenames = worker_constants.ALL_AGENT_FILENAMES_BY_ROLE[
        worker_constants.DEFAULT_ROLE
    ]
    assert charter_filenames
    assert all(charter_name.endswith(".md") for charter_name in charter_filenames)


def test_known_tool_profiles_hold_readonly_and_build() -> None:
    assert set(worker_constants.ALL_KNOWN_TOOL_PROFILES) == {
        worker_constants.TOOL_PROFILE_READONLY,
        worker_constants.TOOL_PROFILE_BUILD,
    }
