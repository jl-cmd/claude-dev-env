"""Tests for check_js_bare_flag_return_directive.

The check catches a JS/.mjs self-contradiction. A converge workflow states a
full result-object contract that rules out a bare status flag ("the full down
result {sha, clean:false, down:true, findings:[]}, never a bare down flag"),
then, in its agent-prompt prose, tells the agent to "return down: true" — the
same bare flag the workflow just ruled out. A StructuredOutput run whose
schema needs every field would reject a lone {down:true}, so the shorthand
drifts from the contract stated a couple of lines above.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HOOK_DIRECTORY = Path(__file__).parent
if str(_HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIRECTORY))

from code_rules_imports_logging import (  # noqa: E402
    check_js_bare_flag_return_directive,
)

_MJS_PATH = "skills/autoconverge/workflow/converge.mjs"

_DOWN_CONTRACT = (
    "the full down result {sha, clean:false, down:true, findings:[]}, "
    "never a bare down flag"
)


def _contract_with_bare_directive_source() -> str:
    return (
        "const PREAMBLE =\n"
        f"  'When the run carries a result schema, {_DOWN_CONTRACT}.'\n\n"
        "function gate(head) {\n"
        "  return spawn(\n"
        "    `Poll for the review; once the budget runs out with no review on "
        "HEAD, return down: true.`,\n"
        "    { label: 'gate' },\n"
        "  )\n"
        "}\n"
    )


def _contract_with_full_result_source() -> str:
    return _contract_with_bare_directive_source().replace(
        "return down: true",
        "return {sha:`${head}`, clean:false, down:true, findings:[]}",
    )


def _bare_directive_without_contract_source() -> str:
    return (
        "function gate(head) {\n"
        "  return spawn(\n"
        "    `Poll for a review; once the budget runs out, return down: true.`,\n"
        "    { label: 'gate' },\n"
        "  )\n"
        "}\n"
    )


def _return_the_result_phrase_source() -> str:
    return (
        "const PREAMBLE = 'the full down result {...}, never a bare down flag'\n\n"
        "function gate(head) {\n"
        "  return spawn(\n"
        "    `Out-of-usage notice on HEAD -> return the down result above and stop.`,\n"
        "    { label: 'gate' },\n"
        "  )\n"
        "}\n"
    )


def _contract_with_bare_false_directive_source() -> str:
    return (
        "const PREAMBLE =\n"
        f"  'When the run carries a result schema, {_DOWN_CONTRACT}.'\n\n"
        "function gate(head) {\n"
        "  return spawn(\n"
        "    `Poll for the review; once HEAD stays clean with no findings, "
        "return down: false.`,\n"
        "    { label: 'gate' },\n"
        "  )\n"
        "}\n"
    )


def _other_flag_name_source() -> str:
    return (
        "const PREAMBLE = 'the full result {clean, stale}, never a bare stale flag'\n\n"
        "function gate(head) {\n"
        "  return spawn(\n"
        "    `If nothing lands in the window, return stale: true.`,\n"
        "    { label: 'gate' },\n"
        "  )\n"
        "}\n"
    )


def _capitalized_contract_with_bare_directive_source() -> str:
    return (
        "const PREAMBLE =\n"
        "  'When the run carries a result schema, the full down result "
        "{sha, clean:false, down:true, findings:[]}, Never a bare Down flag.'\n\n"
        "function gate(head) {\n"
        "  return spawn(\n"
        "    `Poll for the review; once the budget runs out with no review on "
        "HEAD, return down: true.`,\n"
        "    { label: 'gate' },\n"
        "  )\n"
        "}\n"
    )


def _contract_with_capitalized_directive_source() -> str:
    return (
        "const PREAMBLE =\n"
        f"  'When the run carries a result schema, {_DOWN_CONTRACT}.'\n\n"
        "function gate(head) {\n"
        "  return spawn(\n"
        "    `Poll for the review; once the budget runs out with no review on "
        "HEAD, Return down: true.`,\n"
        "    { label: 'gate' },\n"
        "  )\n"
        "}\n"
    )


def test_flags_bare_down_directive_when_the_workflow_states_the_contract() -> None:
    issues = check_js_bare_flag_return_directive(
        _contract_with_bare_directive_source(), _MJS_PATH
    )
    assert len(issues) == 1
    assert "return down" in issues[0]
    assert "never a bare down flag" in issues[0]


def test_flags_bare_down_false_directive_when_the_workflow_states_the_contract() -> None:
    issues = check_js_bare_flag_return_directive(
        _contract_with_bare_false_directive_source(), _MJS_PATH
    )
    assert len(issues) == 1
    assert "return down" in issues[0]
    assert "never a bare down flag" in issues[0]


def test_generalizes_to_any_flag_name_the_contract_rules_out() -> None:
    issues = check_js_bare_flag_return_directive(_other_flag_name_source(), _MJS_PATH)
    assert len(issues) == 1
    assert "return stale" in issues[0]


def test_accepts_a_full_result_object_return() -> None:
    issues = check_js_bare_flag_return_directive(
        _contract_with_full_result_source(), _MJS_PATH
    )
    assert issues == []


def test_accepts_a_bare_directive_when_the_workflow_states_no_contract() -> None:
    issues = check_js_bare_flag_return_directive(
        _bare_directive_without_contract_source(), _MJS_PATH
    )
    assert issues == []


def test_accepts_return_the_result_prose_that_names_no_bare_flag() -> None:
    issues = check_js_bare_flag_return_directive(
        _return_the_result_phrase_source(), _MJS_PATH
    )
    assert issues == []


def test_flags_bare_directive_when_contract_uses_capitalized_never() -> None:
    issues = check_js_bare_flag_return_directive(
        _capitalized_contract_with_bare_directive_source(), _MJS_PATH
    )
    assert len(issues) == 1
    assert "return down" in issues[0]


def test_flags_capitalized_return_directive_against_lowercase_contract() -> None:
    issues = check_js_bare_flag_return_directive(
        _contract_with_capitalized_directive_source(), _MJS_PATH
    )
    assert len(issues) == 1
    assert "never a bare down flag" in issues[0]


def test_skips_python_files() -> None:
    issues = check_js_bare_flag_return_directive(
        _contract_with_bare_directive_source(), "workflow/converge.py"
    )
    assert issues == []
