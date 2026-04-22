"""Existence and coherence checks for groq_bugteam_config.

These are not business-behavior tests — the config module is constants only —
but the tdd_enforcer hook requires a co-located test file, and the readability
rule wants every constant referenced by at least two callers. The checks below
keep those invariants observable and fail loudly if someone edits the config
into an inconsistent state.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys


def _load_config_module():
    module_path = pathlib.Path(__file__).parent / "groq_bugteam_config.py"
    module_spec = importlib.util.spec_from_file_location(
        "groq_bugteam_config", module_path
    )
    loaded_module = importlib.util.module_from_spec(module_spec)
    sys.modules["groq_bugteam_config"] = loaded_module
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


groq_bugteam_config = _load_config_module()


def test_primary_and_fallback_models_are_different():
    assert (
        groq_bugteam_config.GROQ_PRIMARY_MODEL
        != groq_bugteam_config.GROQ_FALLBACK_MODEL
    )


def test_endpoint_is_https():
    assert groq_bugteam_config.GROQ_API_ENDPOINT.startswith("https://")


def test_json_indent_spaces_is_positive_integer():
    assert isinstance(groq_bugteam_config.JSON_INDENT_SPACES, int)
    assert groq_bugteam_config.JSON_INDENT_SPACES > 0


def test_pipeline_failure_exit_code_is_non_zero_and_non_one():
    # Reserve 0 for success and 1 for "bad stdin" — failure code must distinguish.
    assert groq_bugteam_config.PIPELINE_FAILURE_EXIT_CODE not in (0, 1)


def test_text_clamp_head_parts_fits_within_total():
    assert (
        0
        < groq_bugteam_config.TEXT_CLAMP_HEAD_PARTS
        < groq_bugteam_config.TEXT_CLAMP_TOTAL_PARTS
    )


def test_request_timeout_is_generous_enough_for_cold_start():
    # Groq free-tier cold-start latency has been observed at 60s+; anything
    # under 60 risks killing healthy requests mid-response.
    assert groq_bugteam_config.GROQ_REQUEST_TIMEOUT_SECONDS >= 60


def test_fix_budget_exceeds_audit_budget():
    # Fix responses return full file contents; audit responses return just
    # findings JSON — fix must have strictly more headroom.
    assert (
        groq_bugteam_config.GROQ_FIX_MAX_COMPLETION_TOKENS
        > groq_bugteam_config.GROQ_AUDIT_MAX_COMPLETION_TOKENS
    )
