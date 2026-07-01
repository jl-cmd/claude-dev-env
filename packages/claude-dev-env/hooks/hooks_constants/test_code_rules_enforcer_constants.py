"""Behavior tests for the JS returns-object schema-less detection patterns.

These regexes drive ``check_js_returns_object_schemaless_branch``: they locate a
JSDoc-documented ``function`` declaration, decide whether its ``@returns`` clause
promises a ``Promise<object>``, find each ``return`` that calls a helper, and spot
a ``schema`` key inside an options object. Each test pins one pattern against the
shapes it must accept and the near-misses it must reject.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants.code_rules_enforcer_constants import (
    FUNCTION_WITH_JSDOC_PATTERN,
    JSDOC_RETURNS_STRUCTURED_OBJECT_PROMISE_PATTERN,
    RETURN_CALL_OPENING_PARENTHESIS_PATTERN,
    SCHEMA_OPTIONS_PROPERTY_KEY_PATTERN,
)


def test_function_with_jsdoc_pattern_captures_name_and_jsdoc() -> None:
    source = (
        "/**\n * @returns {Promise<object>} the structured output\n */\n"
        "function runGitTask(task, head) {\n"
    )
    match = FUNCTION_WITH_JSDOC_PATTERN.search(source)
    assert match is not None
    assert match.group("name") == "runGitTask"
    assert "@returns" in match.group("jsdoc")


def test_function_with_jsdoc_pattern_captures_async_declaration() -> None:
    source = "/** @returns {Promise<object>} */\nasync function fixerWithRecovery(head) {\n"
    match = FUNCTION_WITH_JSDOC_PATTERN.search(source)
    assert match is not None
    assert match.group("name") == "fixerWithRecovery"


def test_returns_object_promise_pattern_matches_structured_object_claim() -> None:
    lowercase_match = JSDOC_RETURNS_STRUCTURED_OBJECT_PROMISE_PATTERN.search(
        "@returns {Promise<object>} the structured output"
    )
    assert lowercase_match is not None
    assert lowercase_match.group(0) == "@returns {Promise<object>}"
    capitalized_match = JSDOC_RETURNS_STRUCTURED_OBJECT_PROMISE_PATTERN.search(
        "@return {Promise<Object>}"
    )
    assert capitalized_match is not None
    assert capitalized_match.group(0) == "@return {Promise<Object>}"


def test_returns_object_promise_pattern_rejects_string_and_array_claims() -> None:
    assert JSDOC_RETURNS_STRUCTURED_OBJECT_PROMISE_PATTERN.search("@returns {Promise<*>}") is None
    assert (
        JSDOC_RETURNS_STRUCTURED_OBJECT_PROMISE_PATTERN.search("@returns {Promise<string>}") is None
    )
    assert (
        JSDOC_RETURNS_STRUCTURED_OBJECT_PROMISE_PATTERN.search("@returns {Promise<object[]>}")
        is None
    )


def test_return_call_pattern_captures_plain_and_awaited_callees() -> None:
    plain_match = RETURN_CALL_OPENING_PARENTHESIS_PATTERN.search(
        "  return convergeAgent(prompt, {})"
    )
    assert plain_match is not None
    assert plain_match.group("callee") == "convergeAgent"
    awaited_match = RETURN_CALL_OPENING_PARENTHESIS_PATTERN.search(
        "  return await commitWithRecovery({})"
    )
    assert awaited_match is not None
    assert awaited_match.group("callee") == "commitWithRecovery"


def test_return_call_pattern_ignores_identifiers_beginning_with_return() -> None:
    assert RETURN_CALL_OPENING_PARENTHESIS_PATTERN.search("const x = returnValue(payload)") is None


def test_schema_property_key_pattern_matches_only_the_options_key() -> None:
    assert (
        SCHEMA_OPTIONS_PROPERTY_KEY_PATTERN.search("{ label: 'x', schema: HEAD_SCHEMA }")
        is not None
    )
    assert SCHEMA_OPTIONS_PROPERTY_KEY_PATTERN.search("{ label: 'x', schema : X }") is not None
    assert SCHEMA_OPTIONS_PROPERTY_KEY_PATTERN.search("{ agentType, phase }, HEAD_SCHEMA") is None
    assert SCHEMA_OPTIONS_PROPERTY_KEY_PATTERN.search("{ myschema: X }") is None
