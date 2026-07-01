"""Behavioral tests for the JavaScript boolean-naming and banned-identifier checks."""

import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)

from code_rules_js_conventions import (  # noqa: E402
    check_js_banned_identifiers,
    check_js_boolean_naming,
)

CONVERGE_PATH = "packages/claude-dev-env/skills/autoconverge/workflow/converge.mjs"


def test_flags_unprefixed_boolean_let_declaration() -> None:
    content = "let hardeningPrOpened = false\n"
    issues = check_js_boolean_naming(content, CONVERGE_PATH)
    assert len(issues) == 1
    assert "hardeningPrOpened" in issues[0]
    assert "Line 1" in issues[0]


def test_flags_unprefixed_boolean_negation_declaration() -> None:
    content = "const readyState = !pending\n"
    issues = check_js_boolean_naming(content, CONVERGE_PATH)
    assert len(issues) == 1
    assert "readyState" in issues[0]


def test_flags_pure_negation_declaration() -> None:
    content = "const ready = !pending;\n"
    issues = check_js_boolean_naming(content, CONVERGE_PATH)
    assert len(issues) == 1
    assert "ready" in issues[0]


def test_does_not_flag_ternary_negation_string_declaration() -> None:
    content = 'const label = !isActive ? "on" : "off";\n'
    assert check_js_boolean_naming(content, CONVERGE_PATH) == []


def test_does_not_flag_ternary_negation_number_declaration() -> None:
    content = "const count = !arr.length ? 0 : arr.length;\n"
    assert check_js_boolean_naming(content, CONVERGE_PATH) == []


def test_does_not_flag_negation_logical_and_declaration() -> None:
    content = "const name = !err && getName();\n"
    assert check_js_boolean_naming(content, CONVERGE_PATH) == []


def test_does_not_flag_negation_logical_or_declaration() -> None:
    content = "const port = !custom || 8080;\n"
    assert check_js_boolean_naming(content, CONVERGE_PATH) == []


def test_flags_unprefixed_boolean_jsdoc_param() -> None:
    content = (
        "/**\n"
        " * @param {boolean} alreadyOpened whether the PR is open\n"
        " */\n"
        "function note(alreadyOpened) { return alreadyOpened }\n"
    )
    issues = check_js_boolean_naming(content, CONVERGE_PATH)
    assert len(issues) == 1
    assert "alreadyOpened" in issues[0]
    assert "parameter" in issues[0].lower()


def test_accepts_prefixed_boolean_declarations() -> None:
    content = (
        "let isReady = true\n"
        "const hasItems = false\n"
        "let shouldRetry = !done\n"
        "var wasOpened = true\n"
    )
    assert check_js_boolean_naming(content, CONVERGE_PATH) == []


def test_accepts_prefixed_boolean_jsdoc_param() -> None:
    content = (
        "/**\n"
        " * @param {boolean} isOpen whether the PR is open\n"
        " */\n"
        "function note(isOpen) { return isOpen }\n"
    )
    assert check_js_boolean_naming(content, CONVERGE_PATH) == []


def test_ignores_boolean_declaration_inside_string_literal() -> None:
    content = 'const label = "let flagged = false"\n'
    assert check_js_boolean_naming(content, CONVERGE_PATH) == []


def test_ignores_boolean_declaration_inside_line_comment() -> None:
    content = "// let flagged = false\nconst isReady = true\n"
    assert check_js_boolean_naming(content, CONVERGE_PATH) == []


def test_does_not_flag_falsely_named_non_boolean_declaration() -> None:
    content = "const counted = falsely()\n"
    assert check_js_boolean_naming(content, CONVERGE_PATH) == []


def test_boolean_naming_scoped_to_changed_lines() -> None:
    content = "let alreadyRun = false\nconst isReady = true\n"
    unchanged_only = check_js_boolean_naming(content, CONVERGE_PATH, {2})
    assert unchanged_only == []
    changed = check_js_boolean_naming(content, CONVERGE_PATH, {1})
    assert len(changed) == 1
    assert "alreadyRun" in changed[0]


def test_boolean_naming_defer_scope_returns_all() -> None:
    content = "let alreadyRun = false\n"
    deferred = check_js_boolean_naming(content, CONVERGE_PATH, None, True)
    assert len(deferred) == 1


def test_boolean_naming_exempts_test_files() -> None:
    content = "let alreadyRun = false\n"
    assert check_js_boolean_naming(content, "workflow/converge.test.mjs") == []


def test_flags_banned_identifier_declaration() -> None:
    content = "let data = fetchThings()\n"
    issues = check_js_banned_identifiers(content, CONVERGE_PATH)
    assert len(issues) == 1
    assert "data" in issues[0]
    assert "Line 1" in issues[0]


def test_accepts_descriptive_identifier_declaration() -> None:
    content = "let allOrders = fetchThings()\n"
    assert check_js_banned_identifiers(content, CONVERGE_PATH) == []


def test_flags_each_banned_identifier_name() -> None:
    content = "const result = compute()\nlet response = call()\nvar ctx = build()\n"
    issues = check_js_banned_identifiers(content, CONVERGE_PATH)
    assert len(issues) == 3


def test_banned_identifier_ignores_string_literal() -> None:
    content = 'const label = "let data = 1"\n'
    assert check_js_banned_identifiers(content, CONVERGE_PATH) == []


def test_banned_identifier_scoped_to_changed_lines() -> None:
    content = "let data = one()\nconst allOrders = two()\n"
    assert check_js_banned_identifiers(content, CONVERGE_PATH, {2}) == []
    changed = check_js_banned_identifiers(content, CONVERGE_PATH, {1})
    assert len(changed) == 1


def test_banned_identifier_exempts_test_files() -> None:
    content = "let data = one()\n"
    assert check_js_banned_identifiers(content, "workflow/converge.test.mjs") == []
